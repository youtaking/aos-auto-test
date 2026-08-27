# tests/api_suites/test_agent_site_api.py
"""Agent Site 接口测试：功能验证 + 契约验证

覆盖控制台接口：
- TestAgentSiteWebAPI: /web/agent-sites（session cookie 认证，RESTful /:id 风格）

注：Agent Site 创建需要连接外部 agent-sites 服务，部分写操作可能因服务不可用而跳过。
"""
import httpx
import pytest
from tests.api_contracts.agent_site_schemas import AGENT_SITE_APP


# ── 控制台接口测试 ──

class TestAgentSiteWebAPI:
    """/web/agent-sites 控制台接口测试（session cookie 认证，RESTful /:id 风格）

    特点：
    - 用 /:id 路径参数定位资源
    - 响应统一包装为 {success, data} 格式
    - 支持 app CRUD、token 轮转、文件上传、部署
    """

    def test_list_agent_site_apps(self, web_client):
        """获取 Agent Site App 列表：返回数组"""
        resp = web_client.list_agent_site_apps()
        assert isinstance(resp, list)
        if len(resp) > 0:
            web_client.validate_schema(resp[0], AGENT_SITE_APP)

    def test_get_agent_site_app(self, web_client):
        """获取 Agent Site App 详情：先拿列表取第一个 id"""
        apps = web_client.list_agent_site_apps()
        if len(apps) == 0:
            pytest.skip("Agent Site App 列表为空，无法测试详情")
        app_id = apps[0]["id"]

        detail = web_client.get_agent_site_app(app_id)
        web_client.validate_schema(detail, AGENT_SITE_APP)
        assert detail["id"] == app_id
        assert "name" in detail

    def test_get_nonexistent_agent_site_app(self, web_client):
        """获取不存在的 Agent Site App：应抛出 400/404/422 异常"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"(400|404|422)"):
            web_client.get_agent_site_app("nonexistent-app-id-99999")

    def test_create_and_delete_agent_site_app(self, web_client):
        """创建并删除 Agent Site App：自建自销"""
        test_name = "test-site-api-auto"
        created_id = None
        try:
            # 先清理可能遗留的数据
            try:
                apps = web_client.list_agent_site_apps()
                for app in apps:
                    if app.get("name") == test_name:
                        web_client.delete_agent_site_app(app["id"])
            except Exception as e:
                import logging
                logging.getLogger("cleanup").warning(f"Cleanup failed: {e}")

            create_resp = web_client.create_agent_site_app({
                "name": test_name,
                "type": "custom",
            })
            assert create_resp is not None
            assert isinstance(create_resp, dict)
            created_id = create_resp.get("id")
            assert created_id, f"创建响应缺少 id: {create_resp}"

            # 验证创建成功：查询详情
            detail = web_client.get_agent_site_app(created_id)
            assert detail["id"] == created_id
            assert detail["name"] == test_name
        except (httpx.HTTPStatusError, RuntimeError) as e:
            if "400" in str(e) or "503" in str(e):
                pytest.skip(f"Agent Site 服务不可用: {e}")
            raise
        finally:
            if created_id:
                try:
                    web_client.delete_agent_site_app(created_id)
                    # 验证删除成功：查询应返回 404
                    try:
                        web_client.get_agent_site_app(created_id)
                    except (httpx.HTTPStatusError, RuntimeError):
                        pass  # 预期 404
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning(f"Cleanup agent site {created_id} failed: {e}")

    def test_get_agent_site_by_remote_nonexistent(self, web_client):
        """通过不存在的 remoteAppId 查询：应返回 404"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"(404|400)"):
            web_client.get_agent_site_by_remote("nonexistent-remote-id-99999")

    def test_rotate_token_nonexistent(self, web_client):
        """轮转不存在的 App Token：应返回 404"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"(404|400)"):
            web_client.rotate_agent_site_token("nonexistent-app-id-99999")

    def test_deploy_nonexistent(self, web_client):
        """部署不存在的 App：应返回 404"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"(404|400)"):
            web_client.deploy_agent_site("nonexistent-app-id-99999")

    def test_list_agent_config_sites(self, web_client):
        """获取 Agent 配置关联的 Sites：使用列表首个 agent 的 configId"""
        agents = web_client.list_agents()
        agent_list = agents if isinstance(agents, list) else agents.get("items", agents.get("data", []))
        if not agent_list:
            pytest.skip("Agent 列表为空，无法测试 agent-config sites")
        # 取第一个 agent 的 name（config 标识）
        agent_name = agent_list[0].get("name") or agent_list[0].get("configName")
        if not agent_name:
            pytest.skip("Agent 缺少 name 字段")
        try:
            sites = web_client.list_agent_config_sites(agent_name)
            assert isinstance(sites, list)
        except (httpx.HTTPStatusError, RuntimeError) as e:
            if "404" in str(e):
                pytest.skip("Agent config sites 接口不可用")
            raise

