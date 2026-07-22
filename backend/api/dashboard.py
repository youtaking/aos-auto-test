# backend/api/dashboard.py
"""看板统计 API"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from backend.db.config import get_async_session
from backend.db.models import TestCase, TestRun, TestResult
from backend.schemas.common import ApiResponse

router = APIRouter()


@router.get("/dashboard/summary", response_model=ApiResponse)
async def dashboard_summary(db: AsyncSession = Depends(get_async_session)):
    """看板总览：用例总数、最近运行状态、通过率"""
    total_cases = (await db.execute(select(func.count()).select_from(TestCase))).scalar() or 0

    latest_run = (await db.execute(
        select(TestRun).order_by(TestRun.created_at.desc()).limit(1)
    )).scalar_one_or_none()

    total_results = (await db.execute(
        select(func.count()).select_from(TestResult)
    )).scalar() or 0

    passed_results = (await db.execute(
        select(func.count()).select_from(TestResult).where(TestResult.status == "passed")
    )).scalar() or 0

    pass_rate = round(passed_results / total_results * 100, 1) if total_results > 0 else 0.0

    return ApiResponse(data={
        "total_cases": total_cases,
        "latest_run_status": latest_run.status if latest_run else None,
        "pass_rate": pass_rate,
        "total_runs": (await db.execute(
            select(func.count()).select_from(TestRun)
        )).scalar() or 0,
    })


@router.get("/dashboard/trend", response_model=ApiResponse)
async def dashboard_trend(limit: int = 10, db: AsyncSession = Depends(get_async_session)):
    """最近 N 次运行的趋势数据"""
    result = await db.execute(
        select(TestRun).order_by(TestRun.created_at.desc()).limit(limit)
    )
    runs = result.scalars().all()

    trend = []
    for run in reversed(runs):
        trend.append({
            "id": run.id,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "status": run.status,
            "total": run.total,
            "passed": run.passed,
            "failed": run.failed,
            "skipped": run.skipped,
            "pass_rate": round(run.passed / run.total * 100, 1) if run.total > 0 else 0.0,
        })

    return ApiResponse(data=trend)
