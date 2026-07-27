# backend/api/api_tests.py
"""接口测试 API 路由"""
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
    """解析 pytest -v 输出的单行结果"""
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

        report_path = f"api_report_{run_id}.json"
        cmd = [
            sys.executable, "-m", "pytest", API_TEST_DIR,
            "-v", "--tb=short",
            f"--base-url={api_base_url}",
            "--json-report", f"--json-report-file={report_path}",
        ]

        if case_ids:
            cases_query = await db.execute(
                select(TestCase).where(TestCase.id.in_(case_ids))
            )
            func_names = [c.function_name for c in cases_query.scalars().all()]
            if func_names:
                k_expr = " or ".join(func_names)
                cmd.extend(["-k", k_expr])

        env = {
            **os.environ,
            "FENIX_API_KEY": api_key,
        }

        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", env=env,
        )

        passed = 0
        failed = 0
        skipped = 0

        for line in proc.stdout:
            stripped = line.rstrip()
            if stripped:
                await ws_module.broadcast(run_id, "log", {"line": stripped})

            parsed = _parse_pytest_line(line)
            if not parsed:
                continue

            func_name = parsed["func_name"]
            outcome = parsed["outcome"]

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

            await ws_module.broadcast(run_id, "result_update", {
                "case_name": func_name,
                "suite_name": parsed["suite_name"],
                "status": outcome,
                "passed": passed, "failed": failed, "skipped": skipped,
            })

        proc.wait(timeout=300)
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

        await ws_module.broadcast(run_id, "run_complete", {
            "run_id": run_id,
            "status": run.status,
            "total": run.total,
            "passed": run.passed,
            "failed": run.failed,
            "skipped": run.skipped,
            "duration_ms": run.duration_ms,
        })


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
    api_suite_ids_q = await db.execute(
        select(TestSuite.id).where(TestSuite.test_type == "api")
    )
    api_suite_ids = {r[0] for r in api_suite_ids_q.all()}

    api_run_ids_q = await db.execute(
        select(TestResult.run_id).distinct().where(
            TestResult.suite_name.in_(["agent_api"])
        )
    )
    api_run_ids = {r[0] for r in api_run_ids_q.all()}

    query = select(TestRun).where(TestRun.id.in_(api_run_ids)).order_by(TestRun.created_at.desc())
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
