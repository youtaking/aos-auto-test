# branches/refactor/yjs/api_suites/test_workflow_custom_tools_api.py
"""Workflow Custom Tools 接口测试：功能验证 + 契约验证

覆盖控制台接口：
- TestWorkflowCustomToolsWebAPI: /web/workflow-custom-tools（session cookie 认证）

自定义工具列表是全局注册的 CustomNode 工具元数据，不按 organizationId 隔离。
"""
import pytest


class TestWorkflowCustomToolsWebAPI:
    """/web/workflow-custom-tools 自定义工具列表接口（session cookie 认证）

    特点：
    - GET /workflow-custom-tools — 返回 {success, data: [...]}
    - 数据源：WORKFLOW_TOOLS_DIR 下注册的 CustomNode 工具
    - 每个工具包含 name, description, inputs, produces 等字段
    """

    def test_list_workflow_custom_tools(self, web_client):
        """获取自定义工具列表：返回数组"""
        result = web_client.list_workflow_custom_tools()
        assert isinstance(result, list)

    def test_custom_tools_raw_response(self, web_client):
        """自定义工具原始响应：验证 {success, data} 包装"""
        resp = web_client.get("/web/workflow-custom-tools")
        assert isinstance(resp, dict)
        assert resp.get("success") is True
        assert "data" in resp
        assert isinstance(resp["data"], list)

    def test_custom_tools_schema(self, web_client):
        """自定义工具元数据 schema：如有工具，验证字段结构"""
        tools = web_client.list_workflow_custom_tools()
        if len(tools) == 0:
            pytest.skip("自定义工具列表为空，无法验证 schema")

        tool = tools[0]
        assert isinstance(tool, dict)
        # 每个工具至少应有 name 字段
        assert "name" in tool
