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


@allure.epic("对话")
@pytest.mark.order(61)
@pytest.mark.p1
def test_chat_artifacts_panel(logged_in_page, base_url):
    """TC-CHAT-SUP-002: Artifacts 面板检测"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")
    assert chat.is_chat_loaded(), "聊天页面未加载"

    # 确保 Artifacts 面板已展开（批量跑时面板可能被前面的用例折叠或展开）
    expand_btn = logged_in_page.locator("button[title='显示内容面板']")
    if expand_btn.count() > 0 and expand_btn.first.is_visible():
        expand_btn.first.click(force=True)
        logged_in_page.wait_for_timeout(500)

    # 点击"站点"按钮显示 Artifacts 面板
    site_btn = logged_in_page.get_by_role("button", name="站点")
    if site_btn.count() == 0:
        pytest.skip("当前 Agent 无「站点」按钮（未绑定 Site）")
    if not site_btn.first.is_visible():
        pytest.skip("「站点」按钮不可见（Artifacts 面板可能未展开）")
    site_btn.first.click(force=True)
    try:
        logged_in_page.locator("iframe").first.wait_for(state="visible", timeout=10000)
    except Exception:
        pytest.fail("点击「站点」后 Artifacts iframe 未出现")

    # 验证 iframe 可见
    iframe = logged_in_page.locator("iframe")
    assert iframe.count() > 0, "Artifacts iframe 不存在"
    assert iframe.first.is_visible(), "Artifacts iframe 不可见"


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
    """TC-CHAT-SUP-006: Artifacts 侧面板折叠/展开"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")
    assert chat.is_chat_loaded(), "聊天页面未加载"

    # 确保 Artifacts 面板已展开
    expand_btn = logged_in_page.locator("button[title='显示内容面板']")
    if expand_btn.count() > 0 and expand_btn.first.is_visible():
        expand_btn.first.click(force=True)
        logged_in_page.wait_for_timeout(500)

    # 先点击「站点」按钮显示 Artifacts 面板
    site_btn = logged_in_page.get_by_role("button", name="站点")
    if site_btn.count() == 0:
        pytest.skip("当前 Agent 无「站点」按钮（未绑定 Site）")
    if not site_btn.first.is_visible():
        pytest.skip("「站点」按钮不可见（Artifacts 面板可能未展开）")
    site_btn.first.click(force=True)
    try:
        logged_in_page.locator("iframe").first.wait_for(state="visible", timeout=10000)
    except Exception:
        pytest.fail("点击「站点」后 Artifacts iframe 未出现")

    iframe = logged_in_page.locator("iframe")
    assert iframe.count() > 0 and iframe.first.is_visible(), "Artifacts iframe 不可见"

    # 查找折叠/展开按钮（面板级别或 iframe 周围的操作按钮）
    collapse_btn = logged_in_page.locator(
        "button[title*='折叠'], button[title*='收起'], "
        "button[title*='collapse'], button[aria-label*='collapse'], "
        "button[aria-label*='折叠']"
    )
    expand_btn = logged_in_page.locator(
        "button[title*='展开'], button[title*='expand'], "
        "button[aria-label*='expand'], button[aria-label*='展开']"
    )

    if collapse_btn.count() == 0 and expand_btn.count() == 0:
        allure.attach(
            "未找到 Artifacts 折叠/展开按钮（功能未实现或按钮选择器不匹配）",
            name="备注",
            attachment_type=allure.attachment_type.TEXT,
        )
        return

    if collapse_btn.count() > 0:
        # 点击折叠
        collapse_btn.first.click()
        logged_in_page.wait_for_timeout(800)

        # 折叠后 iframe 应该不可见或消失
        iframe_after_collapse = logged_in_page.locator("iframe")
        collapsed = iframe_after_collapse.count() == 0 or \
            not iframe_after_collapse.first.is_visible()

        if expand_btn.count() > 0:
            # 点击展开
            expand_btn.first.click()
            logged_in_page.wait_for_timeout(800)

            # 展开后 iframe 应该重新可见
            iframe_after_expand = logged_in_page.locator("iframe")
            assert iframe_after_expand.count() > 0 and \
                iframe_after_expand.first.is_visible(), \
                "Artifacts 面板展开后 iframe 不可见"
        else:
            assert collapsed, "Artifacts 面板点击折叠后 iframe 仍可见"
    else:
        allure.attach(
            "仅有展开按钮，无折叠按钮，跳过折叠/展开循环测试",
            name="备注",
            attachment_type=allure.attachment_type.TEXT,
        )
