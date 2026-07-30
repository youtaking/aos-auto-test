# tests/api_contracts/registry_schemas.py
"""Registry 模块 JSON Schema（Web /web/registry）"""

MACHINE_ITEM = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "status": {"type": "string"},
    },
    "required": ["id"],
    "additionalProperties": True,
}

WEB_MACHINE_LIST_RESPONSE = {
    "type": "object",
    "properties": {
        "success": {"type": "boolean"},
        "data": {
            "type": "object",
            "properties": {
                "items": {"type": "array", "items": MACHINE_ITEM},
                "total": {"type": "integer"},
            },
            "additionalProperties": True,
        },
    },
    "required": ["success", "data"],
    "additionalProperties": True,
}

WEB_MACHINE_DETAIL_RESPONSE = {
    "type": "object",
    "properties": {
        "success": {"type": "boolean"},
        "data": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
                "recentEvents": {"type": "array"},
            },
            "additionalProperties": True,
        },
    },
    "required": ["success", "data"],
    "additionalProperties": True,
}

WEB_MACHINE_EVENT_LIST_RESPONSE = {
    "type": "object",
    "properties": {
        "success": {"type": "boolean"},
        "data": {
            "type": "object",
            "properties": {
                "items": {"type": "array"},
                "total": {"type": "integer"},
            },
            "additionalProperties": True,
        },
    },
    "required": ["success", "data"],
    "additionalProperties": True,
}
