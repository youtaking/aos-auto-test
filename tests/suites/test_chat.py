# tests/suites/test_chat.py
"""Chat 对话模块回归测试"""
import pytest
from tests.pages.chat_page import ChatPage


@pytest.mark.order(11)
@pytest.mark.p0
def test_chat_home_loads(logged_in_page, base_url):
    """对话首页能正常加载"""
    chat = ChatPage(logged_in_page, base_url)
    chat.goto_home()
    assert chat.is_home_loaded()


@pytest.mark.order(12)
@pytest.mark.p1
def test_chat_sidebar_has_agents(logged_in_page, base_url):
    """侧边栏显示智能体列表"""
    chat = ChatPage(logged_in_page, base_url)
    chat.goto_home()
    agents = chat.get_sidebar_agents()
    assert len(agents) > 0, "侧边栏没有智能体"


@pytest.mark.order(13)
@pytest.mark.p0
def test_sessions_page_loads(logged_in_page, base_url):
    """会话列表页面能正常加载"""
    chat = ChatPage(logged_in_page, base_url)
    chat.goto_sessions()
    assert "/session" in logged_in_page.url.lower(), \
        f"会话页面 URL 异常: {logged_in_page.url}"
    # 验证页面有实质内容 — 会话列表区域或空状态提示
    main_content = logged_in_page.locator("div.agent-panel-body, div.flex-1.overflow-y-auto")
    has_visible_content = main_content.first.is_visible() if main_content.count() > 0 else False
    body_text = logged_in_page.locator("body").inner_text().strip()
    # 会话相关关键词或空状态提示
    has_session_info = any(kw in body_text for kw in [
        "会话", "新会话", "暂无", "历史", "Session", "No session",
    ])
    assert has_visible_content or has_session_info, \
        f"会话列表页面无可视内容（main可见={has_visible_content}，body长度={len(body_text)}）"
