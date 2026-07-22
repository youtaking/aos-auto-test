# backend/schemas/run.py
"""测试运行相关 Schema"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class RunTrigger(BaseModel):
    project_id: int
    suite_ids: Optional[List[int]] = None
    case_ids: Optional[List[int]] = None
    trigger_type: str = "manual"


class RunResponse(BaseModel):
    id: int
    project_id: int
    trigger_type: str
    trigger_user: str
    git_commit: str
    git_branch: str
    status: str
    total: int
    passed: int
    failed: int
    skipped: int
    duration_ms: int
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RunReportItem(BaseModel):
    suite_name: str
    case_name: str
    file_path: str
    function_name: str
    status: str
    duration_ms: int = 0
    error_message: Optional[str] = None
    stack_trace: Optional[str] = None
    screenshot_path: Optional[str] = None


class RunReport(BaseModel):
    project_name: str
    trigger_type: str = "ci"
    git_commit: str = ""
    git_branch: str = ""
    started_at: datetime
    finished_at: datetime
    results: List[RunReportItem]


class ResultResponse(BaseModel):
    id: int
    run_id: int
    case_id: Optional[int] = None
    case_name: str
    suite_name: str
    status: str
    duration_ms: int
    error_message: Optional[str] = None
    stack_trace: Optional[str] = None
    screenshot_path: Optional[str] = None
    retry_count: int
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
