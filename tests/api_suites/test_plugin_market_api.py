# tests/api_suites/test_plugin_market_api.py
"""Plugin Market 接口测试（只读）

覆盖：
- Web 控制台 /web/config/plugin-market/packages（session cookie）
- System API /api/system/plugin-market/packages（System API Key）

发布/下架/恢复属于破坏性管理动作，只覆盖列表与详情；不存在包返回 404。
"""
import httpx
import pytest


class TestPluginMarketWebAPI:
    """/web/config/plugin-market 控制台接口测试"""

    @pytest.mark.p1
    def test_list_packages(self, web_client):
        """列出插件包：packages 为数组，total 为整数"""
        data = web_client.list_plugin_market_packages()
        assert isinstance(data.get("packages"), list)
        assert isinstance(data.get("total"), int)

    @pytest.mark.p2
    def test_get_nonexistent_package(self, web_client):
        """获取不存在的插件包：应返回 404"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"(404|NOT_FOUND)"):
            web_client.get_plugin_market_package("nonexistent-package-slug-99999")


class TestPluginMarketSystemAPI:
    """/api/system/plugin-market 只读接口测试（System API Key）"""

    @pytest.mark.p1
    def test_list_packages(self, api_client, system_access):
        """列出插件包：data.packages 为数组"""
        data = api_client.list_system_plugin_market_packages()
        assert isinstance(data.get("packages"), list)
        assert isinstance(data.get("total"), int)

    @pytest.mark.p2
    def test_get_nonexistent_package(self, api_client, system_access):
        """获取不存在的插件包：应返回 404 NOT_FOUND"""
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            api_client.get_system_plugin_market_package("nonexistent-package-slug-99999")
        assert exc_info.value.response.status_code == 404
        body = exc_info.value.response.json()
        assert body.get("error", {}).get("code") == "NOT_FOUND"
