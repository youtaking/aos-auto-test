# tests/api_contracts/organization_schemas.py
"""Organization 接口响应 JSON Schema 定义

控制台接口：/web/organizations（RESTful /:id 风格，{success, data} 包装）
"""

# ── 通用字段定义 ──

# /web/* 业务错误信封（路由显式返回 {success:false, error:{code,message}}）
WEB_ERROR_RESPONSE = {
    "type": "object",
    "required": ["success", "error"],
    "properties": {
        "success": {"const": False},
        "error": {
            "type": "object",
            "required": ["code", "message"],
            "properties": {
                "code": {"type": "string"},
                "message": {"type": "string"},
            },
            "additionalProperties": True,
        },
    },
    "additionalProperties": True,
}

# /web/* 宿主参数校验错误（Elysia schema 失败经 errorPlugin 输出 {error:{type,message}}）
WEB_VALIDATION_ERROR_RESPONSE = {
    "type": "object",
    "required": ["error"],
    "properties": {
        "error": {
            "type": "object",
            "required": ["type", "message"],
            "properties": {
                "type": {"const": "VALIDATION_ERROR"},
                "message": {"type": "string"},
            },
            "additionalProperties": True,
        },
    },
    "additionalProperties": True,
}

# 创建组织请求体：name / slug 必须包含非空白字符（服务端 schema refine）
ORGANIZATION_CREATE_REQUEST = {
    "type": "object",
    "required": ["name", "slug"],
    "properties": {
        "name": {"type": "string", "pattern": r"\S"},
        "slug": {"type": "string", "pattern": r"\S"},
        "description": {"type": "string"},
    },
    "additionalProperties": True,
}

# 更新组织请求体：顶层 name/slug 与透传 data 互斥，两种格式内部字段都不得为空白
ORGANIZATION_UPDATE_REQUEST = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "pattern": r"\S"},
        "slug": {"type": "string", "pattern": r"\S"},
        "data": {"type": "object"},
    },
    "not": {
        "anyOf": [
            {"required": ["name", "data"]},
            {"required": ["slug", "data"]},
        ]
    },
    "additionalProperties": True,
}

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
