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
        """获取不存在的 Agent Site App：应抛出 404/422 异常"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"(400|404|422)"):
            web_client.get_agent_site_app("nonexistent-app-id-99999")

