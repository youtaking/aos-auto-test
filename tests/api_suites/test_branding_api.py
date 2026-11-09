# tests/api_suites/test_branding_api.py
"""Branding / Sidebar / CustomTools 只读配置接口测试：功能验证 + 契约验证

覆盖控制台接口：
- TestBrandingWebAPI: /web/branding（无需认证）
- TestSidebarConfigWebAPI: /web/sidebar-config（无需认证）
- TestWorkflowCustomToolsWebAPI: /web/workflow-custom-tools（session cookie 认证）
"""
import pytest
from tests.api_contracts.branding_schemas import BRANDING_DATA, CUSTOM_TOOL, SIDEBAR_CONFIG_DATA


class TestBrandingWebAPI:
    """/web/branding 品牌配置接口（无需认证）"""

    @pytest.mark.p1
    def test_get_branding(self, web_client):
        """获取品牌配置：返回 brandName 和 logoUrl"""
        resp = web_client.get_branding()
        web_client.validate_schema(resp, BRANDING_DATA)
        assert isinstance(resp["brandName"], str)

    @pytest.mark.p2
    def test_get_branding_logo(self, web_client):
        """获取品牌 Logo：未配置时 404 为环境前置，配置时返回图片字节"""
        resp = web_client.client.get("/web/branding/logo")
        if resp.status_code == 404:
            body = resp.json()
            assert body["success"] is False
            assert body["error"]["code"] == "NOT_FOUND"
            pytest.skip("当前部署未配置品牌 Logo（404）")

        assert resp.status_code == 200, f"期望 200，实际 {resp.status_code}: {resp.text[:200]}"
        assert resp.headers.get("content-type", "").startswith("image/")
        assert len(resp.content) > 0


class TestSystemModulesWebAPI:
    """/web/system/modules 部署模块清单接口"""

    @pytest.mark.p1
    def test_get_system_modules(self, web_client):
        """获取启用模块清单：modules 与 web 均为非空数组"""
        resp = web_client.get_system_modules()
        assert isinstance(resp["modules"], list) and resp["modules"]
        assert isinstance(resp["web"], list) and resp["web"]
        assert "knowledge" in resp["modules"]


class TestSidebarConfigWebAPI:
    """/web/sidebar-config 侧边栏配置接口（无需认证）"""

    @pytest.mark.p1
    def test_get_sidebar_config(self, web_client):
        """获取侧边栏配置：Schema 校验 + hiddenTabs 数组"""
        resp = web_client.get_sidebar_config()
        web_client.validate_schema(resp, SIDEBAR_CONFIG_DATA)
        assert isinstance(resp, dict)
        assert isinstance(resp.get("hiddenTabs"), list), \
            f"hiddenTabs 应为数组，实际: {type(resp.get('hiddenTabs'))}"


class TestWorkflowCustomToolsWebAPI:
    """/web/workflow-custom-tools 自定义工具列表（session cookie 认证）"""

    @pytest.mark.p1
    def test_list_workflow_custom_tools(self, web_client):
        """获取自定义工具列表：返回工具元数据数组"""
        resp = web_client.list_workflow_custom_tools()
        assert isinstance(resp, list)
        if len(resp) > 0:
            web_client.validate_schema(resp[0], CUSTOM_TOOL)
        else:
            # 空列表也是有效结果，至少验证类型
            assert resp == []
