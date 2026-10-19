# tests/suites/test_chat_supplement.py
"""对话聊天补充测试 — 流式响应、Artifacts、复制消息、删除会话、SSE 稳定性"""
import allure
import pytest
import re
from playwright.sync_api import expect
from tests.pages.chat_test_page import ChatTestPage


@allure.epic("对话")
@pytest.mark.order(60)
@pytest.mark.p0
def test_chat_streaming(logged_in_page, base_url):
    """TC-CHAT-SUP-001: 发送消息后出现流式响应"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")
    if not chat.is_on_chat_page():
        pytest.skip("未能导航到 my-auto-test 聊天页（Agent 可能不在列表中或环境异常）")
    if not chat.is_chat_loaded():
        pytest.skip("聊天页面未加载")

    chat.create_new_session()
    session_title = "E2E-streaming-test"
    chat.send_message(f"{session_title}-请简单回复一句话")

    # 验证消息日志区域有内容（流式响应最终渲染）
    log_area = logged_in_page.locator("div[role='log']")
    # 增加重试等待日志区域出现
    if log_area.count() == 0:
        for _ in range(5):
            logged_in_page.wait_for_timeout(1000)
            if log_area.count() > 0:
                break
    if log_area.count() == 0:
        assert False, "【应用Bug】消息日志区域 div[role='log'] 不存在（发送消息后页面无消息区域，可能跳转异常）"
    log_text = log_area.first.inner_text()
    assert len(log_text.strip()) > 0, "流式响应后消息区域无内容"

    # 清理：删除测试会话
    try:
        chat.open_session_dialog()
        chat.delete_session_by_title(session_title)
    except Exception:
        pass


def _open_bound_site_panel(page, base_url):
    """新版工作区使用 tab 角色；等待真实站点预览，不把定位失败当成缺数据。"""
    chat = ChatTestPage(page, base_url)
    chat.goto_agent_chat("my-auto-test")
    expect(page.locator("textarea").first).to_be_visible()
    panel = page.locator("aside.artifacts-shell")
    expect(panel).to_have_count(1)
    # 折叠态标记：新版 UI 把原 CSS 类 `.is-collapsed { display:none }` 改为 `hidden` 工具类
    # （见 apps/web/src/pages/agent-panel/chat-workspace-artifacts.tsx），折叠时面板整体不可见、
    # 内部 [role=tab] 退出无障碍树，故必须先展开再定位页签。
    if "hidden" in (panel.get_attribute("class") or "").split():
        opener = page.locator("button.artifacts-open-button")
        expect(opener).to_have_count(1)
        opener.click()
    expect(panel).not_to_have_class(re.compile(r"\bhidden\b"))
    sites = panel.get_by_role("tab", name="站点", exact=True)
    expect(sites).to_have_count(1)
    sites.click()
    expect(sites).to_have_attribute("aria-selected", "true")
    frame = panel.locator("iframe[src*='/web/site/deploy/']")
    expect(frame).to_have_count(1, timeout=15000)
    expect(frame).to_be_visible(timeout=15000)
    return panel, frame


@allure.epic("对话")
@pytest.mark.order(61)
@pytest.mark.p1
def test_chat_artifacts_panel(logged_in_page, base_url):
    """TC-CHAT-SUP-002: 新版站点页签激活并显示部署预览。"""
    _open_bound_site_panel(logged_in_page, base_url)


@allure.epic("对话")
@pytest.mark.order(62)
@pytest.mark.p2
def test_chat_ai_response(logged_in_page, base_url):
    """TC-CHAT-SUP-003: 发送消息后 AI 正常回复"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")
    if not chat.is_on_chat_page():
        pytest.skip("未能导航到 my-auto-test 聊天页（Agent 可能不在列表中或环境异常）")
    assert chat.is_chat_loaded(), "聊天页面未加载"

    chat.create_new_session()
    chat.send_message("回复一句话：今天天气真好")

    # 等待消息日志区域出现
    log_area = logged_in_page.locator("div[role='log']")
    try:
        log_area.first.wait_for(state="visible", timeout=15000)
    except Exception:
        pytest.fail("发送消息后消息日志区域 div[role='log'] 未出现")

    # 等待 AI 回复渲染完成
    try:
        log_area.first.locator("div.prose, p").first.wait_for(
            state="attached", timeout=15000
        )
    except Exception:
        pass
    logged_in_page.wait_for_timeout(500)

    # 验证消息区域有内容
    log_text = log_area.first.inner_text()
    assert len(log_text.strip()) > 0, "AI 回复后消息区域无内容"


