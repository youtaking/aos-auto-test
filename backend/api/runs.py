# backend/api/runs.py
"""测试运行 API"""
import asyncio
import json
import os
import re
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, BackgroundTasks
from fastapi.responses import FileResponse, RedirectResponse, PlainTextResponse
import yaml
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.db.config import get_async_session, async_session
from backend.db.models import TestRun, TestResult, TestCase, TestSuite, Project, AuthConfig, TestCollection
from backend.schemas.run import RunResponse, RunReport, ResultResponse
from backend.schemas.common import ApiResponse
from backend import ws as ws_module

router = APIRouter()

ALLURE_RESULTS_DIR = "allure-results"
ALLURE_REPORT_DIR = "allure-report"
LOG_DIR = Path("run_logs")

# 运行中的进程跟踪：run_id -> subprocess.Popen
_running_processes: dict[int, subprocess.Popen] = {}


async def _resolve_collection_case_ids(db, collection_ids: list[int]) -> list[int]:
    """解析多个用例集，合并去重，跳过已删除的用例"""
    if not collection_ids:
        return []
    result = await db.execute(
        select(TestCollection).where(TestCollection.id.in_(collection_ids))
    )
    collections = result.scalars().all()
    all_case_ids: set[int] = set()
    for c in collections:
        if c.case_ids:
            all_case_ids.update(c.case_ids)
    if not all_case_ids:
        return []
    valid = await db.execute(
        select(TestCase).where(TestCase.id.in_(list(all_case_ids)))
    )
    return [r[0].id for r in valid.all()]


def _parse_pytest_line(line: str) -> dict | None:
    """解析 pytest -v 输出的单行结果"""
    m = re.match(r"^(tests/\S+::\w+)\s+(PASSED|FAILED|SKIPPED|ERROR)", line.strip())
    if not m:
        return None
    nodeid = m.group(1)
    outcome = m.group(2).lower()
    parts = nodeid.split("::")
    file_path = parts[0] if parts else ""
    func_name = "::".join(parts[1:]) if len(parts) > 1 else ""
    suite_name = Path(file_path).stem.replace("test_", "")
    return {
        "nodeid": nodeid,
        "file_path": file_path,
        "func_name": func_name,
        "suite_name": suite_name,
        "outcome": outcome,
    }


