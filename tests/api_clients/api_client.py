# tests/api_clients/api_client.py
"""/api/* 对外接口客户端（API Key 认证）

对外 OpenAPI 接口特点：
- 路径前缀 /api/
- RESTful 风格：用 /:id 定位资源
- 列表接口带分页 {items, total, page, pageSize}
- 响应为裸数据，无 {success, data} 包装
"""
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
        """获取 Agent 列表
        GET /api/agents?page=1&pageSize=20 → {items, total, page, pageSize}
        """
        return self.get("/api/agents", params=params)

    def get_agent(self, agent_id: str) -> dict:
        """获取 Agent 详情
        GET /api/agents/:id → agent detail
        """
        return self.get(f"/api/agents/{agent_id}")

    def create_agent(self, data: dict) -> dict:
        """创建 Agent
        POST /api/agents body: {name, description, ...} → agent detail
        """
        return self.post("/api/agents", json=data)

    def update_agent(self, agent_id: str, data: dict) -> dict:
        """更新 Agent
        PUT /api/agents/:id body: {description, ...} → agent detail
        """
        return self.put(f"/api/agents/{agent_id}", json=data)

    def delete_agent(self, agent_id: str) -> dict:
        """删除 Agent
        DELETE /api/agents/:id → {id, deleted: true}
        """
        return self.delete(f"/api/agents/{agent_id}")

    # ── MCP 模块（RESTful，资源用 /:id 定位） ──

    def list_mcp_servers(self, params: dict | None = None) -> dict:
        """获取 MCP Server 列表
        GET /api/mcp?page=1&pageSize=20 → {items, total, page, pageSize}
        """
        return self.get("/api/mcp", params=params)

    def get_mcp_server(self, server_id: str) -> dict:
        """获取 MCP Server 详情
        GET /api/mcp/:id → mcp detail {id, name, type, enabled, summary, config, resourceAccess}
        """
        return self.get(f"/api/mcp/{server_id}")

    def create_mcp_server(self, data: dict) -> dict:
        """创建 MCP Server
        POST /api/mcp body: {name, type, command/url, ...} → mcp detail
        """
        return self.post("/api/mcp", json=data)

    def update_mcp_server(self, server_id: str, data: dict) -> dict:
        """更新 MCP Server（按 ID 定位）
        PUT /api/mcp/:id body: {type, command/url, ...} → mcp detail
        """
        return self.put(f"/api/mcp/{server_id}", json=data)

    def delete_mcp_server(self, server_id: str) -> dict:
        """删除 MCP Server
        DELETE /api/mcp/:id → {id, deleted: true}
        """
        return self.delete(f"/api/mcp/{server_id}")

    # ── Skill 模块 ──

    def list_skills(self, params: dict | None = None) -> dict:
        """获取 Skill 列表
        GET /api/skills?page=1&pageSize=20 → {items, total, page, pageSize}
        """
        return self.get("/api/skills", params=params)

    def get_skill(self, skill_id: str) -> dict:
        """获取 Skill 详情
        GET /api/skills/:id → skill detail
        """
        return self.get(f"/api/skills/{skill_id}")

    def delete_skill(self, skill_id: str) -> dict:
        """删除 Skill
        DELETE /api/skills/:id → {id, deleted: true}
        """
        return self.delete(f"/api/skills/{skill_id}")

    # ── Provider 模块（OpenAPI） ──

    def list_providers(self, params: dict | None = None) -> dict:
        """获取 Provider 列表
        GET /api/models/providers?page=1&pageSize=20 → {items, total, page, pageSize}
        """
        return self.get("/api/models/providers", params=params)

    def get_provider(self, provider_id: str) -> dict:
        """获取 Provider 详情
        GET /api/models/providers/:providerId → provider detail
        """
        return self.get(f"/api/models/providers/{provider_id}")

    def create_provider(self, data: dict) -> dict:
        """创建 Provider
        POST /api/models/providers body: {name, protocol, ...} → provider detail
        """
        return self.post("/api/models/providers", json=data)

    def update_provider(self, provider_id: str, data: dict) -> dict:
        """更新 Provider
        PUT /api/models/providers/:providerId body: {...} → provider detail
        """
        return self.put(f"/api/models/providers/{provider_id}", json=data)

    def delete_provider(self, provider_id: str) -> dict:
        """删除 Provider
        DELETE /api/models/providers/:providerId → {id, deleted: true}
        """
        return self.delete(f"/api/models/providers/{provider_id}")

    # ── Model 模块（OpenAPI） ──

    def list_models(self, provider_id: str, params: dict | None = None) -> dict:
        """获取 Model 列表
        GET /api/models/providers/:providerId/models → {items, total, page, pageSize}
        """
        return self.get(f"/api/models/providers/{provider_id}/models", params=params)

    def get_model(self, provider_id: str, model_id: str) -> dict:
        """获取 Model 详情
        GET /api/models/providers/:providerId/models/:id → model detail
        """
        return self.get(f"/api/models/providers/{provider_id}/models/{model_id}")

    def create_model(self, provider_id: str, data: dict) -> dict:
        """创建 Model
        POST /api/models/providers/:providerId/models body: {modelId, ...} → model detail
        """
        return self.post(f"/api/models/providers/{provider_id}/models", json=data)

    def update_model(self, provider_id: str, model_id: str, data: dict) -> dict:
        """更新 Model
        PUT /api/models/providers/:providerId/models/:id body: {...} → model detail
        """
        return self.put(f"/api/models/providers/{provider_id}/models/{model_id}", json=data)

    def delete_model(self, provider_id: str, model_id: str) -> dict:
        """删除 Model
        DELETE /api/models/providers/:providerId/models/:id → {id, deleted: true}
        """
        return self.delete(f"/api/models/providers/{provider_id}/models/{model_id}")

    # ── Knowledge Bases 模块 ──

    def list_knowledge_bases(self, params: dict | None = None) -> dict:
        """获取知识库列表
        GET /api/knowledge-bases?page=1&pageSize=20 → {items, total, page, pageSize}
        """
        return self.get("/api/knowledge-bases", params=params)

    # ── System API 模块（/api/system，需要 System API Key） ──

    def list_users(self, params: dict | None = None) -> dict:
        """获取用户列表
        GET /api/system/users → {items, total, page, pageSize}
        """
        return self.get("/api/system/users", params=params)

    def get_user(self, user_id: str) -> dict:
        """获取用户详情
        GET /api/system/users/:id → user detail
        """
        return self.get(f"/api/system/users/{user_id}")

    def create_user(self, data: dict) -> dict:
        """创建用户
        POST /api/system/users body: {name, email, ...} → user detail
        """
        return self.post("/api/system/users", json=data)

    def delete_user(self, user_id: str) -> dict:
        """删除用户
        DELETE /api/system/users/:id → {success: true}
        """
        return self.delete(f"/api/system/users/{user_id}")

    def list_organizations(self, params: dict | None = None) -> dict:
        """获取组织列表
        GET /api/system/organizations → {items, total, page, pageSize}
        """
        return self.get("/api/system/organizations", params=params)

    def get_organization(self, org_id: str) -> dict:
        """获取组织详情
        GET /api/system/organizations/:id → organization detail
        """
        return self.get(f"/api/system/organizations/{org_id}")

    def create_organization(self, data: dict) -> dict:
        """创建组织
        POST /api/system/organizations body: {name, ...} → organization detail
        """
        return self.post("/api/system/organizations", json=data)

    def delete_organization(self, org_id: str) -> dict:
        """删除组织
        DELETE /api/system/organizations/:id → {success: true}
        """
        return self.delete(f"/api/system/organizations/{org_id}")

    def list_user_api_keys(self, user_id: str, params: dict | None = None) -> dict:
        """获取用户 API Key 列表
        GET /api/system/users/:userId/api-keys → {items, total, page, pageSize}
        """
        return self.get(f"/api/system/users/{user_id}/api-keys", params=params)

    def reset_user_password(self, data: dict) -> dict:
        """重置用户密码
        POST /api/system/users/reset-password body: {userId/email/phoneNumber, newPassword}
        """
        return self.post("/api/system/users/reset-password", json=data)

    def list_user_organizations(self, user_id: str, params: dict | None = None) -> dict:
        """获取用户所属组织列表
        GET /api/system/users/:userId/organizations → {items, total, page, pageSize}
        """
        return self.get(f"/api/system/users/{user_id}/organizations", params=params)

    def add_organization_member(self, org_id: str, data: dict) -> dict:
        """添加组织成员
        POST /api/system/organizations/:id/members body: {userId, role}
        """
        return self.post(f"/api/system/organizations/{org_id}/members", json=data)

    def create_api_key(self, data: dict) -> dict:
        """代用户创建 API Key
        POST /api/system/api-keys body: {userId, organizationId, role, expiresAt}
        """
        return self.post("/api/system/api-keys", json=data)

    def delete_api_key(self, key_id: str) -> dict:
        """删除用户 API Key
        DELETE /api/system/api-keys/:id → {id, deleted: true}
        """
        return self.delete(f"/api/system/api-keys/{key_id}")

    # ── Instance Connect 模块 ──

    def connect_instance(self, agent_id: str, data: dict | None = None) -> dict:
        """连接 Agent Instance
        POST /api/agents/:agentId/instances/connect body: {...}
        """
        return self.post(f"/api/agents/{agent_id}/instances/connect", json=data or {})

    # ── Workflow 模块 ──

    def execute_workflow(self, workflow_id: str, data: dict) -> dict:
        """执行工作流
        POST /api/workflows/:workflowId/execute body: {inputs, mode}
        """
        return self.post(f"/api/workflows/{workflow_id}/execute", json=data)
