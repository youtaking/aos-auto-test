# backend/schemas/ci.py
"""Pipeline / CI 配置 Pydantic Schema"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class TestConfigOverride(BaseModel):
    """PR 触发时的测试配置覆盖"""
    run_api_tests: Optional[bool] = None
    run_e2e_p0: Optional[bool] = None
    run_e2e_all: Optional[bool] = None
    custom_case_ids: Optional[List[int]] = None


class PRTriggerRequest(BaseModel):
    """PR 触发请求"""
    pr_id: int
    pr_title: str = ""
    commit_sha: str
    branch: str = ""
    repo_url: str = ""
    author: str = ""
    test_config: Optional[TestConfigOverride] = None


class PRUpdateRequest(BaseModel):
    """同一 PR 新 commit 更新请求"""
    pr_id: int
    commit_sha: str


class RerunRequest(BaseModel):
    """重跑测试请求"""
    case_ids: Optional[List[int]] = None


class PipelineResponse(BaseModel):
    """Pipeline 响应"""
    id: int
    pr_id: int
    pr_title: str
    commit_sha: str
    branch: str
    repo_url: str
    author: str
    slot_id: Optional[int] = None
    slot_name: Optional[str] = None
    status: str
    docker_image: str
    rcs_url: str
    run_id: Optional[int] = None
    queue_position: int
    timeout_at: Optional[datetime] = None
    environment_info: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    # 关联的测试统计（可选）
    test_total: int = 0
    test_passed: int = 0
    test_failed: int = 0
    test_skipped: int = 0

    model_config = {"from_attributes": True}


class CIConfigResponse(BaseModel):
    """CI 配置响应"""
    id: int
    timeout_minutes: int
    max_queue_size: int
    auth_token: str
    run_api_tests: int
    run_e2e_p0: int
    run_e2e_all: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CIConfigUpdate(BaseModel):
    """CI 配置更新"""
    timeout_minutes: Optional[int] = None
    max_queue_size: Optional[int] = None
    auth_token: Optional[str] = None
    run_api_tests: Optional[int] = None
    run_e2e_p0: Optional[int] = None
    run_e2e_all: Optional[int] = None
