# tests/api_contracts/api_key_schemas.py
"""API Key 模块 JSON Schema（Web /web/api-keys）"""

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
