# tests/api_suites/test_registry_api.py
"""Registry 接口测试：功能验证 + 契约验证

覆盖控制台接口：
- TestRegistryWebAPI: /web/registry（session cookie 认证，RESTful /:id 风格）
"""
import httpx
import pytest
from tests.api_contracts.registry_schemas import (
    MACHINE_ITEM,
    MACHINE_EVENT_ITEM,
)

# unwrapped schema (data portion after _unwrap)
_WEB_MACHINE_EVENT_LIST_DATA = {
    "type": "object",
    "properties": {
        "items": {"type": "array", "items": MACHINE_EVENT_ITEM},
        "total": {"type": "integer"},
    },
    "additionalProperties": True,
}

# unwrapped schema (data portion after _unwrap)
_WEB_MACHINE_LIST_DATA = {
    "type": "object",
    "properties": {
        "items": {"type": "array", "items": MACHINE_ITEM},
        "total": {"type": "integer"},
    },
    "additionalProperties": True,
}


# ── 控制台接口测试 ──

class TestRegistryWebAPI:
    """/web/registry 控制台接口测试（session cookie 认证，RESTful /:id 风格）

    特点：
    - 机器列表返回 {items, total}
    - 机器详情含 recentEvents
    """

    @pytest.mark.p1
    def test_list_machines(self, web_client):
        """获取机器列表：返回分页结构"""
        resp = web_client.list_machines()
        web_client.validate_schema(resp, _WEB_MACHINE_LIST_DATA)
        assert "items" in resp
        assert isinstance(resp["items"], list)

    @pytest.mark.p1
    def test_get_machine(self, web_client):
        """获取机器详情：先拿列表取第一个 id"""
        list_resp = web_client.list_machines()
        if len(list_resp["items"]) == 0:
            pytest.skip("机器列表为空，无法测试详情")
        machine_id = list_resp["items"][0]["id"]

        detail = web_client.get_machine(machine_id)
        web_client.validate_schema(detail, MACHINE_ITEM)
        assert detail["id"] == machine_id
        assert "recentEvents" in detail

    @pytest.mark.p1
    def test_list_machine_events(self, web_client):
        """获取机器事件列表：先拿列表取第一个 id"""
        list_resp = web_client.list_machines()
        if len(list_resp["items"]) == 0:
            pytest.skip("机器列表为空，无法测试事件")
        machine_id = list_resp["items"][0]["id"]

        resp = web_client.list_machine_events(machine_id)
        web_client.validate_schema(resp, _WEB_MACHINE_EVENT_LIST_DATA)
        assert "items" in resp
        assert isinstance(resp["items"], list)

    @pytest.mark.p2
    def test_get_nonexistent_machine(self, web_client):
        """获取不存在的机器：应抛出 404 异常"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"404"):
            web_client.get_machine("nonexistent-machine-id-99999")

    @pytest.mark.p2
    def test_get_machine_connection_parameters(self, web_client):
        """获取机器连接参数：返回 machineId/agentType/rcsUrl"""
        list_resp = web_client.list_machines()
        if len(list_resp["items"]) == 0:
            pytest.skip("机器列表为空，无法测试连接参数")
        machine_id = list_resp["items"][0]["id"]

        params = web_client.get_machine_connection_parameters(machine_id)
        assert params["machineId"] == machine_id
        assert isinstance(params["agentType"], str) and params["agentType"]
        assert params["rcsUrl"].startswith(("ws://", "wss://", "http://", "https://"))

    @pytest.mark.p2
    def test_acp_runtime_invalid_platform(self, web_client):
        """下载 ACP Runtime 使用非法平台：应返回 400 VALIDATION_ERROR"""
        resp = web_client.client.get("/web/registry/acp-runtime/bogus-platform")
        assert resp.status_code == 400, f"期望 400，实际 {resp.status_code}: {resp.text[:200]}"
        err = resp.json().get("error", {})
        assert err.get("type") == "VALIDATION_ERROR"
        assert "platform" in err.get("message", "")

    @pytest.mark.p2
    def test_download_acp_runtime_linux_x64(self, web_client):
        """下载 linux-x64 ACP Runtime：返回非空 ELF 二进制"""
        content = web_client.get_acp_runtime("linux-x64")
        assert len(content) > 0
        assert content[:4] == b"\x7fELF", f"期望 ELF 魔数，实际 {content[:8]!r}"

    @pytest.mark.p2
    def test_list_acp_agents(self, web_client):
        """获取 ACP agent 列表：返回数组且元素含 id/status"""
        agents = web_client.list_acp_agents()
        assert isinstance(agents, list)
        for agent in agents:
            assert isinstance(agent.get("id"), str)
            assert isinstance(agent.get("status"), str)
