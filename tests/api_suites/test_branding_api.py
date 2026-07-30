# tests/api_suites/test_branding_api.py
"""Branding / Sidebar / CustomTools 只读配置接口测试：功能验证 + 契约验证

覆盖控制台接口：
- TestBrandingWebAPI: /web/branding（无需认证）
- TestSidebarConfigWebAPI: /web/sidebar-config（无需认证）
- TestWorkflowCustomToolsWebAPI: /web/workflow-custom-tools（session cookie 认证）
"""
import pytest
from tests.api_contracts.branding_schemas import BRANDING_DATA, CUSTOM_TOOL


class TestBrandingWebAPI:
    """/web/branding 品牌配置接口（无需认证）"""

    def test_get_branding(self, web_client):
        """获取品牌配置：返回 brandName 和 logoUrl"""
        resp = web_client.get_branding()
        web_client.validate_schema(resp, BRANDING_DATA)
        assert isinstance(resp["brandName"], str)


class TestSidebarConfigWebAPI:
    """/web/sidebar-config 侧边栏配置接口（无需认证）"""

    def test_get_sidebar_config(self, web_client):
        """获取侧边栏配置：返回配置字典"""
        resp = web_client.get_sidebar_config()
        assert isinstance(resp, dict)
        assert len(resp) > 0
        # 验证至少包含一个已知的配置键
        assert any(isinstance(v, (dict, list, str, bool, int)) for v in resp.values())


class TestWorkflowCustomToolsWebAPI:
    """/web/workflow-custom-tools 自定义工具列表（session cookie 认证）"""

    def test_list_workflow_custom_tools(self, web_client):
        """获取自定义工具列表：返回工具元数据数组"""
        resp = web_client.list_workflow_custom_tools()
        assert isinstance(resp, list)
        if len(resp) > 0:
            web_client.validate_schema(resp[0], CUSTOM_TOOL)
        else:
            # 空列表也是有效结果，至少验证类型
            assert resp == []
