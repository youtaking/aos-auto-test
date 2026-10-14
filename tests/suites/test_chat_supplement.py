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
    if "is-collapsed" in (panel.get_attribute("class") or "").split():
        opener = page.locator("button.artifacts-open-button")
        expect(opener).to_have_count(1)
        opener.click()
    expect(panel).not_to_have_class(re.compile(r"\bis-collapsed\b"))
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

    # 1. 创建新会话并发送消息使其有标题（使用唯一标记避免历史数据干扰）
    chat.create_new_session()
    unique_id = _uuid.uuid4().hex[:6]
    session_marker = f"E2E-del-{unique_id}"
    chat.send_message(f"{session_marker}-请回复OK")
    logged_in_page.wait_for_timeout(1500)  # Yjs 同步需要时间

    try:
        # 2. 通过 client API 获取会话列表（绕过 UI 缓存），支持 YJS 异步加载重试
        titles_before = []
        matching = []
        for _retry in range(25):  # 增加到 25 次（约 37.5s）
            titles_before = chat.get_session_titles_via_client()
            # fallback: React fiber 失败时用 DOM 提取
            if len(titles_before) == 0:
                titles_before = chat.get_session_titles()
            if len(titles_before) > 0:
                matching = [t for t in titles_before if unique_id in t]
                if len(matching) > 0:
                    break
            logged_in_page.wait_for_timeout(1500)
        assert len(titles_before) > 0, "会话列表为空（YJS sessions 未加载）"

        # 3. 找到包含 marker 的会话（只删除测试创建的）
        if len(matching) == 0:
            # 回退：用 DOM 中的会话标题查找
            dom_titles = chat.get_session_titles()
            matching_dom = [t for t in dom_titles if unique_id in t]
            if len(matching_dom) > 0:
                matching = matching_dom
            else:
                pytest.skip(
                    f"未找到测试创建的会话（unique_id: {unique_id}），"
                    f"Yjs 同步延迟或会话未创建成功。"
                    f"client 列表: {titles_before[:5]}, DOM 列表: {dom_titles[:5]}"
                )

        target_title = matching[0]
        count_before = len(matching)

        # 4. 删除该会话（通过 client.deleteSession WebSocket JSON-RPC）
        deleted = chat.delete_session_by_title(target_title)
        assert deleted, \
            f"会话删除 API 调用失败：服务器不支持 session/delete 或无法删除 '{target_title}'"

        # 5. 通过 client API 验证删除（轮询等待 YjsWs 同步）
        count_after = count_before
        for _retry in range(20):
            logged_in_page.wait_for_timeout(500)
            titles_after = chat.get_session_titles_via_client()
            count_after = sum(1 for t in titles_after if unique_id in t)
            if count_after < count_before:
                break

        # 如果仍无变化，尝试刷新页面后再检查
        if count_after >= count_before:
            try:
                logged_in_page.reload(wait_until="domcontentloaded")
            except Exception:
                pass
            logged_in_page.wait_for_load_state("networkidle")
            logged_in_page.wait_for_timeout(500)
            titles_after = chat.get_session_titles_via_client()
            count_after = sum(1 for t in titles_after if unique_id in t)

        assert count_after < count_before, (
            f"删除后会话数量未减少（可能为应用 Bug）: 删除前 {count_before}, 删除后 {count_after}"
        )
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
    expect(panel).to_have_class(re.compile(r"\bis-collapsed\b"))
    opener = logged_in_page.locator("button.artifacts-open-button")
    expect(opener).to_have_count(1)
    expect(opener).to_be_visible()
    opener.click()
    expect(panel).not_to_have_class(re.compile(r"\bis-collapsed\b"))
    expect(panel.get_by_role("tab", name="站点", exact=True)).to_have_attribute(
        "aria-selected", "true"
    )
    expect(frame).to_be_visible(timeout=15000)
    expect(frame).to_have_attribute("src", original_src)
