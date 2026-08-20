# backend/main.py
"""FastAPI 应用入口"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.db.config import init_db, close_db
from backend.api import (
    projects, suites, runs, cases, dashboard, api_tests,
    auth_configs, llm_configs, zentao_configs, ai_analysis,
    ci, collections, unit_tests, settings, branches,
)
from backend import ws as ws_module

logger = logging.getLogger(__name__)


async def _branch_poll_loop():
    """后台定时轮询 GitHub PR"""
    from backend.services.branch_poller import BranchPoller
    from backend.db.config import async_session
    from backend.db.models import Setting
    from sqlalchemy import select

    poller = BranchPoller()
    logger.info("[BranchPoller] 后台轮询任务已启动")

    while True:
        try:
            async with async_session() as db:
                result = await db.execute(select(Setting))
                cfg = {s.key: s.value for s in result.scalars().all()}

            enabled = cfg.get("branch_poll_enabled", "false") == "true"
            if not enabled:
                await asyncio.sleep(60)
                continue

            interval = int(cfg.get("branch_poll_interval", "300"))
            interval = max(interval, 30)  # 最小 30 秒

            res = await poller.poll_once()
            logger.info("[BranchPoller] poll result: %s", res)

            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            logger.info("[BranchPoller] 后台轮询任务已取消")
            break
        except Exception as e:
            logger.error("[BranchPoller] poll error: %s", e)
            await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时建表 + 自动发现用例，关闭时释放连接"""
    await init_db()
    from backend.db.config import async_session
    from sqlalchemy import select

    try:
        from engine.runner import TestRunner
        from backend.db.models import Project
        from backend.api.cases import sync_test_cases, SUITE_LABELS, API_SUITE_LABELS

        runner = TestRunner()

        async with async_session() as db:
            result = await db.execute(select(Project).where(Project.is_active == 1))
            project = result.scalars().first()
            if not project:
                result = await db.execute(select(Project).limit(1))
                project = result.scalars().first()

            if project:
                ui_collected = runner.collect_tests()
                if ui_collected:
                    ui_stats = await sync_test_cases(db, project, ui_collected, SUITE_LABELS, "ui")
                    print(f"[AutoDiscover] UI: scanned {ui_stats['discovered']}, "
                          f"new {ui_stats['new_cases']}, cleaned {ui_stats['removed_cases']}")

                api_collected = runner.collect_tests_api()
                if api_collected:
                    api_stats = await sync_test_cases(db, project, api_collected, API_SUITE_LABELS, "api")
                    print(f"[AutoDiscover] API: scanned {api_stats['discovered']}, "
                          f"new {api_stats['new_cases']}, cleaned {api_stats['removed_cases']}")

                # 分支 API 测试扫描
                from pathlib import Path as _Path
                branches_dir = _Path(__file__).resolve().parent.parent / "branches"
                if branches_dir.exists():
                    for branch_api_dir in branches_dir.rglob("api_suites"):
                        if not branch_api_dir.is_dir() or "node_modules" in branch_api_dir.parts:
                            continue
                        # 从相对路径提取分支名：branches/refactor/yjs/api_suites → refactor/yjs
                        branch_name = str(branch_api_dir.relative_to(branches_dir).parent).replace("\\", "/")
                        if branch_name == ".":
                            continue
                        branch_collected = runner.collect_tests_api(test_dir=str(branch_api_dir))
                        if branch_collected:
                            branch_stats = await sync_test_cases(
                                db, project, branch_collected, API_SUITE_LABELS, "api",
                                branch=branch_name,
                            )
                            print(f"[AutoDiscover] API ({branch_name}): scanned {branch_stats['discovered']}, "
                                  f"new {branch_stats['new_cases']}, cleaned {branch_stats['removed_cases']}")

    except Exception as e:
        print(f"[AutoDiscover] 用例同步失败: {e}")

    # 单元测试用例自动发现
    try:
        from backend.api.unit_tests import discover_unit_tests, UNIT_TESTS_DIR, _sync_unit_test_cases
        from backend.db.models import UnitTestCase, UnitTestResult

        # Main 基线
        if UNIT_TESTS_DIR.exists():
            discovered = discover_unit_tests(UNIT_TESTS_DIR, branch="main")
            seen = set()
            unique_discovered = []
            for c in discovered:
                key = (c["full_name"], c["branch"])
                if key not in seen:
                    seen.add(key)
                    unique_discovered.append(c)
            async with async_session() as db:
                new_c, updated_c, removed_c = await _sync_unit_test_cases(db, unique_discovered, branch="main")
            print(f"[AutoDiscover] Unit (main): discovered {len(unique_discovered)}, "
                  f"new {new_c}, updated {updated_c}, removed {removed_c}")

        # 分支目录（支持含斜杠的分支名，如 refactor/yjs）
        branches_dir = UNIT_TESTS_DIR.parent / "branches"
        if branches_dir.exists():
            for branch_unit_dir in branches_dir.rglob("unit_tests"):
                if not branch_unit_dir.is_dir() or "node_modules" in branch_unit_dir.parts:
                    continue
                # 从相对路径提取分支名：branches/refactor/yjs/unit_tests → refactor/yjs
                branch_name = str(branch_unit_dir.relative_to(branches_dir).parent).replace("\\", "/")
                if branch_name == ".":
                    continue
                discovered = discover_unit_tests(branch_unit_dir, branch=branch_name)
                seen = set()
                unique_discovered = []
                for c in discovered:
                    key = (c["full_name"], c["branch"])
                    if key not in seen:
                        seen.add(key)
                        unique_discovered.append(c)
                async with async_session() as db:
                    new_c, updated_c, removed_c = await _sync_unit_test_cases(db, unique_discovered, branch=branch_name)
                print(f"[AutoDiscover] Unit ({branch_name}): discovered {len(unique_discovered)}, "
                      f"new {new_c}, updated {updated_c}, removed {removed_c}")
    except Exception as e:
        print(f"[AutoDiscover] Unit test discovery failed: {e}")

    # 启动分支轮询后台任务（仅在实际服务进程中启动）
    poll_task = None
    is_reload_child = os.environ.get("UVICORN_RELOADING") == "true" or os.environ.get("WERKZEUG_RUN_MAIN") == "true"
    if not os.environ.get("UVICORN_RELOADING") or is_reload_child:
        poll_task = asyncio.create_task(_branch_poll_loop())

    yield

    if poll_task:
        poll_task.cancel()
        try:
            await poll_task
        except asyncio.CancelledError:
            pass

    await close_db()


