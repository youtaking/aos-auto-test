# tests/test_reporter.py
"""Reporter 单元测试"""
from engine.reporter import AutoTestReporter


def test_reporter_init():
    """测试 Reporter 初始化"""
    reporter = AutoTestReporter(run_id=1, backend_url="http://localhost:8000")
    assert reporter.run_id == 1
    assert reporter.backend_url == "http://localhost:8000"
    assert reporter._results == []
    reporter._client.close()


def test_reporter_push_silently_fails():
    """推送失败不影响执行"""
    reporter = AutoTestReporter(run_id=999, backend_url="http://nonexistent:1234")
    reporter._push("test_event", {"key": "value"})
    reporter._client.close()
