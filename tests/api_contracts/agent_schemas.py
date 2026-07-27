# tests/api_contracts/agent_schemas.py
"""Agent 接口响应 JSON Schema 定义

基于 /api/agents 实际响应格式（非 /web/* 包装格式）。
列表接口返回分页结构 {items, total, page, pageSize}，
详情/创建/更新接口直接返回 Agent 对象。
"""

AGENT_LIST_ITEM = {
    "type": "object",
    "required": ["id", "name"],
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "builtIn": {"type": "boolean"},
        "model": {"type": ["string", "null"]},
        "modelId": {"type": ["string", "null"]},
        "description": {"type": ["string", "null"]},
        "machineId": {"type": ["string", "null"]},
        "knowledgeBaseCount": {"type": "integer"},
        "resourceAccess": {"type": "object"},
    },
    "additionalProperties": True,
}

AGENT_DETAIL = {
    "type": "object",
    "required": ["id", "name"],
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "builtIn": {"type": "boolean"},
        "model": {"type": ["string", "null"]},
        "modelId": {"type": ["string", "null"]},
        "prompt": {"type": ["string", "null"]},
        "description": {"type": ["string", "null"]},
        "extra": {},
        "knowledge": {},
        "skillIds": {"type": "array"},
        "mcpIds": {"type": "array"},
        "machineId": {"type": ["string", "null"]},
        "resourceAccess": {"type": "object"},
    },
    "additionalProperties": True,
}

AGENT_LIST_RESPONSE = {
    "type": "object",
    "required": ["items", "total"],
    "properties": {
        "items": {"type": "array", "items": AGENT_LIST_ITEM},
        "total": {"type": "integer"},
        "page": {"type": "integer"},
        "pageSize": {"type": "integer"},
    },
}

AGENT_DETAIL_RESPONSE = AGENT_DETAIL

CREATE_AGENT_RESPONSE = AGENT_DETAIL
