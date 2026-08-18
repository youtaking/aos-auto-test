# tests/api_contracts/system_api_schemas.py
"""System API JSON Schema 定义

/api/system/* 系统管理接口（System API Key 认证，RESTful 风格）
涵盖：用户管理、组织管理、API Key 管理

响应为裸数据，无 {success, data} 包装。
列表接口返回 {items, total, page, pageSize} 分页结构。
"""

# ── 通用字段 ──

SYSTEM_USER = {
    "type": "object",
    "required": ["id", "name", "email"],
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "email": {"type": "string"},
        "emailVerified": {"type": "boolean"},
        "phoneNumber": {"type": ["string", "null"]},
        "phoneNumberVerified": {"type": "boolean"},
        "createdAt": {"type": ["string", "number"]},
        "updatedAt": {"type": ["string", "number"]},
    },
    "additionalProperties": True,
}

SYSTEM_ORGANIZATION = {
    "type": "object",
    "required": ["id", "name", "slug"],
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "slug": {"type": "string"},
        "logo": {"type": ["string", "null"]},
        "metadata": {"type": ["object", "null"]},
        "createdAt": {"type": ["string", "number"]},
    },
    "additionalProperties": True,
}

SYSTEM_ORGANIZATION_MEMBER = {
    "type": "object",
    "required": ["id", "organizationId", "userId", "role"],
    "properties": {
        "id": {"type": "string"},
        "organizationId": {"type": "string"},
        "userId": {"type": "string"},
        "role": {"type": "string"},
        "createdAt": {"type": ["string", "number"]},
    },
    "additionalProperties": True,
}

SYSTEM_ORGANIZATION_DETAIL = {
    "type": "object",
    "required": ["id", "name", "slug", "members"],
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "slug": {"type": "string"},
        "logo": {"type": ["string", "null"]},
        "metadata": {"type": ["object", "null"]},
        "createdAt": {"type": ["string", "number"]},
        "members": {"type": "array", "items": SYSTEM_ORGANIZATION_MEMBER},
    },
    "additionalProperties": True,
}

SYSTEM_API_KEY_RESULT = {
    "type": "object",
    "required": ["id", "userId", "organizationId", "role"],
    "properties": {
        "id": {"type": "string"},
        "name": {"type": ["string", "null"]},
        "prefix": {"type": ["string", "null"]},
        "key": {"type": "string"},
        "start": {"type": ["string", "null"]},
        "userId": {"type": "string"},
        "organizationId": {"type": "string"},
        "role": {"type": "string"},
        "createdAt": {"type": ["string", "number"]},
        "expiresAt": {"type": ["string", "number", "null"]},
        "metadata": {"type": ["object", "null"]},
    },
    "additionalProperties": True,
}

SYSTEM_API_KEY_LIST_ITEM = {
    "type": "object",
    "required": ["id", "userId", "organizationId", "role"],
    "properties": {
        "id": {"type": "string"},
        "name": {"type": ["string", "null"]},
        "prefix": {"type": ["string", "null"]},
        "start": {"type": ["string", "null"]},
        "userId": {"type": "string"},
        "organizationId": {"type": "string"},
        "role": {"type": "string"},
        "createdAt": {"type": ["string", "number"]},
        "expiresAt": {"type": ["string", "number", "null"]},
        "metadata": {"type": ["object", "null"]},
    },
    "additionalProperties": True,
}

# ── 列表响应 ──

SYSTEM_USER_LIST_RESPONSE = {
    "type": "object",
    "required": ["items", "total"],
    "properties": {
        "items": {"type": "array", "items": SYSTEM_USER},
        "total": {"type": "integer"},
        "page": {"type": "integer"},
        "pageSize": {"type": "integer"},
    },
}

SYSTEM_ORGANIZATION_LIST_RESPONSE = {
    "type": "object",
    "required": ["items", "total"],
    "properties": {
        "items": {"type": "array", "items": SYSTEM_ORGANIZATION},
        "total": {"type": "integer"},
        "page": {"type": "integer"},
        "pageSize": {"type": "integer"},
    },
}

SYSTEM_API_KEY_LIST_RESPONSE = {
    "type": "object",
    "required": ["items", "total"],
    "properties": {
        "items": {"type": "array", "items": SYSTEM_API_KEY_LIST_ITEM},
        "total": {"type": "integer"},
        "page": {"type": "integer"},
        "pageSize": {"type": "integer"},
    },
}

SYSTEM_USER_ORGANIZATION_LIST_RESPONSE = {
    "type": "object",
    "required": ["items", "total"],
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "name"],
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "slug": {"type": "string"},
                    "memberId": {"type": "string"},
                    "role": {"type": "string"},
                    "memberCreatedAt": {"type": ["string", "number"]},
                },
                "additionalProperties": True,
            },
        },
        "total": {"type": "integer"},
        "page": {"type": "integer"},
        "pageSize": {"type": "integer"},
    },
}

# ── 写操作响应 ──

SYSTEM_DELETE_RESPONSE = {
    "type": "object",
    "required": ["deleted"],
    "properties": {
        "deleted": {"type": "boolean"},
    },
    "additionalProperties": True,
}

SYSTEM_UPDATE_RESPONSE = {
    "type": "object",
    "required": ["updated"],
    "properties": {
        "updated": {"type": "boolean"},
    },
    "additionalProperties": True,
}

# ── 详情响应（复用通用定义） ──

SYSTEM_USER_DETAIL_RESPONSE = SYSTEM_USER
SYSTEM_ORGANIZATION_DETAIL_RESPONSE = SYSTEM_ORGANIZATION_DETAIL
SYSTEM_CREATE_USER_RESPONSE = SYSTEM_USER
SYSTEM_CREATE_ORGANIZATION_RESPONSE = {
    "type": "object",
    "required": ["id", "name", "slug"],
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "slug": {"type": "string"},
        "createdAt": {"type": ["string", "number"]},
    },
    "additionalProperties": True,
}
SYSTEM_CREATE_API_KEY_RESPONSE = SYSTEM_API_KEY_RESULT
