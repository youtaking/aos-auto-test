# tests/api_clients/web_client.py
"""/web/* 控制台接口客户端（better-auth session cookie 认证）

控制台接口特点：
- 路径前缀 /web/
- action 风格：用 ?name=xxx 定位资源，而非 RESTful 的 /:id
- 响应统一包装为 {success, data} 格式
"""
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

    def _unwrap(self, resp: dict) -> dict:
        """解包 {success, data} 响应，返回 data 部分"""
        if not resp.get("success"):
            error = resp.get("error", {})
            raise RuntimeError(f"Web API error: {error.get('code', 'UNKNOWN')} - {error.get('message', '')}")
        return resp.get("data")

    # ── Agent 模块 ──

    def list_agents(self) -> dict:
        """获取 Agent 列表
        GET /web/config/agents → {success, data: {default_agent, agents: [...]}}
        """
        resp = self.get("/web/config/agents")
        return self._unwrap(resp)

    def get_agent(self, name: str) -> dict:
        """获取单个 Agent 详情（按名称查询）
        GET /web/config/agents?name=xxx → {success, data: {agent detail}}
        """
        resp = self.get("/web/config/agents", params={"name": name})
        return self._unwrap(resp)

    def create_agent(self, data: dict) -> dict:
        """创建 Agent
        POST /web/config/agents body: {name, data} → {success, data: {name, id}}
        """
        name = data.get("name", "")
        body = {"name": name, "data": {k: v for k, v in data.items() if k != "name"}}
        resp = self.post("/web/config/agents", json=body)
        return self._unwrap(resp)

    def update_agent(self, name: str, data: dict) -> dict:
        """更新 Agent（按名称定位）
        PUT /web/config/agents?name=xxx body: {data} → {success, data: {name, ...}}
        """
        resp = self.put("/web/config/agents", params={"name": name}, json={"data": data})
        return self._unwrap(resp)

    def delete_agent(self, name: str) -> dict:
        """删除 Agent（按名称定位）
        DELETE /web/config/agents?name=xxx → {success, data: null}
        """
        resp = self.delete("/web/config/agents", params={"name": name})
        return self._unwrap(resp)

    def get_agent_templates(self) -> dict:
        """获取 Agent 模板列表
        GET /web/config/agents/templates → {success, data: {templates: [...]}}
        """
        resp = self.get("/web/config/agents/templates")
        return self._unwrap(resp)

    def set_default_agent(self, name: str) -> dict:
        """设置默认 Agent
        POST /web/config/agents/default body: {name} → {success, data: {default_agent}}
        """
        resp = self.post("/web/config/agents/default", json={"name": name})
        return self._unwrap(resp)

    # ── MCP 模块（action 风格，资源用 ?name=xxx 定位） ──

    def list_mcp_servers(self) -> dict:
        """获取 MCP Server 列表
        GET /web/config/mcp → {success, data: {servers: [...]}}
        """
        resp = self.get("/web/config/mcp")
        return self._unwrap(resp)

    def get_mcp_server(self, name: str) -> dict:
        """获取单个 MCP Server 详情（按名称查询）
        GET /web/config/mcp?name=xxx → {success, data: {name, config, resourceAccess}}
        """
        resp = self.get("/web/config/mcp", params={"name": name})
        return self._unwrap(resp)

    def create_mcp_server(self, data: dict) -> dict:
        """创建 MCP Server
        POST /web/config/mcp body: {name, config: {...}} → {success, data: {name}}
        data 中 name 单独提取，其余字段放入 config
        """
        name = data.get("name", "")
        config = {k: v for k, v in data.items() if k != "name"}
        resp = self.post("/web/config/mcp", json={"name": name, "config": config})
        return self._unwrap(resp)

    def update_mcp_server(self, name: str, config: dict) -> dict:
        """更新 MCP Server（按名称定位）
        PUT /web/config/mcp?name=xxx body: {config: {...}} → {success, data: {name}}
        """
        resp = self.put("/web/config/mcp", params={"name": name}, json={"config": config})
        return self._unwrap(resp)

    def delete_mcp_server(self, name: str) -> dict:
        """删除 MCP Server（按名称定位）
        DELETE /web/config/mcp?name=xxx → {success, data: null}
        """
        resp = self.delete("/web/config/mcp", params={"name": name})
        return self._unwrap(resp)

    def enable_mcp_server(self, name: str) -> dict:
        """启用 MCP Server
        POST /web/config/mcp/actions/enable?name=xxx → {success, data: {name, enabled: true}}
        """
        resp = self.post("/web/config/mcp/actions/enable", params={"name": name})
        return self._unwrap(resp)

    def disable_mcp_server(self, name: str) -> dict:
        """禁用 MCP Server
        POST /web/config/mcp/actions/disable?name=xxx → {success, data: {name, enabled: false}}
        """
        resp = self.post("/web/config/mcp/actions/disable", params={"name": name})
        return self._unwrap(resp)

    def list_mcp_tools(self, name: str) -> dict:
        """获取 MCP Server 的缓存工具列表
        GET /web/config/mcp/actions/tools?name=xxx → {success, data: {name, tools: [...]}}
        """
        resp = self.get("/web/config/mcp/actions/tools", params={"name": name})
        return self._unwrap(resp)

    # ── Skill 模块（RESTful 风格，资源用 /:name 路径参数定位） ──

    def list_skills(self) -> dict:
        """获取 Skill 列表
        GET /web/config/skills → {success, data: {skills: [...]}}
        """
        resp = self.get("/web/config/skills")
        return self._unwrap(resp)

    def get_skill(self, name: str) -> dict:
        """获取单个 Skill 详情
        GET /web/config/skills/:name → {success, data: {detail}}
        """
        resp = self.get(f"/web/config/skills/{name}")
        return self._unwrap(resp)

    def create_skill(self, data: dict) -> dict:
        """创建 Skill
        POST /web/config/skills body: {name, data: {description, content}} → {success, data: {name, resourceAccess}}
        """
        resp = self.post("/web/config/skills", json=data)
        return self._unwrap(resp)

    def update_skill(self, name: str, data: dict) -> dict:
        """更新 Skill
        PUT /web/config/skills/:name body: {data: {description, content}} → {success, data: {name, resourceAccess}}
        """
        resp = self.put(f"/web/config/skills/{name}", json={"data": data})
        return self._unwrap(resp)

    def delete_skill(self, name: str) -> dict:
        """删除 Skill
        DELETE /web/config/skills/:name → {success, data: null}
        """
        resp = self.delete(f"/web/config/skills/{name}")
        return self._unwrap(resp)

    # ── Provider 模块（action 风格，资源用 ?name=xxx 定位） ──

    def list_providers(self) -> dict:
        """获取 Provider 列表
        GET /web/config/providers → {success, data: {providers: [...]}}
        """
        resp = self.get("/web/config/providers")
        return self._unwrap(resp)

    def get_provider(self, name: str) -> dict:
        """获取单个 Provider 详情（按名称查询）
        GET /web/config/providers?name=xxx → {success, data: {detail}}
        """
        resp = self.get("/web/config/providers", params={"name": name})
        return self._unwrap(resp)

    def update_provider(self, name: str, data: dict) -> dict:
        """更新 Provider（按名称定位）
        PUT /web/config/providers?name=xxx body: {...} → {success, data: {...}}
        """
        resp = self.put("/web/config/providers", params={"name": name}, json=data)
        return self._unwrap(resp)

    def delete_provider(self, name: str) -> dict:
        """删除 Provider（按名称定位）
        DELETE /web/config/providers?name=xxx → {success, data: null}
        """
        resp = self.delete("/web/config/providers", params={"name": name})
        return self._unwrap(resp)

    def add_provider_model(self, name: str, data: dict) -> dict:
        """为 Provider 添加模型
        POST /web/config/providers/actions/models?name=xxx body: {modelId, ...} → {success, data: {modelId}}
        """
        resp = self.post("/web/config/providers/actions/models", params={"name": name}, json=data)
        return self._unwrap(resp)

    def update_provider_model(self, name: str, model_id: str, data: dict) -> dict:
        """更新 Provider 下的模型
        PUT /web/config/providers/actions/models/:modelId?name=xxx body: {...} → {success, data: {modelId}}
        """
        resp = self.put(f"/web/config/providers/actions/models/{model_id}", params={"name": name}, json=data)
        return self._unwrap(resp)

    def delete_provider_model(self, name: str, model_id: str) -> dict:
        """删除 Provider 下的模型
        DELETE /web/config/providers/actions/models/:modelId?name=xxx → {success, data: {modelId}}
        """
        resp = self.delete(f"/web/config/providers/actions/models/{model_id}", params={"name": name})
        return self._unwrap(resp)

    # ── Model 偏好模块 ──

    def get_model_preferences(self) -> dict:
        """获取模型偏好与可用模型列表
        GET /web/config/models → {success, data: {current, available}}
        """
        resp = self.get("/web/config/models")
        return self._unwrap(resp)

    def set_model_preferences(self, data: dict) -> dict:
        """更新模型偏好
        PUT /web/config/models body: {model, small_model, permission} → {success, data: {...}}
        """
        resp = self.put("/web/config/models", json=data)
        return self._unwrap(resp)

    def refresh_models(self) -> dict:
        """强制刷新可用模型缓存
        POST /web/config/models/refresh → {success, data: {count}}
        """
        resp = self.post("/web/config/models/refresh")
        return self._unwrap(resp)

    # ── API Key 模块（RESTful /:id） ──

    def list_api_keys(self) -> dict:
        """获取 API Key 列表
        GET /web/api-keys → {success, data: [...]}
        """
        resp = self.get("/web/api-keys")
        return self._unwrap(resp)

    def create_api_key(self, data: dict) -> dict:
        """创建 API Key
        POST /web/api-keys body: {name, ...} → {success, data: {id, key, ...}}
        """
        resp = self.post("/web/api-keys", json=data)
        return self._unwrap(resp)

    def update_api_key(self, key_id: str, data: dict) -> dict:
        """更新 API Key
        PUT /web/api-keys/:id body: {name} → {success, data: null}
        """
        resp = self.put(f"/web/api-keys/{key_id}", json=data)
        return self._unwrap(resp)

    def delete_api_key(self, key_id: str) -> dict:
        """删除 API Key
        DELETE /web/api-keys/:id → {success, data: {deleted: true}}
        """
        resp = self.delete(f"/web/api-keys/{key_id}")
        return self._unwrap(resp)

    # ── Environment 模块（RESTful /:id） ──

    def list_environments(self) -> dict:
        """获取环境列表
        GET /web/environments → {success, data: [...]}
        """
        resp = self.get("/web/environments")
        return self._unwrap(resp)

    def get_environment(self, env_id: str) -> dict:
        """获取环境详情
        GET /web/environments/:id → {success, data: {detail}}
        """
        resp = self.get(f"/web/environments/{env_id}")
        return self._unwrap(resp)

    def create_environment(self, data: dict) -> dict:
        """创建环境
        POST /web/environments body: {name, agentConfigId, ...} → {success, data: {env}}
        """
        resp = self.post("/web/environments", json=data)
        return self._unwrap(resp)

    def update_environment(self, env_id: str, data: dict) -> dict:
        """更新环境
        PUT /web/environments/:id body: {name, description, ...} → {success, data: {env}}
        """
        resp = self.put(f"/web/environments/{env_id}", json=data)
        return self._unwrap(resp)

    def delete_environment(self, env_id: str) -> dict:
        """删除环境
        DELETE /web/environments/:id → {success, data: null}
        """
        resp = self.delete(f"/web/environments/{env_id}")
        return self._unwrap(resp)

    def enter_environment(self, env_id: str, data: dict | None = None) -> dict:
        """进入环境
        POST /web/environments/:id/enter → {success, data: {...}}
        """
        resp = self.post(f"/web/environments/{env_id}/enter", json=data or {})
        return self._unwrap(resp)

    def list_environment_instances(self, env_id: str) -> dict:
        """获取环境实例列表
        GET /web/environments/:id/instances → {success, data: {...}}
        """
        resp = self.get(f"/web/environments/{env_id}/instances")
        return self._unwrap(resp)

    # ── ProdView 模块（RESTful /:id） ──

    def list_prod_views(self, params: dict | None = None) -> dict:
        """获取 ProdView 列表
        GET /web/config/prod-views → {success, data: {...}}
        """
        resp = self.get("/web/config/prod-views", params=params)
        return self._unwrap(resp)

    def get_prod_view(self, view_id: str) -> dict:
        """获取 ProdView 详情
        GET /web/config/prod-views/:id → {success, data: {detail}}
        """
        resp = self.get(f"/web/config/prod-views/{view_id}")
        return self._unwrap(resp)

    def create_prod_view(self, data: dict) -> dict:
        """创建 ProdView
        POST /web/config/prod-views body: {...} → {success, data: {...}}
        """
        resp = self.post("/web/config/prod-views", json=data)
        return self._unwrap(resp)

    def update_prod_view(self, view_id: str, data: dict) -> dict:
        """更新 ProdView
        PUT /web/config/prod-views/:id body: {...} → {success, data: {...}}
        """
        resp = self.put(f"/web/config/prod-views/{view_id}", json=data)
        return self._unwrap(resp)

    def delete_prod_view(self, view_id: str) -> dict:
        """删除 ProdView
        DELETE /web/config/prod-views/:id → {success, data: {...}}
        """
        resp = self.delete(f"/web/config/prod-views/{view_id}")
        return self._unwrap(resp)

    # ── Channel 模块（RESTful for bindings /:id） ──

    def list_channel_providers(self) -> dict:
        """获取通道平台列表
        GET /web/channels/providers → {success, data: {...}}
        """
        resp = self.get("/web/channels/providers")
        return self._unwrap(resp)

    def get_hermes_status(self) -> dict:
        """获取 Hermes 状态
        GET /web/channels/hermes/status → {success, data: {connected, ...}}
        """
        resp = self.get("/web/channels/hermes/status")
        return self._unwrap(resp)

    def list_channel_bindings(self) -> dict:
        """获取通道绑定列表
        GET /web/channels/bindings → {success, data: [...]}
        """
        resp = self.get("/web/channels/bindings")
        return self._unwrap(resp)

    def create_channel_binding(self, data: dict) -> dict:
        """创建通道绑定
        POST /web/channels/bindings body: {platform, agentId, ...} → {success, data: {binding}}
        """
        resp = self.post("/web/channels/bindings", json=data)
        return self._unwrap(resp)

    def update_channel_binding(self, binding_id: str, data: dict) -> dict:
        """更新通道绑定
        PATCH /web/channels/bindings/:id body: {...} → {success, data: {binding}}
        """
        resp = self.patch(f"/web/channels/bindings/{binding_id}", json=data)
        return self._unwrap(resp)

    def delete_channel_binding(self, binding_id: str) -> dict:
        """删除通道绑定
        DELETE /web/channels/bindings/:id → {success, data: null}
        """
        resp = self.delete(f"/web/channels/bindings/{binding_id}")
        return self._unwrap(resp)

    # ── Task V2 模块（RESTful /:id） ──

    def list_tasks_v2(self, params: dict | None = None) -> dict:
        """获取任务 V2 列表
        GET /web/tasks/v2 → {success, data: {items, total, page, pageSize}}
        """
        resp = self.get("/web/tasks/v2", params=params)
        return self._unwrap(resp)

    def get_task_v2(self, task_id: str) -> dict:
        """获取任务 V2 详情
        GET /web/tasks/v2/:id → {success, data: {task}}
        """
        resp = self.get(f"/web/tasks/v2/{task_id}")
        return self._unwrap(resp)

    def create_task_v2(self, data: dict) -> dict:
        """创建任务 V2
        POST /web/tasks/v2 body: {...} → {success, data: {task}}
        """
        resp = self.post("/web/tasks/v2", json=data)
        return self._unwrap(resp)

    def update_task_v2(self, task_id: str, data: dict) -> dict:
        """更新任务 V2
        PUT /web/tasks/v2/:id body: {...} → {success, data: {task}}
        """
        resp = self.put(f"/web/tasks/v2/{task_id}", json=data)
        return self._unwrap(resp)

    def delete_task_v2(self, task_id: str) -> dict:
        """删除任务 V2
        DELETE /web/tasks/v2/:id → {success, data: null}
        """
        resp = self.delete(f"/web/tasks/v2/{task_id}")
        return self._unwrap(resp)

    def toggle_task_v2(self, task_id: str) -> dict:
        """切换任务 V2 启用状态
        POST /web/tasks/v2/:id/toggle → {success, data: {task}}
        """
        resp = self.post(f"/web/tasks/v2/{task_id}/toggle")
        return self._unwrap(resp)

    def trigger_task_v2(self, task_id: str) -> dict:
        """手动触发任务 V2
        POST /web/tasks/v2/:id/trigger → {success, data: {task}}
        """
        resp = self.post(f"/web/tasks/v2/{task_id}/trigger")
        return self._unwrap(resp)

    def get_task_v2_logs(self, task_id: str, params: dict | None = None) -> dict:
        """获取任务 V2 执行日志
        GET /web/tasks/v2/:id/logs → {success, data: {logs}}
        """
        resp = self.get(f"/web/tasks/v2/{task_id}/logs", params=params)
        return self._unwrap(resp)

    def clear_task_v2_logs(self, task_id: str) -> dict:
        """清空任务 V2 日志
        DELETE /web/tasks/v2/:id/logs → {success, data: null}
        """
        resp = self.delete(f"/web/tasks/v2/{task_id}/logs")
        return self._unwrap(resp)

    # ── Instance 模块 ──

    def get_instance_activity(self, params: dict | None = None) -> dict:
        """获取实例活跃度
        GET /web/instances/activity → {success, data: {...}}
        """
        resp = self.get("/web/instances/activity", params=params)
        return self._unwrap(resp)

    def spawn_instance(self, data: dict) -> dict:
        """从环境启动实例
        POST /web/instances/from-environment body: {environmentId} → {success, data: {instance}}
        """
        resp = self.post("/web/instances/from-environment", json=data)
        return self._unwrap(resp)

    def delete_instance(self, instance_id: str) -> dict:
        """删除实例
        DELETE /web/instances/:id → {success, data: null}
        """
        resp = self.delete(f"/web/instances/{instance_id}")
        return self._unwrap(resp)

    # ── Registry 模块（RESTful /:id） ──

    def list_machines(self, params: dict | None = None) -> dict:
        """获取机器列表
        GET /web/registry/machines → {success, data: {items, total}}
        """
        resp = self.get("/web/registry/machines", params=params)
        return self._unwrap(resp)

    def get_machine(self, machine_id: str) -> dict:
        """获取机器详情
        GET /web/registry/machines/:id → {success, data: {machine, recentEvents}}
        """
        resp = self.get(f"/web/registry/machines/{machine_id}")
        return self._unwrap(resp)

    def create_machine(self, data: dict) -> dict:
        """创建机器
        POST /web/registry/machines body: {name, ...} → {success, data: {machine}}
        """
        resp = self.post("/web/registry/machines", json=data)
        return self._unwrap(resp)

    def update_machine(self, machine_id: str, data: dict) -> dict:
        """更新机器
        PATCH /web/registry/machines/:id body: {name, ...} → {success, data: {machine}}
        """
        resp = self.patch(f"/web/registry/machines/{machine_id}", json=data)
        return self._unwrap(resp)

    def list_machine_events(self, machine_id: str, params: dict | None = None) -> dict:
        """获取机器事件列表
        GET /web/registry/machines/:id/events → {success, data: {items, total}}
        """
        resp = self.get(f"/web/registry/machines/{machine_id}/events", params=params)
        return self._unwrap(resp)

    # ── Hindsight 模块（代理到外部服务） ──

    def get_hindsight_status(self) -> dict:
        """获取 Hindsight 状态
        GET /web/hindsight/status → {success, data: {enabled, ...}}
        """
        resp = self.get("/web/hindsight/status")
        return self._unwrap(resp)

    # ── 只读配置模块 ──

    def get_branding(self) -> dict:
        """获取品牌配置（无需认证）
        GET /web/branding → {success, data: {brandName, logoUrl}}
        """
        resp = self.get("/web/branding")
        return self._unwrap(resp)

    def get_sidebar_config(self) -> dict:
        """获取侧边栏配置（无需认证）
        GET /web/sidebar-config → {success, data: {...}}
        """
        resp = self.get("/web/sidebar-config")
        return self._unwrap(resp)

    def list_workflow_custom_tools(self) -> dict:
        """获取自定义工具列表
        GET /web/workflow-custom-tools → {success, data: [...]}
        """
        resp = self.get("/web/workflow-custom-tools")
        return self._unwrap(resp)

    # ── ProdView 加载（非 config 路径） ──

    def load_prod_view(self, view_id: str) -> dict:
        """加载 ProdView 视图数据
        GET /web/prod-views/:id/load → {success, data: {...}}
        """
        resp = self.get(f"/web/prod-views/{view_id}/load")
        return self._unwrap(resp)

    # ── Agent Sites 模块（RESTful /:id） ──

    def list_agent_site_apps(self) -> dict:
        """获取 Agent Site App 列表
        GET /web/agent-sites/apps → {success, data: [...]}
        """
        resp = self.get("/web/agent-sites/apps")
        return self._unwrap(resp)

    def get_agent_site_app(self, app_id: str) -> dict:
        """获取 Agent Site App 详情
        GET /web/agent-sites/apps/:id → {success, data: {app}}
        """
        resp = self.get(f"/web/agent-sites/apps/{app_id}")
        return self._unwrap(resp)

    def create_agent_site_app(self, data: dict) -> dict:
        """创建 Agent Site App
        POST /web/agent-sites/apps body: {name, type, ...} → {success, data: {app}}
        """
        resp = self.post("/web/agent-sites/apps", json=data)
        return self._unwrap(resp)

    def update_agent_site_app(self, app_id: str, data: dict) -> dict:
        """更新 Agent Site App
        PATCH /web/agent-sites/apps/:id body: {...} → {success, data: {app}}
        """
        resp = self.patch(f"/web/agent-sites/apps/{app_id}", json=data)
        return self._unwrap(resp)

    def delete_agent_site_app(self, app_id: str) -> dict:
        """删除 Agent Site App
        DELETE /web/agent-sites/apps/:id → {success, data: null}
        """
        resp = self.delete(f"/web/agent-sites/apps/{app_id}")
        return self._unwrap(resp)

    # ── Organization 模块（RESTful /:id） ──

    def list_organizations(self) -> dict:
        """获取组织列表
        GET /web/organizations → {success, data: [...]}
        """
        resp = self.get("/web/organizations")
        return self._unwrap(resp)

    def get_organization(self, org_id: str) -> dict:
        """获取组织详情
        GET /web/organizations/:id → {success, data: {detail}}
        """
        resp = self.get(f"/web/organizations/{org_id}")
        return self._unwrap(resp)

    def create_organization(self, data: dict) -> dict:
        """创建组织
        POST /web/organizations body: {name, slug} → {success, data: {org}}
        """
        resp = self.post("/web/organizations", json=data)
        return self._unwrap(resp)

    def update_organization(self, org_id: str, data: dict) -> dict:
        """更新组织
        PUT /web/organizations/:id body: {name, slug} → {success, data: {org}}
        """
        resp = self.put(f"/web/organizations/{org_id}", json=data)
        return self._unwrap(resp)

    def delete_organization(self, org_id: str) -> dict:
        """删除组织
        DELETE /web/organizations/:id → {success, data: {deleted: true}}
        """
        resp = self.delete(f"/web/organizations/{org_id}")
        return self._unwrap(resp)

    def set_active_organization(self, org_id: str) -> dict:
        """设置活跃组织
        POST /web/organizations/:id/set-active → {success, data: null}
        """
        resp = self.post(f"/web/organizations/{org_id}/set-active")
        return self._unwrap(resp)

    def list_organization_members(self, org_id: str) -> dict:
        """获取组织成员列表
        GET /web/organizations/:id/members → {success, data: [...]}
        """
        resp = self.get(f"/web/organizations/{org_id}/members")
        return self._unwrap(resp)

    def search_member_candidates(self, org_id: str, keyword: str) -> dict:
        """搜索可添加成员候选项
        GET /web/organizations/:id/member-candidates?keyword=xxx → {success, data: [...]}
        """
        resp = self.get(f"/web/organizations/{org_id}/member-candidates", params={"keyword": keyword})
        return self._unwrap(resp)

    def add_organization_members(self, org_id: str, data: dict) -> dict:
        """添加组织成员
        POST /web/organizations/:id/members body: {userIds, role} → {success, data: [...]}
        """
        resp = self.post(f"/web/organizations/{org_id}/members", json=data)
        return self._unwrap(resp)

    def remove_organization_member(self, org_id: str, member_id: str) -> dict:
        """移除组织成员
        DELETE /web/organizations/:id/members/:memberId → {success, data: null}
        """
        resp = self.delete(f"/web/organizations/{org_id}/members/{member_id}")
        return self._unwrap(resp)

    def update_member_role(self, org_id: str, member_id: str, role: str) -> dict:
        """更新成员角色
        PUT /web/organizations/:id/members/:memberId body: {role} → {success, data: null}
        """
        resp = self.put(f"/web/organizations/{org_id}/members/{member_id}", json={"role": role})
        return self._unwrap(resp)

    # ── Meta Agent 模块 ──

    def ensure_meta_agent(self) -> dict:
        """确保 Meta Agent 可用
        POST /web/meta-agent/ensure → {success, data: {environmentId, instanceId, status, apiKey}}
        """
        resp = self.post("/web/meta-agent/ensure")
        return self._unwrap(resp)

    # ── Agent Generation 模块 ──

    def generate_agent(self, prompt: str) -> dict:
        """AI 生成 Agent 配置
        POST /web/agent-generation body: {prompt} → {success, data: {name, systemPrompt, skills}}
        """
        resp = self.post("/web/agent-generation", json={"prompt": prompt})
        return self._unwrap(resp)

    # ── Workflow Def 模块（RESTful /:id） ──

    def list_workflow_defs(self) -> dict:
        """获取工作流定义列表
        GET /web/workflow-defs → {success, data: [...]}
        """
        resp = self.get("/web/workflow-defs")
        return self._unwrap(resp)

    def get_workflow_def(self, wf_id: str) -> dict:
        """获取工作流定义详情
        GET /web/workflow-defs/:id → {success, data: {detail}}
        """
        resp = self.get(f"/web/workflow-defs/{wf_id}")
        return self._unwrap(resp)

    def create_workflow_def(self, data: dict) -> dict:
        """创建工作流定义
        POST /web/workflow-defs body: {name, description} → {success, data: {workflow}}
        """
        resp = self.post("/web/workflow-defs", json=data)
        return self._unwrap(resp)

    def update_workflow_def_meta(self, wf_id: str, data: dict) -> dict:
        """更新工作流元数据
        PATCH /web/workflow-defs/:id body: {name, description} → {success, data: {workflow}}
        """
        resp = self.patch(f"/web/workflow-defs/{wf_id}", json=data)
        return self._unwrap(resp)

    def delete_workflow_def(self, wf_id: str) -> dict:
        """删除工作流定义
        DELETE /web/workflow-defs/:id → {success, data: null}
        """
        resp = self.delete(f"/web/workflow-defs/{wf_id}")
        return self._unwrap(resp)

    def list_workflow_def_versions(self, wf_id: str) -> dict:
        """获取工作流版本列表
        GET /web/workflow-defs/:id/versions → {success, data: [...]}
        """
        resp = self.get(f"/web/workflow-defs/{wf_id}/versions")
        return self._unwrap(resp)

    def list_workflow_def_triggers(self, wf_id: str) -> dict:
        """获取工作流触发器列表
        GET /web/workflow-defs/:id/triggers → {success, data: [...]}
        """
        resp = self.get(f"/web/workflow-defs/{wf_id}/triggers")
        return self._unwrap(resp)

    def get_recoverable_workflow_defs(self) -> dict:
        """获取可恢复的工作流 ID 列表
        GET /web/workflow-defs/recoverable → {success, data: [...]}
        """
        resp = self.get("/web/workflow-defs/recoverable")
        return self._unwrap(resp)

    # ── Workflow Run 模块（RESTful /:runId） ──

    def list_workflow_runs(self, params: dict | None = None) -> dict:
        """获取工作流运行记录列表
        GET /web/workflow-runs → {success, data: [...]}
        """
        resp = self.get("/web/workflow-runs", params=params)
        return self._unwrap(resp)

    def get_workflow_run(self, run_id: str) -> dict:
        """获取工作流运行记录详情
        GET /web/workflow-runs/:runId → {success, data: {detail}}
        """
        resp = self.get(f"/web/workflow-runs/{run_id}")
        return self._unwrap(resp)

    def get_workflow_run_events(self, run_id: str) -> dict:
        """获取工作流运行事件列表
        GET /web/workflow-runs/:runId/events → {success, data: [...]}
        """
        resp = self.get(f"/web/workflow-runs/{run_id}/events")
        return self._unwrap(resp)

    def get_workflow_run_approvals(self, run_id: str) -> dict:
        """获取工作流审批列表
        GET /web/workflow-runs/:runId/approvals → {success, data: [...]}
        """
        resp = self.get(f"/web/workflow-runs/{run_id}/approvals")
        return self._unwrap(resp)

    # ── Knowledge Base 模块（RESTful /:id） ──

    def list_knowledge_bases(self) -> dict:
        """获取知识库列表
        GET /web/knowledgeBases → {success, data: [...]}
        """
        resp = self.get("/web/knowledgeBases")
        return self._unwrap(resp)

    def get_knowledge_base(self, kb_id: str) -> dict:
        """获取知识库详情
        GET /web/knowledgeBases/:id → {success, data: {detail}}
        """
        resp = self.get(f"/web/knowledgeBases/{kb_id}")
        return self._unwrap(resp)

    def create_knowledge_base(self, data: dict) -> dict:
        """创建知识库
        POST /web/knowledgeBases body: {name, slug, description, ...} → {success, data: {kb}}
        """
        resp = self.post("/web/knowledgeBases", json=data)
        return self._unwrap(resp)

    def update_knowledge_base(self, kb_id: str, data: dict) -> dict:
        """更新知识库
        PATCH /web/knowledgeBases/:id body: {name, description, ...} → {success, data: {kb}}
        """
        resp = self.patch(f"/web/knowledgeBases/{kb_id}", json=data)
        return self._unwrap(resp)

    def delete_knowledge_base(self, kb_id: str) -> dict:
        """删除知识库
        DELETE /web/knowledgeBases/:id → {success, data: null}
        """
        resp = self.delete(f"/web/knowledgeBases/{kb_id}")
        return self._unwrap(resp)

    def list_knowledge_form_options(self) -> dict:
        """获取知识库表单选项（embedding providers、parse methods 等）
        GET /web/knowledgeBases/form-options → {success, data: {options}}
        """
        resp = self.get("/web/knowledgeBases/form-options")
        return self._unwrap(resp)

    def list_rerank_models(self) -> dict:
        """获取可用的 rerank 模型列表
        GET /web/knowledgeBases/rerank-models → {success, data: [...]}
        """
        resp = self.get("/web/knowledgeBases/rerank-models")
        return self._unwrap(resp)

    def list_knowledge_resources(self, kb_id: str) -> dict:
        """获取知识库资源列表
        GET /web/knowledgeBases/:id/resources → {success, data: [...]}
        """
        resp = self.get(f"/web/knowledgeBases/{kb_id}/resources")
        return self._unwrap(resp)

    def search_knowledge_base(self, kb_id: str, query: str) -> dict:
        """检索测试知识库
        POST /web/knowledgeBases/:id/search body: {query} → {success, data: {hits, total}}
        """
        resp = self.post(f"/web/knowledgeBases/{kb_id}/search", json={"query": query})
        return self._unwrap(resp)

    def delete_knowledge_resource(self, kb_id: str, resource_id: str) -> dict:
        """删除知识库资源
        DELETE /web/knowledgeBases/:id/resources/:resourceId → {success, data: null}
        """
        resp = self.delete(f"/web/knowledgeBases/{kb_id}/resources/{resource_id}")
        return self._unwrap(resp)

    def toggle_knowledge_resource(self, kb_id: str, resource_id: str, enabled: bool) -> dict:
        """启用/禁用知识库资源
        PATCH /web/knowledgeBases/:id/resources/:resourceId/enabled body: {enabled} → {success, data: {enabled}}
        """
        resp = self.patch(f"/web/knowledgeBases/{kb_id}/resources/{resource_id}/enabled", json={"enabled": enabled})
        return self._unwrap(resp)
