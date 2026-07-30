# tests/api_contracts/workflow_def_schemas.py
"""Workflow Definition 接口响应 JSON Schema 定义

控制台接口：/web/workflow-defs（RESTful /:id 风格，{success, data} 包装）
"""

WORKFLOW_DEF = {
    "type": "object",
    "required": ["id", "name"],
    "properties": {
        "id": {"type": "string"},
        "userId": {"type": "string"},
        "organizationId": {"type": "string"},
        "name": {"type": "string"},
        "description": {"type": ["string", "null"]},
        "latestVersion": {"type": ["integer", "null"]},
        "storagePath": {"type": ["string", "null"]},
        "createdAt": {"type": ["string", "number"]},
        "updatedAt": {"type": ["string", "number"]},
    },
    "additionalProperties": True,
}

WORKFLOW_VERSION = {
    "type": "object",
    "required": ["id", "workflowId", "version"],
    "properties": {
        "id": {"type": "string"},
        "workflowId": {"type": "string"},
        "version": {"type": "integer"},
        "filePath": {"type": "string"},
        "status": {"type": "string"},
        "createdBy": {"type": "string"},
        "createdAt": {"type": ["string", "number"]},
    },
    "additionalProperties": True,
}

WORKFLOW_TRIGGER = {
    "type": "object",
    "required": ["id"],
    "properties": {
        "id": {"type": "string"},
        "workflowId": {"type": "string"},
        "type": {"type": "string"},
        "enabled": {"type": "boolean"},
        "hash": {"type": "string"},
        "createdAt": {"type": ["string", "number"]},
    },
    "additionalProperties": True,
}
