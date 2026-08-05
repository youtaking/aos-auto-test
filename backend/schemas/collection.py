# backend/schemas/collection.py
"""用例集 Schema"""
from pydantic import BaseModel, ConfigDict
from datetime import datetime


class CollectionCreate(BaseModel):
    name: str
    description: str = ""
    case_ids: list[int] = []


class CollectionUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    case_ids: list[int] | None = None


class CollectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    name: str
    description: str
    case_ids: list[int]
    created_at: datetime
    updated_at: datetime