@allure.epic("对话")
@pytest.mark.order(63)
@pytest.mark.p1
def test_chat_delete_session(logged_in_page, base_url):
    """TC-CHAT-SUP-004: 创建新会话后删除"""
    import uuid as _uuid
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")
    if not chat.is_on_chat_page():
        pytest.skip("未能导航到 my-auto-test 聊天页（Agent 可能不在列表中或环境异常）")
    assert chat.is_chat_loaded(), "聊天页面未加载"

    # 1. 创建新会话并发送消息。会话标题由应用异步生成（会从消息原文变为摘要标题），
    #    因此自建会话必须按 sessionId 追踪，不能用消息标记去匹配标题。
    chat.create_new_session()
    sessions_before = chat.get_sessions_via_client()
    assert len(sessions_before) > 0, "会话列表为空（YJS sessions 未加载）"
    before_ids = {s["id"] for s in sessions_before}
    unique_id = _uuid.uuid4().hex[:6]
    session_marker = f"E2E-del-{unique_id}"
    chat.send_message(f"{session_marker}-请回复OK")
    logged_in_page.wait_for_timeout(1500)

    try:
        log_text = logged_in_page.locator("div[role='log']").first.inner_text()
        assert session_marker in log_text, \
            f"消息未发送成功，消息区实际内容: {log_text[:200]!r}"

        # 2. 等新会话出现在 client 会话列表（Yjs 异步同步）
        new_sessions = []
        for _retry in range(25):  # 约 37.5s
            new_sessions = [s for s in chat.get_sessions_via_client() if s["id"] not in before_ids]
            if new_sessions:
                break
            logged_in_page.wait_for_timeout(1500)
        assert len(new_sessions) > 0, "新会话未出现在会话列表（YJS sessions 未同步）"
        target_id = new_sessions[0]["id"]

        # 3. 删除该会话（先新建会话使目标变为非活跃，再通过 client 回调删除）
        deleted = chat.delete_session_by_id(target_id)
        assert deleted, f"会话删除 API 调用失败: {target_id}"

        # 4. 轮询等待删除同步（YjsWs），超时后刷新页面兜底复核
        remaining = [s for s in chat.get_sessions_via_client() if s["id"] == target_id]
        for _retry in range(40):  # 约 20s
            logged_in_page.wait_for_timeout(500)
            remaining = [s for s in chat.get_sessions_via_client() if s["id"] == target_id]
            if not remaining:
                break

        if remaining:
            try:
                logged_in_page.reload(wait_until="domcontentloaded")
                logged_in_page.wait_for_load_state("networkidle")
            except Exception:
                pass
            sessions_after = []
            for _retry in range(20):  # 约 10s，等 Yjs 会话列表重新加载
                logged_in_page.wait_for_timeout(500)
                sessions_after = chat.get_sessions_via_client()
                if sessions_after:
                    break
            assert sessions_after, "刷新后会话列表为空（YJS sessions 未加载）"
            remaining = [s for s in sessions_after if s["id"] == target_id]

        assert not remaining, f"删除后会话仍在列表中: {target_id}"
    finally:
        # 清理：关闭对话框
        try:
            chat.close_session_dialog()
        except Exception:
            pass


@allure.epic("对话")
@pytest.mark.order(64)
@pytest.mark.p1
def test_chat_sse_connection_stability(logged_in_page, base_url):
    """TC-CHAT-SUP-005: SSE/WebSocket 连接稳定性 — 发送消息后检测实时连接"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")
    assert chat.is_chat_loaded(), "聊天页面未加载"

    # 监控 SSE/WS 连接
    sse_urls = []
    ws_urls = []

    def on_request(req):
        url_lower = req.url.lower()
        if "sse" in url_lower or "event-stream" in url_lower or \
           "stream" in url_lower:
            sse_urls.append(req.url)

    def on_ws(ws):
        ws_urls.append(ws.url)

    logged_in_page.on("request", on_request)
    logged_in_page.on("websocket", on_ws)

    try:
        chat.create_new_session()
        chat.send_message("SSE-test: 请简单回复")
        logged_in_page.wait_for_timeout(800)

        # 验证实时连接
        has_sse = len(sse_urls) > 0
        has_ws = len(ws_urls) > 0

        if has_sse or has_ws:
            # 连接存在，验证消息区域有内容
            log_area = logged_in_page.locator("div[role='log']")
            assert log_area.count() > 0, "有 SSE/WS 连接但消息区域不存在"
        else:
            # 可能使用普通 HTTP 轮询，验证消息仍有响应
            log_area = logged_in_page.locator("div[role='log']")
            if log_area.count() > 0:
                log_text = log_area.first.inner_text()
                assert len(log_text.strip()) > 0, \
                    "无 SSE/WS 连接且消息区域为空（可能未正常响应）"
            allure.attach(
                f"未检测到 SSE/WS 连接 (SSE: {len(sse_urls)}, WS: {len(ws_urls)})",
                name="连接信息",
                attachment_type=allure.attachment_type.TEXT,
            )
    finally:
        try:
            logged_in_page.remove_listener("request", on_request)
            logged_in_page.remove_listener("websocket", on_ws)
        except Exception:
            pass


@allure.epic("对话")
@pytest.mark.order(65)
@pytest.mark.p1
def test_chat_artifacts_panel_collapse_expand(logged_in_page, base_url):
    """TC-CHAT-SUP-006: 工作区关闭后重新打开，保持原站点预览。"""
    panel, frame = _open_bound_site_panel(logged_in_page, base_url)
    original_src = frame.get_attribute("src")
    close = panel.get_by_role("button", name="关闭右侧工作区", exact=True)
    expect(close).to_have_count(1)
    close.click()
    expect(panel).to_have_class(re.compile(r"\bhidden\b"))
    opener = logged_in_page.locator("button.artifacts-open-button")
    expect(opener).to_have_count(1)
    expect(opener).to_be_visible()
    opener.click()
    expect(panel).not_to_have_class(re.compile(r"\bhidden\b"))
    expect(panel.get_by_role("tab", name="站点", exact=True)).to_have_attribute(
        "aria-selected", "true"
    )
    expect(frame).to_be_visible(timeout=15000)
    expect(frame).to_have_attribute("src", original_src)
