# tests/api_suites/test_sidebar_config_api.py
"""Sidebar Config 接口测试：功能验证 + 契约验证

覆盖控制台接口：
- TestSidebarConfigWebAPI: /web/sidebar-config（无需认证）

侧边栏配置是公开的只读端点，返回前端侧边栏的展示配置。
"""
import pytest

from tests.api_contracts.branding_schemas import SIDEBAR_CONFIG_DATA


class TestSidebarConfigWebAPI:
    """/web/sidebar-config 侧边栏配置接口（无需认证）

    特点：
    - GET /sidebar-config — 返回 {success, data: {hiddenTabs: [...]}}
    - 数据为前端侧边栏展示配置（如隐藏的 tab 列表）
    """

    def test_get_sidebar_config(self, web_client):
        """获取侧边栏配置：Schema 校验 + hiddenTabs 数组"""
        result = web_client.get_sidebar_config()
        web_client.validate_schema(result, SIDEBAR_CONFIG_DATA)
        assert isinstance(result.get("hiddenTabs"), list)

    def test_sidebar_config_raw_response(self, web_client):
        """侧边栏配置原始响应：验证 {success, data} 包装"""
        resp = web_client.get("/web/sidebar-config")
        assert isinstance(resp, dict)
        assert resp.get("success") is True
        assert "data" in resp
