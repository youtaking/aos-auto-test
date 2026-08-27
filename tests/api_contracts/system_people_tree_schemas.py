# tests/api_contracts/system_people_tree_schemas.py
"""System People Tree API JSON Schema 定义

/api/system/people-tree 组织人员智能体层级接口（System API Key 认证）
响应格式：{success: true, data: {organizations: [...]}} 包装

端点：
- GET /api/system/people-tree → 组织 → 成员 → 智能体配置层级
"""

# ── 子结构 ──

SYSTEM_PEOPLE_AGENT = {
    "type": "object",
    "required": ["id", "name"],
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "description": {"type": ["string", "null"]},
        "machineId": {"type": ["string", "null"]},
        "engineType": {"type": ["string", "null"]},
    },
    "additionalProperties": True,
}

SYSTEM_PEOPLE_USER = {
    "type": "object",
    "required": ["id", "name", "email", "agents"],
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "email": {"type": "string"},
        "phoneNumber": {"type": ["string", "null"]},
        "role": {"type": ["string", "null"]},
        "agents": {"type": "array", "items": SYSTEM_PEOPLE_AGENT},
    },
    "additionalProperties": True,
}

SYSTEM_PEOPLE_ORGANIZATION = {
    "type": "object",
    "required": ["id", "name", "slug", "users"],
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "slug": {"type": "string"},
        "users": {"type": "array", "items": SYSTEM_PEOPLE_USER},
    },
    "additionalProperties": True,
}

# ── 响应 Schema ──

SYSTEM_PEOPLE_TREE_RESPONSE = {
    "type": "object",
    "required": ["organizations"],
    "properties": {
        "organizations": {"type": "array", "items": SYSTEM_PEOPLE_ORGANIZATION},
    },
    "additionalProperties": True,
}
