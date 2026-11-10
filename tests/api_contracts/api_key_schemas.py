# tests/api_contracts/api_key_schemas.py
"""API Key 模块 JSON Schema（Web /web/api-keys）"""

# 创建 API Key 请求体：expiresAt 可省略；提供时必须是晚于当前时间的合法时间
API_KEY_CREATE_REQUEST = {
    "type": "object",
    "required": ["name"],
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "expiresAt": {"type": ["string", "number"]},
        "metadata": {"type": "object"},
    },
    "additionalProperties": True,
}

# /web/* 失败信封（宿主错误处理器统一输出）
WEB_ERROR_RESPONSE = {
    "type": "object",
    "required": ["success", "error"],
    "properties": {
        "success": {"const": False},
        "error": {
            "type": "object",
            "required": ["code", "message"],
            "properties": {
                "code": {"type": "string"},
                "message": {"type": "string"},
            },
            "additionalProperties": True,
        },
    },
    "additionalProperties": True,
}

API_KEY_ITEM = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "prefix": {"type": "string"},
        "createdAt": {},
        "expiresAt": {},
    },
    "required": ["id"],
    "additionalProperties": True,
}

WEB_API_KEY_LIST_RESPONSE = {
    "type": "object",
    "properties": {
        "success": {"type": "boolean"},
        "data": {"type": "array", "items": API_KEY_ITEM},
    },
    "required": ["success", "data"],
    "additionalProperties": True,
}

WEB_API_KEY_CREATE_RESPONSE = {
    "type": "object",
    "properties": {
        "success": {"type": "boolean"},
        "data": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
                "key": {"type": "string"},
            },
            "additionalProperties": True,
        },
    },
    "required": ["success", "data"],
    "additionalProperties": True,
}
