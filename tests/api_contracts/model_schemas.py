# tests/api_contracts/model_schemas.py
"""Model 接口响应 JSON Schema 定义

两套接口响应格式不同：
- /web/config/models（控制台）: 用户偏好设置，响应包装为 {success, data}
- /api/v1/providers 与 /api/v1/providers/:providerId/models（OpenAPI）: Provider + Model CRUD，
  响应为 {success, data}，客户端解包后为裸数据，列表带分页
"""

# ── 通用字段定义 ──

_SCOPE = {
    "type": "object",
    "properties": {
        "organizationId": {"type": "string"},
        "ownerUserId": {"type": "string"},
        "visibility": {"type": "string", "enum": ["private", "public"]},
    },
    "additionalProperties": True,
}

_ACCESS = {
    "type": "object",
    "properties": {"actions": {"type": "array", "items": {"type": "string"}}},
    "additionalProperties": True,
}

PROVIDER_LIST_ITEM = {
    "type": "object",
    "required": ["id", "name"],
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "displayName": {"type": ["string", "null"]},
        "kind": {"type": "string", "enum": ["direct", "gateway"]},
        "gatewayType": {"type": ["string", "null"]},
        "protocol": {"type": "string", "enum": ["openai", "anthropic"]},
        "baseUrl": {"type": ["string", "null"]},
        "modelCount": {"type": "integer"},
        "hasApiKey": {"type": "boolean"},
        "scope": _SCOPE,
        "access": _ACCESS,
    },
    "additionalProperties": True,
}

PROVIDER_DETAIL = {
    "type": "object",
    "required": ["id", "name"],
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "displayName": {"type": ["string", "null"]},
        "kind": {"type": "string", "enum": ["direct", "gateway"]},
        "gatewayType": {"type": ["string", "null"]},
        "protocol": {"type": "string", "enum": ["openai", "anthropic"]},
        "baseUrl": {"type": ["string", "null"]},
        "extraOptions": {},
        "models": {"type": "array"},
        "hasApiKey": {"type": "boolean"},
        "scope": _SCOPE,
        "access": _ACCESS,
    },
    "additionalProperties": True,
}

MODEL_DETAIL = {
    "type": "object",
    "required": ["id", "modelId", "providerId"],
    "properties": {
        "providerId": {"type": "string"},
        "id": {"type": "string"},
        "modelId": {"type": "string"},
        "displayName": {"type": ["string", "null"]},
        "modalities": {},
        "limitConfig": {},
        "cost": {},
        "options": {},
    },
    "additionalProperties": True,
}

# ── /api/v1/* OpenAPI 响应格式（客户端解包 {success,data} 后的裸数据） ──

API_PROVIDER_LIST_RESPONSE = {
    "type": "object",
    "required": ["items", "total"],
    "properties": {
        "items": {"type": "array", "items": PROVIDER_LIST_ITEM},
        "total": {"type": "integer"},
        "page": {"type": "integer"},
        "pageSize": {"type": "integer"},
    },
}

API_PROVIDER_DETAIL_RESPONSE = PROVIDER_DETAIL

# v1 删除成功返回 data: null
API_PROVIDER_DELETE_RESPONSE = {"type": "null"}

API_MODEL_LIST_RESPONSE = {
    "type": "object",
    "required": ["items", "total"],
    "properties": {
        "items": {"type": "array", "items": MODEL_DETAIL},
        "total": {"type": "integer"},
        "page": {"type": "integer"},
        "pageSize": {"type": "integer"},
    },
}

API_MODEL_DETAIL_RESPONSE = MODEL_DETAIL

API_MODEL_DELETE_RESPONSE = {"type": "null"}

# ── /web/* 控制台响应格式（{success, data} 包装） ──

WEB_MODEL_PREFERENCES_DATA = {
    "type": "object",
    "properties": {
        "current": {
            "type": "object",
            "properties": {
                "model": {"type": ["string", "null"]},
                "small_model": {"type": ["string", "null"]},
                "permission": {},
            },
            "additionalProperties": True,
        },
        "available": {"type": "array"},
    },
    "additionalProperties": True,
}

WEB_MODEL_PREFERENCES_RESPONSE = {
    "type": "object",
    "required": ["success", "data"],
    "properties": {
        "success": {"type": "boolean"},
        "data": WEB_MODEL_PREFERENCES_DATA,
    },
}

WEB_MODEL_SET_RESPONSE = {
    "type": "object",
    "required": ["success", "data"],
    "properties": {
        "success": {"type": "boolean"},
        "data": {
            "type": "object",
            "properties": {
                "model": {"type": ["string", "null"]},
                "small_model": {"type": ["string", "null"]},
                "permission": {},
            },
            "additionalProperties": True,
        },
    },
}

WEB_MODEL_REFRESH_RESPONSE = {
    "type": "object",
    "required": ["success", "data"],
    "properties": {
        "success": {"type": "boolean"},
        "data": {
            "type": "object",
            "properties": {
                "count": {"type": "integer"},
            },
            "additionalProperties": True,
        },
    },
}
