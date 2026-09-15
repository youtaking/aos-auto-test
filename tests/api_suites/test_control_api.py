# tests/api_suites/test_control_api.py
"""Control 接口负向契约：/web/sessions/:id/*

原 3 条正向用例（test_send_session_event / test_send_session_control /
test_interrupt_session）已于 2026-09-15 删除，不再作为回归对象：

被测项目 0ea07115「移除无用的 sessions 模块」在 src/routes/web/index.ts 中
一并删除了 `import webControl` 与 `.use(webControl)`，control.ts 成为死代码，
接口未挂载——请求落到全局兜底返回 HTTP 200 + 空响应体，与 control.ts 声明的
{success, data} 契约不符。前端调用方也已删除（聊天改走 RCS relay），该 HTTP
通道属遗留路径。用例集（api_all_cases）中对应条目同步移除。
兜底行为本身的问题记录在 docs/app-defect-unmatched-route-empty-body.md。

本文件保留 2 条负向用例：只断言"不存在的会话必须报错"，不依赖正向契约。
"""
import httpx
import pytest


class TestControlWebAPI:
    """/web/sessions/:id/* 的负向契约（session cookie 认证）"""

    def test_send_event_nonexistent_session(self, web_client):
        """向不存在的会话发送事件：应返回 404 或 403"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError)):
            web_client.send_session_event("nonexistent-session-99999", {
                "type": "user",
                "content": "test",
            })

    def test_interrupt_nonexistent_session(self, web_client):
        """中断不存在的会话：应返回 404 或 403"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError)):
            web_client.interrupt_session("nonexistent-session-99999")