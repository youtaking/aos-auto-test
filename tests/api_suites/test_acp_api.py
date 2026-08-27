# tests/api_suites/test_acp_api.py
"""ACP 接口测试：功能验证 + 契约验证

覆盖控制台接口：
- TestAcpWebAPI: /acp/agents（session cookie 认证，直接返回数组无包装）
"""
import httpx
import pytest
from tests.api_contracts.acp_schemas import (
    ACP_AGENT_ITEM,
    ACP_AGENT_LIST_DATA,
)


# ── 控制台接口测试 ──

class TestAcpWebAPI:
    """/acp/agents ACP Agent 列表接口（session cookie 认证）

    特点：
    - GET /acp/agents 返回当前组织下 ACP worker 环境列表
    - 响应为直接数组（无 {success, data} 包装）
    - 每个 item 包含 id, agent_name, status, max_sessions, last_seen_at, created_at
    """

    def test_list_acp_agents(self, web_client):
        """获取 ACP Agent 列表：返回数组"""
        resp = web_client.list_acp_agents()
        assert isinstance(resp, list), f"ACP agents 应返回数组，实际: {type(resp)}"
        web_client.validate_schema(resp, ACP_AGENT_LIST_DATA)

    def test_list_acp_agents_schema_fields(self, web_client):
        """ACP Agent 列表项字段校验"""
        resp = web_client.list_acp_agents()
        if len(resp) == 0:
            pytest.skip("ACP Agent 列表为空，无法测试字段")

        agent = resp[0]
        web_client.validate_schema(agent, ACP_AGENT_ITEM)
        assert isinstance(agent["id"], str), f"id 应为 string: {type(agent['id'])}"
        assert agent["status"] in ("online", "offline"), \
            f"status 应为 online/offline，实际: {agent['status']}"
        assert isinstance(agent["max_sessions"], (int, float)), \
            f"max_sessions 应为 number: {type(agent['max_sessions'])}"
        assert isinstance(agent["created_at"], (int, float)), \
            f"created_at 应为 number: {type(agent['created_at'])}"

    def test_list_acp_agents_unauthorized(self, api_base_url):
        """无认证获取 ACP Agent 列表 — 应返回 401/403"""
        import httpx as _httpx
        with _httpx.Client(base_url=api_base_url, timeout=30, verify=False) as client:
            resp = client.get("/acp/agents")
            assert resp.status_code in (401, 403, 302), \
                f"无认证预期 401/403/302，实际: {resp.status_code}"
