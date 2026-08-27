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

    def __init__(self, base_url: str, api_key: str, system_api_key: str = "", timeout: int = 30):
        super().__init__(
            base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )
        self._system_api_key = system_api_key

    def _system_get(self, path: str, params: dict | None = None) -> dict:
        """System API 专用 GET：使用 system_api_key 替代用户 API Key"""
        import httpx
        headers = {"Authorization": f"Bearer {self._system_api_key}"}
        resp = httpx.get(
            f"{self.base_url}{path}",
            params=params,
            headers=headers,
            timeout=30,
            verify=False,
        )
        resp.raise_for_status()
        return resp.json()

    def _system_get_raw(self, path: str, params: dict | None = None) -> bytes:
        """System API 专用 GET（返回原始字节，用于文件下载）"""
        import httpx
        headers = {"Authorization": f"Bearer {self._system_api_key}"}
        resp = httpx.get(
            f"{self.base_url}{path}",
            params=params,
            headers=headers,
            timeout=30,
            verify=False,
        )
        resp.raise_for_status()
        return resp.content

    def _system_request(self, method: str, path: str, params: dict | None = None, json: dict | None = None) -> dict:
        """System API 通用请求：用 system_api_key 替代用户 Key，复用重试/节流逻辑

        /api/system/* 端点需要 System API Key（RCS_SYSTEM_API_KEYS），普通 API Key 返回 401。
        返回裸 JSON（无 {success, data} 包装），错误码由 _parse_response 抛 HTTPStatusError。
        """
        headers = {"Authorization": f"Bearer {self._system_api_key}"}
        kwargs: dict = {"params": params, "headers": headers}
        if json is not None:
            kwargs["json"] = json
        resp = self._request_with_retry(method, path, **kwargs)
        return self._parse_response(resp)

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
        return self._system_request("get", "/api/system/users", params=params)

    def get_user(self, user_id: str) -> dict:
        """获取用户详情
        GET /api/system/users/:id → user detail
        """
        return self._system_request("get", f"/api/system/users/{user_id}")

    def create_user(self, data: dict) -> dict:
        """创建用户
        POST /api/system/users body: {name, email, ...} → user detail
        """
        return self._system_request("post", "/api/system/users", json=data)

    def delete_user(self, user_id: str) -> dict:
        """删除用户
        DELETE /api/system/users/:id → {success: true}
        """
        return self._system_request("delete", f"/api/system/users/{user_id}")

    def list_organizations(self, params: dict | None = None) -> dict:
        """获取组织列表
        GET /api/system/organizations → {items, total, page, pageSize}
        """
        return self._system_request("get", "/api/system/organizations", params=params)

    def get_organization(self, org_id: str) -> dict:
        """获取组织详情
        GET /api/system/organizations/:id → organization detail
        """
        return self._system_request("get", f"/api/system/organizations/{org_id}")

    def create_organization(self, data: dict) -> dict:
        """创建组织
        POST /api/system/organizations body: {name, ...} → organization detail
        """
        return self._system_request("post", "/api/system/organizations", json=data)

    def delete_organization(self, org_id: str) -> dict:
        """删除组织
        DELETE /api/system/organizations/:id → {success: true}
        """
        return self._system_request("delete", f"/api/system/organizations/{org_id}")

    def list_user_api_keys(self, user_id: str, params: dict | None = None) -> dict:
        """获取用户 API Key 列表
        GET /api/system/users/:userId/api-keys → {items, total, page, pageSize}
        """
        return self._system_request("get", f"/api/system/users/{user_id}/api-keys", params=params)

    def reset_user_password(self, data: dict) -> dict:
        """重置用户密码
        POST /api/system/users/reset-password body: {userId/email/phoneNumber, newPassword}
        """
        return self._system_request("post", "/api/system/users/reset-password", json=data)

    def list_user_organizations(self, user_id: str, params: dict | None = None) -> dict:
        """获取用户所属组织列表
        GET /api/system/users/:userId/organizations → {items, total, page, pageSize}
        """
        return self._system_request("get", f"/api/system/users/{user_id}/organizations", params=params)

    def add_organization_member(self, org_id: str, data: dict) -> dict:
        """添加组织成员
        POST /api/system/organizations/:id/members body: {userId, role}
        """
        return self._system_request("post", f"/api/system/organizations/{org_id}/members", json=data)

    def create_api_key(self, data: dict) -> dict:
        """代用户创建 API Key
        POST /api/system/api-keys body: {userId, organizationId, role, expiresAt}
        """
        return self._system_request("post", "/api/system/api-keys", json=data)

    def delete_api_key(self, key_id: str) -> dict:
        """删除用户 API Key
        DELETE /api/system/api-keys/:id → {id, deleted: true}
        """
        return self._system_request("delete", f"/api/system/api-keys/{key_id}")

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

    # ── Sandbox 模块（/api/system，需要 System API Key） ──

    def list_sandbox_pools(self, params: dict | None = None) -> dict:
        """获取沙盒池列表
        GET /api/system/sandbox-pools → pool list
        """
        return self._system_request("get", "/api/system/sandbox-pools", params=params)

    def create_sandbox_pool(self, data: dict) -> dict:
        """创建沙盒池
        POST /api/system/sandbox-pools body: {name, template, ...} → pool detail
        """
        return self._system_request("post", "/api/system/sandbox-pools", json=data)

    def get_sandbox_pool(self, pool_id: str) -> dict:
        """获取沙盒池详情
        GET /api/system/sandbox-pools/:poolId → pool detail
        """
        return self._system_request("get", f"/api/system/sandbox-pools/{pool_id}")

    def update_sandbox_pool(self, pool_id: str, data: dict) -> dict:
        """更新沙盒池
        PUT /api/system/sandbox-pools/:poolId body: {...} → pool detail
        """
        return self._system_request("put", f"/api/system/sandbox-pools/{pool_id}", json=data)

    def delete_sandbox_pool(self, pool_id: str) -> dict:
        """删除沙盒池
        DELETE /api/system/sandbox-pools/:poolId → {deleted: true}
        """
        return self._system_request("delete", f"/api/system/sandbox-pools/{pool_id}")

    def list_sandbox_instances(self, params: dict | None = None) -> dict:
        """获取沙盒实例列表
        GET /api/system/sandbox-instances → instance list
        """
        return self._system_request("get", "/api/system/sandbox-instances", params=params)

    def get_sandbox_instance(self, instance_id: str) -> dict:
        """获取沙盒实例详情
        GET /api/system/sandbox-instances/:instanceId → instance detail
        """
        return self._system_request("get", f"/api/system/sandbox-instances/{instance_id}")

    def update_sandbox_instance(self, instance_id: str, data: dict) -> dict:
        """更新沙盒实例
        PUT /api/system/sandbox-instances/:instanceId body: {resourceOverrides} → instance detail
        """
        return self._system_request("put", f"/api/system/sandbox-instances/{instance_id}", json=data)

    def delete_sandbox_instance(self, instance_id: str) -> dict:
        """删除沙盒实例
        DELETE /api/system/sandbox-instances/:instanceId → {deleted: true}
        """
        return self._system_request("delete", f"/api/system/sandbox-instances/{instance_id}")

    def rebuild_sandbox_instances(self, data: dict) -> dict:
        """重建沙盒实例
        POST /api/system/sandbox-instances/rebuild body: {poolId, ...} → rebuild result
        """
        return self._system_request("post", "/api/system/sandbox-instances/rebuild", json=data)

    # ── System Logs 模块（/api/system/logs，System API Key 认证） ──

    def _unwrap(self, resp: dict) -> dict:
        """解包 {success, data} 响应，返回 data 部分"""
        if not resp.get("success"):
            error = resp.get("error", {})
            code = error.get("code", "UNKNOWN")
            message = error.get("message", "")
            raise RuntimeError(f"System API error: {code} - {message}")
        return resp.get("data")

    def list_system_log_files(self) -> dict:
        """列出系统日志文件
        GET /api/system/logs → {success, data: {files: [...]}}
        返回 data 部分：{files: [{name, size, modifiedAt, isErrorLog}]}
        """
        resp = self._system_get("/api/system/logs")
        return self._unwrap(resp)

    def search_system_logs(self, params: dict) -> dict:
        """搜索系统日志内容
        GET /api/system/logs/search?file=xxx&q=yyy&errorOnly=false&limit=500
        → {success, data: {file, entries, totalMatches, truncated}}
        返回 data 部分
        """
        resp = self._system_get("/api/system/logs/search", params=params)
        return self._unwrap(resp)

    def download_system_log(self, file_name: str) -> bytes:
        """下载系统日志文件（返回原始字节，非 JSON）
        GET /api/system/logs/download?file=xxx → text/plain stream
        """
        return self._system_get_raw("/api/system/logs/download", params={"file": file_name})

    # ── System Observer 模块（/api/system/observer，System API Key 认证） ──

    def get_observer_acp_link(self) -> dict:
        """获取 ACP 活跃链接观察视图
        GET /api/system/observer/acp-link
        → {success, data: {generatedAt, kind, total, trees, integrity, names}}
        返回 data 部分
        """
        resp = self._system_get("/api/system/observer/acp-link")
        return self._unwrap(resp)

    # ── System People Tree 模块（/api/system/people-tree，System API Key 认证） ──

    def get_people_tree(self) -> dict:
        """获取组织人员智能体层级
        GET /api/system/people-tree
        → {success, data: {organizations: [...]}}
        返回 data 部分
        """
        resp = self._system_get("/api/system/people-tree")
        return self._unwrap(resp)
