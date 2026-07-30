# tests/api_contracts/branding_schemas.py
"""Branding / Sidebar / Custom Tools 接口响应 JSON Schema 定义

控制台接口：只读配置类接口（{success, data} 包装）
"""

BRANDING_DATA = {
    "type": "object",
    "required": ["brandName", "logoUrl"],
    "properties": {
        "brandName": {"type": "string"},
        "logoUrl": {"type": ["string", "null"]},
    },
    "additionalProperties": True,
}

CUSTOM_TOOL = {
    "type": "object",
    "required": ["name"],
    "properties": {
        "name": {"type": "string"},
        "description": {"type": "string"},
        "inputs": {"type": "array"},
        "produces": {"type": ["string", "null"]},
    },
    "additionalProperties": True,
}
