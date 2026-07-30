# tests/api_contracts/mcp_schemas.py
"""MCP 接口响应 JSON Schema 定义

两套接口响应格式不同：
- /web/config/mcp（控制台）: action 风格，响应包装为 {success, data}，资源用 ?name=xxx 定位
- /api/mcp（OpenAPI）: RESTful 风格，响应为裸数据，列表带分页，资源用 /:id 定位
"""

# ── 通用字段定义 ──

MCP_LIST_ITEM = {
    "type": "object",
    "required": ["id", "name", "type"],
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "type": {"type": "string", "enum": ["local", "remote", "streamable-http"]},
        "enabled": {"type": "boolean"},
        "summary": {"type": "string"},
        "toolsCount": {"type": "integer"},
        "resourceAccess": {"type": "object"},
    },
    "additionalProperties": True,
}

MCP_DETAIL = {
    "type": "object",
    "required": ["id", "name", "type"],
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "type": {"type": "string", "enum": ["local", "remote", "streamable-http"]},
        "enabled": {"type": "boolean"},
        "summary": {"type": "string"},
        "config": {},  # unknown/any 类型，不做严格校验
        "resourceAccess": {"type": "object"},
    },
    "additionalProperties": True,
}

# ── /api/* OpenAPI 响应格式（裸数据） ──

API_MCP_LIST_RESPONSE = {
    "type": "object",
    "required": ["items", "total"],
    "properties": {
        "items": {"type": "array", "items": MCP_LIST_ITEM},
        "total": {"type": "integer"},
        "page": {"type": "integer"},
        "pageSize": {"type": "integer"},
    },
}

API_MCP_DETAIL_RESPONSE = MCP_DETAIL

API_CREATE_MCP_RESPONSE = MCP_DETAIL

API_DELETE_MCP_RESPONSE = {
    "type": "object",
    "required": ["id", "deleted"],
    "properties": {
        "id": {"type": "string"},
        "deleted": {"type": "boolean"},
    },
}

# ── /web/* 控制台响应格式（{success, data} 包装） ──

WEB_MCP_LIST_DATA = {
    "type": "object",
    "required": ["servers"],
    "properties": {
        "servers": {"type": "array", "items": {
            "type": "object",
            "required": ["id", "name"],
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
                "type": {"type": "string"},
                "enabled": {"type": "boolean"},
                "toolsCount": {"type": "integer"},
                "resourceAccess": {"type": "object"},
            },
            "additionalProperties": True,
        }},
    },
}

WEB_MCP_LIST_RESPONSE = {
    "type": "object",
    "required": ["success", "data"],
    "properties": {
        "success": {"type": "boolean"},
        "data": WEB_MCP_LIST_DATA,
    },
}

WEB_MCP_DETAIL_RESPONSE = {
    "type": "object",
    "required": ["success", "data"],
    "properties": {
        "success": {"type": "boolean"},
        "data": {
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": {"type": "string"},
                "config": {},
                "resourceAccess": {"type": "object"},
            },
            "additionalProperties": True,
        },
    },
}

WEB_CREATE_MCP_RESPONSE = {
    "type": "object",
    "required": ["success", "data"],
    "properties": {
        "success": {"type": "boolean"},
        "data": {
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": {"type": "string"},
            },
            "additionalProperties": True,
        },
    },
}

WEB_DELETE_MCP_RESPONSE = {
    "type": "object",
    "required": ["success"],
    "properties": {
        "success": {"type": "boolean"},
        "data": {},
    },
}

# ── MCP Action 接口 Schema ──

WEB_MCP_ENABLE_DATA = {
    "type": "object",
    "required": ["name", "enabled"],
    "properties": {
        "name": {"type": "string"},
        "enabled": {"type": "boolean"},
    },
    "additionalProperties": True,
}

WEB_MCP_DISABLE_DATA = {
    "type": "object",
    "required": ["name", "enabled"],
    "properties": {
        "name": {"type": "string"},
        "enabled": {"type": "boolean"},
    },
    "additionalProperties": True,
}

WEB_MCP_TOOLS_DATA = {
    "type": "object",
    "required": ["name", "tools"],
    "properties": {
        "name": {"type": "string"},
        "tools": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["toolName"],
                "properties": {
                    "id": {"type": "string"},
                    "toolName": {"type": "string"},
                    "description": {"type": ["string", "null"]},
                    "inputSchema": {},
                },
                "additionalProperties": True,
            },
        },
    },
    "additionalProperties": True,
}
