# tests/api_contracts/workflow_run_schemas.py
"""Workflow Run 接口响应 JSON Schema 定义

/web/workflow-runs（控制台）: 响应包装为 {success, data}
运行记录查询、事件读取、审批等只读操作。
"""

WORKFLOW_RUN_ITEM = {
    "type": "object",
    "required": ["run_id"],
    "properties": {
        "run_id": {"type": "string"},
        "id": {"type": "string"},
        "workflow_id": {"type": ["string", "null"]},
        "status": {"type": ["string", "null"]},
        "dag_status": {"type": ["string", "null"]},
        "created_at": {"type": ["string", "null"]},
        "updated_at": {"type": ["string", "null"]},
    },
    "additionalProperties": True,
}

WORKFLOW_RUN_DETAIL = {
    "type": "object",
    "required": ["run_id"],
    "properties": {
        "run_id": {"type": "string"},
        "id": {"type": "string"},
        "workflow_id": {"type": ["string", "null"]},
        "status": {"type": ["string", "null"]},
        "dag_status": {"type": ["string", "null"]},
        "inputs": {"type": ["object", "null"]},
        "outputs": {"type": ["object", "null"]},
        "created_at": {"type": ["string", "null"]},
        "updated_at": {"type": ["string", "null"]},
    },
    "additionalProperties": True,
}

WORKFLOW_RUN_EVENT = {
    "type": "object",
    "required": ["event_id", "type"],
    "properties": {
        "event_id": {"type": ["string", "null"]},
        "type": {"type": ["string", "null"]},
        "timestamp": {"type": ["string", "null"]},
        "data": {"type": ["object", "null"]},
    },
    "additionalProperties": True,
}

WORKFLOW_RUN_APPROVAL = {
    "type": "object",
    "required": ["approval_id", "status"],
    "properties": {
        "approval_id": {"type": ["string", "null"]},
        "status": {"type": ["string", "null"]},
        "approver": {"type": ["string", "null"]},
    },
    "additionalProperties": True,
}