async def _execute_tests(
    run_id: int,
    project_url: str,
    headed: bool = False,
    step_delay: float = 0,
    case_ids: list[int] | None = None,
    auth_env: dict | None = None,
):
    """后台任务：执行 pytest，逐条实时更新结果 + WebSocket 广播日志 + 生成 Allure 报告"""
    async with async_session() as db:
        run = await db.get(TestRun, run_id)
        if not run:
            return

        run.status = "running"
        run.started_at = datetime.utcnow()
        await db.commit()

        await ws_module.broadcast(run_id, "run_start", {"run_id": run_id, "status": "running"})

        try:
            # 清理旧的 allure 结果
            allure_dir = Path(ALLURE_RESULTS_DIR)
            if allure_dir.exists():
                for f in allure_dir.iterdir():
                    f.unlink()
            else:
                allure_dir.mkdir(parents=True, exist_ok=True)

            report_path = f"report_{run_id}.json"
            cmd = [
                sys.executable, "-m", "pytest",
                "tests/suites/", "tests/api_suites/",
                "-v", "--tb=short",
                f"--base-url={project_url}",
                f"--step-delay={step_delay}",
                "--json-report", f"--json-report-file={report_path}",
                f"--alluredir={ALLURE_RESULTS_DIR}",
            ]

            if case_ids:
                cases_query = await db.execute(
                    select(TestCase).where(TestCase.id.in_(case_ids))
                )
                selected_cases = cases_query.scalars().all()
                if selected_cases:
                    nodeids = [f"{c.file_path}::{c.function_name}" for c in selected_cases]
                    cmd.extend(nodeids)
                    cmd = [c for c in cmd if c not in ("tests/suites/", "tests/api_suites/")]

            env = {
                **os.environ,
                "HEADLESS": "false" if headed else "true",
                "STEP_DELAY": str(step_delay),
                "FENIX_URL": project_url,
                "PYTHONUNBUFFERED": "1",
            }
            if auth_env:
                env.update(auth_env)

            print(f"[Run #{run_id}] 执行命令: {' '.join(cmd)}", flush=True)

            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=env,
                cwd=os.getcwd(),
            )
            _running_processes[run_id] = proc

            passed = 0
            failed = 0
            skipped = 0

            LOG_DIR.mkdir(parents=True, exist_ok=True)
            log_path = LOG_DIR / f"{run_id}.log"
            with open(log_path, "w", encoding="utf-8") as log_file:
                while True:
                    raw = await asyncio.to_thread(proc.stdout.readline)
                    if not raw:
                        break
                    line = raw.decode("utf-8", errors="replace")
                    stripped = line.rstrip()
                    if stripped:
                        log_file.write(stripped + "\n")
                        print(f"[Run #{run_id}] {stripped}", flush=True)
                        await ws_module.broadcast(run_id, "log", {"line": stripped})

                    parsed = _parse_pytest_line(line)
                    if not parsed:
                        continue

                    func_name = parsed["func_name"]
                    outcome = parsed["outcome"]

                    case_query = await db.execute(
                        select(TestCase).where(TestCase.function_name == func_name)
                    )
                    case = case_query.scalars().first()

                    result = TestResult(
                        run_id=run_id,
                        case_id=case.id if case else None,
                        case_name=func_name,
                        suite_name=parsed["suite_name"],
                        status=outcome if outcome in ("passed", "failed", "skipped") else "error",
                        duration_ms=0,
                    )
                    db.add(result)

                    if outcome == "passed":
                        passed += 1
                    elif outcome in ("failed", "error"):
                        failed += 1
                    else:
                        skipped += 1

                    run.total = passed + failed + skipped
                    run.passed = passed
                    run.failed = failed
                    run.skipped = skipped
                    await db.commit()

                    await ws_module.broadcast(run_id, "result_update", {
                        "case_name": func_name,
                        "suite_name": parsed["suite_name"],
                        "status": outcome,
                        "passed": passed, "failed": failed, "skipped": skipped,
                    })

            await asyncio.to_thread(proc.wait)
            finished = datetime.utcnow()

            # 用 JSON 报告补充 duration 和 error 信息
            try:
                rf = Path(report_path)
                if rf.exists():
                    with open(rf, "r", encoding="utf-8") as f:
                        report = json.load(f)
                    for test in report.get("tests", []):
                        nodeid = test.get("nodeid", "")
                        parts = nodeid.split("::")
                        func_name = "::".join(parts[1:]) if len(parts) > 1 else ""
                        call_info = test.get("call", {})
                        duration_ms = int(call_info.get("duration", 0) * 1000)
                        longrepr = str(call_info.get("longrepr", "")) if call_info.get("longrepr") else None
                        existing = await db.execute(
                            select(TestResult).where(
                                TestResult.run_id == run_id,
                                TestResult.case_name == func_name,
                            )
                        )
                        r = existing.scalars().first()
                        if r:
                            r.duration_ms = duration_ms
                            r.error_message = longrepr[:500] if longrepr else None
                            r.stack_trace = longrepr
                    rf.unlink(missing_ok=True)
            except Exception as e:
                print(f"[Run #{run_id}] JSON 报告处理失败: {e}", flush=True)

            # 重新读取 run，避免覆盖 cancel 状态
            await db.refresh(run)
            if run.status != "cancelled":
                run.status = "passed" if failed == 0 else "failed"
                run.finished_at = finished
                run.duration_ms = int((finished - run.started_at).total_seconds() * 1000)
                await db.commit()

            # 生成 Allure 报告
            try:
                import shutil
                allure_bin = shutil.which("allure") or r"C:\Users\52686\AppData\Roaming\npm\allure.cmd"
                report_dir = Path(ALLURE_REPORT_DIR) / str(run_id)
                cmd_str = f'"{allure_bin}" generate "{allure_dir}" -o "{report_dir}" --clean'

                def _run_allure():
                    return subprocess.run(cmd_str, shell=True, capture_output=True, timeout=60)

                allure_result = await asyncio.to_thread(_run_allure)
                if allure_result.returncode != 0:
                    print(f"[Allure] stderr: {allure_result.stderr.decode(errors='replace')}")
                else:
                    print(f"[Allure] 报告生成成功: {report_dir}")
            except Exception as e:
                print(f"[Allure] 报告生成失败: {e}")

            # 广播运行完成（取消时由 cancel 端点广播，不重复）
            if run.status != "cancelled":
                await ws_module.broadcast(run_id, "run_complete", {
                    "run_id": run_id,
                    "status": run.status,
                    "total": run.total,
                    "passed": run.passed,
                    "failed": run.failed,
                    "skipped": run.skipped,
                    "duration_ms": run.duration_ms,
                })

        except Exception as e:
            print(f"[Run #{run_id}] 执行异常: {type(e).__name__}: {e}", flush=True)
            traceback.print_exc()
            run.status = "error"
            run.finished_at = datetime.utcnow()
            await db.commit()
            await ws_module.broadcast(run_id, "run_complete", {
                "run_id": run_id, "status": "error", "error": str(e),
            })
        finally:
            _running_processes.pop(run_id, None)


