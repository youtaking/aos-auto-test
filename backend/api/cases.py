# backend/api/cases.py
"""测试用例管理 API"""
from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete, update
from backend.db.config import get_async_session
from backend.db.models import TestCase, TestResult, TestSuite, TestCollection, Project
from backend.schemas.case import CaseResponse, CaseCreate
from backend.schemas.common import ApiResponse

router = APIRouter()

# ── 套件显示名映射 ──

SUITE_LABELS = {
    "login": "登录/认证", "dashboard": "Dashboard",
    "agent": "Agent 管理", "agent_manage": "Agent 管理",
    "agent_config_v2": "Agent_Config_V2",
    "chat": "Chat 对话", "chat_v2": "对话聊天",
    "sidebar": "侧边栏导航", "sites": "Agent Sites",
    "tasks": "定时任务", "knowledge": "知识库",
    "apikey": "API Key", "skills_v2": "Skills_V2",
    "auth": "Auth", "mcp": "Mcp",
    "algorithms": "Algorithms", "model_config": "Model_Config",
    "org": "Org", "vertical_models": "Vertical_Models",
}

API_SUITE_LABELS = {
    "agent_api": "Agent_Api (API)",
}


def _infer_priority(func_name: str) -> str:
    """根据函数名推断优先级"""
    if any(t in func_name for t in ["login", "auth", "redirect", "page_loads"]):
        return "P0"
    return "P1"


