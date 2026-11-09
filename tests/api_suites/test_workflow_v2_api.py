# tests/api_suites/test_workflow_v2_api.py
"""Workflow V2 接口测试

覆盖 /web/workflow-v2（session cookie 认证）：
- 工作流列表、运行记录、平台账号、组织应用、发布记录（只读）
- iframe 代码与创建/更新/删除的参数校验与不存在资源
"""
import httpx
import pytest


class TestWorkflowV2WebAPI:
    """/web/workflow-v2 控制台接口测试"""

    @pytest.mark.p0
    def test_list_workflows(self, web_client):
        """列出 V2 工作流：items 为数组且元素含 id/name"""
        data = web_client.list_workflow_v2_workflows()
        assert isinstance(data, dict)
        assert isinstance(data.get("items"), list)
        for item in data["items"]:
            assert isinstance(item.get("id"), str)
            assert isinstance(item.get("name"), str)

    @pytest.mark.p1
    def test_list_run_records(self, web_client):
        """列出 V2 运行记录：items/workflows 为数组"""
        data = web_client.list_workflow_v2_run_records()
        assert isinstance(data, dict)
        assert isinstance(data.get("items"), list)
        assert isinstance(data.get("workflows"), list)
        assert isinstance(data.get("scannedWorkflows"), int)

    @pytest.mark.p1
    def test_get_org_app(self, web_client):
        """获取组织级 V2 应用绑定：appId 与 status 存在"""
        data = web_client.get_workflow_v2_org_app()
        assert isinstance(data.get("appId"), str)
        assert isinstance(data.get("status"), str)

    @pytest.mark.p1
    def test_get_platform_account(self, web_client):
        """获取 V2 平台账号状态：platformUserId 与 status 存在"""
        data = web_client.get_workflow_v2_platform_account()
        assert isinstance(data.get("platformUserId"), str)
        assert isinstance(data.get("status"), str)

    @pytest.mark.p2
    def test_get_publish_records_nonexistent(self, web_client):
        """不存在的工作流发布记录：应返回 404 NOT_FOUND"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"(404|NOT_FOUND)"):
            web_client.get_workflow_v2_publish_records("nonexistent-workflow-id-99999")

    @pytest.mark.p2
    def test_run_record_io_missing_upstream_workflow(self, web_client):
        """运行记录 IO 缺少 upstreamWorkflowId：应返回 400 VALIDATION_ERROR"""
        resp = web_client.client.get("/web/workflow-v2/run-records/nonexistent/io")
        assert resp.status_code == 400, f"期望 400，实际 {resp.status_code}: {resp.text[:200]}"
        err = resp.json().get("error", {})
        assert err.get("type") == "VALIDATION_ERROR"
        assert "upstreamWorkflowId" in err.get("message", "")

    @pytest.mark.p2
    def test_iframe_code_missing_workflow(self, web_client):
        """生成 iframe 代码缺少 workflowId：应返回 400 VALIDATION_ERROR"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"(400|VALIDATION_ERROR|workflowId)"):
            web_client.create_workflow_v2_iframe_code({})

    @pytest.mark.p2
    def test_create_workflow_missing_name(self, web_client):
        """创建工作流缺少 name：应返回 400 VALIDATION_ERROR（不落库）"""
        resp = web_client.client.post("/web/workflow-v2/workflows", json={})
        assert resp.status_code == 400, f"期望 400，实际 {resp.status_code}: {resp.text[:200]}"
        err = resp.json().get("error", {})
        assert err.get("type") == "VALIDATION_ERROR"
        assert "name" in err.get("message", "")

    @pytest.mark.p2
    def test_update_workflow_empty_body(self, web_client):
        """更新工作流但未提供可改字段：应返回 400 INVALID_REQUEST"""
        resp = web_client.client.patch("/web/workflow-v2/workflows/nonexistent-workflow-id-99999", json={})
        assert resp.status_code == 400, f"期望 400，实际 {resp.status_code}: {resp.text[:200]}"
        err = resp.json().get("error", {})
        assert err.get("code") == "INVALID_REQUEST"

    @pytest.mark.p2
    def test_delete_nonexistent_workflow(self, web_client):
        """删除不存在的工作流：应返回 404 NOT_FOUND"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"(404|NOT_FOUND)"):
            web_client.delete_workflow_v2_workflow("nonexistent-workflow-id-99999")

    @pytest.mark.p2
    def test_org_app_rebind_missing_app_id(self, web_client):
        """组织应用重新绑定缺少 appId：应返回 400 VALIDATION_ERROR"""
        resp = web_client.client.post("/web/workflow-v2/org-app/rebind", json={})
        assert resp.status_code == 400, f"期望 400，实际 {resp.status_code}: {resp.text[:200]}"
        err = resp.json().get("error", {})
        assert err.get("type") == "VALIDATION_ERROR"
        assert "appId" in err.get("message", "")


class TestWorkflowV2OpenAPI:
    """/api/v1/workflow-v2 对外接口测试（API Key 认证）

    特点：
    - POST /api/v1/workflow-v2/workflows/:id/run
    - :id 必须是本地工作流主键 UUID，非 UUID 在边界返回 422
    - 不存在/跨组织 → 404 WORKFLOW_NOT_FOUND；未发布 → 409
    - 响应为 {success, data} 信封，client 已解包为 data
    """

    @pytest.mark.p2
    def test_run_nonexistent_workflow(self, api_client, _openapi_access):
        """workflow id 非 UUID：返回 422 VALIDATION_ERROR"""
        with pytest.raises(httpx.HTTPStatusError) as caught:
            api_client.run_workflow_v2("nonexistent-workflow-id-99999", {})
        assert caught.value.response.status_code == 422
        body = caught.value.response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert "id" in body["error"]["message"]

    @pytest.mark.p2
    def test_run_nonexistent_workflow_valid_uuid(self, api_client, _openapi_access):
        """合法 UUID 但工作流不存在：返回 404 WORKFLOW_NOT_FOUND"""
        with pytest.raises(httpx.HTTPStatusError) as caught:
            api_client.run_workflow_v2("00000000-0000-4000-8000-000000000000", {})
        assert caught.value.response.status_code == 404
        body = caught.value.response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "WORKFLOW_NOT_FOUND"

    @pytest.mark.p2
    def test_run_invalid_parameters_type(self, api_client, _openapi_access):
        """parameters 传入数字：schema 校验失败，返回 422 VALIDATION_ERROR"""
        with pytest.raises(httpx.HTTPStatusError) as caught:
            api_client.run_workflow_v2(
                "00000000-0000-4000-8000-000000000000",
                {"parameters": 123},
            )
        assert caught.value.response.status_code == 422
        body = caught.value.response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "VALIDATION_ERROR"
