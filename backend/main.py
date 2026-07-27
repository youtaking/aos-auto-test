# backend/main.py
"""FastAPI 应用入口"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.db.config import init_db, close_db
from backend.api import projects, suites, runs, cases, dashboard, api_tests
from backend import ws as ws_module


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时建表 + 自动发现用例，关闭时释放连接"""
    await init_db()
    # 启动时自动扫描并注册测试用例
    try:
        from engine.runner import TestRunner
        from backend.db.config import async_session
        from backend.db.models import TestCase, TestSuite, Project
        from sqlalchemy import select

        runner = TestRunner()
        collected = runner.collect_tests()

        if collected:
            async with async_session() as db:
                # 获取激活项目
                result = await db.execute(select(Project).where(Project.is_active == 1))
                project = result.scalar_one_or_none()
                if not project:
                    result = await db.execute(select(Project).limit(1))
                    project = result.scalar_one_or_none()

                if project:
                    result = await db.execute(
                        select(TestSuite).where(TestSuite.project_id == project.id)
                    )
                    suites = {s.name: s for s in result.scalars().all()}

                    SUITE_LABELS = {
                        "login": "登录/认证", "dashboard": "Dashboard",
                        "agent": "Agent 管理", "chat": "Chat 对话",
                        "workflow": "智能体编排", "memory": "记忆",
                        "knowledge": "知识库", "tasks": "定时任务",
                        "organization": "组织", "apikey": "API Key",
                        "sidebar": "侧边栏导航", "sites": "Agent Sites",
                        "chat_v2": "对话聊天", "skills_v2": "技能管理",
                    }

                    new_cases = 0
                    for item in collected:
                        suite_key = item["suite_name"]
                        func_name = item["function_name"]
                        suite_label = SUITE_LABELS.get(suite_key, suite_key.title())

                        if suite_label not in suites:
                            suite = TestSuite(
                                project_id=project.id, name=suite_label,
                                description=f"自动发现的 {suite_key} 测试套件", tags=suite_key,
                            )
                            db.add(suite)
                            await db.flush()
                            suites[suite_label] = suite

                        suite = suites[suite_label]
                        existing = await db.execute(
                            select(TestCase).where(TestCase.function_name == func_name)
                        )
                        if existing.scalar_one_or_none():
                            continue

                        priority = "P0" if any(t in func_name for t in ["login", "auth", "redirect", "page_loads"]) else "P1"
                        db.add(TestCase(
                            suite_id=suite.id,
                            name=func_name.replace("test_", "").replace("_", " ").title(),
                            file_path=item["file_path"], function_name=func_name,
                            tags=f"{priority.lower()},{suite_key}", priority=priority, timeout=30,
                        ))
                        new_cases += 1

                    await db.commit()
                    print(f"[AutoDiscover] 发现 {len(collected)} 条用例，新增 {new_cases} 条")

                    # ── 接口测试用例自动发现 ──
                    try:
                        api_collected = runner.collect_tests_api()
                        if api_collected:
                            api_new = 0
                            for item in api_collected:
                                suite_key = item["suite_name"]
                                func_name = item["function_name"]
                                suite_label = SUITE_LABELS.get(suite_key, suite_key.title()) + " (API)"

                                if suite_label not in suites:
                                    suite = TestSuite(
                                        project_id=project.id,
                                        name=suite_label,
                                        description=f"自动发现的 {suite_key} 接口测试套件",
                                        tags=suite_key,
                                        test_type="api",
                                    )
                                    db.add(suite)
                                    await db.flush()
                                    suites[suite_label] = suite

                                suite = suites[suite_label]
                                existing = await db.execute(
                                    select(TestCase).where(TestCase.function_name == func_name)
                                )
                                if existing.scalar_one_or_none():
                                    continue

                                db.add(TestCase(
                                    suite_id=suite.id,
                                    name=func_name.replace("test_", "").replace("_", " ").title(),
                                    file_path=item["file_path"],
                                    function_name=func_name,
                                    tags=f"api,{suite_key}",
                                    priority="P0",
                                    timeout=15,
                                ))
                                api_new += 1

                            await db.commit()
                            print(f"[AutoDiscover] 接口测试：发现 {len(api_collected)} 条用例，新增 {api_new} 条")
                    except Exception as e:
                        print(f"[AutoDiscover] 接口测试用例发现失败: {e}")

    except Exception as e:
        print(f"[AutoDiscover] 用例发现失败: {e}")

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
app.include_router(ws_module.router, tags=["websocket"])


@app.get("/api/health")
async def health():
    return {"success": True, "data": {"status": "ok"}}
