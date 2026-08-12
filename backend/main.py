# backend/main.py
"""FastAPI 应用入口"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.db.config import init_db, close_db
from backend.api import (
    projects, suites, runs, cases, dashboard, api_tests,
    auth_configs, llm_configs, zentao_configs, ai_analysis,
    ci, collections, unit_tests, settings,
)
from backend import ws as ws_module


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
                    for branch_dir in branches_dir.iterdir():
                        if not branch_dir.is_dir():
                            continue
                        branch_api_dir = str(branch_dir / "api_suites")
                        if not _Path(branch_api_dir).exists():
                            continue
                        branch_name = branch_dir.name
                        branch_collected = runner.collect_tests_api(test_dir=branch_api_dir)
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

        # 分支目录
        branches_dir = UNIT_TESTS_DIR.parent / "branches"
        if branches_dir.exists():
            for branch_dir in branches_dir.iterdir():
                if not branch_dir.is_dir():
                    continue
                branch_unit_dir = branch_dir / "unit_tests"
                if not branch_unit_dir.exists():
                    continue
                branch_name = branch_dir.name
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

    yield
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
app.include_router(ws_module.router, tags=["websocket"])


@app.get("/api/health")
async def health():
    return {"success": True, "data": {"status": "ok"}}
