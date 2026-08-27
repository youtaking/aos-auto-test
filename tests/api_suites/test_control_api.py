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
                    session_id = inst.get("sessionId") or inst.get("rcsSessionId")
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
    """

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
