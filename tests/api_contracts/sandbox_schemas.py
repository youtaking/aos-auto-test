"""Sandbox 接口响应 JSON Schema 定义

System API 接口（/api/system/sandbox-pools, /api/system/sandbox-instances）
需要 System API Key（RCS_SYSTEM_API_KEYS）认证。
"""

SANDBOX_POOL_ITEM = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "poolId": {"type": "string"},
        "name": {"type": ["string", "null"]},
        "status": {"type": ["string", "null"]},
    },
    "required": ["id"],
    "additionalProperties": True,
}

SANDBOX_INSTANCE_ITEM = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "instanceId": {"type": "string"},
        "poolId": {"type": ["string", "null"]},
        "status": {"type": ["string", "null"]},
    },
    "required": ["id"],
    "additionalProperties": True,
}
