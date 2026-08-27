# tests/api_suites/test_workflow_api.py
"""Workflow 接口测试：功能验证 + 契约验证

覆盖对外 OpenAPI：
- TestWorkflowOpenAPI: /api/workflows（API Key 认证）

接口清单：
- POST /api/workflows/:workflowId/execute → 执行工作流
"""
import httpx
import pytest


class TestWorkflowOpenAPI:
    """/api/workflows 对外 OpenAPI 测试（API Key 认证）

    特点：
    - POST /api/workflows/:workflowId/execute 执行工作流
    - 支持同步/异步模式
    - 响应可能包含 output 或 runId
    """

    @pytest.mark.xfail(reason="应用 Bug：执行不存在 workflow 返回 500 而非 404（源码应 404，已确认）", strict=True)
    def test_execute_workflow_not_found(self, api_client, _openapi_access):
        """执行不存在的 workflow：契约应返回 404（当前 500，应用 Bug）"""

        with pytest.raises(httpx.HTTPStatusError, match=r"404"):
            api_client.execute_workflow("nonexistent-workflow-id-99999", {
                "inputs": {},
            })

    @pytest.mark.xfail(reason="应用 Bug：执行不存在 workflow 返回 500 而非 404（源码应 404，已确认）", strict=True)
    def test_execute_workflow_invalid_inputs(self, api_client, _openapi_access):
        """执行不存在的 workflow 带错误 inputs：契约应返回 404（当前 500，应用 Bug）"""

        with pytest.raises(httpx.HTTPStatusError, match=r"404"):
            api_client.execute_workflow("nonexistent-workflow-id-99999", {
                "inputs": {"invalid_key": "invalid_value"},
                "mode": "sync",
            })

    @pytest.mark.xfail(reason="应用 Bug：执行不存在 workflow 返回 500 而非 404（源码应 404，已确认）", strict=True)
    def test_execute_workflow_empty_body(self, api_client, _openapi_access):
        """执行 workflow 带空 body：契约应返回 404（当前 500，应用 Bug）"""

        with pytest.raises(httpx.HTTPStatusError, match=r"404"):
            api_client.execute_workflow("fake-workflow-id", {})

    def test_execute_real_workflow_invalid_inputs(self, api_client, web_client, _openapi_access):
        """用真实 workflow ID + 错误 inputs 执行：应返回错误或服务端容错处理"""
        # 通过 web 接口获取一个真实的工作流定义 ID
        try:
            wf_defs = web_client.list_workflow_defs()
        except Exception:
            pytest.skip("无法获取工作流定义列表")
        if len(wf_defs) == 0:
            pytest.skip("工作流定义列表为空，无法测试真实执行")
        real_wf_id = wf_defs[0]["id"]

        # 用错误的 inputs 执行真实 workflow - 可能抛异常或返回错误
        try:
            resp = api_client.execute_workflow(real_wf_id, {
                "inputs": {"__invalid_key__": "__invalid_value__"},
                "mode": "sync",
            })
            # 如果没抛异常，验证响应中至少有某种结构
            assert isinstance(resp, dict), f"响应应为 dict，实际为 {type(resp)}"
        except httpx.HTTPStatusError as e:
            # 抛异常也是预期行为，验证状态码（400/404/422 为客户端错误）
            assert e.response.status_code in (400, 404, 422), \
                f"意外状态码: {e.response.status_code}"
