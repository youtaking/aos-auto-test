# tests/api_suites/test_meta_agent_api.py
"""Meta Agent 接口测试：功能验证 + 契约验证

覆盖控制台接口：
- TestMetaAgentWebAPI: /web/meta-agent（session cookie 认证）
"""
import pytest
from tests.api_contracts.meta_agent_schemas import META_AGENT_ENSURE_DATA


class TestMetaAgentWebAPI:
    """/web/meta-agent 控制台接口测试

    特点：
    - POST /meta-agent/ensure 查找或创建 meta environment + spawn 实例
    """

    def test_ensure_meta_agent(self, web_client):
        """确保 Meta Agent 可用：返回 environmentId 和 status"""
        resp = web_client.ensure_meta_agent()
        web_client.validate_schema(resp, META_AGENT_ENSURE_DATA)
        assert isinstance(resp["environmentId"], str)
        assert resp["status"] in ("created", "reused")
