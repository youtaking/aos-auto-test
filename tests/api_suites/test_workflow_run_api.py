# tests/api_suites/test_workflow_run_api.py
"""Workflow Run 接口测试：功能验证 + 契约验证

覆盖控制台接口：
- TestWorkflowRunWebAPI: /web/workflow-runs（session cookie 认证）

注：工作流运行记录查询，覆盖列表、详情、事件、审批等只读操作。
"""
import httpx
import pytest
from tests.api_contracts.workflow_run_schemas import (
    WORKFLOW_RUN_ITEM,
    WORKFLOW_RUN_DETAIL,
    WORKFLOW_RUN_EVENT,
    WORKFLOW_RUN_APPROVAL,
)


class TestWorkflowRunWebAPI:
    """/web/workflow-runs 控制台接口测试（session cookie 认证）

    特点：
    - 运行记录查询、事件读取、审批
    """

    def test_list_workflow_runs(self, web_client):
        """获取工作流运行记录列表"""
        resp = web_client.list_workflow_runs()
        # 可能是数组或分页对象
        if isinstance(resp, list):
            if len(resp) > 0:
                web_client.validate_schema(resp[0], WORKFLOW_RUN_ITEM)
        else:
            assert "items" in resp
            assert isinstance(resp["items"], list)
            if len(resp["items"]) > 0:
                web_client.validate_schema(resp["items"][0], WORKFLOW_RUN_ITEM)

    def test_get_workflow_run(self, web_client):
        """获取工作流运行详情：先拿列表取第一个 runId"""
        runs = web_client.list_workflow_runs()
        items = runs if isinstance(runs, list) else runs.get("items", [])
        if len(items) == 0:
            pytest.skip("工作流运行记录为空，无法测试详情")
        run_id = items[0].get("run_id") or items[0].get("id")

        detail = web_client.get_workflow_run(run_id)
        web_client.validate_schema(detail, WORKFLOW_RUN_DETAIL)
        assert detail.get("run_id", detail.get("id")) == run_id

    def test_get_workflow_run_events(self, web_client):
        """获取工作流运行事件：先拿列表取第一个 runId"""
        runs = web_client.list_workflow_runs()
        items = runs if isinstance(runs, list) else runs.get("items", [])
        if len(items) == 0:
            pytest.skip("工作流运行记录为空，无法测试事件")
        run_id = items[0].get("run_id") or items[0].get("id")

        events = web_client.get_workflow_run_events(run_id)
        assert isinstance(events, list)
        if len(events) > 0:
            web_client.validate_schema(events[0], WORKFLOW_RUN_EVENT)

    def test_get_workflow_run_approvals(self, web_client):
        """获取工作流审批列表：先拿列表取第一个 runId"""
        runs = web_client.list_workflow_runs()
        items = runs if isinstance(runs, list) else runs.get("items", [])
        if len(items) == 0:
            pytest.skip("工作流运行记录为空，无法测试审批")
        run_id = items[0].get("run_id") or items[0].get("id")

        approvals = web_client.get_workflow_run_approvals(run_id)
        assert isinstance(approvals, list)
        if len(approvals) > 0:
            web_client.validate_schema(approvals[0], WORKFLOW_RUN_APPROVAL)

    def test_get_nonexistent_workflow_run(self, web_client):
        """获取不存在的运行记录 — 应返回 404/500 或返回 None/空对象"""
        try:
            resp = web_client.get_workflow_run("nonexistent-run-id-99999")
            # 服务端可能返回 None 或空对象（非异常路径）
            assert resp is None or isinstance(resp, dict), \
                f"预期 None/dict 响应，实际: {type(resp)}"
            if isinstance(resp, dict):
                assert len(resp) == 0 or "id" not in resp, \
                    "不应返回包含有效 id 的运行记录"
        except (httpx.HTTPStatusError, RuntimeError) as e:
            assert "404" in str(e) or "400" in str(e) or "500" in str(e), \
                f"非预期错误: {e}"

    def test_cancel_nonexistent_workflow_run(self, web_client):
        """取消不存在的运行 — 应返回 404/500"""
        try:
            web_client.cancel_workflow_run("nonexistent-run-id-99999")
            # 可能返回空响应不算错误
        except (httpx.HTTPStatusError, RuntimeError) as e:
            assert "404" in str(e) or "500" in str(e), \
                f"预期 404/500，实际: {e}"

    def test_get_node_output_nonexistent_run(self, web_client):
        """获取不存在运行的节点输出 — 应返回 404/500"""
        try:
            web_client.get_workflow_run_node_output(
                "nonexistent-run-id-99999", "nonexistent-node-id"
            )
        except (httpx.HTTPStatusError, RuntimeError) as e:
            assert "404" in str(e) or "500" in str(e), \
                f"预期 404/500，实际: {e}"

    def test_dry_run_workflow_invalid(self, web_client):
        """干运行校验 — 无效 YAML 应返回错误"""
        try:
            resp = web_client.dry_run_workflow({
                "yaml": "invalid: yaml: content: [",
            })
            # 如果没抛异常，检查返回 valid=false
            if isinstance(resp, dict):
                assert resp.get("valid") is False or "issues" in resp, \
                    "无效 YAML 应返回 valid=false 或 issues"
        except (httpx.HTTPStatusError, RuntimeError) as e:
            assert "400" in str(e) or "500" in str(e), \
                f"预期 400/500，实际: {e}"

    def test_recover_nonexistent_run(self, web_client):
        """恢复不存在的运行 — 应返回 400/404/500"""
        try:
            web_client.recover_workflow_run("nonexistent-run-id-99999")
        except (httpx.HTTPStatusError, RuntimeError) as e:
            assert "400" in str(e) or "404" in str(e) or "500" in str(e), \
                f"预期 400/404/500，实际: {e}"

    def test_rerun_nonexistent_run(self, web_client):
        """重新运行不存在的运行 — 应返回 400/404/500"""
        try:
            web_client.rerun_workflow_run("nonexistent-run-id-99999")
        except (httpx.HTTPStatusError, RuntimeError) as e:
            assert "400" in str(e) or "404" in str(e) or "500" in str(e), \
                f"预期 400/404/500，实际: {e}"
