# tests/api_contracts/system_observer_schemas.py
"""System Observer API JSON Schema 定义

/api/system/observer 系统观察接口（System API Key 认证）
响应格式：{success: true, data: {...}} 包装

端点：
- GET /api/system/observer/acp-link → ACP 活跃链接观察视图
"""

# ── 子结构 ──

OBSERVER_LEAF_VIEW = {
    "type": "object",
    "required": ["id", "source"],
    "properties": {
        "id": {"type": "string"},
        "source": {"type": "string"},
        "machineId": {"type": ["string", "null"]},
        "payload": {"type": ["object", "null"]},
    },
    "additionalProperties": True,
}

OBSERVER_INSTANCE_NODE = {
    "type": "object",
    "required": ["instanceId", "leafCount", "leaves"],
    "properties": {
        "instanceId": {"type": "string"},
        "leafCount": {"type": "integer"},
        "leaves": {"type": "array", "items": OBSERVER_LEAF_VIEW},
    },
    "additionalProperties": True,
}

OBSERVER_AGENT_NODE = {
    "type": "object",
    "required": ["agentConfigId", "instanceCount", "leafCount", "children"],
    "properties": {
        "agentConfigId": {"type": "string"},
        "instanceCount": {"type": "integer"},
        "leafCount": {"type": "integer"},
        "children": {"type": "array", "items": OBSERVER_INSTANCE_NODE},
        "leaves": {"type": "array", "items": OBSERVER_LEAF_VIEW},
    },
    "additionalProperties": True,
}

OBSERVER_USER_NODE = {
    "type": "object",
    "required": ["userId", "agentCount", "leafCount", "children"],
    "properties": {
        "userId": {"type": "string"},
        "agentCount": {"type": "integer"},
        "leafCount": {"type": "integer"},
        "children": {"type": "array", "items": OBSERVER_AGENT_NODE},
    },
    "additionalProperties": True,
}

OBSERVER_ORG_NODE = {
    "type": "object",
    "required": ["organizationId", "userCount", "agentCount", "instanceCount", "leafCount", "children"],
    "properties": {
        "organizationId": {"type": "string"},
        "userCount": {"type": "integer"},
        "agentCount": {"type": "integer"},
        "instanceCount": {"type": "integer"},
        "leafCount": {"type": "integer"},
        "children": {"type": "array", "items": OBSERVER_USER_NODE},
    },
    "additionalProperties": True,
}

OBSERVER_MACHINE_TREE_LEAF = {
    "type": "object",
    "required": ["id", "source", "roleId"],
    "properties": {
        "id": {"type": "string"},
        "source": {"type": "string"},
        "roleId": {"type": "string"},
    },
    "additionalProperties": True,
}

OBSERVER_MACHINE_TREE = {
    "type": "object",
    "required": ["machineId", "count", "leaves"],
    "properties": {
        "machineId": {"type": "string"},
        "count": {"type": "integer"},
        "leaves": {"type": "array", "items": OBSERVER_MACHINE_TREE_LEAF},
    },
    "additionalProperties": True,
}

OBSERVER_INTEGRITY_SUMMARY = {
    "type": "object",
    "required": ["checked", "mismatched", "mismatchedItems"],
    "properties": {
        "checked": {"type": "integer"},
        "mismatched": {"type": "integer"},
        "mismatchedItems": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["kind", "id"],
                "properties": {
                    "kind": {"type": "string"},
                    "id": {"type": "string"},
                },
            },
        },
    },
    "additionalProperties": True,
}

OBSERVER_NAMES = {
    "type": "object",
    "properties": {
        "organizationId": {"type": "object"},
        "userId": {"type": "object"},
        "agentConfigId": {"type": "object"},
        "instanceId": {"type": "object"},
        "machineId": {"type": "object"},
    },
    "additionalProperties": True,
}

# ── 响应 Schema ──

OBSERVER_ACP_LINK_DATA = {
    "type": "object",
    "required": ["generatedAt", "kind", "total", "trees", "integrity", "names"],
    "properties": {
        "generatedAt": {"type": "string"},
        "kind": {"type": "string", "enum": ["acp-link"]},
        "total": {"type": "integer"},
        "trees": {
            "type": "object",
            "required": ["byEntity", "byOrg"],
            "properties": {
                "byEntity": {"type": "array", "items": OBSERVER_MACHINE_TREE},
                "byOrg": {"type": "array", "items": OBSERVER_ORG_NODE},
            },
            "additionalProperties": True,
        },
        "integrity": OBSERVER_INTEGRITY_SUMMARY,
        "names": OBSERVER_NAMES,
    },
    "additionalProperties": True,
}
