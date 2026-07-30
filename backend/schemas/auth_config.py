# backend/schemas/auth_config.py
"""认证配置 Schema"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class AuthConfigCreate(BaseModel):
    name: str
    ui_test_email: str = ""
    ui_test_password: str = ""
    api_test_email: str = ""
    api_test_password: str = ""
    open_api_key: str = ""


class AuthConfigUpdate(BaseModel):
    name: Optional[str] = None
    ui_test_email: Optional[str] = None
    ui_test_password: Optional[str] = None
    api_test_email: Optional[str] = None
    api_test_password: Optional[str] = None
    open_api_key: Optional[str] = None


class AuthConfigResponse(BaseModel):
    id: int
    name: str
    ui_test_email: str = ""
    ui_test_password: str = ""
    api_test_email: str = ""
    api_test_password: str = ""
    open_api_key: str = ""
    is_active: int
    created_at: datetime

    model_config = {"from_attributes": True}
