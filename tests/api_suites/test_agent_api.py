# tests/api_suites/test_agent_api.py
"""Agent 接口测试：功能验证 + 契约验证"""
import httpx
import pytest
from tests.api_contracts.agent_schemas import (
    AGENT_LIST_RESPONSE,
    AGENT_DETAIL_RESPONSE,
    CREATE_AGENT_RESPONSE,
)


def _cleanup_agent(client, name: str):
    """按名称查找并删除 Agent，忽略错误"""
    try:
        list_resp = client.list_agents(params={"pageSize": 100})
        for agent in list_resp["items"]:
            if agent["name"] == name:
                client.delete(f"/api/agents/{agent['id']}")
    except Exception:
        pass


class TestAgentWebAPI:
    """/api/* Agent 接口测试（session cookie 认证）"""

    def test_list_agents(self, web_client):
        """获取 Agent 列表：返回非空数组"""
        resp = web_client.list_agents()
        web_client.validate_schema(resp, AGENT_LIST_RESPONSE)
        assert isinstance(resp["items"], list)
        assert len(resp["items"]) > 0

    def test_get_agent(self, web_client):
        """获取单个 Agent 详情：先拿列表取第一个 ID，再查详情"""
        list_resp = web_client.list_agents()
        assert len(list_resp["items"]) > 0, "Agent 列表为空，无法测试详情"
        agent_id = list_resp["items"][0]["id"]

        resp = web_client.get_agent(agent_id)
        web_client.validate_schema(resp, AGENT_DETAIL_RESPONSE)
        assert resp["id"] == agent_id

    def test_create_and_delete_agent(self, web_client):
        """创建并删除 Agent：写操作生命周期测试"""
        test_name = "api-test-agent-001"

        # 先清理可能遗留的同名 Agent
        _cleanup_agent(web_client, test_name)

        create_data = {
            "name": test_name,
            "description": "API 测试自动创建的 Agent，测试结束后删除",
        }

        # 创建
        create_resp = web_client.create_agent(create_data)
        web_client.validate_schema(create_resp, CREATE_AGENT_RESPONSE)
        agent_id = create_resp["id"]
        assert create_resp["name"] == test_name

        try:
            # 验证创建成功
            get_resp = web_client.get_agent(agent_id)
            assert get_resp["name"] == test_name
        finally:
            # 清理：无论断言是否失败都要删除
            web_client.delete_agent(agent_id)

    def test_update_agent(self, web_client):
        """更新 Agent：创建 → 修改描述 → 验证 → 删除"""
        test_name = "api-test-agent-002"
        updated_desc = "updated by api test"

        # 先清理可能遗留的同名 Agent
        _cleanup_agent(web_client, test_name)

        create_resp = web_client.create_agent({"name": test_name})
        agent_id = create_resp["id"]

        try:
            update_resp = web_client.update_agent(agent_id, {"description": updated_desc})
            assert update_resp["description"] == updated_desc

            # 再次获取确认更新生效
            get_resp = web_client.get_agent(agent_id)
            assert get_resp["description"] == updated_desc
        finally:
            web_client.delete_agent(agent_id)

    def test_get_nonexistent_agent(self, web_client):
        """获取不存在的 Agent：应返回 404 或 success=false"""
        with pytest.raises(Exception):
            web_client.get_agent("nonexistent-agent-id-99999")


class TestAgentOpenAPI:
    """/api/* Agent 接口测试（API Key 认证）"""

    def test_list_agents(self, api_client, api_test_config):
        """通过 OpenAPI 获取 Agent 列表"""
        if api_test_config["fenixagent"]["api_key"] == "test-api-key-placeholder":
            pytest.skip("API Key 未配置，跳过 OpenAPI 测试")
        resp = api_client.list_agents()
        api_client.validate_schema(resp, AGENT_LIST_RESPONSE)
        assert isinstance(resp["items"], list)

    def test_get_agent(self, api_client, api_test_config):
        """通过 OpenAPI 获取单个 Agent 详情"""
        if api_test_config["fenixagent"]["api_key"] == "test-api-key-placeholder":
            pytest.skip("API Key 未配置，跳过 OpenAPI 测试")
        list_resp = api_client.list_agents()
        if len(list_resp["items"]) == 0:
            pytest.skip("Agent 列表为空，跳过详情测试")
        agent_id = list_resp["items"][0]["id"]

        resp = api_client.get_agent(agent_id)
        api_client.validate_schema(resp, AGENT_DETAIL_RESPONSE)
        assert resp["id"] == agent_id
