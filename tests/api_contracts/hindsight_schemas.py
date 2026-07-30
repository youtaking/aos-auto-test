# tests/api_contracts/hindsight_schemas.py
"""Hindsight 模块 JSON Schema（Web /web/hindsight，代理到外部服务）"""

WEB_HINDSIGHT_STATUS_RESPONSE = {
    "type": "object",
    "properties": {
        "success": {"type": "boolean"},
        "data": {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean"},
            },
            "additionalProperties": True,
        },
    },
    "required": ["success", "data"],
    "additionalProperties": True,
}

WEB_HINDSIGHT_PROXY_RESPONSE = {
    "type": "object",
    "properties": {
        "success": {"type": "boolean"},
        "data": {"additionalProperties": True},
    },
    "required": ["success", "data"],
    "additionalProperties": True,
}
