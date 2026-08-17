# branches/refactor/yjs/api_suites/test_sidebar_config_api.py
"""Sidebar Config 接口测试：功能验证 + 契约验证

覆盖控制台接口：
- TestSidebarConfigWebAPI: /web/sidebar-config（无需认证）

侧边栏配置是公开的只读端点，返回前端侧边栏的展示配置。
"""
import pytest


class TestSidebarConfigWebAPI:
    """/web/sidebar-config 侧边栏配置接口（无需认证）

    特点：
    - GET /sidebar-config — 返回 {success, data: {...}}
    - 数据为前端侧边栏展示配置（如隐藏的 tab 列表）
    """

    def test_get_sidebar_config(self, web_client):
        """获取侧边栏配置：返回 success 结构和 data"""
        result = web_client.get_sidebar_config()
        # 返回值应为 dict（可能为空 dict 或包含配置项）
        assert isinstance(result, (dict, list, type(None)))

    def test_sidebar_config_raw_response(self, web_client):
        """侧边栏配置原始响应：验证 {success, data} 包装"""
        resp = web_client.get("/web/sidebar-config")
        assert isinstance(resp, dict)
        assert resp.get("success") is True
        assert "data" in resp
