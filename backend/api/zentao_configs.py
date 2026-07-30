# backend/api/zentao_configs.py
"""禅道配置 API"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.db.config import get_async_session
from backend.db.models import ZentaoConfig
from backend.schemas.zentao_config import ZentaoConfigCreate, ZentaoConfigUpdate, ZentaoConfigResponse
from backend.schemas.common import ApiResponse

router = APIRouter()


@router.get("/zentao-configs", response_model=ApiResponse)
async def list_zentao_configs(db: AsyncSession = Depends(get_async_session)):
    """获取禅道配置列表"""
    result = await db.execute(select(ZentaoConfig).order_by(ZentaoConfig.created_at.desc()))
    configs = result.scalars().all()
    return ApiResponse(data=[ZentaoConfigResponse.model_validate(c) for c in configs])


@router.post("/zentao-configs", response_model=ApiResponse)
async def create_zentao_config(body: ZentaoConfigCreate, db: AsyncSession = Depends(get_async_session)):
    """创建禅道配置"""
    config = ZentaoConfig(
        name=body.name,
        base_url=body.base_url,
        username=body.username,
        password=body.password,
        product_id=body.product_id,
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)
    result = await db.execute(select(ZentaoConfig))
    if len(result.scalars().all()) == 1:
        config.is_active = 1
        await db.commit()
        await db.refresh(config)
    return ApiResponse(data=ZentaoConfigResponse.model_validate(config))


@router.put("/zentao-configs/{config_id}", response_model=ApiResponse)
async def update_zentao_config(
    config_id: int, body: ZentaoConfigUpdate, db: AsyncSession = Depends(get_async_session)
):
    """更新禅道配置"""
    config = await db.get(ZentaoConfig, config_id)
    if not config:
        return ApiResponse(success=False, error="禅道配置不存在")
    for field in ["name", "base_url", "username", "password", "product_id"]:
        value = getattr(body, field, None)
        if value is not None:
            setattr(config, field, value)
    await db.commit()
    await db.refresh(config)
    return ApiResponse(data=ZentaoConfigResponse.model_validate(config))


@router.delete("/zentao-configs/{config_id}", response_model=ApiResponse)
async def delete_zentao_config(config_id: int, db: AsyncSession = Depends(get_async_session)):
    """删除禅道配置"""
    config = await db.get(ZentaoConfig, config_id)
    if not config:
        return ApiResponse(success=False, error="禅道配置不存在")
    was_active = config.is_active
    await db.delete(config)
    await db.commit()
    if was_active:
        result = await db.execute(select(ZentaoConfig).order_by(ZentaoConfig.created_at.desc()))
        remaining = result.scalars().all()
        if remaining:
            remaining[0].is_active = 1
            await db.commit()
    return ApiResponse(data={"deleted": True})


@router.post("/zentao-configs/{config_id}/activate", response_model=ApiResponse)
async def activate_zentao_config(config_id: int, db: AsyncSession = Depends(get_async_session)):
    """激活禅道配置"""
    config = await db.get(ZentaoConfig, config_id)
    if not config:
        return ApiResponse(success=False, error="禅道配置不存在")
    result = await db.execute(select(ZentaoConfig))
    for c in result.scalars().all():
        c.is_active = 0
    config.is_active = 1
    await db.commit()
    await db.refresh(config)
    return ApiResponse(data=ZentaoConfigResponse.model_validate(config))
