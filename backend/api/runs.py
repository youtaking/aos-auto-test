# backend/api/runs.py
"""测试运行 API"""
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, BackgroundTasks
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.db.config import get_async_session, async_session
from backend.db.models import TestRun, TestResult, TestCase, Project
from backend.schemas.run import RunResponse, RunReport, ResultResponse
from backend.schemas.common import ApiResponse

router = APIRouter()

ALLURE_RESULTS_DIR = "allure-results"
ALLURE_REPORT_DIR = "allure-report"


def _parse_pytest_line(line: str) -> dict | None:
    """解析 pytest -v 输出的单行结果"""
    # 格式：tests/suites/test_login.py::test_login_page_loads PASSED
    m = re.match(r"^(tests/\S+::\w+)\s+(PASSED|FAILED|SKIPPED|ERROR)", line.strip())
    if not m:
        return None
    nodeid = m.group(1)
    outcome = m.group(2).lower()
    parts = nodeid.split("::")
    file_path = parts[0] if parts else ""
    func_name = parts[-1] if len(parts) > 1 else ""
    suite_name = Path(file_path).stem.replace("test_", "")
    return {
        "nodeid": nodeid,
        "file_path": file_path,
        "func_name": func_name,
        "suite_name": suite_name,
        "outcome": outcome,
    }


async def _execute_tests(run_id: int, project_url: str, headed: bool = False, step_delay: float = 0):
    """后台任务：执行 pytest，逐条实时更新结果 + 生成 Allure 报告"""
    async with async_session() as db:
        run = await db.get(TestRun, run_id)
        if not run:
            return

        run.status = "running"
        run.started_at = datetime.utcnow()
        await db.commit()

        # 清理旧的 allure 结果
        allure_dir = Path(ALLURE_RESULTS_DIR)
        if allure_dir.exists():
            for f in allure_dir.iterdir():
                f.unlink()
        else:
            allure_dir.mkdir(parents=True, exist_ok=True)

        report_path = f"report_{run_id}.json"
        cmd = [
            sys.executable, "-m", "pytest", "tests/suites/",
            "-v", "--tb=short",
            f"--base-url={project_url}",
            f"--step-delay={step_delay}",
            "--json-report", f"--json-report-file={report_path}",
            f"--alluredir={ALLURE_RESULTS_DIR}",
        ]

        env = {
            **__import__("os").environ,
            "HEADLESS": "false" if headed else "true",
            "STEP_DELAY": str(step_delay),
        }

        # 用 Popen 逐行读取输出
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", env=env,
        )

        passed = 0
        failed = 0
        skipped = 0
        error_details = {}  # func_name -> error message

        # 实时解析 pytest 输出
        for line in proc.stdout:
            parsed = _parse_pytest_line(line)
            if not parsed:
                continue

            func_name = parsed["func_name"]
            outcome = parsed["outcome"]

            # 查找匹配的 TestCase
            case_query = await db.execute(
                select(TestCase).where(TestCase.function_name == func_name)
            )
            case = case_query.scalar_one_or_none()

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

        proc.wait(timeout=600)
        finished = datetime.utcnow()

        # 用 JSON 报告补充 duration 和 error 信息
        rf = Path(report_path)
        if rf.exists():
            with open(rf, "r", encoding="utf-8") as f:
                report = json.load(f)
            for test in report.get("tests", []):
                nodeid = test.get("nodeid", "")
                func_name = nodeid.split("::")[-1] if "::" in nodeid else ""
                call_info = test.get("call", {})
                duration_ms = int(call_info.get("duration", 0) * 1000)
                longrepr = str(call_info.get("longrepr", "")) if call_info.get("longrepr") else None
                # 更新已有结果
                existing = await db.execute(
                    select(TestResult).where(
                        TestResult.run_id == run_id,
                        TestResult.case_name == func_name,
                    )
                )
                r = existing.scalar_one_or_none()
                if r:
                    r.duration_ms = duration_ms
                    r.error_message = longrepr[:500] if longrepr else None
                    r.stack_trace = longrepr
            rf.unlink(missing_ok=True)

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
            result = subprocess.run(
                cmd_str, shell=True,
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode != 0:
                print(f"[Allure] stderr: {result.stderr}")
            else:
                print(f"[Allure] 报告生成成功: {report_dir}")
        except Exception as e:
            print(f"[Allure] 报告生成失败: {e}")


@router.get("/runs", response_model=ApiResponse)
async def list_runs(
    project_id: int | None = None,
    status: str | None = None,
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
    db: AsyncSession = Depends(get_async_session),
):
    """触发一次测试运行"""
    project = await db.get(Project, project_id)
    project_url = project.url if project else "http://localhost:3001"

    run = TestRun(
        project_id=project_id,
        trigger_type=trigger_type,
        status="pending",
        started_at=datetime.utcnow(),
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    background_tasks.add_task(_execute_tests, run.id, project_url, headed, step_delay)

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
    return ApiResponse(data={"deleted": True})


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
