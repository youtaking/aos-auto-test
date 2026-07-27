# tests/api_clients/web_client.py
"""/api/* 控制台接口客户端（better-auth session cookie 认证）"""
from tests.api_clients.base_client import BaseClient


class WebClient(BaseClient):
    """控制台内部接口客户端，通过登录获取 session cookie"""

    def login(self, email: str, password: str) -> None:
        """登录 better-auth，session cookie 自动保存在 httpx.Client 中"""
        resp = self.client.post("/api/auth/sign-in/email", json={
            "email": email,
            "password": password,
        })
        resp.raise_for_status()

    # ── Agent 模块 ──

    def list_agents(self, params: dict | None = None) -> dict:
        """获取 Agent 列表"""
        return self.get("/api/agents", params=params)

    def get_agent(self, agent_id: str) -> dict:
        """获取 Agent 详情"""
        return self.get(f"/api/agents/{agent_id}")

    def create_agent(self, data: dict) -> dict:
        """创建 Agent"""
        return self.post("/api/agents", json=data)

    def update_agent(self, agent_id: str, data: dict) -> dict:
        """更新 Agent"""
        return self.put(f"/api/agents/{agent_id}", json=data)

    def delete_agent(self, agent_id: str) -> dict:
        """删除 Agent"""
        return self.delete(f"/api/agents/{agent_id}")
