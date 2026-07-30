# tests/api_suites/test_agent_api.py
"""Agent 接口测试：功能验证 + 契约验证

覆盖两套接口：
- TestAgentWebAPI: /web/config/agents 控制台接口（session cookie 认证，action 风格）
- TestAgentOpenAPI: /api/agents 对外 OpenAPI（API Key 认证，RESTful 风格）
"""
import httpx
import pytest
from tests.api_contracts.agent_schemas import (
    WEB_AGENT_LIST_DATA,
    AGENT_DETAIL,
    API_AGENT_LIST_RESPONSE,
    API_AGENT_DETAIL_RESPONSE,
    API_CREATE_AGENT_RESPONSE,
    WEB_AGENT_TEMPLATES_DATA,
    WEB_SET_DEFAULT_AGENT_DATA,
)


# ── 工具函数 ──

def _cleanup_web_agent(client, name: str):
    """通过 web 接口按名称删除 Agent，忽略错误"""
    try:
        client.delete_agent(name)
    except Exception as e:
        import logging
        logging.getLogger("cleanup").warning(f"Cleanup failed: {e}")


def _cleanup_api_agent(client, name: str):
    """通过 api 接口按名称查找并删除 Agent，忽略错误"""
    try:
        list_resp = client.list_agents(params={"pageSize": 100})
        for agent in list_resp["items"]:
            if agent["name"] == name:
                client.delete_agent(agent["id"])
    except Exception as e:
        import logging
        logging.getLogger("cleanup").warning(f"Cleanup failed: {e}")


# ── 控制台接口测试 ──

