# tests/api_contracts/agent_schemas.py
"""Agent 接口响应 JSON Schema 定义

两套接口响应格式不同：
- /web/config/agents（控制台）: action 风格，响应包装为 {success, data}
- /api/agents（OpenAPI）: RESTful 风格，响应为裸数据，列表带分页
"""

# ── 通用 Agent 字段定义 ──

AGENT_LIST_ITEM = {
    "type": "object",
    "required": ["id", "name"],
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "builtIn": {"type": "boolean"},
        "model": {"type": ["string", "null"]},
        "modelId": {"type": ["string", "null"]},
        "description": {"type": ["string", "null"]},
        "machineId": {"type": ["string", "null"]},
        "knowledgeBaseCount": {"type": "integer"},
        "resourceAccess": {"type": "object"},
    },
    "additionalProperties": True,
}

AGENT_DETAIL = {
    "type": "object",
    "required": ["id", "name"],
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "builtIn": {"type": "boolean"},
        "model": {"type": ["string", "null"]},
        "modelId": {"type": ["string", "null"]},
        "prompt": {"type": ["string", "null"]},
        "description": {"type": ["string", "null"]},
        "extra": {},
        "knowledge": {},
        "skillIds": {"type": "array"},
        "mcpIds": {"type": "array"},
        "machineId": {"type": ["string", "null"]},
        "resourceAccess": {"type": "object"},
    },
    "additionalProperties": True,
}

# ── /api/* OpenAPI 响应格式（裸数据） ──

API_AGENT_LIST_RESPONSE = {
    "type": "object",
    "required": ["items", "total"],
    "properties": {
        "items": {"type": "array", "items": AGENT_LIST_ITEM},
        "total": {"type": "integer"},
        "page": {"type": "integer"},
        "pageSize": {"type": "integer"},
    },
}

API_AGENT_DETAIL_RESPONSE = AGENT_DETAIL

API_CREATE_AGENT_RESPONSE = AGENT_DETAIL

API_DELETE_AGENT_RESPONSE = {
    "type": "object",
    "required": ["id", "deleted"],
    "properties": {
        "id": {"type": "string"},
        "deleted": {"type": "boolean"},
    },
}

# ── /web/* 控制台响应格式（{success, data} 包装） ──

WEB_AGENT_LIST_DATA = {
    "type": "object",
    "required": ["agents"],
    "properties": {
        "default_agent": {"type": ["string", "null"]},
        "agents": {"type": "array", "items": {
            "type": "object",
            "required": ["id", "name"],
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
                "builtIn": {"type": "boolean"},
                "model": {"type": ["string", "null"]},
                "modelId": {"type": ["string", "null"]},
                "description": {"type": ["string", "null"]},
                "engineType": {"type": "string"},
            },
            "additionalProperties": True,
        }},
    },
}

WEB_AGENT_LIST_RESPONSE = {
    "type": "object",
    "required": ["success", "data"],
    "properties": {
        "success": {"type": "boolean"},
        "data": WEB_AGENT_LIST_DATA,
    },
}

WEB_AGENT_DETAIL_RESPONSE = {
    "type": "object",
    "required": ["success", "data"],
    "properties": {
        "success": {"type": "boolean"},
        "data": AGENT_DETAIL,
    },
}

WEB_CREATE_AGENT_RESPONSE = {
    "type": "object",
    "required": ["success", "data"],
    "properties": {
        "success": {"type": "boolean"},
        "data": {
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": {"type": "string"},
                "id": {"type": "string"},
            },
            "additionalProperties": True,
        },
    },
}

WEB_DELETE_AGENT_RESPONSE = {
    "type": "object",
    "required": ["success"],
    "properties": {
        "success": {"type": "boolean"},
        "data": {},
    },
}

# ── 向后兼容别名 ──

AGENT_LIST_RESPONSE = API_AGENT_LIST_RESPONSE
AGENT_DETAIL_RESPONSE = API_AGENT_DETAIL_RESPONSE
CREATE_AGENT_RESPONSE = API_CREATE_AGENT_RESPONSE

# ── Agent 扩展接口 Schema ──

WEB_AGENT_TEMPLATES_DATA = {
    "type": "object",
    "required": ["templates"],
    "properties": {
        "templates": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name"],
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": ["string", "null"]},
                    "prompt": {"type": ["string", "null"]},
                },
                "additionalProperties": True,
            },
        },
    },
}

WEB_SET_DEFAULT_AGENT_DATA = {
    "type": "object",
    "required": ["default_agent"],
    "properties": {
        "default_agent": {"type": ["string", "null"]},
        "resourceAccess": {"type": "object"},
    },
    "additionalProperties": True,
}
