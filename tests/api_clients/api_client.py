# tests/api_clients/api_client.py
"""/api/v1/* 对外接口客户端（API Key 认证）

对外 OpenAPI 特点（FenixAgent main e01f1bb7e 起重整为 v1）：
- 业务接口前缀 /api/v1/（平台系统接口仍是 /api/system/）
- RESTful 风格：用 /:id 定位资源，更新统一用 PATCH
- 列表接口带分页 {items, total, page, pageSize}
- 响应统一信封 {success: true, data}，错误 {success: false, error: {code, message}}
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

    def _system_raw_response(self, path: str, params: dict | None = None) -> "httpx.Response":
        """System API 专用 GET，返回原始 httpx.Response（供需要读响应头的用例使用）"""
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
        return resp

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

    def _v1(self, method: str, path: str, params: dict | None = None, json: dict | None = None, **extra) -> dict:
        """v1 业务接口通用请求：解包 {success, data}，错误由 _parse_response 抛 HTTPStatusError

        extra 透传给 httpx（如 multipart 的 data/files），并支持 get_v1/post_v1 等场景复用。
        """
        kwargs: dict = {"params": params, **extra}
        if json is not None:
            kwargs["json"] = json
        resp = self._request_with_retry(method, path, **kwargs)
        body = self._parse_response(resp)
        return self._unwrap(body)

    def _v1_raw(self, method: str, path: str, params: dict | None = None, **extra) -> "httpx.Response":
        """v1 接口返回原始 Response（用于文件下载、流式响应等非 JSON 场景）"""
        kwargs: dict = {"params": params, **extra}
        resp = self._request_with_retry(method, path, **kwargs)
        resp.raise_for_status()
        return resp

    # ── Agent 模块 ──

    def list_agents(self, params: dict | None = None) -> dict:
        """获取 Agent 列表
        GET /api/v1/agents?page=1&pageSize=20 → {items, total, page, pageSize}
        """
        return self._v1("get", "/api/v1/agents", params=params)

    def get_agent(self, agent_id: str) -> dict:
        """获取 Agent 详情
        GET /api/v1/agents/:id → agent detail
        """
        return self._v1("get", f"/api/v1/agents/{agent_id}")

    def create_agent(self, data: dict) -> dict:
        """创建 Agent（201）
        POST /api/v1/agents body: {name, description, ...} → agent detail
        """
        return self._v1("post", "/api/v1/agents", json=data)

    def update_agent(self, agent_id: str, data: dict) -> dict:
        """更新 Agent
        PATCH /api/v1/agents/:id body: {description, ...} → agent detail
        """
        return self._v1("patch", f"/api/v1/agents/{agent_id}", json=data)

    def delete_agent(self, agent_id: str) -> None:
        """删除 Agent
        DELETE /api/v1/agents/:id → data: null
        """
        return self._v1("delete", f"/api/v1/agents/{agent_id}")

    # ── MCP 模块（RESTful，资源用 /:id 定位） ──

    def list_mcp_servers(self, params: dict | None = None) -> dict:
        """获取 MCP Server 列表
        GET /api/v1/mcp-servers?page=1&pageSize=20 → {items, total, page, pageSize}
        """
        return self._v1("get", "/api/v1/mcp-servers", params=params)

    def get_mcp_server(self, server_id: str) -> dict:
        """获取 MCP Server 详情
        GET /api/v1/mcp-servers/:id → {id, name, type, enabled, summary, config, headerNames, ...}
        """
        return self._v1("get", f"/api/v1/mcp-servers/{server_id}")

    def create_mcp_server(self, data: dict) -> dict:
        """创建 MCP Server（201）
        POST /api/v1/mcp-servers body: {name, config: {type: local|remote|streamable-http, ...}}
        """
        return self._v1("post", "/api/v1/mcp-servers", json=data)

    def update_mcp_server(self, server_id: str, data: dict) -> dict:
        """更新 MCP Server（enabled / config / publicReadable 三选一）
        PATCH /api/v1/mcp-servers/:id → mcp detail
        """
        return self._v1("patch", f"/api/v1/mcp-servers/{server_id}", json=data)

    def delete_mcp_server(self, server_id: str) -> None:
        """删除 MCP Server
        DELETE /api/v1/mcp-servers/:id → data: null
        """
        return self._v1("delete", f"/api/v1/mcp-servers/{server_id}")

    # ── Skill 模块 ──

    def list_skills(self, params: dict | None = None) -> dict:
        """获取 Skill 列表
        GET /api/v1/skills?page=1&pageSize=20 → {items, total, page, pageSize}
        """
        return self._v1("get", "/api/v1/skills", params=params)

    def get_skill(self, skill_id: str) -> dict:
        """获取 Skill 详情
        GET /api/v1/skills/:id → {id, name, description, scope, access, content, metadata}
        """
        return self._v1("get", f"/api/v1/skills/{skill_id}")

    def create_skill(self, manifest: list | str, files: list[tuple], overwrite: str = "false") -> dict:
        """导入 Skill（multipart）

        POST /api/v1/skills
        - manifest: [{"skillName": "demo", "relativePath": "SKILL.md"}]，或已序列化的 JSON 字符串
        - files: [(filename, bytes), ...]，与 manifest 条目顺序一一对应
        - overwrite: "true" / "false"
        新建返回 201，覆盖返回 200；data 为 skill detail。
        """
        import json as _json
        manifest_raw = manifest if isinstance(manifest, str) else _json.dumps(manifest, ensure_ascii=False)
        multipart = [("files", (name, content, "application/octet-stream")) for name, content in files]
        return self._v1(
            "post",
            "/api/v1/skills",
            data={"manifest": manifest_raw, "overwrite": overwrite},
            files=multipart,
        )

    def update_skill(self, skill_id: str, data: dict) -> dict:
        """更新 Skill（content / description / metadata / publicReadable，空更新报错）
        PATCH /api/v1/skills/:id → skill detail
        """
        return self._v1("patch", f"/api/v1/skills/{skill_id}", json=data)

    def delete_skill(self, skill_id: str) -> None:
        """删除 Skill
        DELETE /api/v1/skills/:id → data: null
        """
        return self._v1("delete", f"/api/v1/skills/{skill_id}")

    # ── Provider 模块（OpenAPI） ──

    def list_providers(self, params: dict | None = None) -> dict:
        """获取 Provider 列表
        GET /api/v1/providers?page=1&pageSize=20 → {items, total, page, pageSize}
        """
        return self._v1("get", "/api/v1/providers", params=params)

    def get_provider(self, provider_id: str) -> dict:
        """获取 Provider 详情
        GET /api/v1/providers/:providerId → provider detail
        """
        return self._v1("get", f"/api/v1/providers/{provider_id}")

    def create_provider(self, data: dict) -> dict:
        """创建 Provider（201）
        POST /api/v1/providers body: {name, protocol, ...} → provider detail
        """
        return self._v1("post", "/api/v1/providers", json=data)

    def update_provider(self, provider_id: str, data: dict) -> dict:
        """更新 Provider
        PATCH /api/v1/providers/:providerId body: {...} → provider detail
        """
        return self._v1("patch", f"/api/v1/providers/{provider_id}", json=data)

    def delete_provider(self, provider_id: str) -> None:
        """删除 Provider
        DELETE /api/v1/providers/:providerId → data: null
        """
        return self._v1("delete", f"/api/v1/providers/{provider_id}")

    # ── Model 模块（OpenAPI） ──

    def list_models(self, provider_id: str, params: dict | None = None) -> dict:
        """获取 Model 列表
        GET /api/v1/providers/:providerId/models → {items, total, page, pageSize}
        """
        return self._v1("get", f"/api/v1/providers/{provider_id}/models", params=params)

    def get_model(self, provider_id: str, model_id: str) -> dict:
        """获取 Model 详情
        GET /api/v1/providers/:providerId/models/:id → model detail
        """
        return self._v1("get", f"/api/v1/providers/{provider_id}/models/{model_id}")

    def create_model(self, provider_id: str, data: dict) -> dict:
        """创建 Model（201）
        POST /api/v1/providers/:providerId/models body: {modelId, ...} → model detail
        """
        return self._v1("post", f"/api/v1/providers/{provider_id}/models", json=data)

    def update_model(self, provider_id: str, model_id: str, data: dict) -> dict:
        """更新 Model
        PATCH /api/v1/providers/:providerId/models/:id body: {...} → model detail
        """
        return self._v1("patch", f"/api/v1/providers/{provider_id}/models/{model_id}", json=data)

    def delete_model(self, provider_id: str, model_id: str) -> None:
        """删除 Model
        DELETE /api/v1/providers/:providerId/models/:id → data: null
        """
        return self._v1("delete", f"/api/v1/providers/{provider_id}/models/{model_id}")

    # ── Knowledge Bases 模块（只读） ──

    def list_knowledge_bases(self, params: dict | None = None) -> dict:
        """获取知识库列表（v1 仅提供只读列表）
        GET /api/v1/knowledge-bases?page=1&pageSize=20 → {items, total, page, pageSize}
        """
        return self._v1("get", "/api/v1/knowledge-bases", params=params)

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

    # ── Instance 模块 ──

    def connect_instance(self, agent_id: str, data: dict | None = None) -> dict:
        """连接 Agent Instance（必要时自动创建 environment 并启动实例）
        POST /api/v1/agents/:id/instances/connect
        body: {instanceId?: "inst_..."}（可选，用于复用已有实例）
        → {agentConfigId, environmentId, instanceId, status: "running", runtimeGeneration, relay: {wsUrl}}
        """
        return self._v1("post", f"/api/v1/agents/{agent_id}/instances/connect", json=data or {})

    def list_instances(self, agent_id: str, params: dict | None = None) -> dict:
        """查询 Agent 的现有实例
        GET /api/v1/agents/:id/instances → {items, total, page, pageSize}
        """
        return self._v1("get", f"/api/v1/agents/{agent_id}/instances", params=params)

    def get_instance(self, instance_id: str) -> dict:
        """查询现有实例
        GET /api/v1/instances/:id → instance detail
        """
        return self._v1("get", f"/api/v1/instances/{instance_id}")

    def stop_instance(self, instance_id: str) -> None:
        """严格停止实例
        POST /api/v1/instances/:id/stop → data: null
        """
        return self._v1("post", f"/api/v1/instances/{instance_id}/stop")

    def restart_instance(self, instance_id: str) -> dict:
        """重启实例
        POST /api/v1/instances/:id/restart → instance detail
        """
        return self._v1("post", f"/api/v1/instances/{instance_id}/restart")

    # ── Workflow 模块（经典引擎） ──

    def execute_workflow(self, workflow_id: str, data: dict) -> dict:
        """执行工作流
        POST /api/v1/workflows/:workflowId/execute body: {inputs, mode: sync|async, version?, timeout?}
        """
        return self._v1("post", f"/api/v1/workflows/{workflow_id}/execute", json=data)

    # ── Workflow v2 模块 ──

    def run_workflow_v2(self, workflow_id: str, data: dict | None = None) -> dict:
        """触发工作流 v2 运行
        POST /api/v1/workflow-v2/workflows/:id/run
        body: {parameters?: object|string, isAsync?: boolean, ext?: {user_id?}}
        → {executeId, data, token, cost, debugUrl}
        """
        return self._v1("post", f"/api/v1/workflow-v2/workflows/{workflow_id}/run", json=data or {})

    # ── Workspace 文件模块 ──

    def list_workspace_files(self, environment_id: str) -> dict:
        """查询 Environment 工作区文件树
        GET /api/v1/environments/:environmentId/workspace/files
        → {environmentId, paths, mtimes?, errors?}
        """
        return self._v1("get", f"/api/v1/environments/{environment_id}/workspace/files")

    def download_workspace_file(self, environment_id: str, path: str) -> bytes:
        """下载工作区文件（原始文件流）
        GET /api/v1/environments/:environmentId/workspace/files/download?path=...
        """
        resp = self._v1_raw(
            "get",
            f"/api/v1/environments/{environment_id}/workspace/files/download",
            params={"path": path},
        )
        return resp.content

    def upload_workspace_files(
        self,
        environment_id: str,
        files: list[tuple],
        path: str = "user",
        relative_paths: str | None = None,
    ) -> dict:
        """上传文件到工作区（multipart）
        POST /api/v1/environments/:environmentId/workspace/files
        - files: [(filename, bytes), ...]
        - path: 工作区内相对目录，省略为 user，"" 或 "." 表示根目录
        → {environmentId, written, skipped, ...}
        """
        multipart = [("files", (name, content, "application/octet-stream")) for name, content in files]
        data = {"path": path}
        if relative_paths is not None:
            data["relativePaths"] = relative_paths
        return self._v1(
            "post",
            f"/api/v1/environments/{environment_id}/workspace/files",
            data=data,
            files=multipart,
        )

    # ── OpenAI 兼容对话模块 ──

    def chat_completions(self, data: dict) -> dict:
        """OpenAI 兼容对话（非流式）
        POST /api/v1/chat/completions
        body: {model: <agentConfigId uuid>, messages: [{role, content}], stream: false}
        → {id, object: "chat.completion", created, model, choices: [...]}
        """
        payload = {"stream": False, **data}
        # chat 走 OpenAI 原生格式，不是 {success, data} 信封，不能 _unwrap
        resp = self._request_with_retry("post", "/api/v1/chat/completions", json=payload)
        return self._parse_response(resp)

    def chat_completions_raw(self, data: dict) -> "httpx.Response":
        """OpenAI 兼容对话（原始响应，供流式 SSE 用例读取）"""
        payload = {"stream": False, **data}
        return self._v1_raw("post", "/api/v1/chat/completions", json=payload)

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
            raise RuntimeError(f"API error: {code} - {message}")
        return resp.get("data")

    def list_system_log_sources(self) -> dict:
        """列出可检索的日志源
        GET /api/system/logs → {success, data: {sources: [...]}}
        返回 data 部分：{sources: [{id, kind, date, size, modifiedAt}]}
        """
        resp = self._system_get("/api/system/logs")
        return self._unwrap(resp)

    def search_system_logs(self, params: dict) -> dict:
        """检索系统日志投影
        GET /api/system/logs/search?sourceId=xxx&q=yyy&errorOnly=false&limit=500
        → {success, data: {source, entries, totalMatches, truncated}}
        返回 data 部分
        """
        resp = self._system_get("/api/system/logs/search", params=params)
        return self._unwrap(resp)

    def download_system_log(self, source_id: str) -> bytes:
        """导出系统日志投影为 JSON Lines（返回原始字节，非 JSON 包装）
        GET /api/system/logs/download?sourceId=xxx → application/x-ndjson
        """
        return self._system_get_raw("/api/system/logs/download", params={"sourceId": source_id})

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

    # ── Auth 模块（/api/auth，无需 System Key） ──

    def get_auth_encryption_key(self) -> dict:
        """获取当前会话的加密公钥
        GET /api/auth/encryption-key → {key}
        """
        return self.get("/api/auth/encryption-key")

    def get_auth_signup_status(self) -> dict:
        """查询是否开放注册
        GET /api/auth/signup-status → {signupAllowed}
        """
        return self.get("/api/auth/signup-status")

    # ── System Channels 模块（/api/system/channels，System API Key） ──

    def list_system_channels(self) -> dict:
        """获取渠道接入总览
        GET /api/system/channels → {success, data: {status, organizations}}
        返回 data 部分
        """
        resp = self._system_get("/api/system/channels")
        return self._unwrap(resp)

    # ── System Model Gateway 模块（/api/system/model-gateway，System API Key） ──

    def get_system_model_gateway_config(self) -> dict:
        """获取模型网关配置
        GET /api/system/model-gateway/config → {provider, adminUiUrl, ...}
        """
        return self._system_request("get", "/api/system/model-gateway/config")

    def list_system_model_gateway_keys(self, params: dict | None = None) -> dict:
        """获取模型网关 Key 列表
        GET /api/system/model-gateway/keys → {items, total}
        """
        return self._system_request("get", "/api/system/model-gateway/keys", params=params)

    def list_system_model_gateway_budgets(self, params: dict | None = None) -> dict:
        """获取模型网关预算列表
        GET /api/system/model-gateway/budgets → {items, total}
        """
        return self._system_request("get", "/api/system/model-gateway/budgets", params=params)

    def get_system_model_gateway_models_status(self) -> dict:
        """获取模型同步状态
        GET /api/system/model-gateway/models/status → {status, changes, models}
        """
        return self._system_request("get", "/api/system/model-gateway/models/status")

    def list_system_model_gateway_subjects_users(self, params: dict | None = None) -> dict:
        """获取模型网关计费主体（用户）
        GET /api/system/model-gateway/subjects/users → {items, total}
        """
        return self._system_request(
            "get", "/api/system/model-gateway/subjects/users", params=params
        )

    def list_system_model_gateway_subjects_agents(self, params: dict | None = None) -> list:
        """获取模型网关计费主体（Agent）
        GET /api/system/model-gateway/subjects/agents → [{id, name, ...}]
        """
        return self._system_request(
            "get", "/api/system/model-gateway/subjects/agents", params=params
        )

    def get_system_model_gateway_usage(self, params: dict | None = None) -> dict:
        """获取模型网关用量
        GET /api/system/model-gateway/usage?startAt=... → {items, ...}
        """
        return self._system_request("get", "/api/system/model-gateway/usage", params=params)

    # ── System Plugin Market 模块（/api/system/plugin-market，System API Key） ──

    def list_system_plugin_market_packages(self, params: dict | None = None) -> dict:
        """列出插件市场包
        GET /api/system/plugin-market/packages → {success, data: {packages, total}}
        返回 data 部分
        """
        resp = self._system_get("/api/system/plugin-market/packages", params=params)
        return self._unwrap(resp)

    def get_system_plugin_market_package(self, slug: str) -> dict:
        """获取插件市场包详情
        GET /api/system/plugin-market/packages/:slug → package detail
        """
        return self._system_request("get", f"/api/system/plugin-market/packages/{slug}")

    # ── System Sandbox Cluster 模块（/api/system/sandbox-cluster，System API Key） ──

    def list_sandbox_cluster_pools(self, params: dict | None = None) -> list:
        """获取沙盒集群池列表
        GET /api/system/sandbox-cluster/pools → [{id, name, status, ...}]
        """
        return self._system_request("get", "/api/system/sandbox-cluster/pools", params=params)

    def get_sandbox_cluster_pool(self, pool_id: str) -> dict:
        """获取沙盒集群池详情
        GET /api/system/sandbox-cluster/pools/:poolId → pool detail
        """
        return self._system_request("get", f"/api/system/sandbox-cluster/pools/{pool_id}")

    def list_sandbox_cluster_servers(self, params: dict | None = None) -> list:
        """获取沙盒集群服务器列表
        GET /api/system/sandbox-cluster/servers → [{id, poolId, status, ...}]
        """
        return self._system_request("get", "/api/system/sandbox-cluster/servers", params=params)

    def get_sandbox_cluster_server(self, server_id: str) -> dict:
        """获取沙盒集群服务器详情
        GET /api/system/sandbox-cluster/servers/:serverId → server detail
        """
        return self._system_request("get", f"/api/system/sandbox-cluster/servers/{server_id}")

    # ── System Sandbox Server 模块（/api/system/sandbox-server，System API Key） ──

    def list_sandbox_server_sandboxes(self, server_id: str, params: dict | None = None) -> dict:
        """列出服务器上的沙盒
        GET /api/system/sandbox-server/servers/:serverId/sandboxes → {items, ...}
        """
        return self._system_request(
            "get", f"/api/system/sandbox-server/servers/{server_id}/sandboxes", params=params
        )

    def get_sandbox_server_sandbox(self, server_id: str, sandbox_id: str) -> dict:
        """获取服务器上的沙盒详情
        GET /api/system/sandbox-server/servers/:serverId/sandboxes/:sandboxId
        """
        return self._system_request(
            "get", f"/api/system/sandbox-server/servers/{server_id}/sandboxes/{sandbox_id}"
        )

    def get_sandbox_server_sandbox_diagnostics(self, server_id: str, sandbox_id: str) -> dict:
        """获取沙盒诊断信息
        GET /api/system/sandbox-server/servers/:serverId/sandboxes/:sandboxId/diagnostics
        """
        return self._system_request(
            "get",
            f"/api/system/sandbox-server/servers/{server_id}/sandboxes/{sandbox_id}/diagnostics",
        )
