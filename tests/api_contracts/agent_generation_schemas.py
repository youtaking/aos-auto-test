# tests/api_contracts/agent_generation_schemas.py
"""Agent Generation 接口响应 JSON Schema 定义

控制台接口：/web/agent-generation（{success, data} 包装）
"""

AGENT_GENERATION_SKILL = {
    "type": "object",
    "required": ["id", "name", "description"],
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "description": {"type": "string"},
    },
    "additionalProperties": True,
}

AGENT_GENERATION_RESULT = {
    "type": "object",
    "required": ["name", "systemPrompt", "skills"],
    "properties": {
        "name": {"type": "string"},
        "systemPrompt": {"type": "string"},
        "skills": {"type": "array", "items": AGENT_GENERATION_SKILL},
    },
    "additionalProperties": True,
}
