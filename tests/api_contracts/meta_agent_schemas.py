# tests/api_contracts/meta_agent_schemas.py
"""Meta Agent 接口响应 JSON Schema 定义

控制台接口：/web/meta-agent（{success, data} 包装）
"""

META_AGENT_ENSURE_DATA = {
    "type": "object",
    "required": ["environmentId", "status"],
    "properties": {
        "environmentId": {"type": "string"},
        "instanceId": {"type": "string"},
        "status": {"type": "string", "enum": ["created", "reused"]},
        "apiKey": {"type": "string"},
    },
    "additionalProperties": True,
}
