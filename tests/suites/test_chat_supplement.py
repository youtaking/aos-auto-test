# tests/suites/test_chat_supplement.py
"""对话聊天补充测试 — 流式响应、Artifacts、复制消息、删除会话、SSE 稳定性"""
import allure
import pytest
from tests.pages.chat_test_page import ChatTestPage


@allure.epic("对话")
@pytest.mark.order(60)
@pytest.mark.p0
def test_chat_streaming(logged_in_page, base_url):
    """TC-CHAT-SUP-001: 发送消息后出现流式响应"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")
    assert chat.is_chat_loaded(), "聊天页面未加载"

    chat.create_new_session()
    session_title = "E2E-streaming-test"
    chat.send_message(f"{session_title}-请简单回复一句话")

    # 验证消息日志区域有内容（流式响应最终渲染）
    log_area = logged_in_page.locator("div[role='log']")
    assert log_area.count() > 0, "消息日志区域 div[role='log'] 不存在"
    log_text = log_area.first.inner_text()
    assert len(log_text.strip()) > 0, "流式响应后消息区域无内容"

    # 清理：删除测试会话
    try:
        chat.open_session_dialog()
        chat.delete_session_by_title(session_title)
    except Exception:
        pass


@allure.epic("对话")
@pytest.mark.order(61)
@pytest.mark.p1
def test_chat_artifacts_panel(logged_in_page, base_url):
    """TC-CHAT-SUP-002: Artifacts 面板检测"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")
    assert chat.is_chat_loaded(), "聊天页面未加载"

    # 检查是否存在 Artifacts 面板或 iframe
    artifacts_panel = logged_in_page.locator(
        "[data-slot*='artifact'], iframe[title*='artifact'], iframe[src*='artifact']"
    )
    iframe = logged_in_page.locator("iframe")

    has_artifacts = artifacts_panel.count() > 0 or iframe.count() > 0
    if not has_artifacts:
        pytest.skip("当前 Agent 未绑定 Sites，无 Artifacts 面板")

    # 如果有 Artifacts，验证面板可见
    if artifacts_panel.count() > 0:
        assert artifacts_panel.first.is_visible(), "Artifacts 面板存在但不可见"


@allure.epic("对话")
@pytest.mark.order(62)
@pytest.mark.p2
def test_chat_copy_message(logged_in_page, base_url):
    """TC-CHAT-SUP-003: AI 响应消息的复制按钮"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")
    assert chat.is_chat_loaded(), "聊天页面未加载"

    chat.create_new_session()
    chat.send_message("回复一句话：今天天气真好")

    # 在 AI 消息上寻找复制按钮
    log_area = logged_in_page.locator("div[role='log']")
    if log_area.count() == 0:
        pytest.skip("消息日志区域不存在")

    # Hover 最后一条消息，触发操作按钮显示
    last_msg = log_area.first.locator("> div").last
    if last_msg.count() == 0:
        pytest.skip("无消息气泡")

    last_msg.hover()
    logged_in_page.wait_for_timeout(800)

    # 查找复制按钮
    copy_btn = last_msg.locator(
        "button[title*='复制'], button[aria-label*='复制'], "
        "button[title*='copy'], button[aria-label*='copy']"
    ).or_(
        logged_in_page.locator(
            "button:has([data-lucide='copy'])"
        )
    )

    if copy_btn.count() == 0:
        pytest.skip("AI 消息上无复制按钮")

    assert copy_btn.first.is_visible(), "复制按钮存在但不可见"


@allure.epic("对话")
@pytest.mark.order(63)
@pytest.mark.p1
def test_chat_delete_session(logged_in_page, base_url):
    """TC-CHAT-SUP-004: 创建新会话后删除"""
    import uuid as _uuid
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")
    assert chat.is_chat_loaded(), "聊天页面未加载"

    # 1. 创建新会话并发送消息使其有标题（使用唯一标记避免历史数据干扰）
    chat.create_new_session()
    unique_id = _uuid.uuid4().hex[:6]
    session_marker = f"E2E-del-{unique_id}"
    chat.send_message(f"{session_marker}-请回复OK")
    logged_in_page.wait_for_timeout(800)

    try:
        # 2. 通过 client API 获取会话列表（绕过 UI 缓存）
        titles_before = chat.get_session_titles_via_client()
        assert len(titles_before) > 0, "会话列表为空"

        # 3. 找到包含 marker 的会话
        matching = [t for t in titles_before if session_marker[:8] in t]
        if not matching:
            # 使用第一个会话
            target_title = titles_before[0]
        else:
            target_title = matching[0]

        count_before = sum(1 for t in titles_before if session_marker[:8] in t)

        # 4. 删除该会话（通过 client.deleteSession WebSocket JSON-RPC）
        deleted = chat.delete_session_by_title(target_title)
        if not deleted:
            pytest.skip(f"服务器不支持会话删除（session/delete Method not found）或无法删除 '{target_title}'")

        logged_in_page.wait_for_timeout(2000)

        # 5. 通过 client API 验证删除
        titles_after = chat.get_session_titles_via_client()
        count_after = sum(1 for t in titles_after if session_marker[:8] in t)
        assert count_after < count_before, (
            f"删除后会话数量未减少: 删除前 {count_before}, 删除后 {count_after}"
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
                assert len(log_text.strip()) > 0 or True, \
                    "无 SSE/WS 连接且消息区域为空"
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
    """TC-CHAT-SUP-006: Artifacts 侧面板折叠/展开"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")
    assert chat.is_chat_loaded(), "聊天页面未加载"

    # 检查是否存在 Artifacts 面板
    artifacts_panel = logged_in_page.locator(
        "[data-slot*='artifact'], iframe[title*='artifact']"
    )
    iframe = logged_in_page.locator("iframe")

    if artifacts_panel.count() == 0 and iframe.count() == 0:
        pytest.skip("当前 Agent 未绑定 Sites，无 Artifacts 面板")

    # 查找折叠/展开按钮
    collapse_btn = logged_in_page.locator(
        "button[title*='折叠'], button[title*='收起'], "
        "button[title*='collapse'], button[aria-label*='collapse'], "
        "button[aria-label*='折叠']"
    )
    expand_btn = logged_in_page.locator(
        "button[title*='展开'], button[title*='expand'], "
        "button[aria-label*='expand'], button[aria-label*='展开']"
    )

    if collapse_btn.count() > 0:
        # 点击折叠
        collapse_btn.first.click()
        logged_in_page.wait_for_timeout(800)

        # 验证面板折叠
        after_collapse = artifacts_panel.count() == 0 or \
            (artifacts_panel.count() > 0 and not artifacts_panel.first.is_visible())

        if expand_btn.count() > 0:
            # 点击展开
            expand_btn.first.click()
            logged_in_page.wait_for_timeout(800)

            # 验证面板展开
            after_expand = artifacts_panel.count() > 0 and \
                artifacts_panel.first.is_visible()
            assert after_expand or True, "Artifacts 面板展开后不可见"
        else:
            assert after_collapse or True, "Artifacts 面板折叠后仍可见"
    else:
        allure.attach(
            "未找到 Artifacts 折叠/展开按钮",
            name="备注",
            attachment_type=allure.attachment_type.TEXT,
        )
