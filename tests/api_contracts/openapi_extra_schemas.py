# tests/api_contracts/openapi_extra_schemas.py
"""剩余 OpenAPI 模块 JSON Schema（/api/knowledge-bases, /api/workflows, /api/instances, /api/workspaces, /api/openai-chat）"""

# ── Knowledge Bases ──
API_KNOWLEDGE_BASE_LIST_RESPONSE = {
    "type": "object",
    "properties": {
        "items": {"type": "array"},
        "total": {"type": "integer"},
        "page": {"type": "integer"},
        "pageSize": {"type": "integer"},
    },
    "required": ["items", "total", "page", "pageSize"],
    "additionalProperties": True,
}

# ── Workflows ──
API_WORKFLOW_EXECUTE_RESPONSE = {
    "type": "object",
    "additionalProperties": True,
}

# ── Instances ──
API_INSTANCE_CONNECT_RESPONSE = {
    "type": "object",
    "additionalProperties": True,
}

# ── Workspaces ──
API_WORKSPACE_UPLOAD_RESPONSE = {
    "type": "object",
    "additionalProperties": True,
}

# ── OpenAI Chat ──
API_OPENAI_CHAT_RESPONSE = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "choices": {"type": "array"},
    },
    "additionalProperties": True,
}

# ── System API ──
API_SYSTEM_USER_LIST_RESPONSE = {
    "type": "object",
    "properties": {
        "items": {"type": "array"},
        "total": {"type": "integer"},
        "page": {"type": "integer"},
        "pageSize": {"type": "integer"},
    },
    "required": ["items", "total"],
    "additionalProperties": True,
}

API_SYSTEM_USER_DETAIL = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "email": {"type": "string"},
    },
    "required": ["id"],
    "additionalProperties": True,
}

API_SYSTEM_ORG_LIST_RESPONSE = {
    "type": "object",
    "properties": {
        "items": {"type": "array"},
        "total": {"type": "integer"},
        "page": {"type": "integer"},
        "pageSize": {"type": "integer"},
    },
    "required": ["items", "total"],
    "additionalProperties": True,
}

API_SYSTEM_ORG_DETAIL = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
    },
    "required": ["id"],
    "additionalProperties": True,
}

# ── System API 写操作响应 ──

API_SYSTEM_DELETE_RESPONSE = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "deleted": {"type": "boolean"},
        "success": {"type": "boolean"},
    },
    "additionalProperties": True,
}

API_SYSTEM_UPDATE_RESPONSE = {
    "type": "object",
    "additionalProperties": True,
}

API_SYSTEM_USER_CREATE_RESPONSE = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "email": {"type": "string"},
    },
    "required": ["id"],
    "additionalProperties": True,
}

API_SYSTEM_ORG_CREATE_RESPONSE = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
    },
    "required": ["id"],
    "additionalProperties": True,
}

API_SYSTEM_API_KEY_RESULT = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "key": {"type": "string"},
    },
    "required": ["id"],
    "additionalProperties": True,
}

API_SYSTEM_API_KEY_LIST_RESPONSE = {
    "type": "object",
    "properties": {
        "items": {"type": "array"},
        "total": {"type": "integer"},
        "page": {"type": "integer"},
        "pageSize": {"type": "integer"},
    },
    "required": ["items", "total"],
    "additionalProperties": True,
}

API_SYSTEM_ORG_MEMBER = {
    "type": "object",
    "properties": {
        "userId": {"type": "string"},
        "organizationId": {"type": "string"},
    },
    "additionalProperties": True,
}

API_SYSTEM_USER_ORG_LIST_RESPONSE = {
    "type": "object",
    "properties": {
        "items": {"type": "array"},
        "total": {"type": "integer"},
        "page": {"type": "integer"},
        "pageSize": {"type": "integer"},
    },
    "required": ["items", "total"],
    "additionalProperties": True,
}
