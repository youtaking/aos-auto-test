# backend/schemas/project.py
"""项目相关 Schema"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str
    url: str
    description: str = ""


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    url: str
    description: str
    is_active: int
    created_at: datetime

    model_config = {"from_attributes": True}
