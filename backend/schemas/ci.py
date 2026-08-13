# backend/schemas/ci.py
"""Pipeline / CI 配置 Pydantic Schema"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class BuildInfo(BaseModel):
    """Jenkins 构建信息"""
    jenkins_url: str = ""
    build_number: int = 0
    docker_image: str = ""
    rcs_port: int = 0
    pg_port: int = 0
    litellm_port: int = 0


class CreatePipelineRequest(BaseModel):
    """Jenkins 创建 Pipeline 记录"""
    pr_id: Optional[int] = None  # staging 无 PR
    pr_title: str = ""
    commit_sha: str
    branch: str = ""
    repo_url: str = ""
    author: str = ""
    target_url: str = ""
    docker_image: str = ""
    build_info: Optional[BuildInfo] = None


class UpdatePipelineStatusRequest(BaseModel):
    """更新 Pipeline 状态"""
    status: str
    error_message: Optional[str] = None


class PipelineResponse(BaseModel):
    """Pipeline 响应"""
    id: int
    pr_id: Optional[int] = None  # staging 无 PR
    pr_title: str
    commit_sha: str
    branch: str
    repo_url: str
    author: str
    status: str
    docker_image: str
    target_url: str = ""
    rcs_url: str
    run_id: Optional[int] = None
    build_info: Optional[dict] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
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
    collection_ids: Optional[List[int]] = None
    staging_collection_ids: Optional[List[int]] = None  # Staging 测试集 ID 数组
    branch_e2e_collection_ids: Optional[List[int]] = None  # PR 分支 E2E 测试集 ID 数组
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
    collection_ids: Optional[List[int]] = None
    staging_collection_ids: Optional[List[int]] = None  # Staging 测试集 ID 数组
    branch_e2e_collection_ids: Optional[List[int]] = None  # PR 分支 E2E 测试集 ID 数组
