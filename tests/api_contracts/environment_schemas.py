# tests/api_contracts/environment_schemas.py
"""Environment 模块 JSON Schema（Web /web/environments）"""

ENVIRONMENT_ITEM = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "organizationId": {"type": "string"},
    },
    "required": ["id", "name"],
    "additionalProperties": True,
}

WEB_ENV_LIST_RESPONSE = {
    "type": "object",
    "properties": {
        "success": {"type": "boolean"},
        "data": {"type": "array", "items": ENVIRONMENT_ITEM},
    },
    "required": ["success", "data"],
    "additionalProperties": True,
}

WEB_ENV_DETAIL_RESPONSE = {
    "type": "object",
    "properties": {
        "success": {"type": "boolean"},
        "data": ENVIRONMENT_ITEM,
    },
    "required": ["success", "data"],
    "additionalProperties": True,
}

WEB_ENV_INSTANCES_RESPONSE = {
    "type": "object",
    "properties": {
        "success": {"type": "boolean"},
        "data": {
            "type": "object",
            "additionalProperties": True,
        },
    },
    "required": ["success", "data"],
    "additionalProperties": True,
}
