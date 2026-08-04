# backend/api/ci.py
"""CI/CD 触发 + Pipeline 管理 + CI 配置 API"""
import asyncio
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, BackgroundTasks, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.db.config import get_async_session, async_session
from backend.db.models import PRPipeline, CIConfig, TestRun, EnvironmentSlot
from backend.schemas.ci import (
    PRTriggerRequest, PRUpdateRequest, PipelineResponse,
    RerunRequest, CIConfigResponse, CIConfigUpdate,
)
from backend.schemas.common import ApiResponse
from backend.services import slot_manager
from backend.services.pipeline_runner import (
    start_pipeline, rerun_pipeline, destroy_pipeline,
    cancel_pipeline, handle_pr_update,
)

router = APIRouter()


async def _verify_token(authorization: str = Header(default="")):
    """验证 Bearer Token"""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="缺少认证 Token")
    token = authorization[7:]
    async with async_session() as db:
        config = await slot_manager.get_ci_config(db)
        if config.auth_token and config.auth_token != token:
            raise HTTPException(status_code=403, detail="认证 Token 无效")


@router.post("/ci/pr-trigger", response_model=ApiResponse)
async def pr_trigger(
    body: PRTriggerRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_session),
    authorization: str = Header(default=""),
):
    """接收 GitHub Actions 的 PR 触发请求"""
    # 验证 Token
    await _verify_token(authorization)

    # 幂等检查：同一 PR 同一 commit 不重复创建
    existing = await db.execute(
        select(PRPipeline).where(
            PRPipeline.pr_id == body.pr_id,
            PRPipeline.commit_sha == body.commit_sha,
        )
    )
    if existing.scalar_one_or_none():
        return ApiResponse(data={"message": "同一 PR 同一 commit 已存在，跳过"})

    # 创建 Pipeline 记录
    pipeline = PRPipeline(
        pr_id=body.pr_id,
        pr_title=body.pr_title,
        commit_sha=body.commit_sha,
        branch=body.branch,
        repo_url=body.repo_url,
        author=body.author,
    )
    db.add(pipeline)
    await db.commit()
    await db.refresh(pipeline)

    # 解析 test_config
    test_config = None
    if body.test_config:
        test_config = body.test_config.model_dump(exclude_none=True)

    # 异步启动流水线
    background_tasks.add_task(start_pipeline, pipeline.id, test_config)

    return ApiResponse(data={
        "pipeline_id": pipeline.id,
        "status": "pending",
        "message": f"PR #{body.pr_id} 已接收，正在处理",
    })


@router.post("/ci/pr-update", response_model=ApiResponse)
async def pr_update(
    body: PRUpdateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_session),
    authorization: str = Header(default=""),
):
    """同一 PR 新 commit 更新"""
    await _verify_token(authorization)
    background_tasks.add_task(handle_pr_update, body.pr_id, body.commit_sha)
    return ApiResponse(data={"message": f"PR #{body.pr_id} 更新已接收"})


@router.get("/pipelines", response_model=ApiResponse)
async def list_pipelines(
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_async_session),
):
    """获取 Pipeline 列表"""
    query = select(PRPipeline).order_by(PRPipeline.created_at.desc())
    if status:
        query = query.where(PRPipeline.status == status)
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    pipelines = result.scalars().all()

    items = []
    for p in pipelines:
        slot = await db.get(EnvironmentSlot, p.slot_id) if p.slot_id else None
        run = await db.get(TestRun, p.run_id) if p.run_id else None

        item = PipelineResponse(
            id=p.id, pr_id=p.pr_id, pr_title=p.pr_title,
            commit_sha=p.commit_sha, branch=p.branch,
            repo_url=p.repo_url, author=p.author,
            slot_id=p.slot_id,
            slot_name=slot.name if slot else None,
            status=p.status, docker_image=p.docker_image,
            rcs_url=p.rcs_url, run_id=p.run_id,
            queue_position=p.queue_position,
            timeout_at=p.timeout_at,
            environment_info=p.environment_info,
            error_message=p.error_message,
            created_at=p.created_at, updated_at=p.updated_at,
            test_total=run.total if run else 0,
            test_passed=run.passed if run else 0,
            test_failed=run.failed if run else 0,
            test_skipped=run.skipped if run else 0,
        )
        items.append(item)

    return ApiResponse(data=[i.model_dump() for i in items])


