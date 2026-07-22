# backend/api/cases.py
"""测试用例管理 API"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from backend.db.config import get_async_session
from backend.db.models import TestCase, TestResult
from backend.schemas.case import CaseResponse
from backend.schemas.common import ApiResponse

router = APIRouter()


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
