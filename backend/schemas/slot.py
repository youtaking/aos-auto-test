# backend/schemas/slot.py
"""Slot Pydantic Schema"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class SlotResponse(BaseModel):
    """Slot 响应"""
    id: int
    name: str
    rcs_port: int
    postgres_port: int
    litellm_port: int
    status: str
    # 当前关联的 Pipeline 信息
    pipeline_id: Optional[int] = None
    pipeline_pr_id: Optional[int] = None
    pipeline_status: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SlotUpdate(BaseModel):
    """Slot 更新"""
    name: Optional[str] = None
    rcs_port: Optional[int] = None
    postgres_port: Optional[int] = None
    litellm_port: Optional[int] = None
    status: Optional[str] = None
