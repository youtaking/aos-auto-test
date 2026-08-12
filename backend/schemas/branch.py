# backend/schemas/branch.py
"""分支管理请求/响应模型"""
from pydantic import BaseModel, Field


class BranchCreate(BaseModel):
    branch_name: str = Field(..., pattern=r'^[a-zA-Z0-9._\-/]+$')


class GenerateRequest(BaseModel):
    test_type: str = "api"


class BranchInfo(BaseModel):
    branch_name: str
    last_commit_sha: str
    status: str
    discovered_at: str | None = None
    updated_at: str | None = None


class PromoteReport(BaseModel):
    new_api_files: list[str]
    new_unit_files: list[str]


class CanGenerateResponse(BaseModel):
    can_generate: bool
    autotest_dir: str | None = None
