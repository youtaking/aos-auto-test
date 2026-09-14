# tests/api_suites/test_control_api.py
"""Control 接口测试：功能验证 + 契约验证

覆盖控制台接口：
- TestControlWebAPI: /web/sessions/:id/*（session cookie 认证）

会话控制接口需要活跃的 session。测试会在无可用 session 时跳过。
"""
import httpx
import pytest


def _get_active_session(client):
    """尝试获取一个活跃的 session ID，返回 session_id 或 None"""
    # 尝试从环境实例获取 session
    try:
        envs = client.list_environments()
        if isinstance(envs, list):
            env_list = envs
        elif isinstance(envs, dict):
            env_list = envs.get("items", [])
        else:
            env_list = []

        for env in env_list:
            env_id = env.get("id")
            if not env_id:
                continue
            try:
                instances = client.list_environment_instances(env_id)
                if isinstance(instances, list):
                    inst_list = instances
                elif isinstance(instances, dict):
                    inst_list = instances.get("items", instances.get("instances", []))
                else:
                    inst_list = []

                for inst in inst_list:
                    if inst.get("status") != "running":
                        continue
                    # 当前控制接口以持久 instanceUid 标识会话。
                    session_id = inst.get("instanceUid") or inst.get("sessionId") or inst.get("rcsSessionId")
                    if session_id:
                        return session_id
            except Exception:
                continue
    except Exception:
        pass
    return None


class TestControlWebAPI:
    """/web/sessions/:id/* 会话控制接口（session cookie 认证）

    特点：
    - POST /sessions/:id/events — 发送会话事件
    - POST /sessions/:id/control — 发送控制指令
    - POST /sessions/:id/interrupt — 中断会话

    根因（3 条正向用例 xfail）：src/routes/web/index.ts 未注册 webControl，
    路由未挂载（被测项目 0ea07115「移除无用的 sessions 模块」把 `import webControl`
    与 `.use(webControl)` 一并删除，但 control.ts 文件仍在），请求落到全局兜底，
    返回 HTTP 200 + 空响应体 + 无 Content-Type；空响应被客户端解析为 {}，严格解包失败。
    control.ts 声明的契约仍为 {success:true,data:...}。前端已无 /web/sessions/:id/*
    调用（聊天改走 RCS relay），该 HTTP 通道属遗留路径。
    证据：docs/local-full-api-e2e-20260911.md（三个接口的原始状态码与空响应）。
    若被测项目恢复挂载，本标记会转为 XPASS 失败，提醒同步更新用例。
    """

    _NOT_MOUNTED = (
        "被测接口未挂载：src/routes/web/index.ts 未注册 webControl"
        "（0ea07115 移除 sessions 模块时一并删除了注册），请求落到全局兜底返回"
        " HTTP 200 空响应体，与 control.ts 声明的 {success,data} 契约不符（已确认）"
    )

    @pytest.mark.xfail(
        reason=_NOT_MOUNTED,
        strict=True,
    )
    def test_send_session_event(self, web_client):
        """向会话发送事件：需要活跃 session"""
        session_id = _get_active_session(web_client)
        if not session_id:
            pytest.skip("无活跃会话，无法测试事件发送")

        # 会话 404/403 不再中段 skip：真实反映会话状态（G3 修复）
        result = web_client.send_session_event(session_id, {
            "type": "user",
            "content": "auto-test message",
        })

        assert isinstance(result, dict)
        assert result.get("status") == "ok"

    @pytest.mark.xfail(
        reason=_NOT_MOUNTED,
        strict=True,
    )
    def test_send_session_control(self, web_client):
        """向会话发送控制指令：需要活跃 session"""
        session_id = _get_active_session(web_client)
        if not session_id:
            pytest.skip("无活跃会话，无法测试控制指令")

        result = web_client.send_session_control(session_id, {
            "type": "control_request",
            "action": "approve",
        })

        assert isinstance(result, dict)
        assert result.get("status") == "ok"

    @pytest.mark.xfail(
        reason=_NOT_MOUNTED,
        strict=True,
    )
    def test_interrupt_session(self, web_client):
        """中断会话：需要活跃 session"""
        session_id = _get_active_session(web_client)
        if not session_id:
            pytest.skip("无活跃会话，无法测试中断")

        # interrupt 成功返回 {success, data: null} → _unwrap 返回 None
        result = web_client.interrupt_session(session_id)
        assert result is None, f"interrupt 成功应返回 None（data:null），实际: {result!r}"

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
