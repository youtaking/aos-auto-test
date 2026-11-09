# tests/api_suites/test_instance_api.py
"""Instance 接口测试：功能验证 + 契约验证

覆盖两套接口：
- TestInstanceWebAPI: /web/instances（session cookie 认证）
- TestInstanceOpenAPI: /api/v1/agents/:id/instances 与 /api/v1/instances/:id（API Key 认证）
"""
import httpx
import pytest
from tests.api_contracts.instance_schemas import (
    INSTANCE_INFO,
    WEB_INSTANCE_SPAWN_DATA,
)
from tests.api_contracts.openapi_extra_schemas import API_INSTANCE_LIST_RESPONSE


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

    @pytest.mark.p1
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

    @pytest.mark.p1
    def test_get_instance_activity_all(self, web_client):
        """控制台禁止跨组织实例查询，all=true 必须返回明确的 403。"""
        with pytest.raises(httpx.HTTPStatusError) as caught:
            web_client.get_instance_activity(params={"all": True})
        assert caught.value.response.status_code == 403
        body = caught.value.response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "FORBIDDEN"

    # ── Spawn Instance 测试 ──

    @pytest.mark.p0
    def test_spawn_instance_from_environment(self, web_client):
        """从环境启动实例：正向测试"""
        env_id = _get_test_env_id(web_client)
        if not env_id:
            pytest.skip("无可用环境，无法测试实例启动")

        instance_id = None
        try:
            data = web_client.spawn_instance({"environmentId": env_id})
            assert isinstance(data, dict), f"spawn 返回类型异常: {type(data)}"
            instance_id = data.get("instanceUid")
            web_client.validate_schema(data, WEB_INSTANCE_SPAWN_DATA)
            assert data["environmentId"] == env_id
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

    @pytest.mark.p2
    def test_spawn_instance_missing_environment_id(self, web_client):
        """启动实例缺少 environmentId — 应返回 400/422"""
        try:
            web_client.spawn_instance({})
            pytest.fail("缺少 environmentId 应抛出异常")
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            assert any(code in err_str for code in ("400", "422", "validation")), \
                f"缺少 environmentId 预期 400/422，实际: {e}"

    @pytest.mark.p2
    def test_spawn_instance_empty_environment_id(self, web_client):
        """启动实例 environmentId 为空字符串 — 应返回 400/422"""
        try:
            web_client.spawn_instance({"environmentId": ""})
            pytest.fail("空 environmentId 应抛出异常")
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            assert any(code in err_str for code in ("400", "422", "validation")), \
                f"空 environmentId 预期 400/422，实际: {e}"

    @pytest.mark.p2
    def test_spawn_instance_nonexistent_environment(self, web_client):
        """启动实例 environmentId 不存在 — 应返回 404"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"404"):
            web_client.spawn_instance({"environmentId": "nonexistent-env-99999"})

    # ── Delete Instance 测试 ──

    @pytest.mark.p2
    def test_delete_instance_idempotent(self, web_client):
        """删除不存在的持久实例，两次均返回 NOT_FOUND，且不产生资源。"""
        for _ in range(2):
            with pytest.raises(httpx.HTTPStatusError) as caught:
                web_client.delete_instance("nonexistent-instance-99999")
            assert caught.value.response.status_code == 404
            body = caught.value.response.json()
            assert body["success"] is False
            assert body["error"]["code"] == "NOT_FOUND"

    @pytest.mark.p1
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

        instance_id = data.get("instanceUid")
        if not instance_id:
            pytest.skip("spawn 未返回实例 id")

        try:
            result = web_client.delete_instance(instance_id)
            # 删除成功返回 null
            assert result is None or isinstance(result, (dict, type(None))), \
                f"删除实例返回类型异常: {type(result)}"

            # 持久实例已被删除，再次删除返回明确的 NOT_FOUND。
            with pytest.raises(httpx.HTTPStatusError) as caught:
                web_client.delete_instance(instance_id)
            assert caught.value.response.status_code == 404
            assert caught.value.response.json()["error"]["code"] == "NOT_FOUND"
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "403" in err_str:
                pytest.skip(f"无权限删除实例: {e}")
            raise

    @pytest.mark.p1
    def test_stop_nonexistent_instance(self, web_client):
        """停止不存在的实例：应返回 404 NOT_FOUND"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"(404|NOT_FOUND)"):
            web_client.stop_instance("nonexistent-instance-id-99999")

    @pytest.mark.p1
    def test_restart_nonexistent_instance(self, web_client):
        """重启不存在的实例：应返回 404 NOT_FOUND"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"(404|NOT_FOUND)"):
            web_client.restart_instance("nonexistent-instance-id-99999")


# ── 对外 OpenAPI 测试 ──

class TestInstanceOpenAPI:
    """/api/v1/agents/:id/instances 与 /api/v1/instances/:id（API Key 认证）

    特点：
    - GET  /api/v1/agents/:id/instances → 分页实例快照
    - GET  /api/v1/instances/:id → 单个实例详情
    - POST /api/v1/instances/:id/stop → data: null
    - POST /api/v1/instances/:id/restart → 实例详情
    - 响应为 {success, data} 信封，client 已解包为 data
    """

    def _get_first_agent_id(self, api_client):
        resp = api_client.list_agents()
        if len(resp["items"]) == 0:
            return None
        return resp["items"][0]["id"]

    @pytest.mark.p1
    def test_list_instances(self, api_client, _openapi_access):
        """列出 Agent 现有实例：返回分页结构"""
        agent_id = self._get_first_agent_id(api_client)
        if agent_id is None:
            pytest.skip("Agent 列表为空，跳过实例列表测试")

        resp = api_client.list_instances(agent_id)
        api_client.validate_schema(resp, API_INSTANCE_LIST_RESPONSE)
        assert resp["page"] == 1
        assert isinstance(resp["items"], list)

    @pytest.mark.p2
    def test_list_instances_nonexistent_agent(self, api_client, _openapi_access):
        """列出不存在 Agent 的实例：返回 404 NOT_FOUND"""
        with pytest.raises(httpx.HTTPStatusError) as caught:
            api_client.list_instances("nonexistent-agent-id-99999")
        assert caught.value.response.status_code == 404
        body = caught.value.response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "NOT_FOUND"

    @pytest.mark.p2
    def test_list_instances_invalid_page_size(self, api_client, _openapi_access):
        """pageSize 超出上限（100）：返回 400 VALIDATION_ERROR"""
        with pytest.raises(httpx.HTTPStatusError) as caught:
            api_client.list_instances("nonexistent-agent-id-99999", {"pageSize": 99999})
        assert caught.value.response.status_code == 400
        body = caught.value.response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.p2
    def test_get_nonexistent_instance(self, api_client, _openapi_access):
        """查询不存在的实例：返回 404 NOT_FOUND"""
        with pytest.raises(httpx.HTTPStatusError) as caught:
            api_client.get_instance("nonexistent-instance-id-99999")
        assert caught.value.response.status_code == 404
        body = caught.value.response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "NOT_FOUND"

    @pytest.mark.p2
    def test_stop_nonexistent_instance(self, api_client, _openapi_access):
        """停止不存在的实例：返回 404 NOT_FOUND"""
        with pytest.raises(httpx.HTTPStatusError) as caught:
            api_client.stop_instance("nonexistent-instance-id-99999")
        assert caught.value.response.status_code == 404
        body = caught.value.response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "NOT_FOUND"

    @pytest.mark.p2
    def test_restart_nonexistent_instance(self, api_client, _openapi_access):
        """重启不存在的实例：返回 404 NOT_FOUND"""
        with pytest.raises(httpx.HTTPStatusError) as caught:
            api_client.restart_instance("nonexistent-instance-id-99999")
        assert caught.value.response.status_code == 404
        body = caught.value.response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "NOT_FOUND"
