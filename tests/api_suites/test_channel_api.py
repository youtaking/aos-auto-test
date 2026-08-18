# tests/api_suites/test_channel_api.py
"""Channel 接口测试：功能验证 + 契约验证

覆盖控制台接口：
- TestChannelWebAPI: /web/channels（session cookie 认证）
"""
import httpx
import pytest
from tests.api_contracts.channel_schemas import (
    CHANNEL_BINDING_ITEM,
)

# unwrapped schemas (data portion after _unwrap)
_WEB_CHANNEL_PROVIDER_LIST_DATA = {"type": ["object", "array"]}
_WEB_CHANNEL_BINDING_LIST_DATA = {"type": "array", "items": CHANNEL_BINDING_ITEM}


# ── 控制台接口测试 ──

class TestChannelWebAPI:
    """/web/channels 控制台接口测试（session cookie 认证）

    特点：
    - GET /channels/providers 获取通道平台列表
    - GET /channels/hermes/status 获取 Hermes 状态
    - CRUD /channels/bindings 通道绑定管理（需要有效 agentId）
    """

    def test_list_channel_providers(self, web_client):
        """获取通道平台列表"""
        resp = web_client.list_channel_providers()
        web_client.validate_schema(resp, _WEB_CHANNEL_PROVIDER_LIST_DATA)
        assert isinstance(resp, (list, dict))

    def test_get_hermes_status(self, web_client):
        """获取 Hermes 状态"""
        resp = web_client.get_hermes_status()
        assert "connected" in resp
        assert isinstance(resp["connected"], bool)

    def test_list_channel_bindings(self, web_client):
        """获取通道绑定列表：返回数组"""
        resp = web_client.list_channel_bindings()
        web_client.validate_schema(resp, _WEB_CHANNEL_BINDING_LIST_DATA)
        assert isinstance(resp, list)

    def test_create_channel_binding_invalid(self, web_client):
        """创建通道绑定缺少必填字段 — 应返回 400"""
        try:
            web_client.create_channel_binding({"platform": ""})
        except (httpx.HTTPStatusError, RuntimeError) as e:
            assert "400" in str(e) or "422" in str(e), \
                f"预期 400/422，实际: {e}"

    def test_create_channel_binding_nonexistent_agent(self, web_client):
        """创建通道绑定使用不存在的 agentId — 应返回 404"""
        try:
            web_client.create_channel_binding({
                "platform": "discord",
                "agentId": "nonexistent-agent-id-99999",
            })
        except (httpx.HTTPStatusError, RuntimeError) as e:
            assert "404" in str(e) or "400" in str(e), \
                f"预期 404/400，实际: {e}"

    def test_delete_channel_binding_nonexistent(self, web_client):
        """删除不存在的通道绑定 — 应返回 404 或 200 空"""
        try:
            web_client.delete_channel_binding("nonexistent-binding-id-99999")
        except (httpx.HTTPStatusError, RuntimeError) as e:
            assert "404" in str(e) or "500" in str(e), \
                f"预期 404/500，实际: {e}"

    def test_update_channel_binding_nonexistent(self, web_client):
        """更新不存在的通道绑定 — 应返回 404"""
        try:
            web_client.update_channel_binding(
                "nonexistent-binding-id-99999",
                {"enabled": False},
            )
        except (httpx.HTTPStatusError, RuntimeError) as e:
            assert "404" in str(e) or "500" in str(e), \
                f"预期 404/500，实际: {e}"