app = FastAPI(title="AutoTest API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router, prefix="/api", tags=["projects"])
app.include_router(suites.router, prefix="/api", tags=["suites"])
app.include_router(runs.router, prefix="/api", tags=["runs"])
app.include_router(cases.router, prefix="/api", tags=["cases"])
app.include_router(dashboard.router, prefix="/api", tags=["dashboard"])
app.include_router(api_tests.router, prefix="/api", tags=["api-tests"])
app.include_router(auth_configs.router, prefix="/api", tags=["auth-configs"])
app.include_router(llm_configs.router, prefix="/api", tags=["llm-configs"])
app.include_router(zentao_configs.router, prefix="/api", tags=["zentao-configs"])
app.include_router(ai_analysis.router, prefix="/api", tags=["ai-analysis"])
app.include_router(ci.router, prefix="/api", tags=["ci-pipelines"])
app.include_router(collections.router, prefix="/api", tags=["collections"])
app.include_router(unit_tests.router, prefix="/api", tags=["unit-tests"])
app.include_router(settings.router, prefix="/api", tags=["settings"])
app.include_router(branches.router, prefix="/api", tags=["branches"])
app.include_router(ws_module.router, tags=["websocket"])


@app.get("/api/health")
async def health():
    return {"success": True, "data": {"status": "ok"}}
