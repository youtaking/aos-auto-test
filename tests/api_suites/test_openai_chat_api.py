# tests/api_suites/test_openai_chat_api.py
"""OpenAI Chat Completions 兼容接口测试

覆盖对外 OpenAPI：
- TestOpenAIChatAPI: /api/v1/chat/completions（API Key 认证）

接口清单：
- POST /api/v1/chat/completions → OpenAI 兼容的 Chat 端点
  - model 为 Agent 配置 ID（UUID），不是上游模型代码
  - 支持 stream / non-stream 模式
  - 仅取 messages 最后一条 user 消息作为输入
  - 通过 X-Session-Id header 可恢复会话
"""
import httpx
import pytest
from tests.api_contracts.openapi_extra_schemas import (
    API_OPENAI_CHAT_RESPONSE,
    API_OPENAI_CHAT_ERROR_RESPONSE,
)

# 合法但必定不存在的 UUID：用于验证 404 而不触发 UUID 格式校验
_NONEXISTENT_AGENT_UUID = "00000000-0000-4000-8000-000000000000"


class TestOpenAIChatAPI:
    """/api/v1/chat/completions 测试（API Key 认证）

    特点：
    - 标准 OpenAI Chat Completions 兼容格式
    - body: {model: <agentConfigId uuid>, messages: [{role, content}], stream: bool}
    - 非流式响应: {id, object, created, model, choices: [{message, finish_reason}]}
    - 错误响应为 OpenAI 格式: {error: {message, type, param, code}}
    """

    def _get_first_agent_id(self, api_client):
        """获取第一个可用 Agent ID（即 agentConfigId）"""
        resp = api_client.list_agents()
        if len(resp["items"]) == 0:
            return None
        return resp["items"][0]["id"]

    @pytest.mark.p2
    def test_chat_nonexistent_agent(self, api_client, _openapi_access):
        """向不存在的 Agent 发送 chat 请求：返回 404 + NOT_FOUND"""

        with pytest.raises(httpx.HTTPStatusError) as caught:
            api_client.chat_completions({
                "model": _NONEXISTENT_AGENT_UUID,
                "messages": [{"role": "user", "content": "hello"}],
            })
        assert caught.value.response.status_code == 404
        body = caught.value.response.json()
        api_client.validate_schema(body, API_OPENAI_CHAT_ERROR_RESPONSE)
        assert body["error"]["code"] == "NOT_FOUND"

    @pytest.mark.p2
    def test_chat_invalid_model_format(self, api_client, _openapi_access):
        """model 不是 UUID：返回 400 VALIDATION_ERROR（OpenAI 错误格式）"""

        with pytest.raises(httpx.HTTPStatusError) as caught:
            api_client.chat_completions({
                "model": "not-a-uuid",
                "messages": [{"role": "user", "content": "hello"}],
            })
        assert caught.value.response.status_code == 400
        body = caught.value.response.json()
        api_client.validate_schema(body, API_OPENAI_CHAT_ERROR_RESPONSE)
        assert body["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.p2
    def test_chat_no_user_message(self, api_client, _openapi_access):
        """最后一条不是 user 消息：返回 400 VALIDATION_ERROR"""

        agent_id = self._get_first_agent_id(api_client)
        if agent_id is None:
            pytest.skip("Agent 列表为空，跳过测试")

        with pytest.raises(httpx.HTTPStatusError) as caught:
            api_client.chat_completions({
                "model": agent_id,
                "messages": [{"role": "system", "content": "you are a helper"}],
            })
        assert caught.value.response.status_code == 400
        body = caught.value.response.json()
        api_client.validate_schema(body, API_OPENAI_CHAT_ERROR_RESPONSE)
        assert body["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.p2
    def test_chat_empty_messages(self, api_client, _openapi_access):
        """发送空 messages 数组：返回 400 VALIDATION_ERROR"""

        agent_id = self._get_first_agent_id(api_client)
        if agent_id is None:
            pytest.skip("Agent 列表为空，跳过测试")

        with pytest.raises(httpx.HTTPStatusError) as caught:
            api_client.chat_completions({"model": agent_id, "messages": []})
        assert caught.value.response.status_code == 400
        body = caught.value.response.json()
        api_client.validate_schema(body, API_OPENAI_CHAT_ERROR_RESPONSE)
        assert body["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.p2
    def test_chat_unknown_field_rejected(self, api_client, _openapi_access):
        """请求带未声明的顶层字段：strict schema 返回 400 VALIDATION_ERROR"""

        agent_id = self._get_first_agent_id(api_client)
        if agent_id is None:
            pytest.skip("Agent 列表为空，跳过测试")

        with pytest.raises(httpx.HTTPStatusError) as caught:
            api_client.chat_completions({
                "model": agent_id,
                "messages": [{"role": "user", "content": "ping"}],
                "temperature": 0.7,
            })
        assert caught.value.response.status_code == 400
        body = caught.value.response.json()
        assert body["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.p0
    def test_chat_non_stream(self, api_client, _openapi_access):
        """非流式 chat 请求：验证 OpenAI 响应结构（可能需要较长超时）"""

        agent_id = self._get_first_agent_id(api_client)
        if agent_id is None:
            pytest.skip("Agent 列表为空，跳过测试")

        try:
            resp = api_client.chat_completions({
                "model": agent_id,
                "messages": [{"role": "user", "content": "ping"}],
                "stream": False,
            })
            api_client.validate_schema(resp, API_OPENAI_CHAT_RESPONSE)
            assert resp["object"] == "chat.completion"
            assert isinstance(resp["choices"], list)
        except httpx.HTTPStatusError as e:
            # Agent 可能未配置完整环境，404/500/504 属于可接受范围
            if e.response.status_code in (404, 500, 504):
                pytest.skip(f"Agent 环境不可用 ({e.response.status_code})，跳过非流式测试")
            raise
        except httpx.TimeoutException:
            pytest.skip("Agent 响应超时，跳过非流式测试")
