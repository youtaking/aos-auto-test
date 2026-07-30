# tests/api_contracts/agent_site_schemas.py
"""Agent Site 接口响应 JSON Schema 定义

控制台接口：/web/agent-sites（RESTful /:id 风格，{success, data} 包装）
"""

AGENT_SITE_APP = {
    "type": "object",
    "required": ["id", "name"],
    "properties": {
        "id": {"type": "string"},
        "organizationId": {"type": "string"},
        "userId": {"type": "string"},
        "remoteAppId": {"type": "string"},
        "name": {"type": "string"},
        "description": {"type": ["string", "null"]},
        "visibility": {"type": "string"},
        "appType": {"type": "string"},
        "entryFile": {"type": ["string", "null"]},
        "activeSlot": {"type": ["string", "null"]},
        "deployedAt": {"type": ["integer", "null"]},
        "createdByAgentConfigId": {"type": ["string", "null"]},
        "createdAt": {"type": "integer"},
        "updatedAt": {"type": "integer"},
    },
    "additionalProperties": True,
}
