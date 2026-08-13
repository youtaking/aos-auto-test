# tests/api_suites/test_agent_generation_api.py
"""Agent Generation 接口测试：功能验证 + 契约验证

覆盖控制台接口：
- TestAgentGenerationWebAPI: /web/agent-generation（session cookie 认证）

注：需要配置 AI 生成模型，否则返回 503。
"""
import httpx
import pytest
from tests.api_contracts.agent_generation_schemas import AGENT_GENERATION_RESULT


class TestAgentGenerationWebAPI:
    """/web/agent-generation 控制台接口测试

    特点：
    - POST /agent-generation body: {prompt} → AI 生成 agent 配置
    - 需要服务端配置生成模型，未配置时返回 503
    """

    def test_agent_generation_configured(self, web_client):
        """检查 Agent 生成功能：已配置时返回 name + systemPrompt + skills"""
        try:
            resp = web_client.generate_agent("test assistant")
            web_client.validate_schema(resp, AGENT_GENERATION_RESULT)
            assert isinstance(resp["name"], str)
            assert isinstance(resp["systemPrompt"], str)
            assert isinstance(resp["skills"], list)
        except (httpx.HTTPStatusError, RuntimeError) as e:
            # 503 表示未配置生成模型，这是可接受的
            if "503" in str(e):
                pytest.skip("Agent generation model not configured")
            raise
