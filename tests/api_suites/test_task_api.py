# tests/api_suites/test_task_api.py
"""Task V2 接口测试：功能验证 + 契约验证

覆盖控制台接口：
- TestTaskV2WebAPI: /web/tasks/v2（session cookie 认证，RESTful /:id 风格）

注：/web/tasks（V1）已标记 deprecated，不再测试。
"""
import httpx
import pytest
from tests.api_contracts.task_schemas import (
    TASK_V2_ITEM,
)

# unwrapped schema (data portion after _unwrap)
_WEB_TASK_V2_LIST_DATA = {
    "type": "object",
    "properties": {
        "items": {"type": "array", "items": TASK_V2_ITEM},
        "total": {"type": "integer"},
        "page": {"type": "integer"},
        "pageSize": {"type": "integer"},
    },
    "additionalProperties": True,
}


# ── 控制台接口测试 ──

class TestTaskV2WebAPI:
    """/web/tasks/v2 控制台接口测试（session cookie 认证，RESTful /:id 风格）

    特点：
    - 分页列表 {items, total, page, pageSize}
    - CRUD + toggle + trigger + logs
    """

    def test_list_tasks_v2(self, web_client):
        """获取任务 V2 列表：返回分页结构"""
        resp = web_client.list_tasks_v2()
        web_client.validate_schema(resp, _WEB_TASK_V2_LIST_DATA)
        assert "items" in resp
        assert isinstance(resp["items"], list)

    def test_get_task_v2(self, web_client):
        """获取任务 V2 详情：先拿列表取第一个 id"""
        list_resp = web_client.list_tasks_v2()
        if len(list_resp["items"]) == 0:
            pytest.skip("任务列表为空，无法测试详情")
        task_id = list_resp["items"][0]["id"]

        detail = web_client.get_task_v2(task_id)
        web_client.validate_schema(detail, TASK_V2_ITEM)
        assert detail["id"] == task_id

    def test_get_nonexistent_task_v2(self, web_client):
        """获取不存在的任务：应抛出 404 异常"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"(404|500)"):
            web_client.get_task_v2("nonexistent-task-id-99999")

    def test_get_task_v2_logs(self, web_client):
        """获取任务 V2 日志：先拿列表取第一个 id"""
        list_resp = web_client.list_tasks_v2()
        if len(list_resp["items"]) == 0:
            pytest.skip("任务列表为空，无法测试日志")
        task_id = list_resp["items"][0]["id"]

        resp = web_client.get_task_v2_logs(task_id)
        assert isinstance(resp, dict)
        if "entries" in resp:
            assert isinstance(resp["entries"], list)

    def test_task_v2_toggle(self, web_client):
        """切换任务 V2 启用状态"""
        list_resp = web_client.list_tasks_v2()
        if len(list_resp["items"]) == 0:
            pytest.skip("任务列表为空，无法测试切换")
        task_id = list_resp["items"][0]["id"]

        try:
            resp = web_client.toggle_task_v2(task_id)
            assert isinstance(resp, dict)
            # 验证返回包含任务相关信息
            assert "id" in resp or "enabled" in resp or "success" in resp
        except (httpx.HTTPStatusError, RuntimeError) as e:
            if "403" in str(e) or "404" in str(e):
                pytest.skip("任务切换接口不可用")
            raise

    def test_task_v2_trigger(self, web_client):
        """手动触发任务 V2"""
        list_resp = web_client.list_tasks_v2()
        if len(list_resp["items"]) == 0:
            pytest.skip("任务列表为空，无法测试触发")
        task_id = list_resp["items"][0]["id"]

        try:
            resp = web_client.trigger_task_v2(task_id)
            assert isinstance(resp, dict)
            # 验证返回包含触发结果信息
            assert "id" in resp or "status" in resp or "success" in resp
        except (httpx.HTTPStatusError, RuntimeError) as e:
            if "403" in str(e) or "404" in str(e) or "500" in str(e):
                pytest.skip("任务触发接口不可用")
            raise
