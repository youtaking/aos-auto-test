# backend/schemas/suite.py
"""测试套件相关 Schema"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class SuiteCreate(BaseModel):
    name: str
    description: str = ""
    tags: str = ""


class SuiteUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[str] = None


class SuiteResponse(BaseModel):
    id: int
    project_id: int
    name: str
    description: str
    tags: str
    created_at: datetime

    model_config = {"from_attributes": True}
