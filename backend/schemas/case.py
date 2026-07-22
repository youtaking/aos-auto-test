# backend/schemas/case.py
"""测试用例相关 Schema"""
from datetime import datetime
from pydantic import BaseModel


class CaseResponse(BaseModel):
    id: int
    suite_id: int
    name: str
    file_path: str
    function_name: str
    tags: str
    priority: str
    timeout: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
