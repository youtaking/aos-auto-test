# backend/main.py
"""FastAPI 应用入口"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.db.config import init_db, close_db
from backend.api import projects, suites, runs, cases, dashboard, api_tests, auth_configs, llm_configs, zentao_configs, ai_analysis, ci, slots, collections
from backend import ws as ws_module


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时建表 + 自动发现用例，关闭时释放连接"""
    await init_db()
    from backend.db.config import async_session
    from sqlalchemy import select

    # 启动时自动扫描并全量同步测试用例
    try:
        from engine.runner import TestRunner
        from backend.db.models import Project
        from backend.api.cases import sync_test_cases, SUITE_LABELS, API_SUITE_LABELS

        runner = TestRunner()

        async with async_session() as db:
            # 获取激活项目
            result = await db.execute(select(Project).where(Project.is_active == 1))
            project = result.scalar_one_or_none()
            if not project:
                result = await db.execute(select(Project).limit(1))
                project = result.scalar_one_or_none()

            if project:
                # UI 测试同步
                ui_collected = runner.collect_tests()
                if ui_collected:
                    ui_stats = await sync_test_cases(db, project, ui_collected, SUITE_LABELS, "ui")
                    print(f"[AutoDiscover] UI: 扫描 {ui_stats['discovered']} 条，"
                          f"新增 {ui_stats['new_cases']}，清理 {ui_stats['removed_cases']}，"
                          f"删除空套件 {ui_stats['removed_suites']}")

                # API 测试同步
                api_collected = runner.collect_tests_api()
                if api_collected:
                    api_stats = await sync_test_cases(db, project, api_collected, API_SUITE_LABELS, "api")
                    print(f"[AutoDiscover] API: 扫描 {api_stats['discovered']} 条，"
                          f"新增 {api_stats['new_cases']}，清理 {api_stats['removed_cases']}，"
                          f"删除空套件 {api_stats['removed_suites']}")

    except Exception as e:
        print(f"[AutoDiscover] 用例同步失败: {e}")

    # 初始化默认 Slot（如果不存在）
    try:
        async with async_session() as db:
            from backend.db.models import EnvironmentSlot
            result = await db.execute(select(EnvironmentSlot))
            existing_slots = result.scalars().all()
            if not existing_slots:
                default_slots = [
                    EnvironmentSlot(name="Slot 1", rcs_port=3101, postgres_port=5501, litellm_port=4101),
                    EnvironmentSlot(name="Slot 2", rcs_port=3102, postgres_port=5502, litellm_port=4102),
                    EnvironmentSlot(name="Slot 3", rcs_port=3103, postgres_port=5503, litellm_port=4103),
                ]
                db.add_all(default_slots)
                await db.commit()
                print("[Init] 已创建 3 个默认 Slot")
    except Exception as e:
        print(f"[Init] Slot 初始化失败: {e}")

    # 启动超时检查后台任务
    try:
        from backend.services.timeout_checker import start_timeout_checker
        start_timeout_checker()
    except Exception as e:
        print(f"[Init] 超时检查任务启动失败: {e}")

    yield
    # 停止超时检查
    try:
        from backend.services.timeout_checker import stop_timeout_checker
        stop_timeout_checker()
    except Exception:
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
app.include_router(slots.router, prefix="/api", tags=["slots"])
app.include_router(collections.router, prefix="/api", tags=["collections"])
app.include_router(ws_module.router, tags=["websocket"])


@app.get("/api/health")
async def health():
    return {"success": True, "data": {"status": "ok"}}
