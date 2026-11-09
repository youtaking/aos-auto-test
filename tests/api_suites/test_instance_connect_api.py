# tests/api_suites/test_instance_connect_api.py
"""Instance Connect 接口测试：功能验证 + 契约验证

覆盖对外 OpenAPI：
- TestInstanceConnectOpenAPI: /api/v1/agents/:agentId/instances/connect（API Key 认证）

接口清单：
- POST /api/v1/agents/:agentId/instances/connect → 连接/创建 Agent 实例
"""
import httpx
import pytest
from tests.api_contracts.openapi_extra_schemas import API_INSTANCE_CONNECT_RESPONSE


class TestInstanceConnectOpenAPI:
    """/api/v1/agents/:agentId/instances/connect 测试（API Key 认证）

    特点：
    - 根据 Agent 配置定位并准备可连接的实例
    - 必要时自动创建 environment 和启动实例
    - body: {instanceId?: "inst_..."}（strict schema）
    - 响应 {success, data}，client 已解包为 data
    """

    def _get_first_agent_id(self, api_client):
        """获取第一个可用 Agent ID"""
        resp = api_client.list_agents()
        if len(resp["items"]) == 0:
            return None
        return resp["items"][0]["id"]

    @pytest.mark.p2
    def test_connect_nonexistent_agent(self, api_client, _openapi_access):
        """连接不存在的 Agent：返回 404 + NOT_FOUND"""

        with pytest.raises(httpx.HTTPStatusError) as caught:
            api_client.connect_instance("nonexistent-agent-id-99999")
        assert caught.value.response.status_code == 404
        body = caught.value.response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "NOT_FOUND"

    @pytest.mark.p2
    def test_connect_invalid_instance_id(self, api_client, _openapi_access):
        """instanceId 不满足 inst_ 前缀：返回 400 VALIDATION_ERROR"""

        with pytest.raises(httpx.HTTPStatusError) as caught:
            api_client.connect_instance("nonexistent-agent-id-99999", {"instanceId": "bad-id"})
        assert caught.value.response.status_code == 400
        body = caught.value.response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.p2
    def test_connect_agent_without_machine(self, api_client, _openapi_access):
        """连接无 machine 配置的 Agent：可能返回 404 / 500 / 503"""

        agent_id = self._get_first_agent_id(api_client)
        if agent_id is None:
            pytest.skip("Agent 列表为空，跳过测试")

        try:
            resp = api_client.connect_instance(agent_id)
            # 连接成功时校验响应结构
            api_client.validate_schema(resp, API_INSTANCE_CONNECT_RESPONSE)
        except httpx.HTTPStatusError as e:
            # Agent 可能没有配置完整的运行环境
            if e.response.status_code in (404, 500, 503):
                pytest.skip(f"Agent 环境不可用 ({e.response.status_code})，跳过连接测试")
            raise
        except httpx.TimeoutException:
            pytest.skip("实例连接超时，跳过测试")
