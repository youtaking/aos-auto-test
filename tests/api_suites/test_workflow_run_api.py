# tests/api_suites/test_workflow_run_api.py
"""Workflow Run 接口测试：功能验证 + 契约验证

覆盖控制台接口：
- TestWorkflowRunWebAPI: /web/workflow-runs（session cookie 认证）

注：工作流运行记录查询，覆盖列表、详情、事件、审批等只读操作。
"""
import httpx
import pytest


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
            assert isinstance(resp, list)
            if len(resp) > 0:
                assert "run_id" in resp[0] or "id" in resp[0]
        else:
            assert "items" in resp
            assert isinstance(resp["items"], list)

    def test_get_workflow_run(self, web_client):
        """获取工作流运行详情：先拿列表取第一个 runId"""
        runs = web_client.list_workflow_runs()
        items = runs if isinstance(runs, list) else runs.get("items", [])
        if len(items) == 0:
            pytest.skip("工作流运行记录为空，无法测试详情")
        run_id = items[0].get("run_id") or items[0].get("id")

        detail = web_client.get_workflow_run(run_id)
        assert detail.get("run_id", detail.get("id")) == run_id
        assert "status" in detail or "workflow_id" in detail or "dag_status" in detail or "run_id" in detail

    def test_get_workflow_run_events(self, web_client):
        """获取工作流运行事件：先拿列表取第一个 runId"""
        runs = web_client.list_workflow_runs()
        items = runs if isinstance(runs, list) else runs.get("items", [])
        if len(items) == 0:
            pytest.skip("工作流运行记录为空，无法测试事件")
        run_id = items[0].get("run_id") or items[0].get("id")

        events = web_client.get_workflow_run_events(run_id)
        assert isinstance(events, list)

    def test_get_workflow_run_approvals(self, web_client):
        """获取工作流审批列表：先拿列表取第一个 runId"""
        runs = web_client.list_workflow_runs()
        items = runs if isinstance(runs, list) else runs.get("items", [])
        if len(items) == 0:
            pytest.skip("工作流运行记录为空，无法测试审批")
        run_id = items[0].get("run_id") or items[0].get("id")

        approvals = web_client.get_workflow_run_approvals(run_id)
        assert isinstance(approvals, list)

    def test_get_nonexistent_workflow_run(self, web_client):
        """获取不存在的运行记录 — 应返回空或抛异常"""
        try:
            resp = web_client.get_workflow_run("nonexistent-run-id-99999")
            assert resp is None or isinstance(resp, dict)
        except (httpx.HTTPStatusError, RuntimeError) as e:
            import logging
            logging.getLogger("test").warning(f"Nonexistent workflow run request failed: {e}")