@router.get("/runs", response_model=ApiResponse)
async def list_runs(
    project_id: int | None = None,
    status: str | None = None,
    trigger_type: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_async_session),
):
    """获取运行历史（分页+筛选）"""
    query = select(TestRun).order_by(TestRun.created_at.desc())
    if project_id:
        query = query.where(TestRun.project_id == project_id)
    if status:
        query = query.where(TestRun.status == status)
    if trigger_type:
        query = query.where(TestRun.trigger_type == trigger_type)
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    runs = result.scalars().all()
    return ApiResponse(data=[RunResponse.model_validate(r) for r in runs])


@router.post("/runs", response_model=ApiResponse)
async def trigger_run(
    background_tasks: BackgroundTasks,
    project_id: int,
    trigger_type: str = "manual",
    headed: bool = False,
    step_delay: float = 0,
    case_ids: str = "",
    collection_ids: str = "",
    db: AsyncSession = Depends(get_async_session),
):
    """触发一次测试运行。case_ids: 逗号分隔的用例 ID；collection_ids: 逗号分隔的用例集 ID（优先级高于 case_ids）"""
    project = await db.get(Project, project_id)
    project_url = project.url if project else "http://localhost:3001"

    # 从激活的认证配置读取凭据
    auth_env = {}
    auth_result = await db.execute(select(AuthConfig).where(AuthConfig.is_active == 1))
    auth_config = auth_result.scalar_one_or_none()
    if auth_config:
        auth_env = {
            "FENIX_UI_EMAIL": auth_config.ui_test_email or "",
            "FENIX_UI_PASSWORD": auth_config.ui_test_password or "",
            "FENIX_API_EMAIL": auth_config.api_test_email or "",
            "FENIX_API_PASSWORD": auth_config.api_test_password or "",
            "FENIX_OPEN_API_KEY": auth_config.open_api_key or "",
        }

    # 解析 case_ids
    parsed_case_ids = None
    if case_ids:
        try:
            parsed_case_ids = [int(x.strip()) for x in case_ids.split(",") if x.strip()]
        except ValueError:
            parsed_case_ids = None

    # 解析 collection_ids（优先级高于 case_ids）
    parsed_collection_ids = None
    if collection_ids:
        try:
            parsed_collection_ids = [int(x.strip()) for x in collection_ids.split(",") if x.strip()]
            parsed_case_ids = await _resolve_collection_case_ids(db, parsed_collection_ids)
        except (ValueError, Exception):
            parsed_case_ids = None
            parsed_collection_ids = None

    run = TestRun(
        project_id=project_id,
        trigger_type=trigger_type,
        status="pending",
        started_at=datetime.utcnow(),
        collection_ids=parsed_collection_ids,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    background_tasks.add_task(_execute_tests, run.id, project_url, headed, step_delay, parsed_case_ids, auth_env)

    return ApiResponse(data=RunResponse.model_validate(run))


@router.get("/runs/{run_id}", response_model=ApiResponse)
async def get_run(run_id: int, db: AsyncSession = Depends(get_async_session)):
    """获取单次运行详情"""
    run = await db.get(TestRun, run_id)
    if not run:
        return ApiResponse(success=False, error="运行记录不存在")
    return ApiResponse(data=RunResponse.model_validate(run))


@router.delete("/runs/{run_id}", response_model=ApiResponse)
async def delete_run(run_id: int, db: AsyncSession = Depends(get_async_session)):
    """删除运行记录及其结果"""
    run = await db.get(TestRun, run_id)
    if not run:
        return ApiResponse(success=False, error="运行记录不存在")
    results = await db.execute(select(TestResult).where(TestResult.run_id == run_id))
    for r in results.scalars().all():
        await db.delete(r)
    await db.delete(run)
    await db.commit()
    # 删除日志文件
    log_file = LOG_DIR / f"{run_id}.log"
    log_file.unlink(missing_ok=True)

    return ApiResponse(data={"deleted": True})


@router.post("/runs/{run_id}/cancel", response_model=ApiResponse)
async def cancel_run(run_id: int, db: AsyncSession = Depends(get_async_session)):
    """取消正在运行的测试"""
    run = await db.get(TestRun, run_id)
    if not run:
        return ApiResponse(success=False, error="运行记录不存在")
    if run.status not in ("pending", "running"):
        return ApiResponse(success=False, error=f"当前状态 {run.status} 不可取消")

    # 从 runs.py 和 api_tests.py 的进程字典中查找
    from backend.api import api_tests as api_tests_module
    proc = _running_processes.get(run_id) or api_tests_module._running_processes.get(run_id)

    killed = False
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            await asyncio.to_thread(proc.wait, timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        killed = True

    run.status = "cancelled"
    run.finished_at = datetime.utcnow()
    if run.started_at:
        run.duration_ms = int((run.finished_at - run.started_at).total_seconds() * 1000)
    await db.commit()

    await ws_module.broadcast(run_id, "run_complete", {
        "run_id": run_id,
        "status": "cancelled",
        "total": run.total,
        "passed": run.passed,
        "failed": run.failed,
        "skipped": run.skipped,
        "duration_ms": run.duration_ms,
    })

    return ApiResponse(data={"cancelled": True, "killed_process": killed})


@router.get("/runs/{run_id}/logs", response_model=ApiResponse)
async def get_run_logs(run_id: int):
    """获取运行日志（从文件读取）"""
    log_file = LOG_DIR / f"{run_id}.log"
    if not log_file.exists():
        return ApiResponse(data=[])
    with open(log_file, "r", encoding="utf-8") as f:
        lines = [line.rstrip() for line in f]
    return ApiResponse(data=lines)


@router.get("/runs/{run_id}/results", response_model=ApiResponse)
async def get_run_results(run_id: int, db: AsyncSession = Depends(get_async_session)):
    """获取某次运行的所有用例结果"""
    result = await db.execute(
        select(TestResult).where(TestResult.run_id == run_id).order_by(TestResult.id)
    )
    results = result.scalars().all()
    return ApiResponse(data=[ResultResponse.model_validate(r) for r in results])


@router.get("/runs/{run_id}/allure")
async def get_allure_report(run_id: int):
    """重定向到 Allure 报告首页"""
    report_dir = Path(ALLURE_REPORT_DIR) / str(run_id)
    index_file = report_dir / "index.html"
    if not index_file.exists():
        return ApiResponse(success=False, error="Allure 报告未生成")
    return RedirectResponse(url=f"/api/runs/{run_id}/allure-static/index.html")


@router.get("/runs/{run_id}/allure-static/{file_path:path}")
async def serve_allure_static(run_id: int, file_path: str):
    """提供 Allure 报告静态资源"""
    report_dir = Path(ALLURE_REPORT_DIR) / str(run_id)
    target = report_dir / file_path
    if not target.exists() or not target.is_file():
        return ApiResponse(success=False, error="文件不存在")
    try:
        target.resolve().relative_to(report_dir.resolve())
    except ValueError:
        return ApiResponse(success=False, error="非法路径")
    return FileResponse(target)


@router.post("/runs/{run_id}/report", response_model=ApiResponse)
async def report_run(
    run_id: int, body: RunReport, db: AsyncSession = Depends(get_async_session)
):
    """CI/CD 结果上报"""
    run = await db.get(TestRun, run_id)
    if not run:
        return ApiResponse(success=False, error="运行记录不存在")

    passed_count = 0
    failed_count = 0
    skipped_count = 0

    for item in body.results:
        case_result = await db.execute(
            select(TestCase).where(TestCase.function_name == item.function_name)
        )
        case = case_result.scalar_one_or_none()

        test_result = TestResult(
            run_id=run_id,
            case_id=case.id if case else None,
            case_name=item.case_name,
            suite_name=item.suite_name,
            status=item.status,
            duration_ms=item.duration_ms,
            error_message=item.error_message,
            stack_trace=item.stack_trace,
            screenshot_path=item.screenshot_path,
        )
        db.add(test_result)

        if item.status == "passed":
            passed_count += 1
        elif item.status in ("failed", "error"):
            failed_count += 1
        else:
            skipped_count += 1

    run.status = "passed" if failed_count == 0 else "failed"
    run.total = len(body.results)
    run.passed = passed_count
    run.failed = failed_count
    run.skipped = skipped_count
    run.started_at = body.started_at
    run.finished_at = body.finished_at
    run.duration_ms = int((body.finished_at - body.started_at).total_seconds() * 1000)
    run.git_commit = body.git_commit
    run.git_branch = body.git_branch

    await db.commit()
    return ApiResponse(data={"imported": len(body.results)})


@router.get("/runs/{run_id}/md-report")
async def generate_md_report(run_id: int, db: AsyncSession = Depends(get_async_session)):
    """生成 Markdown 格式测试报告"""
    run = await db.get(TestRun, run_id)
    if not run:
        return ApiResponse(success=False, error="运行记录不存在")

    result = await db.execute(
        select(TestResult).where(TestResult.run_id == run_id).order_by(TestResult.id)
    )
    results = result.scalars().all()

    # 按套件分组
    suites: dict[str, list] = {}
    for r in results:
        suites.setdefault(r.suite_name, []).append(r)

    # 获取项目名
    project = await db.get(Project, run.project_id)
    project_name = project.name if project else "未知项目"

    status_icon = {"passed": "✅", "failed": "❌", "skipped": "⏭️", "error": "⚠️"}
    duration_str = f"{run.duration_ms / 1000:.1f}s" if run.duration_ms else "-"
    started = run.started_at.strftime("%Y-%m-%d %H:%M:%S") if run.started_at else "-"
    finished = run.finished_at.strftime("%Y-%m-%d %H:%M:%S") if run.finished_at else "-"
    pass_rate = f"{run.passed / run.total * 100:.1f}%" if run.total else "-"

    lines = [
        f"# 测试报告 — 运行 #{run.id}",
        "",
        f"**项目**: {project_name}  ",
        f"**触发方式**: {run.trigger_type}  ",
        f"**状态**: {run.status}  ",
        f"**开始时间**: {started}  ",
        f"**结束时间**: {finished}  ",
        f"**总耗时**: {duration_str}  ",
        "",
        "## 概览",
        "",
        "| 指标 | 数值 |",
        "|------|------|",
        f"| 总用例 | {run.total} |",
        f"| 通过 | {run.passed} |",
        f"| 失败 | {run.failed} |",
        f"| 跳过 | {run.skipped} |",
        f"| 通过率 | {pass_rate} |",
        "",
    ]

    # ── 分析总结 ──
    failed_results = [r for r in results if r.status in ("failed", "error")]
    skipped_results = [r for r in results if r.status == "skipped"]
    passed_results = [r for r in results if r.status == "passed"]

    lines.append("## 分析总结")
    lines.append("")

    # 1. 总体结论
    if run.total == 0:
        lines.append("> ⚠️ 本次运行无用例执行。")
    elif run.failed == 0 and run.skipped == 0:
        lines.append(f"> ✅ 全部 {run.total} 条用例通过，通过率 100%，系统状态良好。")
    elif run.failed == 0:
        lines.append(f"> ✅ 无用例失败，但有 {run.skipped} 条被跳过。通过率 {pass_rate}。")
    else:
        lines.append(f"> ❌ 共 {run.failed} 条用例失败，通过率 {pass_rate}，需要关注以下问题。")
    lines.append("")

    # 2. 失败分类（按错误类型分组）
    if failed_results:
        error_groups: dict[str, list] = {}
        for r in failed_results:
            msg = r.error_message or "未知错误"
            first_line = msg.strip().split("\n")[0][:120]
            err_type = "其他"
            for keyword in ["AssertionError", "AssertError", "assert ", "TimeoutError", "timeout",
                            "ConnectionError", "ConnectionRefused", "404", "403", "401", "500",
                            "ElementNotFound", "NoSuchElement", "Locator", "Page closed"]:
                if keyword.lower() in first_line.lower():
                    err_type = keyword if keyword not in ("assert ", "Locator") else "断言失败"
                    if keyword in ("404", "403", "401", "500"):
                        err_type = f"HTTP {keyword}"
                    break
            error_groups.setdefault(err_type, []).append(r)

        lines.append("### 失败分类")
        lines.append("")
        lines.append("| 错误类型 | 数量 | 涉及用例 |")
        lines.append("|----------|------|----------|")
        for err_type, group in sorted(error_groups.items(), key=lambda x: -len(x[1])):
            case_names = ", ".join(r.case_name for r in group[:3])
            if len(group) > 3:
                case_names += f" 等{len(group)}条"
            lines.append(f"| {err_type} | {len(group)} | {case_names} |")
        lines.append("")

    # 3. 套件健康度
    if suites:
        lines.append("### 套件健康度")
        lines.append("")
        lines.append("| 套件 | 总数 | 通过 | 失败 | 跳过 | 通过率 | 状态 |")
        lines.append("|------|------|------|------|------|--------|------|")
        for suite_name, suite_results in suites.items():
            s_total = len(suite_results)
            s_passed = sum(1 for r in suite_results if r.status == "passed")
            s_failed = sum(1 for r in suite_results if r.status in ("failed", "error"))
            s_skipped = sum(1 for r in suite_results if r.status == "skipped")
            s_rate = f"{s_passed / s_total * 100:.0f}%" if s_total else "-"
            s_status = "✅ 健康" if s_failed == 0 else ("⚠️ 部分失败" if s_passed > 0 else "❌ 全部失败")
            lines.append(f"| {suite_name} | {s_total} | {s_passed} | {s_failed} | {s_skipped} | {s_rate} | {s_status} |")
        lines.append("")

    # 4. 最慢用例 Top 5
    if results:
        sorted_by_duration = sorted(results, key=lambda r: r.duration_ms, reverse=True)[:5]
        lines.append("### 最慢用例 Top 5")
        lines.append("")
        lines.append("| 排名 | 用例 | 套件 | 耗时 |")
        lines.append("|------|------|------|------|")
        for i, r in enumerate(sorted_by_duration, 1):
            lines.append(f"| {i} | {r.case_name} | {r.suite_name} | {r.duration_ms}ms |")
        lines.append("")

    # 5. 建议
    lines.append("### 建议")
    lines.append("")
    if failed_results:
        lines.append(f"- 优先修复 {len(failed_results)} 条失败用例，按错误类型集中处理可提高效率")
        timeout_cases = [r for r in failed_results if r.error_message and "timeout" in r.error_message.lower()]
        if timeout_cases:
            lines.append(f"- {len(timeout_cases)} 条用例疑似超时问题，建议检查网络或被测服务性能")
    if skipped_results:
        lines.append(f"- {len(skipped_results)} 条用例被跳过，确认是否为预期跳过")
    slow_cases = [r for r in results if r.duration_ms > 10000]
    if slow_cases:
        lines.append(f"- {len(slow_cases)} 条用例耗时超过 10s，考虑优化或拆分")
    if not failed_results and not skipped_results and not slow_cases:
        lines.append("- 本轮测试表现良好，无需特别关注")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 失败用例详情
    if failed_results:
        lines.append("## 失败用例")
        lines.append("")
        for r in failed_results:
            lines.append(f"### {status_icon.get(r.status, '❓')} {r.suite_name} / {r.case_name}")
            lines.append("")
            if r.error_message:
                lines.append("```")
                lines.append(r.error_message)
                lines.append("```")
                lines.append("")
        lines.append("---")
        lines.append("")

    # 按套件输出详情
    lines.append("## 详细结果")
    lines.append("")
    for suite_name, suite_results in suites.items():
        s_passed = sum(1 for r in suite_results if r.status == "passed")
        s_failed = sum(1 for r in suite_results if r.status in ("failed", "error"))
        s_skipped = sum(1 for r in suite_results if r.status == "skipped")
        lines.append(f"### {suite_name}（{s_passed}✅ {s_failed}❌ {s_skipped}⏭️）")
        lines.append("")
        lines.append("| 状态 | 用例 | 耗时 | 错误 |")
        lines.append("|------|------|------|------|")
        for r in suite_results:
            icon = status_icon.get(r.status, "❓")
            err = (r.error_message or "-")[:80].replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {icon} | {r.case_name} | {r.duration_ms}ms | {err} |")
        lines.append("")

    # 页脚
    lines.append("---")
    lines.append(f"*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

    return PlainTextResponse(content="\n".join(lines), media_type="text/markdown; charset=utf-8")


def _load_api_key() -> str:
    """从 env 或 test_data.yaml 读取 API key"""
    key = os.environ.get("FENIX_API_KEY", "")
    if key:
        return key
    try:
        with open("tests/fixtures/test_data.yaml", "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data.get("fenixagent", {}).get("api_key", "")
    except Exception:
        return ""


@router.post("/tests/run-single", response_model=ApiResponse)
async def run_single_test(
    case_id: int | None = None,
    case_name: str | None = None,
    headed: bool = True,
    db: AsyncSession = Depends(get_async_session),
):
    """
    轻量级单用例执行：直接运行一条测试，返回结果，不产生运行记录。
    用于在运行记录页面快速验证/调试单条失败用例。
    支持 case_id 或 case_name（function_name）查找。
    """
    # 1. 查找用例及其套件
    case = None
    if case_id:
        case = await db.get(TestCase, case_id)
    if not case and case_name:
        query = await db.execute(
            select(TestCase).where(TestCase.function_name == case_name)
        )
        case = query.scalars().first()
    if not case:
        return ApiResponse(success=False, error=f"用例不存在 (case_id={case_id}, case_name={case_name})")

    suite = await db.get(TestSuite, case.suite_id)
    if not suite:
        return ApiResponse(success=False, error="套件不存在")

    is_api = suite.test_type == "api"

    # 2. 获取活跃项目的 base URL
    proj_query = await db.execute(
        select(Project).where(Project.is_active == 1)
    )
    project = proj_query.scalars().first()
    if not project:
        return ApiResponse(success=False, error="没有活跃项目")

    base_url = project.url

    # 3. 构建 pytest 命令
    nodeid = f"{case.file_path}::{case.function_name}"
    report_path = f"single_test_report_{case_id}.json"
    cmd = [
        sys.executable, "-m", "pytest", nodeid,
        "-v", "--tb=long",
        f"--base-url={base_url}",
        "--json-report", f"--json-report-file={report_path}",
        "-p", "no:cacheprovider",
        "--no-header",
    ]

    env = {
        **os.environ,
        "PYTHONUNBUFFERED": "1",
        "PYTHONUTF8": "1",
    }
    if is_api:
        env["FENIX_API_KEY"] = _load_api_key()
    else:
        env["HEADLESS"] = "false" if headed else "true"
        env["FENIX_URL"] = base_url

    # 4. 执行 pytest（同步等待，单条用例不需要后台任务）
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            cwd=os.getcwd(),
        )

        def _wait():
            stdout_data = proc.stdout.read() if proc.stdout else b""
            proc.wait()
            return stdout_data

        raw_output = await asyncio.wait_for(
            asyncio.to_thread(_wait), timeout=120
        )
        stdout = raw_output.decode("utf-8", errors="replace")

        # 5. 从 JSON 报告解析详细结果
        status = "passed" if proc.returncode == 0 else "failed"
        duration_ms = 0
        error_message = None

        rf = Path(report_path)
        if rf.exists():
            try:
                with open(rf, "r", encoding="utf-8") as f:
                    report = json.load(f)
                tests = report.get("tests", [])
                if tests:
                    test = tests[0]
                    call_info = test.get("call", {})
                    duration_ms = int(call_info.get("duration", 0) * 1000)
                    outcome = call_info.get("outcome", "")
                    if outcome:
                        status = outcome
                    longrepr = call_info.get("longrepr", "")
                    if longrepr:
                        error_message = str(longrepr)[:1000]
            except Exception:
                pass
            finally:
                rf.unlink(missing_ok=True)

        # 如果 JSON 报告没有解析到错误信息，从 stdout 提取
        if not error_message and status != "passed":
            # 提取 pytest 输出中的失败信息
            fail_lines = []
            for line in stdout.split("\n"):
                if "FAILED" in line or "AssertionError" in line or "Error" in line:
                    fail_lines.append(line.strip())
            if fail_lines:
                error_message = "\n".join(fail_lines[:5])[:500]

        return ApiResponse(data={
            "status": status,
            "duration_ms": duration_ms,
            "error_message": error_message,
            "output": stdout[-2000:],  # 返回最后 2000 字符供调试
        })

    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        return ApiResponse(success=False, error="执行超时（120秒）")
    except Exception as e:
        print(f"[run-single] Error: {type(e).__name__}: {e}", flush=True)
        return ApiResponse(success=False, error=f"执行失败: {type(e).__name__}: {e}")
