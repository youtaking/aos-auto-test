# tests/api_contracts/agent_schemas.py
"""Agent 接口响应 JSON Schema 定义"""

AGENT_SCHEMA = {
    "type": "object",
    "required": ["id", "name"],
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "description": {"type": ["string", "null"]},
        "avatar": {"type": ["string", "null"]},
        "model": {"type": ["string", "null"]},
        "systemPrompt": {"type": ["string", "null"]},
        "createdAt": {"type": "string"},
        "updatedAt": {"type": ["string", "null"]},
    },
    "additionalProperties": True,
}

AGENT_LIST_RESPONSE = {
    "type": "object",
    "required": ["success", "data"],
    "properties": {
        "success": {"type": "boolean"},
        "data": {"type": "array", "items": AGENT_SCHEMA},
    },
}

AGENT_DETAIL_RESPONSE = {
    "type": "object",
    "required": ["success", "data"],
    "properties": {
        "success": {"type": "boolean"},
        "data": AGENT_SCHEMA,
    },
}

CREATE_AGENT_RESPONSE = {
    "type": "object",
    "required": ["success", "data"],
    "properties": {
        "success": {"type": "boolean"},
        "data": AGENT_SCHEMA,
    },
}
