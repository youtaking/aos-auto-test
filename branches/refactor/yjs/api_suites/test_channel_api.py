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

