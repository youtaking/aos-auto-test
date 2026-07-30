# tests/api_contracts/knowledge_base_schemas.py
"""Knowledge Base 接口响应 JSON Schema 定义

控制台接口：/web/knowledgeBases（RESTful /:id 风格，{success, data} 包装）
"""

KNOWLEDGE_BASE_INFO = {
    "type": "object",
    "required": ["id", "name"],
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "slug": {"type": "string"},
        "description": {"type": ["string", "null"]},
        "provider": {"type": "string"},
        "status": {"type": "string"},
        "remoteId": {"type": ["string", "null"]},
        "embeddingModel": {"type": ["string", "null"]},
        "parseMethod": {"type": ["string", "null"]},
        "resourceCount": {"type": "integer"},
        "createdAt": {"type": ["string", "number"]},
        "updatedAt": {"type": ["string", "number"]},
    },
    "additionalProperties": True,
}

KNOWLEDGE_RESOURCE = {
    "type": "object",
    "required": ["id"],
    "properties": {
        "id": {"type": "string"},
        "knowledgeBaseId": {"type": "string"},
        "name": {"type": "string"},
        "type": {"type": "string"},
        "status": {"type": "string"},
        "enabled": {"type": "boolean"},
        "chunkCount": {"type": "integer"},
        "createdAt": {"type": ["string", "number"]},
    },
    "additionalProperties": True,
}
