# tests/suites/test_chat_multi_client_sync.py
"""多端（双浏览器）聊天同步回归测试。

场景：浏览器 A、B 使用同一账号（小春）打开同一 agent 实例（URL 完全相同的
/ctrl/agent/chat/{agentId}/{ses_inst_env_xxx_1}）。由于两端共享同一
rcsSessionId 的 Y.Doc，A 发消息 / AI 回复 / 任务执行时，B 应实时同步到最新会话内容。

同步延迟 = B 看到内容的时间 − A 看到内容的时间，验收 ≤ 5 秒。
不同步视为被测应用 Bug，严格失败（不 skip）。
"""
import json
import re
import time
import uuid

import allure
import pytest

from tests.pages.chat_test_page import ChatTestPage

AGENT_NAME = "my-auto-test"
SYNC_DEADLINE_S = 5
CHAT_READY_TIMEOUT_S = 30
INSTANCE_URL_TIMEOUT_S = 20
TURN_TIMEOUT_S = 90

LOG_SELECTOR = "div[role='log']"


# ==================== 辅助函数 ====================


def _log_text(page) -> str:
    """读取消息区 div[role='log'] 的文本（用户消息 + 思考指示 + AI 回复）"""
    try:
        el = page.locator(LOG_SELECTOR).first
        if el.count() == 0:
            return ""
        return el.inner_text(timeout=3000)
    except Exception:
        return ""


def _normalize(text: str) -> str:
    """归一化日志：去掉行首尾空白和"思考了 X 秒/思考了一会"指示行。

    A、B 两端对同一推理指示渲染文案可能不同（"思考了 1 秒" vs "思考了一会"），
    同步收敛断言必须去掉这类行，只比较实际会话内容。
    """
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if re.match(r"^思考", line):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _wait_until(page, check, timeout_s, interval=0.5) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            if check():
                return True
        except Exception:
            pass
        page.wait_for_timeout(int(interval * 1000))
    return False


def _wait_chat_ready(page, timeout_s=CHAT_READY_TIMEOUT_S) -> bool:
    """聊天就绪：输入框 textarea 出现 ≈ Yjs WS 已连接"""
    return _wait_until(page, lambda: page.locator("textarea").count() > 0, timeout_s)


def _wait_instance_url(page, timeout_s=INSTANCE_URL_TIMEOUT_S) -> bool:
    """等 A 的 URL 进入实例会话（.../ses_inst_env_xxx_1）"""
    return _wait_until(page, lambda: "/ses_inst_" in page.url, timeout_s)


def _wait_turn_complete(page, token, quiet_s=2.0, timeout_s=TURN_TIMEOUT_S) -> str:
    """等 A 的回合完成：用户消息 token 已出现 + 日志稳定 quiet_s 秒"""
    last = _log_text(page)
    stable_since = time.monotonic()
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        page.wait_for_timeout(500)
        cur = _log_text(page)
        if cur != last:
            last = cur
            stable_since = time.monotonic()
        elif time.monotonic() - stable_since >= quiet_s and token in last:
            return last
    return _log_text(page)


def _open_sync_pair(a, b, base_url, agent_name=AGENT_NAME) -> str:
    """A 进入 agent 聊天（拿到实例 URL）→ B 打开同一 URL → 双方就绪。

    Agent 未进入聊天视为环境数据缺失，开头跳过（前置条件检查）。
    """
    chat = ChatTestPage(a, base_url)
    chat.goto_agent_chat(agent_name)
    if not _wait_instance_url(a):
        pytest.skip(f"Agent {agent_name} 未进入实例聊天（环境数据缺失），当前 URL: {a.url}")
    url = a.url
    b.goto(url, wait_until="domcontentloaded")
    assert _wait_chat_ready(a), "A 聊天未就绪"
    # 停止会话中残留的 AI 流式响应（流式期间 composer 禁发，Enter 不会提交新消息）
    try:
        chat._stop_ai_if_responding()
    except Exception:
        pass
    assert _wait_chat_ready(b), "B 聊天未就绪"
    return url


def _attach_b_diagnostics(b):
    """失败时把 B 侧 WebSocket / 控制台 / JS 错误附加到 Allure 诊断"""
    diag = getattr(b, "_sync_diag", {})
    try:
        allure.attach(
            json.dumps(diag, ensure_ascii=False, indent=2),
            name="B 侧同步诊断",
            attachment_type=allure.attachment_type.JSON,
        )
    except Exception:
        pass


def _assert_b_synced(b, marker, timeout_s=SYNC_DEADLINE_S, label="内容"):
    """断言 B 在 timeout_s 秒内同步到 marker（字符串或回调）。失败则附加诊断并严格失败"""
    if callable(marker):
        ok = _wait_until(b, lambda: marker(_log_text(b)), timeout_s)
        desc = label
    else:
        ok = _wait_until(b, lambda: marker in _log_text(b), timeout_s)
        desc = f"{label}: {marker!r}"
    if not ok:
        _attach_b_diagnostics(b)
        pytest.fail(
            f"浏览器 B 在 {timeout_s}s 内未同步到 {desc}。\n"
            f"B 日志: {_log_text(b)[-400:]!r}"
        )
    return True


# ==================== 用例 ====================