class TestAgentWebAPI:
    """/web/config/agents 控制台接口测试（session cookie 认证，action 风格）

    特点：
    - 用 name 定位资源（?name=xxx），而非 ID
    - 响应统一包装为 {success, data} 格式
    - 列表返回 {default_agent, agents: [...]}
    """

    def test_list_agents(self, web_client):
        """获取 Agent 列表：返回 agents 数组且非空"""
        resp = web_client.list_agents()
        web_client.validate_schema(resp, WEB_AGENT_LIST_DATA)
        # 包装格式已在 _unwrap 中校验 success=true
        assert isinstance(resp["agents"], list)
        assert len(resp["agents"]) > 0

    def test_get_agent(self, web_client):
        """获取单个 Agent 详情：先拿列表取第一个 name，再查详情"""
        list_data = web_client.list_agents()
        assert len(list_data["agents"]) > 0, "Agent 列表为空，无法测试详情"
        agent_name = list_data["agents"][0]["name"]

        detail = web_client.get_agent(agent_name)
        web_client.validate_schema(detail, AGENT_DETAIL)
        assert detail["name"] == agent_name
        assert "id" in detail

    def test_create_and_delete_agent(self, web_client):
        """创建并删除 Agent：写操作生命周期测试"""
        test_name = "api-test-web-agent-001"

        # 先清理可能遗留的同名 Agent
        _cleanup_web_agent(web_client, test_name)

        # 创建
        create_resp = web_client.create_agent({
            "name": test_name,
            "description": "Web API 测试自动创建的 Agent",
        })
        web_client.validate_schema(create_resp, AGENT_DETAIL)
        assert create_resp["name"] == test_name
        assert "id" in create_resp

        try:
            # 验证创建成功
            detail = web_client.get_agent(test_name)
            assert detail["name"] == test_name
            # 删除并验证资源已消失
            web_client.delete_agent(test_name)
            with pytest.raises((httpx.HTTPStatusError, RuntimeError)):
                web_client.get_agent(test_name)
        finally:
            # 清理：无论断言是否失败都要删除
            _cleanup_web_agent(web_client, test_name)

    def test_update_agent(self, web_client):
        """更新 Agent：创建 → 修改描述 → 验证 → 删除"""
        test_name = "api-test-web-agent-002"
        updated_desc = "updated by web api test"

        _cleanup_web_agent(web_client, test_name)

        web_client.create_agent({"name": test_name})

        try:
            # 记录更新前的字段值
            original_detail = web_client.get_agent(test_name)
            original_name = original_detail.get("name")

            web_client.update_agent(test_name, {"description": updated_desc})

            # 再次获取确认更新生效
            detail = web_client.get_agent(test_name)
            web_client.validate_schema(detail, AGENT_DETAIL)
            assert detail["description"] == updated_desc
            # 验证未修改字段未被清空
            assert detail.get("name") == original_name
        finally:
            web_client.delete_agent(test_name)

    def test_get_nonexistent_agent(self, web_client):
        """获取不存在的 Agent：应抛出 404 异常"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"404"):
            web_client.get_agent("nonexistent-agent-name-99999")

    def test_get_agent_templates(self, web_client):
        """获取 Agent 模板列表：返回 templates 数组"""
        resp = web_client.get_agent_templates()
        web_client.validate_schema(resp, WEB_AGENT_TEMPLATES_DATA)
        assert isinstance(resp["templates"], list)

    def test_set_default_agent(self, web_client):
        """设置默认 Agent：从列表取一个已有 Agent 名称设置为默认"""
        list_data = web_client.list_agents()
        if len(list_data["agents"]) == 0:
            pytest.skip("Agent 列表为空，无法测试设置默认")
        agent_name = list_data["agents"][0]["name"]

        resp = web_client.set_default_agent(agent_name)
        web_client.validate_schema(resp, WEB_SET_DEFAULT_AGENT_DATA)
        assert resp["default_agent"] == agent_name


# ── 对外 OpenAPI 测试 ──

class TestAgentOpenAPI:
    """/api/agents 对外 OpenAPI 测试（API Key 认证，RESTful 风格）

    特点：
    - 用 ID 定位资源（/:id）
    - 列表带分页 {items, total, page, pageSize}
    - 响应为裸数据，无 {success, data} 包装
    """

    def test_list_agents(self, api_client, api_test_config):
        """获取 Agent 列表：返回分页结构"""
        if api_test_config["fenixagent"]["api_key"] == "test-api-key-placeholder":
            pytest.skip("API Key 未配置，跳过 OpenAPI 测试")

        resp = api_client.list_agents()
        api_client.validate_schema(resp, API_AGENT_LIST_RESPONSE)
        assert isinstance(resp["items"], list)

    def test_get_agent(self, api_client, api_test_config):
        """获取单个 Agent 详情：先拿列表取第一个 ID，再查详情"""
        if api_test_config["fenixagent"]["api_key"] == "test-api-key-placeholder":
            pytest.skip("API Key 未配置，跳过 OpenAPI 测试")

        list_resp = api_client.list_agents()
        if len(list_resp["items"]) == 0:
            pytest.skip("Agent 列表为空，跳过详情测试")
        agent_id = list_resp["items"][0]["id"]

        resp = api_client.get_agent(agent_id)
        api_client.validate_schema(resp, API_AGENT_DETAIL_RESPONSE)
        assert resp["id"] == agent_id

    def test_create_and_delete_agent(self, api_client, api_test_config):
        """创建并删除 Agent：写操作生命周期测试"""
        if api_test_config["fenixagent"]["api_key"] == "test-api-key-placeholder":
            pytest.skip("API Key 未配置，跳过 OpenAPI 测试")

        test_name = "api-test-openapi-agent-001"

        _cleanup_api_agent(api_client, test_name)

        # 创建
        create_resp = api_client.create_agent({
            "name": test_name,
            "description": "OpenAPI 测试自动创建的 Agent",
        })
        api_client.validate_schema(create_resp, API_CREATE_AGENT_RESPONSE)
        agent_id = create_resp["id"]
        assert create_resp["name"] == test_name

        try:
            # 验证创建成功
            get_resp = api_client.get_agent(agent_id)
            assert get_resp["name"] == test_name
            # 删除并验证资源已消失
            api_client.delete_agent(agent_id)
            with pytest.raises(httpx.HTTPStatusError, match=r"(404|500)"):
                api_client.get_agent(agent_id)
        finally:
            # 清理
            _cleanup_api_agent(api_client, test_name)

    def test_update_agent(self, api_client, api_test_config):
        """更新 Agent：创建 → 修改描述 → 验证 → 删除"""
        if api_test_config["fenixagent"]["api_key"] == "test-api-key-placeholder":
            pytest.skip("API Key 未配置，跳过 OpenAPI 测试")

        test_name = "api-test-openapi-agent-002"
        updated_desc = "updated by openapi test"

        _cleanup_api_agent(api_client, test_name)

        create_resp = api_client.create_agent({"name": test_name})
        agent_id = create_resp["id"]

        try:
            # 记录更新前的字段值
            original_detail = api_client.get_agent(agent_id)
            original_name = original_detail.get("name")

            update_resp = api_client.update_agent(agent_id, {"description": updated_desc})
            api_client.validate_schema(update_resp, API_AGENT_DETAIL_RESPONSE)
            assert update_resp["description"] == updated_desc

            # 再次获取确认更新生效
            get_resp = api_client.get_agent(agent_id)
            api_client.validate_schema(get_resp, API_AGENT_DETAIL_RESPONSE)
            assert get_resp["description"] == updated_desc
            # 验证未修改字段未被清空
            assert get_resp.get("name") == original_name
        finally:
            api_client.delete_agent(agent_id)

    def test_get_nonexistent_agent(self, api_client, api_test_config):
        """获取不存在的 Agent：应返回 404"""
        if api_test_config["fenixagent"]["api_key"] == "test-api-key-placeholder":
            pytest.skip("API Key 未配置，跳过 OpenAPI 测试")

        with pytest.raises(httpx.HTTPStatusError, match=r"(404|500)"):
            api_client.get_agent("nonexistent-agent-id-99999")

    def test_delete_idempotent(self, api_client, api_test_config):
        """验证 DELETE 同一资源两次，第二次返回 404（幂等性）"""
        if api_test_config["fenixagent"]["api_key"] == "test-api-key-placeholder":
            pytest.skip("API Key 未配置，跳过 OpenAPI 测试")
        test_name = "test-idempotent-delete-agent"
        _cleanup_api_agent(api_client, test_name)
        try:
            create_resp = api_client.create_agent({"name": test_name, "description": "Idempotent delete test"})
            agent_id = create_resp["id"]
            api_client.delete_agent(agent_id)
            with pytest.raises(httpx.HTTPStatusError, match=r"404"):
                api_client.delete_agent(agent_id)
        finally:
            _cleanup_api_agent(api_client, test_name)

    def test_update_agent_partial(self, api_client, api_test_config):
        """PUT 部分字段更新，验证未修改字段不被清空"""
        if api_test_config["fenixagent"]["api_key"] == "test-api-key-placeholder":
            pytest.skip("API Key 未配置，跳过 OpenAPI 测试")

        test_name = "api-test-openapi-agent-partial"
        _cleanup_api_agent(api_client, test_name)

        create_resp = api_client.create_agent({
            "name": test_name,
            "description": "original description",
        })
        agent_id = create_resp["id"]

        try:
            original_detail = api_client.get_agent(agent_id)

            # 只更新 description，不传 name
            api_client.update_agent(agent_id, {"description": "partial update"})

            updated = api_client.get_agent(agent_id)
            api_client.validate_schema(updated, API_AGENT_DETAIL_RESPONSE)
            # 更新字段生效
            assert updated["description"] == "partial update"
            # 未修改字段保持不变
            assert updated["name"] == original_detail["name"]
        finally:
            api_client.delete_agent(agent_id)


# ── 新增场景测试 ──

class TestAgentWebAPIExtra:
    """Agent Web API 额外场景测试"""

    def test_create_agent_missing_name(self, web_client):
        """创建 Agent 缺少 name：应返回 400 或抛出异常"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"(400|422)"):
            web_client.create_agent({"description": "no name agent"})

    def test_list_agents_unauthorized(self, api_base_url):
        """无效 Token 访问：应返回 401"""
        from tests.api_clients.web_client import WebClient
        bad_client = WebClient(api_base_url)
        try:
            with pytest.raises(httpx.HTTPStatusError, match="401"):
                bad_client.list_agents()
        finally:
            bad_client.close()

    def test_create_agent_duplicate_name(self, web_client):
        """创建同名 Agent：应返回 409 或抛出异常"""
        test_name = "api-test-web-agent-dup-001"
        _cleanup_web_agent(web_client, test_name)

        web_client.create_agent({"name": test_name})
        try:
            with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"(409|400)"):
                web_client.create_agent({"name": test_name})
        finally:
            _cleanup_web_agent(web_client, test_name)


