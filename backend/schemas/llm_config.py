# backend/schemas/llm_config.py
"""LLM 配置 Schema"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class LLMConfigCreate(BaseModel):
    name: str
    provider: str = "openai"
    base_url: str
    api_key: str
    model: str


class LLMConfigUpdate(BaseModel):
    name: Optional[str] = None
    provider: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None


class LLMConfigResponse(BaseModel):
    id: int
    name: str
    provider: str = "openai"
    base_url: str
    api_key: str
    model: str
    is_active: int
    created_at: datetime

    model_config = {"from_attributes": True}
