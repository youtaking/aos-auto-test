# tests/api_contracts/task_schemas.py
"""Task 模块 JSON Schema（Web /web/tasks/v2，deprecated /web/tasks）"""

TASK_V2_ITEM = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "type": {"type": "string"},
        "enabled": {"type": "boolean"},
    },
    "required": ["id"],
    "additionalProperties": True,
}

WEB_TASK_V2_LIST_RESPONSE = {
    "type": "object",
    "properties": {
        "success": {"type": "boolean"},
        "data": {
            "type": "object",
            "properties": {
                "items": {"type": "array", "items": TASK_V2_ITEM},
                "total": {"type": "integer"},
                "page": {"type": "integer"},
                "pageSize": {"type": "integer"},
            },
            "additionalProperties": True,
        },
    },
    "required": ["success", "data"],
    "additionalProperties": True,
}

WEB_TASK_V2_DETAIL_RESPONSE = {
    "type": "object",
    "properties": {
        "success": {"type": "boolean"},
        "data": TASK_V2_ITEM,
    },
    "required": ["success", "data"],
    "additionalProperties": True,
}
