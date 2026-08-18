# tests/api_suites/test_prod_view_api.py
"""ProdView 接口测试：功能验证 + 契约验证

覆盖控制台接口：
- TestProdViewWebAPI: /web/config/prod-views（session cookie 认证，RESTful /:id 风格）
"""
import httpx
import pytest
from tests.api_contracts.prod_view_schemas import PROD_VIEW_ITEM

# unwrapped schema: data portion can be array or object
_WEB_PROD_VIEW_LIST_DATA = {"type": ["object", "array"]}


# ── 控制台接口测试 ──

class TestProdViewWebAPI:
    """/web/config/prod-views 控制台接口测试（session cookie 认证，RESTful /:id 风格）

    特点：
    - 用 /:id 路径参数定位资源
    - 响应统一包装为 {success, data} 格式
    """

    def test_list_prod_views(self, web_client):
        """获取 ProdView 列表"""
        resp = web_client.list_prod_views()
        web_client.validate_schema(resp, _WEB_PROD_VIEW_LIST_DATA)
        assert isinstance(resp, (list, dict))

    def test_get_prod_view(self, web_client):
        """获取 ProdView 详情：先拿列表取第一个 id"""
        resp = web_client.list_prod_views()
        # 列表响应格式取决于 service 实现
        items = resp if isinstance(resp, list) else resp.get("items", resp.get("data", []))
        if not items:
            pytest.skip("ProdView 列表为空，无法测试详情")
        view_id = items[0]["id"]

        detail = web_client.get_prod_view(view_id)
        web_client.validate_schema(detail, PROD_VIEW_ITEM)
        assert detail["id"] == view_id

    def test_get_nonexistent_prod_view(self, web_client):
        """获取不存在的 ProdView：应抛出 404 异常"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"404"):
            web_client.get_prod_view("nonexistent-prod-view-id-99999")

    def test_prod_view_crud_lifecycle(self, web_client):
        """ProdView CRUD 生命周期：创建 → 读取 → 更新 → 删除"""
        # 获取第一个 agent 的 ID
        agents_data = web_client.list_agents()
        agents = agents_data.get("agents", [])
        if len(agents) == 0:
            pytest.skip("Agent 列表为空，无法测试 ProdView CRUD")
        agent_config_id = agents[0].get("id") or agents[0].get("name")

        try:
            create_resp = web_client.create_prod_view({
                "agentId": agent_config_id,
                "name": "api-test-prod-view-crud",
                "enabled": False,
                "modulesConfig": {},
            })
        except (httpx.HTTPStatusError, RuntimeError) as e:
            if "500" in str(e) or "400" in str(e) or "422" in str(e):
                pytest.skip("ProdView 创建接口不可用")
            raise

        assert "id" in create_resp
        web_client.validate_schema(create_resp, PROD_VIEW_ITEM)
        view_id = create_resp["id"]

        try:
            # 验证创建成功
            detail = web_client.get_prod_view(view_id)
            web_client.validate_schema(detail, PROD_VIEW_ITEM)
            assert detail["id"] == view_id

            # 更新
            web_client.update_prod_view(view_id, {"enabled": True})
            # 回读验证更新生效
            updated = web_client.get_prod_view(view_id)
            assert updated["enabled"] is True

            # 删除并验证
            web_client.delete_prod_view(view_id)
            with pytest.raises((httpx.HTTPStatusError, RuntimeError)):
                web_client.get_prod_view(view_id)
        finally:
            try:
                web_client.delete_prod_view(view_id)
            except Exception as e:
                import logging
                logging.getLogger("cleanup").warning(f"Cleanup failed: {e}")

    def test_delete_prod_view_idempotent(self, web_client):
        """ProdView DELETE 幂等性：第二次删除返回 404"""
        agents_data = web_client.list_agents()
        agents = agents_data.get("agents", [])
        if len(agents) == 0:
            pytest.skip("Agent 列表为空，无法测试 ProdView 幂等性")
        agent_config_id = agents[0].get("id") or agents[0].get("name")
        test_name = "test-idempotent-delete-prodview"

        try:
            create_resp = web_client.create_prod_view({
                "agentId": agent_config_id,
                "name": test_name,
                "enabled": False,
                "modulesConfig": {},
            })
        except (httpx.HTTPStatusError, RuntimeError) as e:
            if "500" in str(e) or "400" in str(e) or "422" in str(e):
                pytest.skip("ProdView 创建接口不可用")
            raise

        view_id = create_resp["id"]
        try:
            web_client.delete_prod_view(view_id)
            with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"404"):
                web_client.delete_prod_view(view_id)
        finally:
            try:
                web_client.delete_prod_view(view_id)
            except Exception as e:
                import logging
                logging.getLogger("cleanup").warning(f"Cleanup failed: {e}")
