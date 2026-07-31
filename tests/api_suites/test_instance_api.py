# tests/api_suites/test_instance_api.py
"""Instance 接口测试：功能验证 + 契约验证

覆盖控制台接口：
- TestInstanceWebAPI: /web/instances（session cookie 认证）
"""
import pytest
# unwrapped schema (data portion after _unwrap) - can be array or object
# Instance activity 响应结构因部署状态不同而变化：
# - 无活跃实例时返回空数组 []
# - 有活跃实例时返回对象 {instances: [...], total: int}
# 因此 schema 允许 array 或 object，但 object 时必须包含 instances 字段
_WEB_INSTANCE_ACTIVITY_DATA = {
    "type": ["object", "array"],
    "properties": {
        "instances": {"type": "array"},
        "total": {"type": "integer"},
    },
}

_WEB_INSTANCE_ACTIVITY_ITEM = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "agentId": {"type": ["string", "null"]},
        "environmentId": {"type": ["string", "null"]},
        "status": {"type": ["string", "null"]},
    },
    "additionalProperties": True,
}


# ── 控制台接口测试 ──

class TestInstanceWebAPI:
    """/web/instances 控制台接口测试（session cookie 认证）

    特点：
    - GET /instances/activity 查看实例活跃度
    - POST /instances/from-environment 从环境启动实例
    - DELETE /instances/:id 停止实例
    """

    def test_get_instance_activity(self, web_client):
        """获取实例活跃度"""
        resp = web_client.get_instance_activity()
        web_client.validate_schema(resp, _WEB_INSTANCE_ACTIVITY_DATA)
        if isinstance(resp, list):
            # 空数组或包含实例对象的数组
            for item in resp:
                assert isinstance(item, dict)
                web_client.validate_schema(item, _WEB_INSTANCE_ACTIVITY_ITEM)
        elif isinstance(resp, dict):
            assert "instances" in resp, f"object 响应缺少 instances 字段: {list(resp.keys())}"
            assert isinstance(resp["instances"], list)
            assert "total" in resp, "object 响应缺少 total 字段"
            assert isinstance(resp["total"], int)
            for item in resp["instances"]:
                web_client.validate_schema(item, _WEB_INSTANCE_ACTIVITY_ITEM)

    def test_get_instance_activity_all(self, web_client):
        """获取所有实例活跃度（all=true）"""
        resp = web_client.get_instance_activity(params={"all": True})
        web_client.validate_schema(resp, _WEB_INSTANCE_ACTIVITY_DATA)

        # 获取默认响应用于对比
        resp_default = web_client.get_instance_activity()

        if isinstance(resp, list):
            for item in resp:
                assert isinstance(item, dict)
                web_client.validate_schema(item, _WEB_INSTANCE_ACTIVITY_ITEM)
            # all=true 应返回不少于默认请求的数据量
            if isinstance(resp_default, list):
                assert len(resp) >= len(resp_default), \
                    "all=true 返回数据量不应少于默认请求"
        elif isinstance(resp, dict):
            assert "instances" in resp, f"object 响应缺少 instances 字段: {list(resp.keys())}"
            assert isinstance(resp["instances"], list)
            assert "total" in resp, "object 响应缺少 total 字段"
            assert isinstance(resp["total"], int)
            for item in resp["instances"]:
                web_client.validate_schema(item, _WEB_INSTANCE_ACTIVITY_ITEM)
