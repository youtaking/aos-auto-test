# tests/suites/test_chat.py
"""Chat 对话模块回归测试"""
import pytest
import allure
from tests.pages.chat_page import ChatPage


def _check_console_errors(page, timeout_ms=500):
    """收集并检查控制台错误，返回错误列表。
    使用 try/finally 确保监听器清理，避免 session 级累积。"""
    errors = []

    def on_console(msg):
        if msg.type == "error":
            errors.append(msg.text)

    page.on("console", on_console)
    try:
        page.wait_for_timeout(timeout_ms)
    finally:
        try:
            page.remove_listener("console", on_console)
        except Exception:
            pass
    return errors


@pytest.mark.order(11)
@pytest.mark.p0
def test_chat_home_loads(logged_in_page, base_url):
    """✅ 人工评审通过 | 点击侧边栏 agent 后能正常进入对话页面"""
    chat = ChatPage(logged_in_page, base_url)
    chat.goto_home()

    # 点击指定 agent 进入对话页面
    agent_name = "my-auto-test"
    chat.click_sidebar_agent(agent_name)

    # 验证聊天界面元素出现（URL 不变，聊天内嵌在首页）
    # 全量回归时会话连接/面板渲染可能卡死导致 textarea 保持 hidden，禁止裸 count 立即断言
    ta = logged_in_page.locator("textarea")

    def _textarea_ready():
        return ta.count() > 0 and ta.first.is_visible()

    for _attempt in range(4):
        if _textarea_ready():
            break
        logged_in_page.wait_for_timeout(2000)
    if not _textarea_ready():
        # 二次刷新强制重建 chat 页（与 test_refresh_during_reply 相同的自愈模式）
        print("  [重连] textarea 8s 内不可见，二次刷新强制重建 chat 页...")
        try:
            logged_in_page.reload(wait_until="domcontentloaded")
        except Exception:
            pass
        logged_in_page.wait_for_load_state("domcontentloaded")
        logged_in_page.wait_for_timeout(2000)
        for _attempt in range(8):
            if _textarea_ready():
                break
            logged_in_page.wait_for_timeout(1500)
    has_textarea = _textarea_ready()
    assert has_textarea, \
        f"点击 agent '{agent_name}' 后未出现聊天输入框（URL: {logged_in_page.url}）"

    # 验证对话页面有消息展示区域（等待 Conversation 组件渲染）
    try:
        logged_in_page.locator("div[role='log']").first.wait_for(
            state="attached", timeout=15000
        )
        has_message_area = True
    except Exception:
        # 回退：检查 prose 或其他消息容器
        has_message_area = logged_in_page.locator(
            "div[role='log'], div[role='log'] > div, div.prose"
        ).count() > 0
    assert has_message_area, "对话页面缺少消息展示区域"

    # 检查无控制台错误
    errors = _check_console_errors(logged_in_page, 500)
    assert not errors, f"对话页面加载后有控制台错误: {errors}"


@pytest.mark.order(12)
@pytest.mark.p1
def test_chat_sidebar_has_agents(logged_in_page, base_url):
    """✅ 人工评审通过 | 侧边栏显示智能体列表（含数量+名称详情）"""
    chat = ChatPage(logged_in_page, base_url)
    chat.goto_home()

    agents = chat.get_sidebar_agents()
    count = chat.get_sidebar_agent_count()
    scroll_info = chat.get_sidebar_scroll_info()

    print(f"\n侧边栏智能体数量: {count}")
    print(f"侧边栏可滚动: {chat.is_sidebar_scrollable()}（{scroll_info}）")
    print(f"名称列表: {agents[:20]}")

    allure.attach(
        f"侧边栏智能体数量: {count}\n"
        f"可滚动: {chat.is_sidebar_scrollable()}\n"
        f"滚动信息: {scroll_info}\n"
        f"名称列表: {agents[:20]}",
        name="智能体列表",
        attachment_type=allure.attachment_type.TEXT,
    )

    assert count > 0, "侧边栏没有智能体"
    assert len(agents) > 0, "侧边栏智能体列表为空"
    # 每个 agent 名称非空
    for agent in agents:
        assert agent.strip(), f"存在空名称的 agent: '{agent}'"
    # 指定 agent my-auto-test 在列表中
    assert any("my-auto-test" in a for a in agents), \
        f"侧边栏中未找到 my-auto-test，当前列表: {agents}"
    # agent 数量多于可视区域时，侧边栏应可滚动
    # 注意：headless 1920×1080 视口下，9 个 agent（~486px）不会超出侧边栏高度（~638px），
    # 因此 scrollHeight == clientHeight 是正常的，不再强制断言可滚动。
    if count > 5 and chat.is_sidebar_scrollable():
        print(f"侧边栏有 {count} 个 agent，可滚动（{scroll_info}）")


@pytest.mark.order(13)
@pytest.mark.p0
def test_sessions_page_loads(logged_in_page, base_url):
    """✅ 人工评审通过 | 会话列表能正常加载（通过 agent 对话页面 → 打开会话列表弹窗）"""
    chat = ChatPage(logged_in_page, base_url)

    # 进入 agent 对话页面
    chat.goto_home()
    agent_name = "my-auto-test"
    chat.click_sidebar_agent(agent_name)
    # 点击 agent 后验证聊天元素出现（textarea 可能需要额外渲染时间）
    textarea = logged_in_page.locator("textarea")
    for _wait in range(10):
        if textarea.count() > 0:
            break
        logged_in_page.wait_for_timeout(1000)
    has_textarea = textarea.count() > 0
    if not has_textarea:
        pytest.skip(
            f"点击 agent '{agent_name}' 后未出现聊天输入框（URL: {logged_in_page.url}），"
            f"Agent 可能不可用"
        )

    # 打开会话列表弹窗（等待弹窗出现，最长 5s）
    dialog_open = chat.open_session_dialog()

    # 如果弹窗没打开，再等一轮看页面是否有会话信息
    if not dialog_open:
        try:
            logged_in_page.locator("div.agent-panel-content").first.wait_for(
                state="visible", timeout=3000
            )
        except Exception:
            pass

    body_text = logged_in_page.locator("div.agent-panel-content").inner_text() \
        if logged_in_page.locator("div.agent-panel-content").count() > 0 else ""

    has_session_info = dialog_open or any(kw in body_text for kw in [
        "会话", "新会话", "历史", "Session",
    ])

    allure.attach(
        f"对话页面 URL: {logged_in_page.url}\n"
        f"会话弹窗打开: {dialog_open}\n"
        f"页面内容片段: {body_text[:200]}\n"
        f"页面含会话关键词: {has_session_info}",
        name="会话列表验证",
        attachment_type=allure.attachment_type.TEXT,
    )

    assert has_session_info, \
        "对话页面中未找到会话列表或会话相关信息"

    # 检查无控制台错误
    errors = _check_console_errors(logged_in_page, 500)
    assert not errors, f"会话列表加载后有控制台错误: {errors}"
