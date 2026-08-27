# tests/api_suites/test_hooks_api.py
"""Hooks Webhook 接口测试：功能验证 + 契约验证

覆盖接口：
- TestHooksWebhookAPI: POST /hooks/:publicHash（无认证，通过 hash 标识 trigger）

源码：src/routes/hooks.ts
"""
import httpx
import pytest


# ── 工具函数 ──

def _get_trigger_hash(web_client) -> str | None:
    """尝试从触发器列表中获取一个有效的 publicHash"""
    try:
        items = web_client.list_workflow_defs()
        if not items or len(items) == 0:
            return None
        wf_id = items[0]["id"]
        try:
            resp = web_client.get(f"/web/workflow-defs/{wf_id}/triggers")
            data = web_client._unwrap(resp)
            if isinstance(data, list) and len(data) > 0:
                trigger = data[0]
                return trigger.get("publicHash") or trigger.get("hash") or trigger.get("id")
            if isinstance(data, dict):
                triggers = data.get("triggers", data.get("items", []))
                if triggers and len(triggers) > 0:
                    return triggers[0].get("publicHash") or triggers[0].get("hash") or triggers[0].get("id")
        except Exception as e:
            import logging
            logging.getLogger("probe").warning(f"获取触发器失败: {e}")
    except Exception as e:
        import logging
        logging.getLogger("probe").warning(f"获取 workflow defs 失败: {e}")
    return None


def _safe_parse_json(resp: httpx.Response) -> dict | None:
    """安全解析 JSON，空 body 返回 None"""
    try:
        if resp.content and len(resp.content) > 0:
            return resp.json()
    except Exception as e:
        import logging
        logging.getLogger("probe").warning(f"JSON 解析失败: {e}")
    return None


# ── Webhook 接口测试 ──

