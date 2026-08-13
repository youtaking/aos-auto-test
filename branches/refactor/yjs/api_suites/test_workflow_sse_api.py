# tests/api_suites/test_workflow_sse_api.py
"""Workflow SSE 接口测试：功能验证 + 契约验证

覆盖控制台接口：
- TestWorkflowSSEWebAPI: /web/workflow/:workflowId/events（session cookie 认证）

SSE 端点返回 text/event-stream，通过 httpx stream 方式验证。
"""
import httpx
import pytest


def _get_workflow_id(client):
    """获取一个工作流定义 ID，返回 workflow_id 或 None"""
    try:
        defs = client.list_workflow_defs()
        if isinstance(defs, list) and len(defs) > 0:
            return defs[0].get("id")
        if isinstance(defs, dict) and "items" in defs:
            items = defs["items"]
            if len(items) > 0:
                return items[0].get("id")
    except Exception:
        pass
    return None


class TestWorkflowSSEWebAPI:
    """/web/workflow/:workflowId/events SSE 事件流接口（session cookie 认证）

    特点：
    - GET /workflow/:workflowId/events — SSE 流
    - Content-Type: text/event-stream
    - 支持 Last-Event-ID / fromSeqNum 断线重连
    """

    def test_sse_connect(self, web_client):
        """连接 SSE 流：验证返回 event-stream content-type"""
        wf_id = _get_workflow_id(web_client)
        if not wf_id:
            pytest.skip("工作流定义列表为空，无法测试 SSE")

        # 使用 httpx stream 请求，连接后立即断开
        try:
            with web_client.client.stream(
                "GET",
                f"/web/workflow/{wf_id}/events",
                timeout=5.0,
            ) as resp:
                assert resp.status_code == 200
                content_type = resp.headers.get("content-type", "")
                assert "text/event-stream" in content_type
                # 读取第一个 keepalive 后关闭
                for line in resp.iter_lines():
                    if line.strip():
                        break
        except httpx.ReadTimeout:
            pass  # 超时是正常的，SSE 是长连接
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                pytest.skip("工作流不存在")
            raise

    def test_sse_nonexistent_workflow(self, web_client):
        """连接不存在的工作流 SSE：应返回 404 或 500"""
        with pytest.raises(httpx.HTTPStatusError, match=r"(404|500)"):
            web_client.client.get("/web/workflow/nonexistent-wf-99999/events").raise_for_status()

    def test_sse_with_from_seq(self, web_client):
        """带 fromSeqNum=0 连接 SSE：验证不断开"""
        wf_id = _get_workflow_id(web_client)
        if not wf_id:
            pytest.skip("工作流定义列表为空，无法测试 SSE")

        try:
            with web_client.client.stream(
                "GET",
                f"/web/workflow/{wf_id}/events?fromSeqNum=0",
                timeout=3.0,
            ) as resp:
                assert resp.status_code == 200
                # 读一行确认连接正常
                for line in resp.iter_lines():
                    if ": keepalive" in line:
                        break
        except httpx.ReadTimeout:
            pass  # 超时是 SSE 正常行为
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                pytest.skip("工作流不存在")
            raise
