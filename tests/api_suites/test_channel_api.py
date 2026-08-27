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
_WEB_CHANNEL_PROVIDER_ITEM = {
    "type": "object",
    "properties": {
        "type": {"type": "string"},
        "label": {"type": "string"},
        "status": {"type": "string"},
    },
    "required": ["type"],
    "additionalProperties": True,
}
_WEB_CHANNEL_PROVIDER_LIST_DATA = {"type": "array", "items": _WEB_CHANNEL_PROVIDER_ITEM}
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
        """获取通道平台列表：每项含 type/label/status 字段"""
        resp = web_client.list_channel_providers()
        web_client.validate_schema(resp, _WEB_CHANNEL_PROVIDER_LIST_DATA)
        assert isinstance(resp, list)
        for item in resp:
            assert isinstance(item, dict), f"通道平台项应为 dict: {item!r}"
            assert "type" in item, f"通道平台项缺少 type 字段: {list(item.keys())}"

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
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"(400|422)"):
            web_client.create_channel_binding({"platform": ""})

    def test_create_channel_binding_nonexistent_agent(self, web_client):
        """创建通道绑定使用不存在的 agentId — 应返回 404"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"(404|400)"):
            web_client.create_channel_binding({
                "platform": "discord",
                "agentId": "nonexistent-agent-id-99999",
            })

    def test_delete_channel_binding_nonexistent(self, web_client):
        """删除不存在的通道绑定 — 应返回 404"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"404"):
            web_client.delete_channel_binding("nonexistent-binding-id-99999")

    def test_update_channel_binding_nonexistent(self, web_client):
        """更新不存在的通道绑定 — 应返回 404"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"404"):
            web_client.update_channel_binding(
                "nonexistent-binding-id-99999",
                {"enabled": False},
            )