class TestHooksWebhookAPI:
    """POST /hooks/:publicHash Webhook 触发接口（无认证）

    特点：
    - 无需认证，通过 publicHash 标识触发器
    - 预期：有效 hash 返回 {received: true}，无效 hash 返回 404
    - 实际：当前版本所有请求返回 200 + 空 body（见应用 Bug #1）

    源码预期行为（src/routes/hooks.ts）：
    - result.accepted = false → 404 {error: "..."}
    - result.accepted = true → 200 {received: true}
    """

    @pytest.mark.xfail(reason="应用缺陷：/hooks/:publicHash 端点未挂载（index.ts 未注册 hooksRoutes，全局兜底 200 空 body），无效 hash 应返回 404（已确认）", strict=True)
    def test_webhook_invalid_hash(self, api_base_url):
        """无效 hash 触发 webhook — 契约：应返回 404 {error: ...}"""
        with httpx.Client(base_url=api_base_url, timeout=30, verify=False) as client:
            resp = client.post(
                "/hooks/nonexistent-hash-99999",
                json={"test": "data"},
            )
            assert resp.status_code == 404, \
                f"无效 hash 契约应为 404，实际: {resp.status_code}"
            body = _safe_parse_json(resp)
            assert body is not None, "404 响应应有 JSON body"
            assert "error" in body, f"404 响应缺少 error 字段: {list(body.keys())}"

    @pytest.mark.xfail(reason="应用缺陷：/hooks/:publicHash 端点未挂载（index.ts 未注册 hooksRoutes，全局兜底 200 空 body），空 hash 应返回 404（已确认）", strict=True)
    def test_webhook_empty_hash(self, api_base_url):
        """空 hash 触发 webhook — 契约：应返回 404"""
        with httpx.Client(base_url=api_base_url, timeout=30, verify=False) as client:
            resp = client.post(
                "/hooks/",
                json={"test": "data"},
            )
            assert resp.status_code == 404, \
                f"空 hash 契约应为 404，实际: {resp.status_code}"

    @pytest.mark.xfail(reason="应用缺陷：/hooks/:publicHash 端点未挂载（index.ts 未注册 hooksRoutes，全局兜底 200 空 body），超大请求应返回 413（源码 1MB 限制）（已确认）", strict=True)
    def test_webhook_payload_too_large(self, api_base_url):
        """超大请求体触发 webhook — 契约：应返回 413（源码 1MB 限制）"""
        large_body = {"data": "x" * (1024 * 1024 + 1)}
        with httpx.Client(base_url=api_base_url, timeout=30, verify=False) as client:
            resp = client.post(
                "/hooks/test-hash",
                json=large_body,
            )
            assert resp.status_code == 413, \
                f"超大请求契约应为 413，实际: {resp.status_code}"

    @pytest.mark.xfail(reason="应用缺陷：/hooks/:publicHash 端点未挂载（index.ts 未注册 hooksRoutes，全局兜底 200 空 body），无 body 请求无效 hash 应返回 404（已确认）", strict=True)
    def test_webhook_no_body(self, api_base_url):
        """无请求体触发 webhook — 契约：无效 hash 应返回 404"""
        with httpx.Client(base_url=api_base_url, timeout=30, verify=False) as client:
            resp = client.post(
                "/hooks/nonexistent-hash-99999",
                content=b"",
                headers={"Content-Type": "application/json"},
            )
            assert resp.status_code == 404, \
                f"无 body 契约应为 404，实际: {resp.status_code}"

    @pytest.mark.xfail(reason="应用缺陷：/hooks/:publicHash 端点未挂载（index.ts 未注册 hooksRoutes，全局兜底 200 空 body），字符串 body 无效 hash 应返回 404（已确认）", strict=True)
    def test_webhook_string_body(self, api_base_url):
        """字符串请求体触发 webhook — 契约：无效 hash 应返回 404"""
        with httpx.Client(base_url=api_base_url, timeout=30, verify=False) as client:
            resp = client.post(
                "/hooks/nonexistent-hash-99999",
                content="plain text body",
                headers={"Content-Type": "text/plain"},
            )
            assert resp.status_code == 404, \
                f"字符串 body 契约应为 404，实际: {resp.status_code}"

    @pytest.mark.xfail(reason="应用缺陷：/hooks/:publicHash 端点未挂载（index.ts 未注册 hooksRoutes，全局兜底 200 空 body），带 query 的无效 hash 应返回 404（已确认）", strict=True)
    def test_webhook_with_query_params(self, api_base_url):
        """带 query 参数触发 webhook — 契约：无效 hash 应返回 404"""
        with httpx.Client(base_url=api_base_url, timeout=30, verify=False) as client:
            resp = client.post(
                "/hooks/nonexistent-hash-99999?key1=value1&key2=value2",
                json={"test": "data"},
            )
            assert resp.status_code == 404, \
                f"带 query 契约应为 404，实际: {resp.status_code}"

    @pytest.mark.xfail(reason="应用缺陷：/hooks/:publicHash 端点未挂载（index.ts 未注册 hooksRoutes，全局兜底 200 空 body），有效 hash 应返回 {received: true}（已确认）", strict=True)
    def test_webhook_valid_trigger(self, web_client, api_base_url):
        """有效触发器 hash 触发 webhook — 契约：应返回 {received: true}"""
        trigger_hash = _get_trigger_hash(web_client)
        if not trigger_hash:
            pytest.skip("无可用的触发器 hash，无法测试有效 webhook")

        with httpx.Client(base_url=api_base_url, timeout=30, verify=False) as client:
            resp = client.post(
                f"/hooks/{trigger_hash}",
                json={"event": "test", "data": {"key": "value"}},
            )
            assert resp.status_code == 200, \
                f"有效 webhook 预期 200，实际: {resp.status_code}"
            body = _safe_parse_json(resp)
            assert body is not None, "有效 webhook 响应应有 JSON body"
            assert body.get("received") is True, \
                f"有效 webhook 应返回 received=true: {body}"