@router.get("/pipelines/{pipeline_id}", response_model=ApiResponse)
async def get_pipeline(pipeline_id: int, db: AsyncSession = Depends(get_async_session)):
    """获取单个 Pipeline 详情"""
    p = await db.get(PRPipeline, pipeline_id)
    if not p:
        return ApiResponse(success=False, error="Pipeline 不存在")

    slot = await db.get(EnvironmentSlot, p.slot_id) if p.slot_id else None
    run = await db.get(TestRun, p.run_id) if p.run_id else None

    return ApiResponse(data=PipelineResponse(
        id=p.id, pr_id=p.pr_id, pr_title=p.pr_title,
        commit_sha=p.commit_sha, branch=p.branch,
        repo_url=p.repo_url, author=p.author,
        slot_id=p.slot_id,
        slot_name=slot.name if slot else None,
        status=p.status, docker_image=p.docker_image,
        rcs_url=p.rcs_url, run_id=p.run_id,
        queue_position=p.queue_position,
        timeout_at=p.timeout_at,
        environment_info=p.environment_info,
        error_message=p.error_message,
        created_at=p.created_at, updated_at=p.updated_at,
        test_total=run.total if run else 0,
        test_passed=run.passed if run else 0,
        test_failed=run.failed if run else 0,
        test_skipped=run.skipped if run else 0,
    ).model_dump())


@router.post("/pipelines/{pipeline_id}/rerun", response_model=ApiResponse)
async def rerun(pipeline_id: int, body: RerunRequest = None, background_tasks: BackgroundTasks = None):
    """重跑测试"""
    case_ids = body.case_ids if body else None
    background_tasks.add_task(rerun_pipeline, pipeline_id, case_ids)
    return ApiResponse(data={"message": "重跑已触发"})


@router.delete("/pipelines/{pipeline_id}", response_model=ApiResponse)
async def destroy(pipeline_id: int, background_tasks: BackgroundTasks):
    """手动销毁环境"""
    background_tasks.add_task(destroy_pipeline, pipeline_id)
    return ApiResponse(data={"message": "销毁已触发"})


@router.post("/pipelines/{pipeline_id}/cancel", response_model=ApiResponse)
async def cancel(pipeline_id: int, background_tasks: BackgroundTasks):
    """取消 Pipeline"""
    background_tasks.add_task(cancel_pipeline, pipeline_id)
    return ApiResponse(data={"message": "取消已触发"})


@router.get("/ci/config", response_model=ApiResponse)
async def get_ci_config(db: AsyncSession = Depends(get_async_session)):
    """获取 CI 配置"""
    config = await slot_manager.get_ci_config(db)
    return ApiResponse(data=CIConfigResponse.model_validate(config).model_dump())


@router.put("/ci/config", response_model=ApiResponse)
async def update_ci_config(
    body: CIConfigUpdate,
    db: AsyncSession = Depends(get_async_session),
):
    """更新 CI 配置"""
    config = await slot_manager.get_ci_config(db)
    for field in ["timeout_minutes", "max_queue_size", "auth_token",
                   "run_api_tests", "run_e2e_p0", "run_e2e_all"]:
        value = getattr(body, field, None)
        if value is not None:
            setattr(config, field, value)
    await db.commit()
    await db.refresh(config)
    return ApiResponse(data=CIConfigResponse.model_validate(config).model_dump())


@router.post("/ci/config/regenerate-token", response_model=ApiResponse)
async def regenerate_token(db: AsyncSession = Depends(get_async_session)):
    """重新生成认证 Token"""
    config = await slot_manager.get_ci_config(db)
    config.auth_token = secrets.token_urlsafe(32)
    await db.commit()
    await db.refresh(config)
    return ApiResponse(data={"token": config.auth_token})
