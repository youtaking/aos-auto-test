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
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"404"):
            web_client.get_task_v2("nonexistent-task-id-99999")

    def test_get_task_v2_logs(self, web_client):
        """获取任务 V2 日志：先拿列表取第一个 id"""
        list_resp = web_client.list_tasks_v2()
        if len(list_resp["items"]) == 0:
            pytest.skip("任务列表为空，无法测试日志")
        task_id = list_resp["items"][0]["id"]

        resp = web_client.get_task_v2_logs(task_id)
        assert isinstance(resp, dict)
        # 验证日志结构：entries/logs 为列表，或空对象表示无日志
        if "entries" in resp:
            assert isinstance(resp["entries"], list)
            for entry in resp["entries"]:
                assert isinstance(entry, dict)
        elif "logs" in resp:
            assert isinstance(resp["logs"], list)
        # 无 entries/logs 字段时，仅验证响应为有效 dict（已在上方校验）

    def test_task_v2_toggle(self, web_client):
        """切换任务 V2 启用状态"""
        list_resp = web_client.list_tasks_v2()
        if len(list_resp["items"]) == 0:
            pytest.skip("任务列表为空，无法测试切换")
        task_id = list_resp["items"][0]["id"]

        detail_before = web_client.get_task_v2(task_id)
        enabled_before = detail_before.get("enabled")

        resp = web_client.toggle_task_v2(task_id)
        assert isinstance(resp, dict)
        assert "id" in resp, f"toggle 响应缺少 id 字段: {list(resp.keys())}"

        if enabled_before is not None:
            detail_after = web_client.get_task_v2(task_id)
            enabled_after = detail_after.get("enabled")
            if enabled_after is not None:
                assert enabled_after != enabled_before, \
                    f"toggle 后 enabled 未变化: {enabled_before} → {enabled_after}"

    def test_task_v2_trigger(self, web_client):
        """手动触发任务 V2"""
        list_resp = web_client.list_tasks_v2()
        if len(list_resp["items"]) == 0:
            pytest.skip("任务列表为空，无法测试触发")
        task_id = list_resp["items"][0]["id"]

        resp = web_client.trigger_task_v2(task_id)
        assert isinstance(resp, dict)
        assert "status" in resp or "id" in resp or "run_id" in resp, \
            f"trigger 响应缺少预期字段: {list(resp.keys())}"


    def test_clear_task_v2_logs(self, web_client):
        """清空任务 V2 日志并验证"""
        list_resp = web_client.list_tasks_v2()
        if len(list_resp["items"]) == 0:
            pytest.skip("任务列表为空，无法测试清空日志")
        task_id = list_resp["items"][0]["id"]

        resp = web_client.clear_task_v2_logs(task_id)
        # 清空后日志应为空或空列表
        logs = web_client.get_task_v2_logs(task_id)
        assert isinstance(logs, dict)
        if "entries" in logs:
            assert len(logs["entries"]) == 0, "清空后 entries 应为空"
        elif "logs" in logs:
            assert len(logs["logs"]) == 0, "清空后 logs 应为空"

    def test_task_v2_toggle_idempotent(self, web_client):
        """toggle 幂等性：连续两次 toggle 应恢复原状态"""
        list_resp = web_client.list_tasks_v2()
        if len(list_resp["items"]) == 0:
            pytest.skip("任务列表为空，无法测试 toggle 幂等性")
        task_id = list_resp["items"][0]["id"]

        detail_before = web_client.get_task_v2(task_id)
        enabled_before = detail_before.get("enabled")

        # 第一次 toggle
        web_client.toggle_task_v2(task_id)
        # 第二次 toggle（恢复原状态）
        web_client.toggle_task_v2(task_id)

        detail_after = web_client.get_task_v2(task_id)
        enabled_after = detail_after.get("enabled")
        if enabled_before is not None and enabled_after is not None:
            assert enabled_after == enabled_before, \
                f"两次 toggle 后 enabled 未恢复: {enabled_before} → {enabled_after}"

    def test_task_v2_trigger_invalid_id(self, web_client):
        """触发不存在的任务：应返回 404"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"404"):
            web_client.trigger_task_v2("nonexistent-task-id-99999")
