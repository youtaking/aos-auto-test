# tests/test_runner.py
"""测试引擎 Runner 单元测试"""
from engine.runner import TestRunner, RunResult, CaseResult


def test_runner_init():
    """测试 Runner 初始化"""
    runner = TestRunner(test_dir="tests/suites")
    assert runner.test_dir == "tests/suites"


def test_runner_collect_tests():
    """测试用例收集返回 list"""
    runner = TestRunner(test_dir="tests/suites")
    collected = runner.collect_tests()
    assert isinstance(collected, list)


def test_run_result_properties():
    """测试 RunResult 属性计算"""
    result = RunResult()
    result.results = [
        CaseResult("login", "test_a", "f.py", "test_a", "passed", 100),
        CaseResult("login", "test_b", "f.py", "test_b", "failed", 200, "err"),
        CaseResult("chat", "test_c", "f.py", "test_c", "skipped", 0),
    ]
    assert result.total == 3
    assert result.passed == 1
    assert result.failed == 1
    assert result.skipped == 1
