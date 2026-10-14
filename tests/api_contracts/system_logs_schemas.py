# tests/api_contracts/system_logs_schemas.py
"""System Logs API JSON Schema 定义

/api/system/logs 系统日志接口（System API Key 认证）
响应格式：{success: true, data: {...}} 包装

新契约（1b80cdfa 起，安全重设计）：
- 不暴露日志文件路径/原始文件名，客户端只能拿到服务端枚举的日志源 id（形如 app-YYYY-MM-DD / error-YYYY-MM-DD）
- GET /api/system/logs → 枚举日志源
- GET /api/system/logs/search?sourceId=.. → 在指定日志源内检索（投影 + 脱敏后的行）
- GET /api/system/logs/download?sourceId=.. → 导出同一投影为 JSON Lines（application/x-ndjson）
"""

# ── 通用字段 ──

SYSTEM_LOG_SOURCE = {
    "type": "object",
    "required": ["id", "kind", "date", "size", "modifiedAt"],
    "properties": {
        "id": {"type": "string"},
        "kind": {"type": "string", "enum": ["app", "error"]},
        "date": {"type": "string"},
        "size": {"type": "integer", "minimum": 0},
        "modifiedAt": {"type": "string"},
    },
    "additionalProperties": True,
}

SYSTEM_LOG_SEARCH_ENTRY = {
    "type": "object",
    "required": ["message"],
    "properties": {
        "timestamp": {"type": ["string", "null"]},
        "level": {"type": ["string", "null"]},
        "module": {"type": ["string", "null"]},
        "requestId": {"type": ["string", "null"]},
        "message": {"type": "string"},
        "error": {
            "type": ["object", "null"],
            "properties": {
                "type": {"type": ["string", "null"]},
                "message": {"type": ["string", "null"]},
                "stack": {"type": ["string", "null"]},
            },
        },
    },
    "additionalProperties": True,
}

# ── 响应 Schema ──

SYSTEM_LOG_SOURCES_RESPONSE = {
    "type": "object",
    "required": ["sources"],
    "properties": {
        "sources": {"type": "array", "items": SYSTEM_LOG_SOURCE},
    },
    "additionalProperties": True,
}

SYSTEM_LOG_SEARCH_RESPONSE = {
    "type": "object",
    "required": ["source", "entries", "totalMatches", "truncated"],
    "properties": {
        "source": SYSTEM_LOG_SOURCE,
        "entries": {"type": "array", "items": SYSTEM_LOG_SEARCH_ENTRY},
        "totalMatches": {"type": "integer", "minimum": 0},
        "truncated": {"type": "boolean"},
    },
    "additionalProperties": True,
}
