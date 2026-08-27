# tests/api_suites/test_instance_api.py
"""Instance 接口测试：功能验证 + 契约验证

覆盖控制台接口：
- TestInstanceWebAPI: /web/instances（session cookie 认证）
"""
import httpx
import pytest
from tests.api_contracts.instance_schemas import (
    INSTANCE_INFO,
    WEB_INSTANCE_SPAWN_DATA,
)


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


# ── 工具函数 ──

def _get_test_env_id(client) -> str | None:
    """获取一个可用的环境 ID，返回 env_id 或 None"""
    try:
        envs = client.list_environments()
        if isinstance(envs, list) and len(envs) > 0:
            return envs[0].get("id")
        if isinstance(envs, dict) and "items" in envs:
            items = envs["items"]
            if len(items) > 0:
                return items[0].get("id")
    except Exception:
        pass
    return None


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

    # ── Spawn Instance 测试 ──

    def test_spawn_instance_from_environment(self, web_client):
        """从环境启动实例：正向测试"""
        env_id = _get_test_env_id(web_client)
        if not env_id:
            pytest.skip("无可用环境，无法测试实例启动")

        instance_id = None
        try:
            data = web_client.spawn_instance({"environmentId": env_id})
            # spawn 返回 InstanceInfo（_unwrap 后的 data 部分）
            if data is not None:
                assert isinstance(data, dict), f"spawn 返回类型异常: {type(data)}"
                web_client.validate_schema(data, WEB_INSTANCE_SPAWN_DATA)
                assert "id" in data, f"spawn 响应缺少 id 字段: {list(data.keys())}"
                instance_id = data["id"]
                assert "status" in data, f"spawn 响应缺少 status 字段"
                assert data["status"] in ("starting", "running", "stopped", "error"), \
                    f"spawn status 非法: {data['status']}"
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "404" in err_str:
                pytest.skip(f"环境 {env_id} 不存在: {e}")
            if "503" in err_str or "502" in err_str:
                pytest.skip(f"实例启动服务不可用: {e}")
            raise
        finally:
            # 清理：删除启动的实例
            if instance_id:
                try:
                    web_client.delete_instance(instance_id)
                except (httpx.HTTPStatusError, RuntimeError):
                    pass  # 幂等删除，忽略错误

    def test_spawn_instance_missing_environment_id(self, web_client):
        """启动实例缺少 environmentId — 应返回 400/422"""
        try:
            web_client.spawn_instance({})
            pytest.fail("缺少 environmentId 应抛出异常")
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            assert any(code in err_str for code in ("400", "422", "validation")), \
                f"缺少 environmentId 预期 400/422，实际: {e}"

    def test_spawn_instance_empty_environment_id(self, web_client):
        """启动实例 environmentId 为空字符串 — 应返回 400/422"""
        try:
            web_client.spawn_instance({"environmentId": ""})
            pytest.fail("空 environmentId 应抛出异常")
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            assert any(code in err_str for code in ("400", "422", "validation")), \
                f"空 environmentId 预期 400/422，实际: {e}"

    def test_spawn_instance_nonexistent_environment(self, web_client):
        """启动实例 environmentId 不存在 — 应返回 404"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"404"):
            web_client.spawn_instance({"environmentId": "nonexistent-env-99999"})

    # ── Delete Instance 测试 ──

    def test_delete_instance_idempotent(self, web_client):
        """DELETE 幂等性：删除不存在的实例应返回成功（幂等）"""
        # 源码逻辑：对已停止或不存在的实例幂等返回成功
        try:
            result = web_client.delete_instance("nonexistent-instance-99999")
            # 幂等删除返回 null 或 dict
            assert result is None or isinstance(result, (dict, type(None))), \
                f"幂等删除返回类型异常: {type(result)}"
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            # 也可能返回 403（跨组织访问）
            assert "403" in err_str, \
                f"幂等删除预期成功或 403，实际: {e}"

    def test_delete_instance_after_spawn(self, web_client):
        """启动后删除实例：生命周期测试"""
        env_id = _get_test_env_id(web_client)
        if not env_id:
            pytest.skip("无可用环境，无法测试实例删除")

        try:
            data = web_client.spawn_instance({"environmentId": env_id})
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "404" in err_str or "503" in err_str or "502" in err_str:
                pytest.skip(f"实例启动不可用: {e}")
            raise

        if data is None or not isinstance(data, dict):
            pytest.skip("spawn 返回空，无法测试删除")

        instance_id = data.get("id")
        if not instance_id:
            pytest.skip("spawn 未返回实例 id")

        try:
            result = web_client.delete_instance(instance_id)
            # 删除成功返回 null
            assert result is None or isinstance(result, (dict, type(None))), \
                f"删除实例返回类型异常: {type(result)}"

            # 幂等验证：第二次删除也应成功
            result2 = web_client.delete_instance(instance_id)
            assert result2 is None or isinstance(result2, (dict, type(None))), \
                f"幂等删除返回类型异常: {type(result2)}"
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "403" in err_str:
                pytest.skip(f"无权限删除实例: {e}")
            raise
