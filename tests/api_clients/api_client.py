# tests/api_clients/api_client.py
"""/api/* 对外接口客户端（API Key 认证）"""
from tests.api_clients.base_client import BaseClient


class ApiClient(BaseClient):
    """对外 OpenAPI 接口客户端，通过 API Key 认证"""

    def __init__(self, base_url: str, api_key: str, timeout: int = 30):
        super().__init__(
            base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )

    # ── Agent 模块 ──

    def list_agents(self, params: dict | None = None) -> dict:
        """获取 Agent 列表"""
        return self.get("/api/agents", params=params)

    def get_agent(self, agent_id: str) -> dict:
        """获取 Agent 详情"""
        return self.get(f"/api/agents/{agent_id}")
