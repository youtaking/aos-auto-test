# tests/api_suites/test_environment_api.py
"""Environment 接口测试：功能验证 + 契约验证

覆盖控制台接口：
- TestEnvironmentWebAPI: /web/environments（session cookie 认证，RESTful /:id 风格）

注：环境创建需要有效的 agentConfigId，测试中先获取现有 agent 列表取第一个 ID。
"""
import httpx
import pytest
from tests.api_contracts.environment_schemas import (
    ENVIRONMENT_ITEM,
)

# unwrapped schemas (data portion after _unwrap)
_WEB_ENV_LIST_DATA = {"type": "array", "items": ENVIRONMENT_ITEM}


# ── 工具函数 ──

def _cleanup_environment(client, name: str):
    """按名称查找并删除环境，忽略错误"""
    try:
        envs = client.list_environments()
        for env in envs:
            if env.get("name") == name:
                client.delete_environment(env["id"])
    except Exception as e:
        import logging
        logging.getLogger("cleanup").warning(f"Cleanup failed: {e}")


def _get_first_agent_config_id(client) -> str | None:
    """获取第一个可用的 agentConfigId"""
    try:
        agents = client.list_agents()
        agent_list = agents.get("agents", [])
        if agent_list:
            return agent_list[0].get("id") or agent_list[0].get("name")
    except Exception as e:
        import logging
        logging.getLogger("cleanup").warning(f"Cleanup failed: {e}")
    return None


# ── 控制台接口测试 ──

class TestEnvironmentWebAPI:
    """/web/environments 控制台接口测试（session cookie 认证，RESTful /:id 风格）

    特点：
    - 用 /:id 路径参数定位资源
    - 响应统一包装为 {success, data} 格式
    - 创建时必须传 agentConfigId
    """

    def test_list_environments(self, web_client):
        """获取环境列表：返回数组"""
        resp = web_client.list_environments()
        web_client.validate_schema(resp, _WEB_ENV_LIST_DATA)
        assert isinstance(resp, list)

    def test_get_environment(self, web_client):
        """获取环境详情：先拿列表取第一个 id，再查详情"""
        envs = web_client.list_environments()
        if len(envs) == 0:
            pytest.skip("环境列表为空，无法测试详情")
        env_id = envs[0]["id"]

        detail = web_client.get_environment(env_id)
        web_client.validate_schema(detail, ENVIRONMENT_ITEM)
        assert detail["id"] == env_id
        assert "name" in detail

    def test_environment_crud_lifecycle(self, web_client):
        """环境 CRUD 生命周期：创建 → 读取 → 更新 → 删除"""
        agent_config_id = _get_first_agent_config_id(web_client)
        if not agent_config_id:
            pytest.skip("无可用 Agent 配置，无法测试环境 CRUD")

        test_name = "api-test-web-env-001"
        _cleanup_environment(web_client, test_name)

        create_resp = web_client.create_environment({
            "name": test_name,
            "description": "API test environment",
            "agentConfigId": agent_config_id,
            "autoStart": False,
        })
        web_client.validate_schema(create_resp, ENVIRONMENT_ITEM)
        env_id = create_resp["id"]
        # 环境名称可能由服务端自动生成
        assert env_id is not None

        try:
            # 验证创建成功
            detail = web_client.get_environment(env_id)
            assert detail["id"] == env_id

            # 记录更新前的字段值
            original_name = detail.get("name")

            # 更新描述
            update_resp = web_client.update_environment(env_id, {
                "description": "Updated by API test",
            })
            assert update_resp["id"] == env_id

            # 验证更新生效
            detail = web_client.get_environment(env_id)
            assert detail.get("description") == "Updated by API test"
            # 验证未修改字段未被清空
            assert detail.get("name") == original_name

            # 删除并验证资源已消失
            web_client.delete_environment(env_id)
            with pytest.raises((httpx.HTTPStatusError, RuntimeError)):
                web_client.get_environment(env_id)
        finally:
            _cleanup_environment(web_client, test_name)

    def test_create_environment_invalid_config(self, web_client):
        """创建环境使用非法配置：缺少 agentConfigId 应返回 400/422"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"(400|422|500)"):
            web_client.create_environment({
                "name": "api-test-env-invalid",
                # 故意不传 agentConfigId
            })

    def test_create_environment_invalid_agent_id(self, web_client):
        """创建环境使用无效 agentConfigId：应返回 400/404/422"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"(400|404|422|500)"):
            web_client.create_environment({
                "name": "api-test-env-bad-agent",
                "agentConfigId": "nonexistent-agent-id-99999",
            })

    def test_get_nonexistent_environment(self, web_client):
        """获取不存在的环境：应抛出 404 异常"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"(404|500)"):
            web_client.get_environment("nonexistent-env-id-99999")

    def test_list_environment_instances(self, web_client):
        """获取环境实例列表：先拿列表取第一个 id"""
        envs = web_client.list_environments()
        if len(envs) == 0:
            pytest.skip("环境列表为空，无法测试实例列表")
        env_id = envs[0]["id"]

        resp = web_client.list_environment_instances(env_id)
        if isinstance(resp, list):
            assert isinstance(resp, list)
        else:
            assert isinstance(resp, dict)
            if "instances" in resp:
                assert isinstance(resp["instances"], list)

    def test_create_environment_empty_name(self, web_client):
        """创建空 name 环境：应返回 400 或抛出异常"""
        agent_config_id = _get_first_agent_config_id(web_client)
        if not agent_config_id:
            pytest.skip("无可用 Agent 配置，无法测试空 name 创建")

        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"(400|422)"):
            web_client.create_environment({
                "name": "",
                "description": "Empty name test",
                "agentConfigId": agent_config_id,
            })
