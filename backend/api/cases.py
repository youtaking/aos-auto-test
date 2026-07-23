# backend/api/cases.py
"""测试用例管理 API"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from backend.db.config import get_async_session
from backend.db.models import TestCase, TestResult, TestSuite, Project
from backend.schemas.case import CaseResponse, CaseCreate
from backend.schemas.common import ApiResponse

router = APIRouter()


@router.post("/suites/{suite_id}/cases", response_model=ApiResponse)
async def create_case(
    suite_id: int, body: CaseCreate, db: AsyncSession = Depends(get_async_session)
):
    """创建测试用例"""
    case = TestCase(
        suite_id=suite_id,
        name=body.name,
        file_path=body.file_path,
        function_name=body.function_name,
        tags=body.tags,
        priority=body.priority,
        timeout=body.timeout,
    )
    db.add(case)
    await db.commit()
    await db.refresh(case)
    return ApiResponse(data=CaseResponse.model_validate(case))


@router.post("/cases/discover", response_model=ApiResponse)
async def discover_cases(db: AsyncSession = Depends(get_async_session)):
    """扫描测试文件，自动发现并注册套件和用例"""
    from engine.runner import TestRunner

    runner = TestRunner()
    collected = runner.collect_tests()

    # 获取激活的项目
    result = await db.execute(
        select(Project).where(Project.is_active == 1)
    )
    active_project = result.scalar_one_or_none()
    if not active_project:
        # 没有激活项目就用第一个项目
        result = await db.execute(select(Project).limit(1))
        active_project = result.scalar_one_or_none()
    if not active_project:
        return ApiResponse(success=False, error="没有项目，请先添加项目")

    # 获取已有套件，按名称索引
    result = await db.execute(
        select(TestSuite).where(TestSuite.project_id == active_project.id)
    )
    suites = {s.name: s for s in result.scalars().all()}

    # 套件名映射：test_xxx.py → "xxx"
    SUITE_LABELS = {
        "login": "登录/认证",
        "dashboard": "Dashboard",
        "agent": "Agent 管理",
        "chat": "Chat 对话",
        "workflow": "智能体编排", "memory": "记忆",
        "knowledge": "知识库", "tasks": "定时任务",
        "organization": "组织", "apikey": "API Key",
        "sidebar": "侧边栏导航", "sites": "Agent Sites",
        "chat_v2": "对话聊天", "skills_v2": "技能管理",
    }

    created_suites = 0
    created_cases = 0

    for item in collected:
        suite_key = item["suite_name"]  # e.g. "login", "dashboard"
        func_name = item["function_name"]

        # 自动创建套件
        suite_label = SUITE_LABELS.get(suite_key, suite_key.title())
        if suite_label not in suites:
            suite = TestSuite(
                project_id=active_project.id,
                name=suite_label,
                description=f"自动发现的 {suite_key} 测试套件",
                tags=suite_key,
            )
            db.add(suite)
            await db.flush()
            suites[suite_label] = suite
            created_suites += 1

        suite = suites[suite_label]

        # 检查用例是否已存在
        existing = await db.execute(
            select(TestCase).where(TestCase.function_name == func_name)
        )
        if existing.scalar_one_or_none():
            continue

        # 推断优先级
        priority = "P1"
        if any(tag in func_name for tag in ["login", "auth", "redirect", "page_loads"]):
            priority = "P0"

        case = TestCase(
            suite_id=suite.id,
            name=func_name.replace("test_", "").replace("_", " ").title(),
            file_path=item["file_path"],
            function_name=func_name,
            tags=f"{priority.lower()},{suite_key}",
            priority=priority,
            timeout=30,
        )
        db.add(case)
        created_cases += 1

    await db.commit()
    return ApiResponse(data={
        "discovered": len(collected),
        "created_suites": created_suites,
        "created_cases": created_cases,
    })


@router.get("/suites/{suite_id}/cases", response_model=ApiResponse)
async def list_cases(suite_id: int, db: AsyncSession = Depends(get_async_session)):
    """获取套件下的用例列表"""
    result = await db.execute(
        select(TestCase).where(TestCase.suite_id == suite_id).order_by(TestCase.name)
    )
    cases = result.scalars().all()
    return ApiResponse(data=[CaseResponse.model_validate(c) for c in cases])


@router.get("/cases/{case_id}", response_model=ApiResponse)
async def get_case(case_id: int, db: AsyncSession = Depends(get_async_session)):
    """获取用例详情（含历史通过率）"""
    case = await db.get(TestCase, case_id)
    if not case:
        return ApiResponse(success=False, error="用例不存在")

    total_result = await db.execute(
        select(func.count()).select_from(TestResult).where(TestResult.case_id == case_id)
    )
    total = total_result.scalar() or 0

    passed_result = await db.execute(
        select(func.count()).select_from(TestResult).where(
            TestResult.case_id == case_id, TestResult.status == "passed"
        )
    )
    passed = passed_result.scalar() or 0

    data = CaseResponse.model_validate(case).model_dump()
    data["pass_rate"] = round(passed / total * 100, 1) if total > 0 else 0.0
    data["total_runs"] = total
    return ApiResponse(data=data)
