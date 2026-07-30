# tests/api_contracts/model_schemas.py
"""Model 接口响应 JSON Schema 定义

两套接口响应格式不同：
- /web/config/models（控制台）: 用户偏好设置，响应包装为 {success, data}
- /api/models/providers/*（OpenAPI）: Provider + Model CRUD，裸数据，列表带分页
"""

# ── 通用字段定义 ──

PROVIDER_LIST_ITEM = {
    "type": "object",
    "required": ["id", "name"],
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "displayName": {"type": ["string", "null"]},
        "protocol": {"type": "string"},
        "baseUrl": {"type": ["string", "null"]},
        "modelCount": {"type": "integer"},
        "resourceAccess": {"type": "object"},
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
        "protocol": {"type": "string"},
        "baseUrl": {"type": ["string", "null"]},
        "extraOptions": {},
        "models": {"type": "array"},
        "resourceAccess": {"type": "object"},
    },
    "additionalProperties": True,
}

MODEL_DETAIL = {
    "type": "object",
    "required": ["id", "modelId"],
    "properties": {
        "providerId": {"type": "string"},
        "id": {"type": "string"},
        "modelId": {"type": "string"},
        "providerName": {"type": "string"},
        "displayName": {"type": ["string", "null"]},
        "modalities": {},
        "limitConfig": {},
        "cost": {},
        "options": {},
    },
    "additionalProperties": True,
}

# ── /api/* OpenAPI 响应格式（裸数据） ──

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

API_PROVIDER_DELETE_RESPONSE = {
    "type": "object",
    "required": ["id", "deleted"],
    "properties": {
        "id": {"type": "string"},
        "deleted": {"type": "boolean"},
    },
}

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

API_MODEL_DELETE_RESPONSE = {
    "type": "object",
    "required": ["id", "deleted"],
    "properties": {
        "id": {"type": "string"},
        "deleted": {"type": "boolean"},
    },
}

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
