# tests/test_schemas.py
"""Pydantic Schema 单元测试"""
from backend.schemas.common import ApiResponse
from backend.schemas.project import ProjectCreate, ProjectResponse
from backend.schemas.run import RunTrigger, RunReport, RunReportItem


def test_api_response_wrapper():
    """测试 API 响应包装"""
    resp = ApiResponse(success=True, data={"key": "value"})
    assert resp.success is True
    assert resp.data == {"key": "value"}


def test_project_create_schema():
    """测试项目创建 schema"""
    p = ProjectCreate(name="FenixAgent", url="http://localhost:3001")
    assert p.name == "FenixAgent"


def test_run_trigger_schema():
    """测试运行触发 schema"""
    r = RunTrigger(project_id=1, trigger_type="manual")
    assert r.trigger_type == "manual"
    assert r.suite_ids is None


def test_run_report_item():
    """测试 CI 上报单条结果"""
    item = RunReportItem(
        suite_name="login",
        case_name="test_login",
        file_path="tests/suites/test_login.py",
        function_name="test_login",
        status="passed",
        duration_ms=1200,
    )
    assert item.status == "passed"
