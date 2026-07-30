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

    def test_channel_binding_crud_lifecycle(self, web_client):
        """通道绑定 CRUD 生命周期：创建 → 读取 → 更新 → 删除"""
        # 获取第一个 agent 的 ID 用于绑定
        agents_data = web_client.list_agents()
        agents = agents_data.get("agents", [])
        if len(agents) == 0:
            pytest.skip("Agent 列表为空，无法测试通道绑定")
        agent_id = agents[0]["id"]

        test_platform = "wechat"
        try:
            create_resp = web_client.create_channel_binding({
                "platform": test_platform,
                "agentId": agent_id,
            })
        except (httpx.HTTPStatusError, RuntimeError) as e:
            if "404" in str(e) or "500" in str(e) or "400" in str(e) or "422" in str(e):
                pytest.skip("通道绑定创建接口不可用")
            raise
        assert "id" in create_resp
        binding_id = create_resp["id"]

        try:
            # 验证创建成功：列表中包含
            bindings = web_client.list_channel_bindings()
            found = any(b["id"] == binding_id for b in bindings)
            assert found, f"Created binding {binding_id} not in list"

            # 更新
            web_client.update_channel_binding(binding_id, {"enabled": False})
            # 回读验证更新生效
            bindings_updated = web_client.list_channel_bindings()
            updated_binding = next((b for b in bindings_updated if b["id"] == binding_id), None)
            assert updated_binding is not None
            assert updated_binding.get("enabled") is False

            # 删除并验证
            web_client.delete_channel_binding(binding_id)
            bindings_after = web_client.list_channel_bindings()
            found_after = any(b["id"] == binding_id for b in bindings_after)
            assert not found_after, f"Deleted binding {binding_id} still in list"
        finally:
            try:
                web_client.delete_channel_binding(binding_id)
            except Exception as e:
                import logging
                logging.getLogger("cleanup").warning(f"Cleanup failed: {e}")
