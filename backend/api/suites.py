# backend/api/suites.py
"""测试套件管理 API"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.db.config import get_async_session
from backend.db.models import TestSuite
from backend.schemas.suite import SuiteCreate, SuiteUpdate, SuiteResponse
from backend.schemas.common import ApiResponse

router = APIRouter()


@router.get("/projects/{project_id}/suites", response_model=ApiResponse)
async def list_suites(project_id: int, db: AsyncSession = Depends(get_async_session)):
    """获取项目下的套件列表"""
    result = await db.execute(
        select(TestSuite).where(TestSuite.project_id == project_id).order_by(TestSuite.name)
    )
    suites = result.scalars().all()
    return ApiResponse(data=[SuiteResponse.model_validate(s) for s in suites])


@router.post("/projects/{project_id}/suites", response_model=ApiResponse)
async def create_suite(
    project_id: int, body: SuiteCreate, db: AsyncSession = Depends(get_async_session)
):
    """创建套件"""
    suite = TestSuite(
        project_id=project_id, name=body.name,
        description=body.description, tags=body.tags
    )
    db.add(suite)
    await db.commit()
    await db.refresh(suite)
    return ApiResponse(data=SuiteResponse.model_validate(suite))


@router.put("/suites/{suite_id}", response_model=ApiResponse)
async def update_suite(
    suite_id: int, body: SuiteUpdate, db: AsyncSession = Depends(get_async_session)
):
    """更新套件"""
    suite = await db.get(TestSuite, suite_id)
    if not suite:
        return ApiResponse(success=False, error="套件不存在")
    if body.name is not None:
        suite.name = body.name
    if body.description is not None:
        suite.description = body.description
    if body.tags is not None:
        suite.tags = body.tags
    await db.commit()
    await db.refresh(suite)
    return ApiResponse(data=SuiteResponse.model_validate(suite))


@router.delete("/suites/{suite_id}", response_model=ApiResponse)
async def delete_suite(suite_id: int, db: AsyncSession = Depends(get_async_session)):
    """删除套件"""
    suite = await db.get(TestSuite, suite_id)
    if not suite:
        return ApiResponse(success=False, error="套件不存在")
    await db.delete(suite)
    await db.commit()
    return ApiResponse(data={"deleted": True})