async def sync_test_cases(
    db: AsyncSession,
    project: Project,
    collected: list[dict],
    suite_labels: dict[str, str],
    test_type: str = "ui",
) -> dict:
    """
    全量同步：对比文件系统与 DB，新增缺失的、清理过期的、删除空套件。
    """
    # 1. 按 suite_key 分组
    grouped: dict[str, list[dict]] = defaultdict(list)
    for item in collected:
        grouped[item["suite_name"]].append(item)

    # 2. 获取已有套件，按 tags 索引
    result = await db.execute(
        select(TestSuite).where(TestSuite.project_id == project.id)
    )
    suites_by_tags = {s.tags: s for s in result.scalars().all()}

    new_cases = 0
    removed_cases = 0

    # 3. 逐套件同步
    for suite_key, items in grouped.items():
        suite_label = suite_labels.get(suite_key, suite_key.title())

        # 按 tags 匹配已有套件，找不到则创建
        suite = suites_by_tags.get(suite_key)
        if not suite:
            suite = TestSuite(
                project_id=project.id,
                name=suite_label,
                description=f"自动发现的 {suite_key} 测试套件",
                tags=suite_key,
                test_type=test_type,
            )
            db.add(suite)
            await db.flush()
            suites_by_tags[suite_key] = suite

        # 文件系统上的函数名集合
        fs_funcs = {item["function_name"] for item in items}

        # DB 中该套件的所有用例
        db_result = await db.execute(
            select(TestCase).where(TestCase.suite_id == suite.id)
        )
        db_cases = {c.function_name: c for c in db_result.scalars().all()}
        # 短名索引（不含类前缀），用于处理 ClassName::test_xxx 的迁移
        db_cases_short: dict[str, TestCase] = {}
        for fn, c in db_cases.items():
            short = fn.split("::")[-1] if "::" in fn else fn
            db_cases_short[short] = c

        updated_funcs: set[str] = set()  # 被更新（而非新增）的函数名

        # 新增：文件系统有但 DB 没有
        for item in items:
            fn = item["function_name"]
            if fn not in db_cases:
                # 尝试通过短名匹配（处理类前缀变更）
                short = fn.split("::")[-1] if "::" in fn else fn
                old_case = db_cases_short.get(short)
                if old_case and old_case.function_name != fn:
                    # 旧名 -> 新名（加了类前缀），更新而非删除+创建
                    old_case.function_name = fn
                    old_case.file_path = item["file_path"]
                    updated_funcs.add(old_case.function_name)
                    continue
                priority = _infer_priority(fn)
                db.add(TestCase(
                    suite_id=suite.id,
                    name=fn.replace("test_", "").replace("_", " ").title(),
                    file_path=item["file_path"],
                    function_name=fn,
                    tags=f"{priority.lower()},{suite_key}",
                    priority=priority,
                    timeout=30,
                ))
                new_cases += 1

        # 清理：DB 有但文件系统没有（排除刚被更新的）
        stale_funcs = [fn for fn in db_cases if fn not in fs_funcs and fn not in updated_funcs]
        if stale_funcs:
            stale_ids = [db_cases[fn].id for fn in stale_funcs]
            await db.execute(
                update(TestResult)
                .where(TestResult.case_id.in_(stale_ids))
                .values(case_id=None)
            )
            await db.execute(
                delete(TestCase).where(TestCase.id.in_(stale_ids))
            )
            removed_cases += len(stale_funcs)

    # 3b. 清理 DB 中存在但文件系统上已完全没有的套件（整个文件被删除）
    fs_suite_keys = set(grouped.keys())
    all_db_suites = await db.execute(
        select(TestSuite).where(
            TestSuite.project_id == project.id,
            TestSuite.test_type == test_type,
        )
    )
    for suite in all_db_suites.scalars().all():
        if suite.tags not in fs_suite_keys:
            # 该套件对应的测试文件已不存在，删除所有用例
            db_result = await db.execute(
                select(TestCase).where(TestCase.suite_id == suite.id)
            )
            stale_cases = db_result.scalars().all()
            if stale_cases:
                stale_ids = [c.id for c in stale_cases]
                await db.execute(
                    update(TestResult)
                    .where(TestResult.case_id.in_(stale_ids))
                    .values(case_id=None)
                )
                await db.execute(
                    delete(TestCase).where(TestCase.id.in_(stale_ids))
                )
                removed_cases += len(stale_cases)

    await db.flush()

    # 4. 删除空套件
    removed_suites = 0
    project_suites = await db.execute(
        select(TestSuite).where(
            TestSuite.project_id == project.id,
            TestSuite.test_type == test_type,
        )
    )
    for suite in project_suites.scalars().all():
        cnt = await db.execute(
            select(func.count()).select_from(TestCase).where(TestCase.suite_id == suite.id)
        )
        if cnt.scalar() == 0:
            await db.delete(suite)
            removed_suites += 1

    # 5. 清理测试集中已删除用例的引用
    await db.flush()
    valid_ids_result = await db.execute(
        select(TestCase.id).where(
            TestCase.suite_id.in_(
                select(TestSuite.id).where(TestSuite.project_id == project.id)
            )
        )
    )
    valid_ids = {row[0] for row in valid_ids_result.fetchall()}

    collections_result = await db.execute(
        select(TestCollection).where(TestCollection.project_id == project.id)
    )
    for coll in collections_result.scalars().all():
        old_ids = coll.case_ids or []
        new_ids = [cid for cid in old_ids if cid in valid_ids]
        if len(new_ids) != len(old_ids):
            coll.case_ids = new_ids

    await db.commit()

    return {
        "discovered": len(collected),
        "new_cases": new_cases,
        "removed_cases": removed_cases,
        "removed_suites": removed_suites,
    }


# ── 端点 ──

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
    """扫描测试文件，全量同步套件和用例（新增 + 清理）"""
    from engine.runner import TestRunner

    # 获取激活的项目
    result = await db.execute(select(Project).where(Project.is_active == 1))
    project = result.scalar_one_or_none()
    if not project:
        result = await db.execute(select(Project).limit(1))
        project = result.scalar_one_or_none()
    if not project:
        return ApiResponse(success=False, error="没有项目，请先添加项目")

    runner = TestRunner()

    # UI 测试同步
    ui_collected = runner.collect_tests()
    ui_stats = await sync_test_cases(db, project, ui_collected, SUITE_LABELS, "ui")

    # API 测试同步
    api_collected = runner.collect_tests_api()
    api_stats = await sync_test_cases(db, project, api_collected, API_SUITE_LABELS, "api")

    return ApiResponse(data={"ui": ui_stats, "api": api_stats})


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
