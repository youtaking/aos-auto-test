# tests/api_contracts/channel_schemas.py
"""Channel 模块 JSON Schema（Web /web/channels）"""

CHANNEL_BINDING_ITEM = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "platform": {"type": "string"},
        "agentId": {"type": "string"},
        "enabled": {"type": "boolean"},
    },
    "required": ["id"],
    "additionalProperties": True,
}

WEB_CHANNEL_PROVIDER_LIST_RESPONSE = {
    "type": "object",
    "properties": {
        "success": {"type": "boolean"},
        "data": {"type": "object", "additionalProperties": True},
    },
    "required": ["success", "data"],
    "additionalProperties": True,
}

WEB_CHANNEL_BINDING_LIST_RESPONSE = {
    "type": "object",
    "properties": {
        "success": {"type": "boolean"},
        "data": {"type": "array", "items": CHANNEL_BINDING_ITEM},
    },
    "required": ["success", "data"],
    "additionalProperties": True,
}

WEB_CHANNEL_BINDING_DETAIL_RESPONSE = {
    "type": "object",
    "properties": {
        "success": {"type": "boolean"},
        "data": CHANNEL_BINDING_ITEM,
    },
    "required": ["success", "data"],
    "additionalProperties": True,
}

WEB_HERMES_STATUS_RESPONSE = {
    "type": "object",
    "properties": {
        "success": {"type": "boolean"},
        "data": {
            "type": "object",
            "properties": {
                "connected": {"type": "boolean"},
            },
            "additionalProperties": True,
        },
    },
    "required": ["success", "data"],
    "additionalProperties": True,
}
