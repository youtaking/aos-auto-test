# tests/api_contracts/system_logs_schemas.py
"""System Logs API JSON Schema 定义

/api/system/logs 系统日志接口（System API Key 认证）
响应格式：{success: true, data: {...}} 包装

端点：
- GET /api/system/logs → 日志文件列表
- GET /api/system/logs/search → 搜索日志内容
- GET /api/system/logs/download → 下载日志文件（text/plain，非 JSON）
"""

# ── 通用字段 ──

SYSTEM_LOG_FILE = {
    "type": "object",
    "required": ["name", "size"],
    "properties": {
        "name": {"type": "string"},
        "size": {"type": "integer"},
        "modifiedAt": {"type": "string"},
        "isErrorLog": {"type": "boolean"},
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

SYSTEM_LOG_FILES_RESPONSE = {
    "type": "object",
    "required": ["files"],
    "properties": {
        "files": {"type": "array", "items": SYSTEM_LOG_FILE},
    },
    "additionalProperties": True,
}

SYSTEM_LOG_SEARCH_RESPONSE = {
    "type": "object",
    "required": ["file", "entries", "totalMatches"],
    "properties": {
        "file": SYSTEM_LOG_FILE,
        "entries": {"type": "array", "items": SYSTEM_LOG_SEARCH_ENTRY},
        "totalMatches": {"type": "integer"},
        "truncated": {"type": "boolean"},
    },
    "additionalProperties": True,
}
