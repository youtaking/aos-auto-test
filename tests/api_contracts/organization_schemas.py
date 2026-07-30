# tests/api_contracts/organization_schemas.py
"""Organization 接口响应 JSON Schema 定义

控制台接口：/web/organizations（RESTful /:id 风格，{success, data} 包装）
"""

# ── 通用字段定义 ──

ORGANIZATION_USER = {
    "type": "object",
    "required": ["id", "name", "email"],
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "email": {"type": "string"},
        "phoneNumber": {"type": ["string", "null"]},
    },
    "additionalProperties": True,
}

ORGANIZATION_MEMBER = {
    "type": "object",
    "required": ["id", "userId", "role"],
    "properties": {
        "id": {"type": "string"},
        "userId": {"type": "string"},
        "role": {"type": "string"},
        "organizationId": {"type": "string"},
        "user": ORGANIZATION_USER,
    },
    "additionalProperties": True,
}

ORGANIZATION_INFO = {
    "type": "object",
    "required": ["id", "name", "slug"],
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "slug": {"type": "string"},
        "logo": {"type": ["string", "null"]},
        "createdAt": {"type": ["string", "number"]},
        "metadata": {"type": ["object", "null"]},
        "role": {"type": "string"},
    },
    "additionalProperties": True,
}

ORGANIZATION_DETAIL = {
    "type": "object",
    "required": ["id", "name", "slug"],
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "slug": {"type": "string"},
        "logo": {"type": ["string", "null"]},
        "createdAt": {"type": ["string", "number"]},
        "metadata": {"type": ["object", "null"]},
        "role": {"type": "string"},
        "members": {"type": "array", "items": ORGANIZATION_MEMBER},
    },
    "additionalProperties": True,
}

ORGANIZATION_MEMBER_CANDIDATE = {
    "type": "object",
    "required": ["id", "name", "email", "isMember"],
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "email": {"type": "string"},
        "phoneNumber": {"type": ["string", "null"]},
        "isMember": {"type": "boolean"},
    },
    "additionalProperties": True,
}
