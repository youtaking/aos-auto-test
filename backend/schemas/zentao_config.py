# backend/schemas/zentao_config.py
"""禅道配置 Schema"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ZentaoConfigCreate(BaseModel):
    name: str
    base_url: str
    username: str = ""
    password: str = ""
    product_id: int = 1


class ZentaoConfigUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    product_id: Optional[int] = None


class ZentaoConfigResponse(BaseModel):
    id: int
    name: str
    base_url: str
    username: str
    password: str
    product_id: int = 1
    is_active: int
    created_at: datetime

    model_config = {"from_attributes": True}