@pytest.mark.p1
def test_user_message_live_sync(logged_in_page, second_browser_page, base_url):
    """TC-SYNC-001 | 用户消息实时同步：A 发消息，B ≤5s 看到"""
    a, b = logged_in_page, second_browser_page
    _open_sync_pair(a, b, base_url)
    token = f"sync-msg-{uuid.uuid4().hex[:6]}"
    a_chat = ChatTestPage(a, base_url)
    a_chat.send_message(token)
    # A 先出现自己的消息
    assert _wait_until(a, lambda: token in _log_text(a), 10), \
        f"A 未显示自己发送的消息 {token!r}"
    # B 5s 内同步到
    _assert_b_synced(b, token, label="用户消息")


@pytest.mark.p1
def test_assistant_reply_sync(logged_in_page, second_browser_page, base_url):
    """TC-SYNC-002 | AI 流式回复同步：A 的 AI 回复，B ≤5s 看到相同内容"""
    a, b = logged_in_page, second_browser_page
    _open_sync_pair(a, b, base_url)
    token = f"sync-reply-{uuid.uuid4().hex[:6]}"
    a_chat = ChatTestPage(a, base_url)
    a_chat.send_message(f"{token} 请只回复两个字：收到")
    assert _wait_until(a, lambda: token in _log_text(a), 10), "A 未显示用户消息"
    _wait_turn_complete(a, token)
    a_norm = _normalize(_log_text(a))
    _assert_b_synced(
        b,
        lambda b_log: _normalize(b_log) == a_norm,
        label="AI 回复（A/B 日志收敛）",
    )


@pytest.mark.p1
def test_task_execution_sync(logged_in_page, second_browser_page, base_url):
    """TC-SYNC-003 | 任务执行同步：A 执行任务（产出代码块），B ≤5s 同步到结果"""
    a, b = logged_in_page, second_browser_page
    _open_sync_pair(a, b, base_url)
    token = f"sync-task-{uuid.uuid4().hex[:6]}"
    a_chat = ChatTestPage(a, base_url)
    a_chat.send_message(
        f"{token} 请用 Python 写一个函数 add(a, b) 返回两数之和，并用 ```python 代码块展示"
    )
    assert _wait_until(a, lambda: token in _log_text(a), 10), "A 未显示用户消息"
    _wait_turn_complete(a, token)
    a_norm = _normalize(_log_text(a))
    _assert_b_synced(
        b,
        lambda b_log: _normalize(b_log) == a_norm,
        label="任务执行结果（A/B 日志收敛）",
    )


@pytest.mark.p1
def test_late_joiner_sync(logged_in_page, second_browser_page, base_url):
    """TC-SYNC-004 | 迟加入者初始同步：B 在 A 聊完后打开同一 URL，立即看到全部历史"""
    a, b = logged_in_page, second_browser_page
    a_chat = ChatTestPage(a, base_url)
    a_chat.goto_agent_chat(AGENT_NAME)
    if not _wait_instance_url(a):
        pytest.skip(f"Agent {AGENT_NAME} 未进入实例聊天（环境数据缺失），当前 URL: {a.url}")
    url = a.url
    # 停止会话中残留的 AI 流式响应（流式期间 composer 禁发）
    try:
        a_chat._stop_ai_if_responding()
    except Exception:
        pass
    token = f"late-{uuid.uuid4().hex[:6]}"
    a_chat.send_message(f"{token} 请回复：ok")
    assert _wait_until(a, lambda: token in _log_text(a), 10), "A 未显示用户消息"
    _wait_turn_complete(a, token)
    a_norm = _normalize(_log_text(a))
    # B 之后才打开同一 URL
    b.goto(url, wait_until="domcontentloaded")
    assert _wait_chat_ready(b), "B 聊天未就绪"
    _assert_b_synced(
        b,
        lambda b_log: _normalize(b_log) == a_norm,
        label="历史会话初始同步（A/B 日志收敛）",
    )


@pytest.mark.p1
def test_reconnect_resync(logged_in_page, second_browser_page, base_url):
    """TC-SYNC-005 | 刷新重连后仍同步：B 刷新重连，A 再发消息 B 仍 ≤5s 看到"""
    a, b = logged_in_page, second_browser_page
    _open_sync_pair(a, b, base_url)
    a_chat = ChatTestPage(a, base_url)

    token1 = f"rec1-{uuid.uuid4().hex[:6]}"
    a_chat.send_message(token1)
    assert _wait_until(a, lambda: token1 in _log_text(a), 10), "A 未显示 token1"
    # 等 AI 回合结束再发下一条（流式期间 composer 禁发，Enter 不会提交）
    _wait_turn_complete(a, token1)
    _assert_b_synced(b, token1, label="token1 用户消息")

    # B 刷新重连，历史应通过初始同步恢复（等待而非瞬时断言）
    b.goto(b.url, wait_until="domcontentloaded")
    assert _wait_chat_ready(b), "B 刷新后未就绪"
    assert _wait_until(b, lambda: token1 in _log_text(b), SYNC_DEADLINE_S), (
        f"B 刷新后丢失历史消息 token1。B 日志: {_log_text(b)[-200:]!r}"
    )

    # A 再发一条，B 重连后仍实时同步
    token2 = f"rec2-{uuid.uuid4().hex[:6]}"
    a_chat.send_message(token2)
    assert _wait_until(a, lambda: token2 in _log_text(a), 10), "A 未显示 token2"
    _assert_b_synced(b, token2, label="token2 用户消息")
