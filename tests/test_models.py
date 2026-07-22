# tests/test_models.py
"""数据库模型单元测试"""
from backend.db.models import Project, TestSuite, TestCase, TestRun, TestResult


def test_project_creation():
    """测试 Project 模型创建"""
    project = Project(name="FenixAgent", url="http://localhost:3001")
    assert project.name == "FenixAgent"
    assert project.url == "http://localhost:3001"


def test_test_suite_creation():
    """测试 TestSuite 模型创建"""
    suite = TestSuite(name="login", project_id=1)
    assert suite.name == "login"
    assert suite.project_id == 1


def test_test_case_creation():
    """测试 TestCase 模型创建"""
    case = TestCase(
        name="test_login_success",
        suite_id=1,
        file_path="tests/suites/test_login.py",
        function_name="test_login_success",
        priority="P0",
    )
    assert case.priority == "P0"


def test_test_run_creation():
    """测试 TestRun 模型创建"""
    run = TestRun(project_id=1, trigger_type="manual", status="pending")
    assert run.trigger_type == "manual"
    assert run.status == "pending"


def test_test_result_creation():
    """测试 TestResult 模型创建"""
    result = TestResult(
        run_id=1, case_id=1, status="passed", duration_ms=3200
    )
    assert result.status == "passed"
    assert result.duration_ms == 3200
