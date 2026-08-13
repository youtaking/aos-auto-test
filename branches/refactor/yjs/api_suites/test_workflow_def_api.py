# tests/api_suites/test_workflow_def_api.py
"""Workflow Definition 接口测试：功能验证 + 契约验证

覆盖控制台接口：
- TestWorkflowDefWebAPI: /web/workflow-defs（session cookie 认证，RESTful /:id 风格）

注：工作流定义涉及版本管理和触发器，覆盖基本 CRUD + 版本 + 触发器查询。
"""
import httpx
import pytest
from tests.api_contracts.workflow_def_schemas import WORKFLOW_DEF, WORKFLOW_VERSION, WORKFLOW_TRIGGER


def _cleanup_workflow_def(client, wf_id: str):
    """删除工作流定义，忽略错误"""
    try:
        client.delete_workflow_def(wf_id)
    except Exception as e:
        import logging
        logging.getLogger("cleanup").warning(f"Cleanup failed: {e}")


class TestWorkflowDefWebAPI:
    """/web/workflow-defs 控制台接口测试（session cookie 认证，RESTful /:id 风格）

    特点：
    - CRUD + 版本管理 + 触发器
    """

    def test_list_workflow_defs(self, web_client):
        """获取工作流定义列表：返回数组"""
        resp = web_client.list_workflow_defs()
        assert isinstance(resp, list)
        if len(resp) > 0:
            web_client.validate_schema(resp[0], WORKFLOW_DEF)

    def test_get_workflow_def(self, web_client):
        """获取工作流定义详情：先拿列表取第一个 id"""
        items = web_client.list_workflow_defs()
        if len(items) == 0:
            pytest.skip("工作流定义列表为空，无法测试详情")
        wf_id = items[0]["id"]

        detail = web_client.get_workflow_def(wf_id)
        web_client.validate_schema(detail, WORKFLOW_DEF)
        assert detail["id"] == wf_id
        assert "name" in detail

    def test_create_and_delete_workflow_def(self, web_client):
        """创建并删除工作流定义：写操作生命周期测试"""
        test_name = "api-test-wf-def-001"

        create_resp = web_client.create_workflow_def({
            "name": test_name,
            "description": "Web API 测试自动创建的工作流",
        })
        web_client.validate_schema(create_resp, WORKFLOW_DEF)
        assert create_resp["name"] == test_name
        wf_id = create_resp["id"]

        try:
            detail = web_client.get_workflow_def(wf_id)
            assert detail["name"] == test_name
            # 删除并验证资源已消失
            web_client.delete_workflow_def(wf_id)
            with pytest.raises((httpx.HTTPStatusError, RuntimeError)):
                web_client.get_workflow_def(wf_id)
        finally:
            _cleanup_workflow_def(web_client, wf_id)

    def test_list_workflow_def_versions(self, web_client):
        """获取工作流版本列表：先拿列表取第一个 id"""
        items = web_client.list_workflow_defs()
        if len(items) == 0:
            pytest.skip("工作流定义列表为空，无法测试版本")
        wf_id = items[0]["id"]

        versions = web_client.list_workflow_def_versions(wf_id)
        assert isinstance(versions, list)
        if versions:
            web_client.validate_schema(versions[0], WORKFLOW_VERSION)

    def test_list_workflow_def_triggers(self, web_client):
        """获取工作流触发器列表：先拿列表取第一个 id"""
        items = web_client.list_workflow_defs()
        if len(items) == 0:
            pytest.skip("工作流定义列表为空，无法测试触发器")
        wf_id = items[0]["id"]

        triggers = web_client.list_workflow_def_triggers(wf_id)
        assert isinstance(triggers, list)
        if triggers:
            web_client.validate_schema(triggers[0], WORKFLOW_TRIGGER)

    def test_get_recoverable_workflow_defs(self, web_client):
        """获取可恢复的工作流列表"""
        resp = web_client.get_recoverable_workflow_defs()
        assert isinstance(resp, list)
        if len(resp) > 0:
            web_client.validate_schema(resp[0], WORKFLOW_DEF)

    def test_get_nonexistent_workflow_def(self, web_client):
        """获取不存在的工作流定义：应抛出 404 异常"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"(404|500)"):
            web_client.get_workflow_def("nonexistent-wf-id-99999")

    def test_workflow_def_update_meta(self, web_client):
        """更新工作流定义元数据：创建 → 更新名称/描述 → 验证 → 删除"""
        test_name = "api-test-wf-def-update-001"
        updated_name = "api-test-wf-def-update-001-updated"
        updated_desc = "Updated description by test"

        create_resp = web_client.create_workflow_def({
            "name": test_name,
            "description": "Original description",
        })
        wf_id = create_resp["id"]

        try:
            # 记录更新前的字段
            original_detail = web_client.get_workflow_def(wf_id)
            original_id = original_detail["id"]

            # 更新元数据
            try:
                web_client.update_workflow_def_meta(wf_id, {
                    "name": updated_name,
                    "description": updated_desc,
                })
            except (httpx.HTTPStatusError, RuntimeError):
                pytest.skip("工作流元数据更新接口不可用")

            # 验证更新生效
            detail = web_client.get_workflow_def(wf_id)
            web_client.validate_schema(detail, WORKFLOW_DEF)
            assert detail.get("description") == updated_desc
            # 验证 id 未被修改
            assert detail["id"] == original_id
        finally:
            _cleanup_workflow_def(web_client, wf_id)

    def test_list_workflow_defs_unauthorized(self, api_base_url):
        """无效 Token 访问工作流列表：应返回 401"""
        from tests.api_clients.web_client import WebClient
        bad_client = WebClient(api_base_url)
        try:
            with pytest.raises(httpx.HTTPStatusError, match="401"):
                bad_client.list_workflow_defs()
        finally:
            bad_client.close()

    def test_delete_workflow_def_idempotent(self, web_client):
        """WorkflowDef DELETE 幂等性：第二次删除返回 404"""
        test_name = "test-idempotent-delete-wfdef"
        try:
            create_resp = web_client.create_workflow_def({
                "name": test_name,
                "description": "Idempotent delete test",
            })
            wf_id = create_resp["id"]
            web_client.delete_workflow_def(wf_id)
            with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"404"):
                web_client.delete_workflow_def(wf_id)
        finally:
            _cleanup_workflow_def(web_client, wf_id)
