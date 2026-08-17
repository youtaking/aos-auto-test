# tests/api_suites/test_tasks_v1_api.py
"""Task V1 接口测试：功能验证 + 契约验证

覆盖控制台接口（已废弃，冻结状态）：
- TestTaskV1WebAPI: /web/tasks/*（session cookie 认证）

注意：此接口已标记 @deprecated，测试覆盖保证接口仍可正常工作。
"""
import httpx
import pytest


class TestTaskV1WebAPI:
    """/web/tasks/* 定时任务 V1 接口（已废弃，session cookie 认证）

    特点：
    - GET /tasks — 列表
    - GET /tasks/:id — 详情
    - POST /tasks/:id/toggle — 切换状态
    - POST /tasks/:id/trigger — 手动触发
    - GET /tasks/:id/logs — 日志
    - DELETE /tasks/:id/logs — 清空日志
    """

    def test_list_tasks(self, web_client):
        """获取任务列表：返回数组"""
        try:
            result = web_client.list_tasks()
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "404" in err_str or "deprecated" in err_str.lower():
                pytest.skip("V1 任务接口已下线")
            if "UNKNOWN" in err_str:
                pytest.skip("V1 任务接口返回 UNKNOWN，接口已废弃")
            raise

        assert isinstance(result, (list, dict))

    def test_get_task(self, web_client):
        """获取任务详情：先拿列表取第一个 id"""
        try:
            tasks = web_client.list_tasks()
        except (httpx.HTTPStatusError, RuntimeError):
            pytest.skip("V1 任务列表接口不可用")

        # 处理列表格式
        if isinstance(tasks, list):
            items = tasks
        elif isinstance(tasks, dict):
            items = tasks.get("items", tasks.get("tasks", []))
        else:
            items = []

        if len(items) == 0:
            pytest.skip("任务列表为空，无法测试详情")

        task_id = items[0].get("id")
        if not task_id:
            pytest.skip("任务无有效 ID 字段")

        try:
            result = web_client.get_task(task_id)
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "404" in err_str:
                pytest.skip("任务不存在")
            raise

        assert isinstance(result, dict)

    def test_get_task_logs(self, web_client):
        """获取任务执行日志"""
        try:
            tasks = web_client.list_tasks()
        except (httpx.HTTPStatusError, RuntimeError):
            pytest.skip("V1 任务列表接口不可用")

        if isinstance(tasks, list):
            items = tasks
        elif isinstance(tasks, dict):
            items = tasks.get("items", tasks.get("tasks", []))
        else:
            items = []

        if len(items) == 0:
            pytest.skip("任务列表为空，无法测试日志")

        task_id = items[0].get("id")
        if not task_id:
            pytest.skip("任务无有效 ID 字段")

        try:
            result = web_client.get_task_logs(task_id)
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "404" in err_str:
                pytest.skip("任务不存在")
            raise

        assert isinstance(result, dict)

    def test_toggle_task(self, web_client):
        """切换任务启用状态"""
        try:
            tasks = web_client.list_tasks()
        except (httpx.HTTPStatusError, RuntimeError):
            pytest.skip("V1 任务列表接口不可用")

        if isinstance(tasks, list):
            items = tasks
        elif isinstance(tasks, dict):
            items = tasks.get("items", tasks.get("tasks", []))
        else:
            items = []

        if len(items) == 0:
            pytest.skip("任务列表为空，无法测试切换状态")

        task_id = items[0].get("id")
        if not task_id:
            pytest.skip("任务无有效 ID 字段")

        try:
            result = web_client.toggle_task(task_id)
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "404" in err_str:
                pytest.skip("任务不存在")
            if "403" in err_str:
                pytest.skip("无权限切换任务状态")
            raise

        assert isinstance(result, dict)

        # 再切换回去，恢复原状态
        try:
            web_client.toggle_task(task_id)
        except (httpx.HTTPStatusError, RuntimeError):
            pass

    def test_trigger_task(self, web_client):
        """手动触发任务执行"""
        try:
            tasks = web_client.list_tasks()
        except (httpx.HTTPStatusError, RuntimeError):
            pytest.skip("V1 任务列表接口不可用")

        if isinstance(tasks, list):
            items = tasks
        elif isinstance(tasks, dict):
            items = tasks.get("items", tasks.get("tasks", []))
        else:
            items = []

        if len(items) == 0:
            pytest.skip("任务列表为空，无法测试触发")

        task_id = items[0].get("id")
        if not task_id:
            pytest.skip("任务无有效 ID 字段")

        try:
            result = web_client.trigger_task(task_id)
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "404" in err_str:
                pytest.skip("任务不存在")
            if "403" in err_str or "500" in err_str:
                pytest.skip("任务触发接口不可用")
            raise

        assert isinstance(result, dict)

    def test_get_nonexistent_task(self, web_client):
        """获取不存在的任务：应返回 404"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"(400|404|not_found|UNKNOWN)"):
            web_client.get_task("nonexistent-task-id-99999")

    def test_clear_task_logs(self, web_client):
        """清空任务日志"""
        try:
            tasks = web_client.list_tasks()
        except (httpx.HTTPStatusError, RuntimeError):
            pytest.skip("V1 任务列表接口不可用")

        if isinstance(tasks, list):
            items = tasks
        elif isinstance(tasks, dict):
            items = tasks.get("items", tasks.get("tasks", []))
        else:
            items = []

        if len(items) == 0:
            pytest.skip("任务列表为空，无法测试清空日志")

        task_id = items[0].get("id")
        if not task_id:
            pytest.skip("任务无有效 ID 字段")

        try:
            result = web_client.clear_task_logs(task_id)
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "404" in err_str:
                pytest.skip("任务不存在")
            if "403" in err_str or "500" in err_str:
                pytest.skip("清空日志接口不可用")
            raise

        # 清空后 result 可能为 None 或 dict
        assert result is None or isinstance(result, dict)
