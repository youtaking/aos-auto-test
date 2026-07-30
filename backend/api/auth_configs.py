# backend/api/auth_configs.py
"""认证配置 API"""
from pathlib import Path
import yaml
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.db.config import get_async_session
from backend.db.models import AuthConfig
from backend.schemas.auth_config import AuthConfigCreate, AuthConfigUpdate, AuthConfigResponse
from backend.schemas.common import ApiResponse

router = APIRouter()

YAML_PATH = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "test_data.yaml"


def _sync_active_to_yaml(config: AuthConfig):
    """将激活的认证配置同步写入 test_data.yaml"""
    if YAML_PATH.exists():
        with open(YAML_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}

    fenix = data.setdefault("fenixagent", {})
    fenix.setdefault("admin", {})
    fenix["admin"]["email"] = config.ui_test_email or ""
    fenix["admin"]["password"] = config.ui_test_password or ""
    fenix["api_email"] = config.api_test_email or ""
    fenix["api_password"] = config.api_test_password or ""
    fenix["api_key"] = config.open_api_key or ""

    YAML_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(YAML_PATH, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


@router.get("/auth-configs", response_model=ApiResponse)
async def list_auth_configs(db: AsyncSession = Depends(get_async_session)):
    """获取认证配置列表"""
    result = await db.execute(select(AuthConfig).order_by(AuthConfig.created_at.desc()))
    configs = result.scalars().all()
    return ApiResponse(data=[AuthConfigResponse.model_validate(c) for c in configs])


@router.post("/auth-configs", response_model=ApiResponse)
async def create_auth_config(body: AuthConfigCreate, db: AsyncSession = Depends(get_async_session)):
    """创建认证配置"""
    config = AuthConfig(
        name=body.name,
        ui_test_email=body.ui_test_email,
        ui_test_password=body.ui_test_password,
        api_test_email=body.api_test_email,
        api_test_password=body.api_test_password,
        open_api_key=body.open_api_key,
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)
    # 如果是唯一配置，自动激活并同步到 yaml
    result = await db.execute(select(AuthConfig))
    all_configs = result.scalars().all()
    if len(all_configs) == 1:
        config.is_active = 1
        await db.commit()
        await db.refresh(config)
        _sync_active_to_yaml(config)
    elif config.is_active:
        _sync_active_to_yaml(config)
    return ApiResponse(data=AuthConfigResponse.model_validate(config))


@router.put("/auth-configs/{config_id}", response_model=ApiResponse)
async def update_auth_config(
    config_id: int, body: AuthConfigUpdate, db: AsyncSession = Depends(get_async_session)
):
    """更新认证配置"""
    config = await db.get(AuthConfig, config_id)
    if not config:
        return ApiResponse(success=False, error="认证配置不存在")
    for field in ["name", "ui_test_email", "ui_test_password", "api_test_email", "api_test_password", "open_api_key"]:
        value = getattr(body, field, None)
        if value is not None:
            setattr(config, field, value)
    await db.commit()
    await db.refresh(config)
    if config.is_active:
        _sync_active_to_yaml(config)
    return ApiResponse(data=AuthConfigResponse.model_validate(config))


@router.delete("/auth-configs/{config_id}", response_model=ApiResponse)
async def delete_auth_config(config_id: int, db: AsyncSession = Depends(get_async_session)):
    """删除认证配置"""
    config = await db.get(AuthConfig, config_id)
    if not config:
        return ApiResponse(success=False, error="认证配置不存在")
    was_active = config.is_active
    await db.delete(config)
    await db.commit()
    # 如果删除的是激活配置，自动激活第一个剩余配置并同步
    if was_active:
        result = await db.execute(select(AuthConfig).order_by(AuthConfig.created_at.desc()))
        remaining = result.scalars().all()
        if remaining:
            remaining[0].is_active = 1
            await db.commit()
            _sync_active_to_yaml(remaining[0])
    return ApiResponse(data={"deleted": True})


@router.post("/auth-configs/{config_id}/activate", response_model=ApiResponse)
async def activate_auth_config(config_id: int, db: AsyncSession = Depends(get_async_session)):
    """激活认证配置（同时取消其他配置的激活状态）"""
    config = await db.get(AuthConfig, config_id)
    if not config:
        return ApiResponse(success=False, error="认证配置不存在")

    # 先全部取消激活
    result = await db.execute(select(AuthConfig))
    for c in result.scalars().all():
        c.is_active = 0

    # 激活目标
    config.is_active = 1
    await db.commit()
    await db.refresh(config)
    _sync_active_to_yaml(config)
    return ApiResponse(data=AuthConfigResponse.model_validate(config))
