# backend/api/api_tests.py
"""接口测试 API 路由"""
import asyncio
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.db.config import get_async_session, async_session
from backend.db.models import TestRun, TestResult, TestCase, TestSuite, Project
from backend.schemas.run import RunResponse, ResultResponse
from backend.schemas.common import ApiResponse
from backend import ws as ws_module

router = APIRouter()

API_TEST_DIR = "tests/api_suites/"
TEST_DATA_YAML = "tests/fixtures/test_data.yaml"
LOG_DIR = Path("run_logs")
ALLURE_RESULTS_DIR = "allure-results"
ALLURE_REPORT_DIR = "allure-report"

# 运行中的进程跟踪：run_id -> subprocess.Popen
_running_processes: dict[int, subprocess.Popen] = {}


def _load_api_key() -> str:
    """从 test_data.yaml 读取 api_key，env 优先"""
    key = os.environ.get("FENIX_API_KEY", "")
    if key:
        return key
    try:
        with open(TEST_DATA_YAML, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data.get("fenixagent", {}).get("api_key", "")
    except Exception:
        return ""


def _parse_pytest_line(line: str) -> dict | None:
    """解析 pytest -v 输出的单行结果，支持 file::Class::function 和 file::function"""
    m = re.match(r"^(tests/\S+?::\S+)\s+(PASSED|FAILED|SKIPPED|ERROR)", line.strip())
    if not m:
        return None
    nodeid = m.group(1)
    outcome = m.group(2).lower()
    parts = nodeid.split("::")
    file_path = parts[0] if parts else ""
    # 处理 Class::function 格式（3段）和 纯 function 格式（2段）
    if len(parts) >= 3:
        func_name = "::".join(parts[1:])  # Class::function
    elif len(parts) == 2:
        func_name = parts[1]
    else:
        func_name = ""
    suite_name = Path(file_path).stem.replace("test_", "")
    return {
        "nodeid": nodeid,
        "file_path": file_path,
        "func_name": func_name,
        "suite_name": suite_name,
        "outcome": outcome,
    }


async def _execute_api_tests(
    run_id: int,
    api_base_url: str,
    api_key: str,
    case_ids: list[int] | None = None,
):
    """后台任务：执行 pytest api_suites，逐条实时更新结果 + WebSocket 广播日志"""
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

            report_path = f"api_report_{run_id}.json"
            cmd = [
                sys.executable, "-m", "pytest", API_TEST_DIR,
                "-v", "--tb=short",
                f"--base-url={api_base_url}",
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
                    cmd = [c for c in cmd if c != API_TEST_DIR]

            env = {
                **os.environ,
                "FENIX_API_KEY": api_key,
                "PYTHONUNBUFFERED": "1",
            }

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
                    raw_line = await asyncio.to_thread(proc.stdout.readline)
                    if not raw_line:
                        break
                    line = raw_line.decode("utf-8", errors="replace")
                    stripped = line.rstrip()
                    if stripped:
                        log_file.write(stripped + "\n")
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
            rf = Path(report_path)
            if rf.exists():
                with open(rf, "r", encoding="utf-8") as f:
                    report = json.load(f)
                for test in report.get("tests", []):
                    nodeid = test.get("nodeid", "")
                    # 正确解析 Class::function 格式
                    node_parts = nodeid.split("::")
                    if len(node_parts) >= 3:
                        func_name = "::".join(node_parts[1:])
                    elif len(node_parts) == 2:
                        func_name = node_parts[1]
                    else:
                        func_name = ""
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
                abs_allure_dir = str(Path(ALLURE_RESULTS_DIR).resolve())
                abs_report_dir = str(report_dir.resolve())
                cmd_str = f'"{allure_bin}" generate "{abs_allure_dir}" -o "{abs_report_dir}" --clean'
                print(f"[Run #{run_id}] Allure 命令: {cmd_str}", flush=True)

                # 检查 allure-results 是否有数据
                result_files = list(Path(ALLURE_RESULTS_DIR).glob("*"))
                print(f"[Run #{run_id}] allure-results 文件数: {len(result_files)}", flush=True)

                def _run_allure():
                    return subprocess.run(cmd_str, shell=True, capture_output=True, timeout=60)

                allure_result = await asyncio.to_thread(_run_allure)
                if allure_result.returncode != 0:
                    print(f"[Run #{run_id}] Allure 失败: {allure_result.stderr.decode(errors='replace')}", flush=True)
                else:
                    print(f"[Run #{run_id}] Allure 报告生成成功: {report_dir}", flush=True)
            except Exception as e:
                print(f"[Run #{run_id}] Allure 报告生成失败: {type(e).__name__}: {e}", flush=True)

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
            # 异常保护：确保 run 状态不会卡在 "running"
            run.status = "error"
            run.finished_at = datetime.utcnow()
            await db.commit()
            await ws_module.broadcast(run_id, "run_complete", {
                "run_id": run_id,
                "status": "error",
                "error": str(e),
            })
        finally:
            _running_processes.pop(run_id, None)


@router.get("/api-tests/cases", response_model=ApiResponse)
async def list_api_cases(
    module: str | None = None,
    priority: str | None = None,
    db: AsyncSession = Depends(get_async_session),
):
    """获取接口测试用例列表"""
    suite_query = await db.execute(
        select(TestSuite).where(TestSuite.test_type == "api")
    )
    suite_ids = [s.id for s in suite_query.scalars().all()]
    if not suite_ids:
        return ApiResponse(data=[])

    query = select(TestCase).where(TestCase.suite_id.in_(suite_ids))
    if module:
        query = query.where(TestCase.tags.contains(module))
    if priority:
        query = query.where(TestCase.priority == priority)
    query = query.order_by(TestCase.id)

    result = await db.execute(query)
    cases = result.scalars().all()

    return ApiResponse(data=[{
        "id": c.id,
        "suite_id": c.suite_id,
        "name": c.name,
        "file_path": c.file_path,
        "function_name": c.function_name,
        "tags": c.tags,
        "priority": c.priority,
        "timeout": c.timeout,
    } for c in cases])


@router.post("/api-tests/run", response_model=ApiResponse)
async def trigger_api_run(
    background_tasks: BackgroundTasks,
    project_id: int,
    case_ids: str = "",
    db: AsyncSession = Depends(get_async_session),
):
    """触发接口测试运行"""
    project = await db.get(Project, project_id)
    if not project:
        return ApiResponse(success=False, error="项目不存在")

    parsed_case_ids = None
    if case_ids:
        try:
            parsed_case_ids = [int(x.strip()) for x in case_ids.split(",") if x.strip()]
        except ValueError:
            parsed_case_ids = None

    run = TestRun(
        project_id=project_id,
        trigger_type="manual",
        status="pending",
        started_at=datetime.utcnow(),
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    api_key = _load_api_key()

    background_tasks.add_task(
        _execute_api_tests, run.id, project.url, api_key, parsed_case_ids
    )

    return ApiResponse(data=RunResponse.model_validate(run))


@router.get("/api-tests/runs", response_model=ApiResponse)
async def list_api_runs(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_async_session),
):
    """获取接口测试运行历史"""
    # 找所有 api 类型的 suite → 其下的 case_id → 关联的 run_id
    api_case_ids_q = await db.execute(
        select(TestCase.id)
        .join(TestSuite, TestCase.suite_id == TestSuite.id)
        .where(TestSuite.test_type == "api")
    )
    api_case_ids = {r[0] for r in api_case_ids_q.all()}

    # 有 API 类型 TestResult 的 run_id
    api_run_ids_q = await db.execute(
        select(TestResult.run_id).distinct().where(
            TestResult.case_id.in_(api_case_ids)
        )
    )
    api_run_ids = {r[0] for r in api_run_ids_q.all()}

    # 同时包含 pending/running 的 run（刚触发、还没产生 TestResult）
    active_runs_q = await db.execute(
        select(TestRun.id).where(TestRun.status.in_(["pending", "running"]))
    )
    active_run_ids = {r[0] for r in active_runs_q.all()}

    all_run_ids = api_run_ids | active_run_ids

    query = select(TestRun).where(TestRun.id.in_(all_run_ids)).order_by(TestRun.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    runs = result.scalars().all()
    return ApiResponse(data=[RunResponse.model_validate(r) for r in runs])


@router.get("/api-tests/runs/{run_id}", response_model=ApiResponse)
async def get_api_run(run_id: int, db: AsyncSession = Depends(get_async_session)):
    """获取接口测试单次运行详情"""
    run = await db.get(TestRun, run_id)
    if not run:
        return ApiResponse(success=False, error="运行记录不存在")

    results_q = await db.execute(
        select(TestResult).where(TestResult.run_id == run_id).order_by(TestResult.id)
    )
    results = results_q.scalars().all()

    return ApiResponse(data={
        "run": RunResponse.model_validate(run),
        "results": [ResultResponse.model_validate(r) for r in results],
    })
