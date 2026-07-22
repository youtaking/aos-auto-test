# backend/schemas/common.py
"""通用 API 响应包装"""
from typing import Any, Optional
from pydantic import BaseModel


class ApiResponse(BaseModel):
    success: bool = True
    data: Any = None
    error: Optional[str] = None
