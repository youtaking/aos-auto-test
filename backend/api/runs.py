# backend/api/runs.py
"""测试运行 API"""
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.db.config import get_async_session
from backend.db.models import TestRun, TestResult, TestCase
from backend.schemas.run import RunResponse, RunReport, ResultResponse
from backend.schemas.common import ApiResponse

router = APIRouter()


@router.get("/runs", response_model=ApiResponse)
async def list_runs(
    project_id: int | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_async_session),
):
    """获取运行历史（分页+筛选）"""
    query = select(TestRun).order_by(TestRun.created_at.desc())
    if project_id:
        query = query.where(TestRun.project_id == project_id)
    if status:
        query = query.where(TestRun.status == status)
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    runs = result.scalars().all()
    return ApiResponse(data=[RunResponse.model_validate(r) for r in runs])


@router.post("/runs", response_model=ApiResponse)
async def trigger_run(
    project_id: int,
    trigger_type: str = "manual",
    db: AsyncSession = Depends(get_async_session),
):
    """触发一次测试运行"""
    run = TestRun(
        project_id=project_id,
        trigger_type=trigger_type,
        status="pending",
        started_at=datetime.utcnow(),
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return ApiResponse(data=RunResponse.model_validate(run))


@router.get("/runs/{run_id}", response_model=ApiResponse)
async def get_run(run_id: int, db: AsyncSession = Depends(get_async_session)):
    """获取单次运行详情"""
    run = await db.get(TestRun, run_id)
    if not run:
        return ApiResponse(success=False, error="运行记录不存在")
    return ApiResponse(data=RunResponse.model_validate(run))


@router.get("/runs/{run_id}/results", response_model=ApiResponse)
async def get_run_results(run_id: int, db: AsyncSession = Depends(get_async_session)):
    """获取某次运行的所有用例结果"""
    result = await db.execute(
        select(TestResult).where(TestResult.run_id == run_id).order_by(TestResult.id)
    )
    results = result.scalars().all()
    return ApiResponse(data=[ResultResponse.model_validate(r) for r in results])


@router.post("/runs/{run_id}/report", response_model=ApiResponse)
async def report_run(
    run_id: int, body: RunReport, db: AsyncSession = Depends(get_async_session)
):
    """CI/CD 结果上报"""
    run = await db.get(TestRun, run_id)
    if not run:
        return ApiResponse(success=False, error="运行记录不存在")

    passed_count = 0
    failed_count = 0
    skipped_count = 0

    for item in body.results:
        case_result = await db.execute(
            select(TestCase).where(TestCase.function_name == item.function_name)
        )
        case = case_result.scalar_one_or_none()

        test_result = TestResult(
            run_id=run_id,
            case_id=case.id if case else None,
            case_name=item.case_name,
            suite_name=item.suite_name,
            status=item.status,
            duration_ms=item.duration_ms,
            error_message=item.error_message,
            stack_trace=item.stack_trace,
            screenshot_path=item.screenshot_path,
        )
        db.add(test_result)

        if item.status == "passed":
            passed_count += 1
        elif item.status in ("failed", "error"):
            failed_count += 1
        else:
            skipped_count += 1

    run.status = "passed" if failed_count == 0 else "failed"
    run.total = len(body.results)
    run.passed = passed_count
    run.failed = failed_count
    run.skipped = skipped_count
    run.started_at = body.started_at
    run.finished_at = body.finished_at
    run.duration_ms = int((body.finished_at - body.started_at).total_seconds() * 1000)
    run.git_commit = body.git_commit
    run.git_branch = body.git_branch

    await db.commit()
    return ApiResponse(data={"imported": len(body.results)})
