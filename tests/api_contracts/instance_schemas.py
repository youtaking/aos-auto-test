# tests/api_contracts/instance_schemas.py
"""Instance 模块 JSON Schema（Web /web/instances）"""

INSTANCE_ITEM = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "environmentId": {"type": "string"},
        "status": {"type": "string"},
    },
    "required": ["id"],
    "additionalProperties": True,
}

WEB_INSTANCE_ACTIVITY_RESPONSE = {
    "type": "object",
    "properties": {
        "success": {"type": "boolean"},
        "data": {"type": "object", "additionalProperties": True},
    },
    "required": ["success", "data"],
    "additionalProperties": True,
}

WEB_INSTANCE_SPAWN_RESPONSE = {
    "type": "object",
    "properties": {
        "success": {"type": "boolean"},
        "data": INSTANCE_ITEM,
    },
    "required": ["success", "data"],
    "additionalProperties": True,
}
