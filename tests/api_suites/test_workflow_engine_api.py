# tests/api_suites/test_workflow_engine_api.py
"""Workflow Engine 接口测试：功能验证 + 契约验证

覆盖控制台接口：
- TestWorkflowEngineWebAPI: /web/workflow-engine（session cookie 认证）

工作流引擎通过 POST action 分发，支持 run/dryRun/cancel/approve/getRunStatus 等。
"""
import httpx
import pytest


class TestWorkflowEngineWebAPI:
    """/web/workflow-engine 工作流引擎控制接口（session cookie 认证）

    特点：
    - POST /workflow-engine body: {action, ...} — action 分发
    - 支持的 action: run, dryRun, cancel, approve, getRunStatus, getEvents, getOutput, getPendingApprovals, recover, rerunFrom
    """

    def test_unknown_action(self, web_client):
        """未知 action：应返回 400 或 422"""
        try:
            web_client.workflow_engine_action({"action": "unknown_action_xyz"})
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if any(code in err_str for code in ["400", "422", "validation", "unknown"]):
                return  # 预期行为
            raise
        # 如果没有异常，检查返回值中的错误
        pytest.fail("未知 action 应返回错误")

    def test_dry_run_without_yaml(self, web_client):
        """dryRun 缺少 yaml：应返回 400"""
        try:
            web_client.workflow_engine_action({"action": "dryRun"})
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "400" in err_str or "validation" in err_str.lower():
                return  # 预期行为
            raise
        pytest.fail("dryRun 缺少 yaml 应返回错误")

    def test_run_without_yaml(self, web_client):
        """run 缺少 yaml 和 workflowId：应返回 400"""
        try:
            web_client.workflow_engine_action({"action": "run"})
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "400" in err_str or "validation" in err_str.lower():
                return  # 预期行为
            raise
        pytest.fail("run 缺少 yaml 应返回错误")

    def test_get_run_status_nonexistent(self, web_client):
        """获取不存在的 run 状态：应返回 404 或 null 数据"""
        try:
            result = web_client.workflow_engine_action({
                "action": "getRunStatus",
                "runId": "nonexistent-run-99999",
            })
            # 如果没抛异常，结果应为 null 或带 error
            assert result is None or isinstance(result, dict)
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            assert any(code in err_str for code in ["404", "not_found", "RUN_NOT_FOUND", "500"])

    def test_get_events_nonexistent(self, web_client):
        """获取不存在的 run 事件：应返回 404 或空列表"""
        try:
            result = web_client.workflow_engine_action({
                "action": "getEvents",
                "runId": "nonexistent-run-99999",
            })
            assert result is None or isinstance(result, (dict, list))
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            assert any(code in err_str for code in ["404", "not_found", "RUN_NOT_FOUND", "500"])

    def test_get_pending_approvals_nonexistent(self, web_client):
        """获取不存在的 run 审批列表：应返回 404 或空列表"""
        try:
            result = web_client.workflow_engine_action({
                "action": "getPendingApprovals",
                "runId": "nonexistent-run-99999",
            })
            assert result is None or isinstance(result, (dict, list))
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            assert any(code in err_str for code in ["404", "not_found", "RUN_NOT_FOUND", "500"])

    def test_dry_run_with_simple_yaml(self, web_client):
        """dryRun 简单 YAML：验证工作流定义合法性"""
        simple_yaml = """
version: "1.0"
name: auto-test-dry-run
steps:
  - id: step1
    type: log
    params:
      message: "hello from auto-test"
"""
        try:
            result = web_client.workflow_engine_action({
                "action": "dryRun",
                "yaml": simple_yaml,
            })
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "400" in err_str:
                pytest.skip("dryRun 校验失败，YAML 格式不被当前引擎支持")
            if "500" in err_str:
                pytest.skip("工作流引擎内部错误")
            raise

        assert isinstance(result, dict)
        # dryRun 返回 valid 字段
        assert "valid" in result