class TestAgentOpenAPIExtra:
    """Agent OpenAPI 额外场景测试"""

    def test_list_agents_pagination(self, api_client, api_test_config):
        """验证分页参数生效"""
        if api_test_config["fenixagent"]["api_key"] == "test-api-key-placeholder":
            pytest.skip("API Key 未配置，跳过 OpenAPI 测试")

        resp = api_client.list_agents(params={"page": 1, "pageSize": 1})
        api_client.validate_schema(resp, API_AGENT_LIST_RESPONSE)
        assert resp["page"] == 1
        assert resp["pageSize"] == 1

    def test_list_agents_pagination_page2(self, api_client, api_test_config):
        """验证获取第 2 页数据，不与第 1 页重复"""
        if api_test_config["fenixagent"]["api_key"] == "test-api-key-placeholder":
            pytest.skip("API Key 未配置，跳过 OpenAPI 测试")
        page1 = api_client.list_agents({"page": 1, "pageSize": 1})
        if page1["total"] <= 1:
            pytest.skip("Not enough agents for pagination")
        page2 = api_client.list_agents({"page": 2, "pageSize": 1})
        api_client.validate_schema(page2, API_AGENT_LIST_RESPONSE)
        assert page2["page"] == 2
        if page1["items"] and page2["items"]:
            assert page1["items"][0]["id"] != page2["items"][0]["id"]
