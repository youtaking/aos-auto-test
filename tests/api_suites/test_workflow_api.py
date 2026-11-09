# tests/api_suites/test_workflow_api.py
"""Workflow 接口测试：功能验证 + 契约验证

覆盖对外 OpenAPI：
- TestWorkflowOpenAPI: /api/v1/workflows（API Key 认证）

接口清单：
- POST /api/v1/workflows/:workflowId/execute → 执行工作流
"""
import httpx
import pytest
from tests.api_contracts.openapi_extra_schemas import API_WORKFLOW_EXECUTE_RESPONSE


class TestWorkflowOpenAPI:
    """/api/v1/workflows 对外 OpenAPI 测试（API Key 认证）

    特点：
    - POST /api/v1/workflows/:workflowId/execute 执行工作流
    - body: {inputs?, mode: sync|async, version?, timeout?}
    - 响应为 {success, data} 信封，client 已解包为 data
    - 不存在 workflow → 404 NOT_FOUND；inputs 不合法 → 422 INVALID_INPUTS
    """

    @pytest.mark.p2
    def test_execute_workflow_not_found(self, api_client, _openapi_access):
        """执行不存在的 workflow：返回 404 + NOT_FOUND"""

        with pytest.raises(httpx.HTTPStatusError) as caught:
            api_client.execute_workflow("nonexistent-workflow-id-99999", {
                "inputs": {},
            })
        assert caught.value.response.status_code == 404
        body = caught.value.response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "NOT_FOUND"

    @pytest.mark.p2
    def test_execute_workflow_invalid_inputs(self, api_client, _openapi_access):
        """执行不存在的 workflow 带错误 inputs：仍应先返回 404 NOT_FOUND"""

        with pytest.raises(httpx.HTTPStatusError) as caught:
            api_client.execute_workflow("nonexistent-workflow-id-99999", {
                "inputs": {"invalid_key": "invalid_value"},
                "mode": "sync",
            })
        assert caught.value.response.status_code == 404
        body = caught.value.response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "NOT_FOUND"

    @pytest.mark.p2
    def test_execute_workflow_empty_body(self, api_client, _openapi_access):
        """执行 workflow 带空 body：mode/timeout 有默认值，仍返回 404 NOT_FOUND"""

        with pytest.raises(httpx.HTTPStatusError) as caught:
            api_client.execute_workflow("fake-workflow-id", {})
        assert caught.value.response.status_code == 404
        body = caught.value.response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "NOT_FOUND"

    @pytest.mark.p2
    def test_execute_workflow_invalid_mode(self, api_client, _openapi_access):
        """执行 workflow 使用非法 mode：返回 422 VALIDATION_ERROR"""
        try:
            api_client.execute_workflow("fake-workflow-id", {"mode": "invalid-mode"})
        except httpx.HTTPStatusError as e:
            assert e.response.status_code == 422, f"期望 422，实际 {e.response.status_code}"
            body = e.response.json()
            assert body["success"] is False
            assert body["error"]["code"] == "VALIDATION_ERROR"
        else:
            pytest.fail("非法 mode 应被 schema 拒绝")

    @pytest.mark.p2
    def test_execute_real_workflow_invalid_inputs(self, api_client, web_client, _openapi_access):
        """用真实 workflow ID + 错误 inputs 执行：成功或返回 404/422 客户端错误"""
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
            # 如果没抛异常，验证响应结构（runId/status/version 由 schema 描述）
            api_client.validate_schema(resp, API_WORKFLOW_EXECUTE_RESPONSE)
            assert isinstance(resp, dict)
        except httpx.HTTPStatusError as e:
            # 抛异常也是预期行为，验证状态码（404/422 为客户端错误）
            assert e.response.status_code in (404, 422), \
                f"意外状态码: {e.response.status_code}"
