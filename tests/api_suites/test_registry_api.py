# tests/api_suites/test_registry_api.py
"""Registry 接口测试：功能验证 + 契约验证

覆盖控制台接口：
- TestRegistryWebAPI: /web/registry（session cookie 认证，RESTful /:id 风格）
"""
import httpx
import pytest
from tests.api_contracts.registry_schemas import (
    MACHINE_ITEM,
)

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

    def test_list_machines(self, web_client):
        """获取机器列表：返回分页结构"""
        resp = web_client.list_machines()
        web_client.validate_schema(resp, _WEB_MACHINE_LIST_DATA)
        assert "items" in resp
        assert isinstance(resp["items"], list)

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

    def test_list_machine_events(self, web_client):
        """获取机器事件列表：先拿列表取第一个 id"""
        list_resp = web_client.list_machines()
        if len(list_resp["items"]) == 0:
            pytest.skip("机器列表为空，无法测试事件")
        machine_id = list_resp["items"][0]["id"]

        resp = web_client.list_machine_events(machine_id)
        assert "items" in resp
        assert isinstance(resp["items"], list)

    def test_get_nonexistent_machine(self, web_client):
        """获取不存在的机器：应抛出 404 异常"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"404"):
            web_client.get_machine("nonexistent-machine-id-99999")
