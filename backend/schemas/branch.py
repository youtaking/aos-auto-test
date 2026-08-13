# backend/schemas/branch.py
"""分支管理请求/响应模型"""
from pydantic import BaseModel, Field, field_validator


class BranchCreate(BaseModel):
    branch_name: str = Field(..., pattern=r'^[a-zA-Z0-9._\-/]+$')

    @field_validator('branch_name')
    @classmethod
    def no_dotdot(cls, v: str) -> str:
        if '..' in v:
            raise ValueError('branch_name must not contain ..')
        return v


class BranchAction(BaseModel):
    branch_name: str


class GenerateRequest(BaseModel):
    branch_name: str
    test_type: str = "api"


class BranchInfo(BaseModel):
    branch_name: str
    last_commit_sha: str
    pr_number: int | None = None
    dev_status: str = "open"
    case_status: str = "pending"
    discovered_at: str | None = None
    updated_at: str | None = None
    has_dir: bool = False


class PromoteReport(BaseModel):
    new_api_files: list[str]
    new_unit_files: list[str]


class CanGenerateResponse(BaseModel):
    can_generate: bool
    autotest_dir: str | None = None
