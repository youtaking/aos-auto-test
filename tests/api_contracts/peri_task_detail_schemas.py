# tests/api_contracts/peri_task_detail_schemas.py
"""Peri Task Detail Web API JSON Schema 定义

/web/agents/:environmentId/sessions/:sessionId/peri-tasks/:taskId/detail
控制台接口（session cookie 认证）
响应格式：{success: true, data: {...}} 包装

data 为 discriminated union（按 kind 区分）：
- kind="preview": 预览详情（items, nextCursor, complete=false, limitation）
- kind="unavailable": 不可用（reason: "not_provided"|"expired"）
"""

# ── 子结构 ──

PERI_TASK_DETAIL_ITEM = {
    "type": "object",
    "required": ["type", "content"],
    "properties": {
        "type": {"type": "string", "enum": ["text"]},
        "content": {"type": "string"},
    },
    "additionalProperties": True,
}

PERI_TASK_PREVIEW_DETAIL = {
    "type": "object",
    "required": ["kind", "taskId", "taskKind", "items", "complete"],
    "properties": {
        "kind": {"type": "string", "enum": ["preview"]},
        "taskId": {"type": "string"},
        "taskKind": {"type": "string", "enum": ["subagent", "background"]},
        "items": {"type": "array", "items": PERI_TASK_DETAIL_ITEM},
        "nextCursor": {},
        "complete": {"type": "boolean"},
        "limitation": {"type": "string"},
    },
    "additionalProperties": True,
}

PERI_TASK_UNAVAILABLE_DETAIL = {
    "type": "object",
    "required": ["kind", "taskId", "taskKind", "reason"],
    "properties": {
        "kind": {"type": "string", "enum": ["unavailable"]},
        "taskId": {"type": "string"},
        "taskKind": {"type": "string", "enum": ["subagent", "background"]},
        "reason": {"type": "string", "enum": ["not_provided", "expired"]},
    },
    "additionalProperties": True,
}

# ── 响应 Schema（data 部分，discriminated union） ──

PERI_TASK_DETAIL_RESPONSE = {
    "oneOf": [PERI_TASK_PREVIEW_DETAIL, PERI_TASK_UNAVAILABLE_DETAIL],
}
