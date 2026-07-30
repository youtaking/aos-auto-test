# tests/api_contracts/prod_view_schemas.py
"""ProdView 模块 JSON Schema（Web /web/prod-views, /web/config/prod-views）"""

PROD_VIEW_ITEM = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "agentConfigId": {"type": "string"},
        "enabled": {"type": "boolean"},
    },
    "required": ["id"],
    "additionalProperties": True,
}

WEB_PROD_VIEW_LIST_RESPONSE = {
    "type": "object",
    "properties": {
        "success": {"type": "boolean"},
        "data": {
            "type": "object",
            "additionalProperties": True,
        },
    },
    "required": ["success", "data"],
    "additionalProperties": True,
}

WEB_PROD_VIEW_DETAIL_RESPONSE = {
    "type": "object",
    "properties": {
        "success": {"type": "boolean"},
        "data": PROD_VIEW_ITEM,
    },
    "required": ["success", "data"],
    "additionalProperties": True,
}
