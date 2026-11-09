# tests/api_contracts/openapi_extra_schemas.py
"""剩余 OpenAPI 模块 JSON Schema

覆盖 /api/v1 下的 knowledge-bases、workflows、instances、workspaces、chat 等接口。
响应为 {success, data} 信封，客户端解包后校验 data。
"""

# ── Knowledge Bases（只读列表） ──
API_KNOWLEDGE_BASE_LIST_ITEM = {
    "type": "object",
    "required": ["id", "name"],
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "description": {"type": ["string", "null"]},
        "provider": {"type": "string"},
        "status": {"type": "string", "enum": ["empty", "indexing", "ready", "error"]},
        "resourcesCount": {"type": "integer"},
        "bindingsCount": {"type": "integer"},
        "embeddingModel": {"type": ["string", "null"]},
        "parseMethod": {"type": ["string", "null"]},
        "chunkMethod": {"type": ["string", "null"]},
        "remoteExists": {"type": "boolean"},
    },
    "additionalProperties": True,
}

API_KNOWLEDGE_BASE_LIST_RESPONSE = {
    "type": "object",
    "properties": {
        "items": {"type": "array", "items": API_KNOWLEDGE_BASE_LIST_ITEM},
        "total": {"type": "integer"},
        "page": {"type": "integer"},
        "pageSize": {"type": "integer"},
    },
    "required": ["items", "total", "page", "pageSize"],
    "additionalProperties": True,
}

# ── Workflows（/api/v1/workflows/:workflowId/execute 的 data） ──
API_WORKFLOW_EXECUTE_RESPONSE = {
    "type": "object",
    "required": ["runId", "status", "version"],
    "properties": {
        "runId": {"type": "string"},
        "status": {"type": "string", "enum": ["SUCCESS", "FAILED", "TIMEOUT"]},
        "version": {"type": "integer"},
        "output": {"type": "object"},
        "error": {"type": "object"},
        "duration": {"type": "number"},
    },
    "additionalProperties": True,
}

# ── Workflow v2（/api/v1/workflow-v2/workflows/:id/run 的 data） ──
API_WORKFLOW_V2_RUN_RESPONSE = {
    "type": "object",
    "required": ["executeId", "data", "token", "cost", "debugUrl"],
    "properties": {
        "executeId": {"type": ["string", "null"]},
        "data": {"type": ["string", "null"]},
        "token": {"type": ["integer", "null"]},
        "cost": {"type": ["string", "null"]},
        "debugUrl": {"type": ["string", "null"]},
    },
    "additionalProperties": True,
}

# ── Instances ──
API_INSTANCE_CONNECT_RESPONSE = {
    "type": "object",
    "required": ["agentConfigId", "environmentId", "instanceId", "status", "runtimeGeneration", "relay"],
    "properties": {
        "agentConfigId": {"type": "string"},
        "environmentId": {"type": "string"},
        "instanceId": {"type": "string"},
        "status": {"type": "string", "enum": ["running"]},
        "runtimeGeneration": {"type": "integer"},
        "relay": {
            "type": "object",
            "required": ["wsUrl"],
            "properties": {"wsUrl": {"type": "string"}},
            "additionalProperties": True,
        },
    },
    "additionalProperties": True,
}

API_INSTANCE_DETAIL = {
    "type": "object",
    "required": [
        "instanceId", "agentConfigId", "environmentId", "name", "creationSource",
        "isDefault", "status", "runtimeGeneration", "createdAt", "updatedAt",
    ],
    "properties": {
        "instanceId": {"type": "string"},
        "agentConfigId": {"type": "string"},
        "environmentId": {"type": "string"},
        "name": {"type": "string"},
        "creationSource": {"type": "string", "enum": ["user", "api"]},
        "isDefault": {"type": "boolean"},
        "status": {"type": "string", "enum": ["stopped", "starting", "running", "stopping", "unknown"]},
        "runtimeGeneration": {"type": "integer"},
        "createdAt": {"type": "string"},
        "updatedAt": {"type": "string"},
    },
    "additionalProperties": True,
}

API_INSTANCE_LIST_RESPONSE = {
    "type": "object",
    "required": ["items", "total", "page", "pageSize"],
    "properties": {
        "items": {"type": "array", "items": API_INSTANCE_DETAIL},
        "total": {"type": "integer"},
        "page": {"type": "integer"},
        "pageSize": {"type": "integer"},
    },
    "additionalProperties": True,
}

