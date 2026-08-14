# backend/services/pipeline_runner.py
"""Pipeline test execution: used for manual/scheduled triggers.
Jenkins-triggered pipelines submit results via API instead."""
import asyncio
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from backend.db.config import async_session
from backend.db.models import TestRun, TestCase, AuthConfig, PRPipeline
from backend import ws as ws_module


async def _broadcast(pipeline_id: int, event: str, data: dict):
    """Broadcast pipeline event via WebSocket"""
    await ws_module.broadcast_pipeline(pipeline_id, event, data)
    await ws_module.broadcast_global(event, {**data, "pipeline_id": pipeline_id})


async def run_manual_tests(
    project_id: int = 1,
    case_ids: list[int] | None = None,
    project_url: str | None = None,
):
    """Execute tests manually (for manual/scheduled triggers from UI).
    Returns the TestRun ID."""
    async with async_session() as db:
        run = TestRun(
            project_id=project_id,
            trigger_type="manual",
            status="running",
            started_at=datetime.utcnow(),
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)

        auth_env = {}
        auth_result = await db.execute(
            select(AuthConfig).where(AuthConfig.is_active == 1)
        )
        auth_config = auth_result.scalars().first()
        if auth_config:
            auth_env = {
                "FENIX_UI_EMAIL": auth_config.ui_test_email or "",
                "FENIX_UI_PASSWORD": auth_config.ui_test_password or "",
                "FENIX_API_EMAIL": auth_config.api_test_email or "",
                "FENIX_API_PASSWORD": auth_config.api_test_password or "",
                "FENIX_OPEN_API_KEY": auth_config.open_api_key or "",
            }

        await _execute_tests(
            run_id=run.id,
            project_url=project_url or "http://localhost:3000",
            auth_env=auth_env,
            case_ids=case_ids,
            pipeline_id=None,
        )
        return run.id


async def _execute_tests(
    run_id: int,
    project_url: str,
    auth_env: dict,
    case_ids: list[int] | None,
    pipeline_id: int | None = None,
    branch: str = "main",
):
    """Execute pytest and store results."""
    async with async_session() as db:
        run = await db.get(TestRun, run_id)
        if not run:
            return

        run.status = "running"
        run.started_at = datetime.utcnow()
        await db.commit()

        passed = failed = skipped = 0

        try:
            report_path = f"report_run_{run_id}.json"

            if branch and branch != "main":
                scan_dirs = [f"branches/{branch}/api_suites/"]
            else:
                scan_dirs = ["tests/suites/", "tests/api_suites/"]

            cmd = [
                sys.executable, "-m", "pytest",
                *scan_dirs,
                "-v", "--tb=short",
                f"--base-url={project_url}",
                "--json-report", f"--json-report-file={report_path}",
            ]

            if case_ids:
                cases_query = await db.execute(
                    select(TestCase).where(TestCase.id.in_(case_ids))
                )
                selected_cases = cases_query.scalars().all()
                if selected_cases:
                    node_ids = [f"{c.file_path}::{c.function_name}" for c in selected_cases]
                    cmd.extend(node_ids)
                    cmd = [c for c in cmd if c not in scan_dirs]

            env = {
                **os.environ,
                "HEADLESS": "true",
                "FENIX_URL": project_url,
                "PYTHONUNBUFFERED": "1",
                "PYTHONUTF8": "1",
                "FENIX_API_BASE_URL": project_url,
            }
            if auth_env:
                env.update(auth_env)

            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                env=env, cwd=os.getcwd(),
            )

            log_name = f"pipeline_{pipeline_id}" if pipeline_id else f"run_{run_id}"
            log_path = Path("run_logs") / f"{log_name}.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)

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
                        if pipeline_id:
                            await _broadcast(pipeline_id, "test_log", {"line": stripped})

                    m = re.match(r"^((?:tests|branches)/\S+::\S+)\s+(PASSED|FAILED|SKIPPED|ERROR)", stripped)
                    if m:
                        outcome = m.group(2).lower()
                        func_name = m.group(1).split("::")[-1]
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
                        if pipeline_id:
                            await _broadcast(pipeline_id, "test_progress", {
                                "case": func_name, "status": outcome,
                                "passed": passed, "failed": failed, "skipped": skipped,
                            })

            await asyncio.to_thread(proc.wait)

            finished = datetime.utcnow()
            run.status = "passed" if failed == 0 else "failed"
            run.finished_at = finished
            run.duration_ms = int((finished - run.started_at).total_seconds() * 1000)
            await db.commit()

            if pipeline_id:
                pipeline = await db.get(PRPipeline, pipeline_id)
                if pipeline:
                    pipeline.status = run.status
                    await db.commit()
                    await _broadcast(pipeline_id, "pipeline_complete", {
                        "status": run.status, "total": run.total,
                        "passed": run.passed, "failed": run.failed, "skipped": run.skipped,
                    })

        except Exception as e:
            print(f"[Run #{run_id}] Test execution error: {e}", flush=True)
            run.status = "error"
            run.finished_at = datetime.utcnow()
            await db.commit()
            if pipeline_id:
                pipeline = await db.get(PRPipeline, pipeline_id)
                if pipeline:
                    pipeline.status = "failed"
                    err_msg = str(e)
                    pipeline.error_message = err_msg[-3000:] if len(err_msg) > 3000 else err_msg
                    await db.commit()
            raise
