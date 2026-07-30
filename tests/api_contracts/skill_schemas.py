# tests/api_contracts/skill_schemas.py
"""Skill 接口响应 JSON Schema 定义

两套接口响应格式不同：
- /web/config/skills（控制台）: RESTful 风格（/:name），响应包装为 {success, data}
- /api/skills（OpenAPI）: RESTful 风格（/:id），响应为裸数据，列表带分页
"""

# ── 通用字段定义 ──

SKILL_LIST_ITEM = {
    "type": "object",
    "required": ["name"],
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "description": {"type": ["string", "null"]},
        "resourceAccess": {"type": "object"},
    },
    "additionalProperties": True,
}

SKILL_DETAIL = {
    "type": "object",
    "required": ["name"],
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "description": {"type": ["string", "null"]},
        "content": {"type": "string"},
        "metadata": {"type": "object"},
        "resourceAccess": {"type": "object"},
    },
    "additionalProperties": True,
}

# ── /api/* OpenAPI 响应格式（裸数据） ──

API_SKILL_LIST_RESPONSE = {
    "type": "object",
    "required": ["items", "total"],
    "properties": {
        "items": {"type": "array", "items": SKILL_LIST_ITEM},
        "total": {"type": "integer"},
        "page": {"type": "integer"},
        "pageSize": {"type": "integer"},
    },
}

API_SKILL_DETAIL_RESPONSE = SKILL_DETAIL

API_DELETE_SKILL_RESPONSE = {
    "type": "object",
    "required": ["id", "deleted"],
    "properties": {
        "id": {"type": "string"},
        "deleted": {"type": "boolean"},
    },
}

# ── /web/* 控制台响应格式（{success, data} 包装） ──

WEB_SKILL_LIST_DATA = {
    "type": "object",
    "required": ["skills"],
    "properties": {
        "skills": {"type": "array", "items": {
            "type": "object",
            "required": ["name"],
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
                "description": {"type": ["string", "null"]},
                "resourceAccess": {"type": "object"},
            },
            "additionalProperties": True,
        }},
    },
}

WEB_SKILL_LIST_RESPONSE = {
    "type": "object",
    "required": ["success", "data"],
    "properties": {
        "success": {"type": "boolean"},
        "data": WEB_SKILL_LIST_DATA,
    },
}

WEB_SKILL_DETAIL_RESPONSE = {
    "type": "object",
    "required": ["success", "data"],
    "properties": {
        "success": {"type": "boolean"},
        "data": SKILL_DETAIL,
    },
}

WEB_CREATE_SKILL_RESPONSE = {
    "type": "object",
    "required": ["success", "data"],
    "properties": {
        "success": {"type": "boolean"},
        "data": {
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": {"type": "string"},
                "resourceAccess": {"type": "object"},
            },
            "additionalProperties": True,
        },
    },
}

WEB_DELETE_SKILL_RESPONSE = {
    "type": "object",
    "required": ["success"],
    "properties": {
        "success": {"type": "boolean"},
        "data": {},
    },
}
