# tests/api_contracts/acp_schemas.py
"""ACP 模块 JSON Schema（/acp/agents）

源码 Schema：src/schemas/acp.schema.ts
"""

# AcpAgentSchema — ACP Agent 列表项
ACP_AGENT_ITEM = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "agent_name": {"type": ["string", "null"]},
        "status": {"type": "string", "enum": ["online", "offline"]},
        "max_sessions": {"type": "number"},
        "last_seen_at": {"type": ["number", "null"]},
        "created_at": {"type": "number"},
    },
    "required": ["id", "status", "max_sessions", "created_at"],
    "additionalProperties": True,
}

# GET /acp/agents 响应：直接数组（无 {success, data} 包装）
ACP_AGENT_LIST_DATA = {
    "type": "array",
    "items": ACP_AGENT_ITEM,
}