# ── Workspaces ──
API_WORKSPACE_FILE_TREE_RESPONSE = {
    "type": "object",
    "required": ["environmentId", "paths"],
    "properties": {
        "environmentId": {"type": "string"},
        "paths": {"type": "array", "items": {"type": "string"}},
        "mtimes": {"type": "object"},
        "errors": {"type": "array"},
    },
    "additionalProperties": True,
}

API_WORKSPACE_UPLOAD_RESPONSE = {
    "type": "object",
    "required": ["environmentId", "files"],
    "properties": {
        "environmentId": {"type": "string"},
        "files": {"type": "array"},
    },
    "additionalProperties": True,
}

# ── OpenAI Chat（/api/v1/chat/completions） ──
API_OPENAI_CHAT_RESPONSE = {
    "type": "object",
    "required": ["id", "object", "created", "model", "choices"],
    "properties": {
        "id": {"type": "string"},
        "object": {"type": "string", "enum": ["chat.completion"]},
        "created": {"type": "integer"},
        "model": {"type": "string"},
        "choices": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["index", "message", "finish_reason"],
                "properties": {
                    "index": {"type": "integer"},
                    "message": {
                        "type": "object",
                        "required": ["role", "content"],
                        "properties": {
                            "role": {"type": "string", "enum": ["assistant"]},
                            "content": {"type": "string"},
                        },
                        "additionalProperties": True,
                    },
                    "finish_reason": {"type": "string", "enum": ["stop", "length"]},
                },
                "additionalProperties": True,
            },
        },
    },
    "additionalProperties": True,
}

# OpenAI 兼容错误信封：{error: {message, type, param, code}}
API_OPENAI_CHAT_ERROR_RESPONSE = {
    "type": "object",
    "required": ["error"],
    "properties": {
        "error": {
            "type": "object",
            "required": ["message", "type"],
            "properties": {
                "message": {"type": "string"},
                "type": {"type": "string"},
                "param": {"type": ["string", "null"]},
                "code": {"type": "string"},
            },
            "additionalProperties": True,
        },
    },
    "additionalProperties": True,
}

# ── System API ──
API_SYSTEM_USER_LIST_RESPONSE = {
    "type": "object",
    "properties": {
        "items": {"type": "array"},
        "total": {"type": "integer"},
        "page": {"type": "integer"},
        "pageSize": {"type": "integer"},
    },
    "required": ["items", "total"],
    "additionalProperties": True,
}

API_SYSTEM_USER_DETAIL = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "email": {"type": "string"},
    },
    "required": ["id"],
    "additionalProperties": True,
}

API_SYSTEM_ORG_LIST_RESPONSE = {
    "type": "object",
    "properties": {
        "items": {"type": "array"},
        "total": {"type": "integer"},
        "page": {"type": "integer"},
        "pageSize": {"type": "integer"},
    },
    "required": ["items", "total"],
    "additionalProperties": True,
}

API_SYSTEM_ORG_DETAIL = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
    },
    "required": ["id"],
    "additionalProperties": True,
}

# ── System API 写操作响应 ──

API_SYSTEM_DELETE_RESPONSE = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "deleted": {"type": "boolean"},
        "success": {"type": "boolean"},
    },
    "additionalProperties": True,
}

API_SYSTEM_UPDATE_RESPONSE = {
    "type": "object",
    "additionalProperties": True,
}

API_SYSTEM_USER_CREATE_RESPONSE = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "email": {"type": "string"},
    },
    "required": ["id"],
    "additionalProperties": True,
}

API_SYSTEM_ORG_CREATE_RESPONSE = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
    },
    "required": ["id"],
    "additionalProperties": True,
}

API_SYSTEM_API_KEY_RESULT = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "key": {"type": "string"},
    },
    "required": ["id"],
    "additionalProperties": True,
}

API_SYSTEM_API_KEY_LIST_RESPONSE = {
    "type": "object",
    "properties": {
        "items": {"type": "array"},
        "total": {"type": "integer"},
        "page": {"type": "integer"},
        "pageSize": {"type": "integer"},
    },
    "required": ["items", "total"],
    "additionalProperties": True,
}

API_SYSTEM_ORG_MEMBER = {
    "type": "object",
    "properties": {
        "userId": {"type": "string"},
        "organizationId": {"type": "string"},
    },
    "additionalProperties": True,
}

API_SYSTEM_USER_ORG_LIST_RESPONSE = {
    "type": "object",
    "properties": {
        "items": {"type": "array"},
        "total": {"type": "integer"},
        "page": {"type": "integer"},
        "pageSize": {"type": "integer"},
    },
    "required": ["items", "total"],
    "additionalProperties": True,
}
