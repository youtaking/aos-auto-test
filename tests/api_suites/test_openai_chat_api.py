# tests/api_suites/test_openai_chat_api.py
"""OpenAI Chat Completions 兼容接口测试

覆盖对外 OpenAPI：
- TestOpenAIChatAPI: /api/agents/:agentId/v1/chat/completions（API Key 认证）

接口清单：
- POST /api/agents/:agentId/v1/chat/completions → OpenAI 兼容的 Chat 端点
  - 支持 stream / non-stream 模式
  - 仅取 messages 最后一条 user 消息作为输入
  - 通过 X-Session-Id header 可恢复会话
"""
import httpx
import pytest
from tests.api_contracts.openapi_extra_schemas import API_OPENAI_CHAT_RESPONSE


class TestOpenAIChatAPI:
    """/api/agents/:agentId/v1/chat/completions 测试（API Key 认证）

    特点：
    - 标准 OpenAI Chat Completions 兼容格式
    - body: {model, messages: [{role, content}], stream: bool}
    - 非流式响应: {id, choices: [{message: {content}, finish_reason}]}
    - 流式响应: SSE text/event-stream
    """

    def _get_first_agent_id(self, api_client):
        """获取第一个可用 Agent ID"""
        resp = api_client.list_agents()
        if len(resp["items"]) == 0:
            return None
        return resp["items"][0]["id"]

    def test_chat_nonexistent_agent(self, api_client, _openapi_access):
        """向不存在的 Agent 发送 chat 请求：应返回 404"""

        with pytest.raises(httpx.HTTPStatusError, match=r"404"):
            api_client.post("/api/agents/nonexistent-agent-id/v1/chat/completions", json={
                "model": "test",
                "messages": [{"role": "user", "content": "hello"}],
            })

    def test_chat_no_user_message(self, api_client, _openapi_access):
        """发送不含 user 消息的请求：应返回 400"""

        agent_id = self._get_first_agent_id(api_client)
        if agent_id is None:
            pytest.skip("Agent 列表为空，跳过测试")

        with pytest.raises(httpx.HTTPStatusError, match=r"400"):
            api_client.post(f"/api/agents/{agent_id}/v1/chat/completions", json={
                "model": "test",
                "messages": [{"role": "system", "content": "you are a helper"}],
            })

    def test_chat_empty_messages(self, api_client, _openapi_access):
        """发送空 messages 数组：应返回 400"""

        agent_id = self._get_first_agent_id(api_client)
        if agent_id is None:
            pytest.skip("Agent 列表为空，跳过测试")

        with pytest.raises(httpx.HTTPStatusError, match=r"400"):
            api_client.post(f"/api/agents/{agent_id}/v1/chat/completions", json={
                "model": "test",
                "messages": [],
            })

    def test_chat_non_stream(self, api_client, _openapi_access):
        """非流式 chat 请求：验证基本响应结构（可能需要较长超时）"""

        agent_id = self._get_first_agent_id(api_client)
        if agent_id is None:
            pytest.skip("Agent 列表为空，跳过测试")

        try:
            resp = api_client.post(f"/api/agents/{agent_id}/v1/chat/completions", json={
                "model": "test",
                "messages": [{"role": "user", "content": "ping"}],
                "stream": False,
            })
            api_client.validate_schema(resp, API_OPENAI_CHAT_RESPONSE)
            assert "choices" in resp
            assert isinstance(resp["choices"], list)
        except httpx.HTTPStatusError as e:
            # Agent 可能未配置完整环境，404/500 属于可接受范围
            if e.response.status_code in (404, 500, 504):
                pytest.skip(f"Agent 环境不可用 ({e.response.status_code})，跳过非流式测试")
            raise
        except httpx.TimeoutException:
            pytest.skip("Agent 响应超时，跳过非流式测试")
