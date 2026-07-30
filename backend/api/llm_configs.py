# backend/api/llm_configs.py
"""LLM 配置 API"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.db.config import get_async_session
from backend.db.models import LLMConfig
from backend.schemas.llm_config import LLMConfigCreate, LLMConfigUpdate, LLMConfigResponse
from backend.schemas.common import ApiResponse

router = APIRouter()


@router.get("/llm-configs", response_model=ApiResponse)
async def list_llm_configs(db: AsyncSession = Depends(get_async_session)):
    """获取 LLM 配置列表"""
    result = await db.execute(select(LLMConfig).order_by(LLMConfig.created_at.desc()))
    configs = result.scalars().all()
    return ApiResponse(data=[LLMConfigResponse.model_validate(c) for c in configs])


@router.post("/llm-configs", response_model=ApiResponse)
async def create_llm_config(body: LLMConfigCreate, db: AsyncSession = Depends(get_async_session)):
    """创建 LLM 配置"""
    config = LLMConfig(
        name=body.name,
        provider=body.provider,
        base_url=body.base_url,
        api_key=body.api_key,
        model=body.model,
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)
    # 如果是唯一配置，自动激活
    result = await db.execute(select(LLMConfig))
    if len(result.scalars().all()) == 1:
        config.is_active = 1
        await db.commit()
        await db.refresh(config)
    return ApiResponse(data=LLMConfigResponse.model_validate(config))


@router.put("/llm-configs/{config_id}", response_model=ApiResponse)
async def update_llm_config(
    config_id: int, body: LLMConfigUpdate, db: AsyncSession = Depends(get_async_session)
):
    """更新 LLM 配置"""
    config = await db.get(LLMConfig, config_id)
    if not config:
        return ApiResponse(success=False, error="LLM 配置不存在")
    for field in ["name", "provider", "base_url", "api_key", "model"]:
        value = getattr(body, field, None)
        if value is not None:
            setattr(config, field, value)
    await db.commit()
    await db.refresh(config)
    return ApiResponse(data=LLMConfigResponse.model_validate(config))


@router.delete("/llm-configs/{config_id}", response_model=ApiResponse)
async def delete_llm_config(config_id: int, db: AsyncSession = Depends(get_async_session)):
    """删除 LLM 配置"""
    config = await db.get(LLMConfig, config_id)
    if not config:
        return ApiResponse(success=False, error="LLM 配置不存在")
    was_active = config.is_active
    await db.delete(config)
    await db.commit()
    if was_active:
        result = await db.execute(select(LLMConfig).order_by(LLMConfig.created_at.desc()))
        remaining = result.scalars().all()
        if remaining:
            remaining[0].is_active = 1
            await db.commit()
    return ApiResponse(data={"deleted": True})


@router.post("/llm-configs/{config_id}/activate", response_model=ApiResponse)
async def activate_llm_config(config_id: int, db: AsyncSession = Depends(get_async_session)):
    """激活 LLM 配置"""
    config = await db.get(LLMConfig, config_id)
    if not config:
        return ApiResponse(success=False, error="LLM 配置不存在")
    result = await db.execute(select(LLMConfig))
    for c in result.scalars().all():
        c.is_active = 0
    config.is_active = 1
    await db.commit()
    await db.refresh(config)
    return ApiResponse(data=LLMConfigResponse.model_validate(config))
