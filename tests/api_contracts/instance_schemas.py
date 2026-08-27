# tests/api_contracts/instance_schemas.py
"""Instance 模块 JSON Schema（Web /web/instances）

源码 Schema：src/schemas/instance.schema.ts
"""

# InstanceInfoSchema — 实例详细信息（spawn/delete 响应）
INSTANCE_INFO = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "port": {"type": "number"},
        "status": {"type": "string", "enum": ["starting", "running", "stopped", "error"]},
        "error": {"type": ["string", "null"]},
        "group_id": {"type": "string"},
        "environment_id": {"type": ["string", "null"]},
        "session_id": {"type": ["string", "null"]},
        "instance_number": {"type": "number"},
        "created_at": {"type": "number"},
    },
    "required": ["id", "status"],
    "additionalProperties": True,
}

# 兼容旧引用
INSTANCE_ITEM = INSTANCE_INFO

WEB_INSTANCE_ACTIVITY_RESPONSE = {
    "type": "object",
    "properties": {
        "success": {"type": "boolean"},
        "data": {"type": "object", "additionalProperties": True},
    },
    "required": ["success", "data"],
    "additionalProperties": True,
}

# Spawn 响应：{success: true, data: InstanceInfo}
WEB_INSTANCE_SPAWN_RESPONSE = {
    "type": "object",
    "properties": {
        "success": {"type": "boolean"},
        "data": INSTANCE_INFO,
    },
    "required": ["success", "data"],
    "additionalProperties": True,
}

# Spawn data 部分（_unwrap 后）
WEB_INSTANCE_SPAWN_DATA = INSTANCE_INFO

# Delete 响应 data 部分：null 或 dict
WEB_INSTANCE_DELETE_DATA = {
    "type": ["null", "object"],
    "additionalProperties": True,
}
