# tests/api_contracts/provider_schemas.py
"""Provider 接口响应 JSON Schema 定义（仅 Web 控制台接口）

/web/config/providers（控制台）: action 风格，响应包装为 {success, data}
"""

# ── 通用字段定义 ──

PROVIDER_LIST_ITEM = {
    "type": "object",
    "required": ["id", "name"],
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "protocol": {"type": ["string", "null"]},
        "keyHint": {"type": ["string", "null"]},
        "baseURL": {"type": ["string", "null"]},
        "modelCount": {"type": "integer"},
        "resourceAccess": {"type": "object"},
        "resourceKey": {"type": ["string", "null"]},
    },
    "additionalProperties": True,
}

PROVIDER_DETAIL = {
    "type": "object",
    "required": ["id", "name"],
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "protocol": {"type": ["string", "null"]},
        "keyHint": {"type": ["string", "null"]},
        "baseURL": {"type": ["string", "null"]},
        "resourceAccess": {"type": "object"},
        "resourceKey": {"type": ["string", "null"]},
        "models": {"type": "array"},
    },
    "additionalProperties": True,
}

# ── /web/* 控制台响应格式（{success, data} 包装） ──

WEB_PROVIDER_LIST_DATA = {
    "type": "object",
    "required": ["providers"],
    "properties": {
        "providers": {"type": "array", "items": PROVIDER_LIST_ITEM},
    },
}

WEB_PROVIDER_LIST_RESPONSE = {
    "type": "object",
    "required": ["success", "data"],
    "properties": {
        "success": {"type": "boolean"},
        "data": WEB_PROVIDER_LIST_DATA,
    },
}

WEB_PROVIDER_DETAIL_RESPONSE = {
    "type": "object",
    "required": ["success", "data"],
    "properties": {
        "success": {"type": "boolean"},
        "data": PROVIDER_DETAIL,
    },
}

WEB_SAVE_PROVIDER_RESPONSE = {
    "type": "object",
    "required": ["success", "data"],
    "properties": {
        "success": {"type": "boolean"},
        "data": {
            "type": "object",
            "required": ["id"],
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
                "protocol": {"type": ["string", "null"]},
                "keyHint": {"type": ["string", "null"]},
            },
            "additionalProperties": True,
        },
    },
}

WEB_DELETE_PROVIDER_RESPONSE = {
    "type": "object",
    "required": ["success"],
    "properties": {
        "success": {"type": "boolean"},
        "data": {},
    },
}

# ── Provider Model Action 接口 Schema ──

WEB_PROVIDER_MODEL_RESULT_DATA = {
    "type": "object",
    "required": ["modelId"],
    "properties": {
        "modelId": {"type": "string"},
    },
    "additionalProperties": True,
}
