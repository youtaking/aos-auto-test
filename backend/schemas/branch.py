# backend/schemas/branch.py
"""分支管理请求/响应模型"""
from pydantic import BaseModel


class BranchCreate(BaseModel):
    branch_name: str


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
