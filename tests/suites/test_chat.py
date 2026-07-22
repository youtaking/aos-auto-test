# tests/suites/test_chat.py
"""Chat 对话模块回归测试"""
import pytest
from tests.pages.chat_page import ChatPage


@pytest.fixture
def logged_in_page(page, login_page, test_config):
    admin = test_config["fenixagent"]["admin"]
    login_page.goto()
    login_page.login(admin["email"], admin["password"])
    return page


@pytest.mark.p1
def test_sessions_page_loads(logged_in_page, base_url):
    """会话列表页面能正常加载"""
    chat = ChatPage(logged_in_page, base_url)
    chat.goto_sessions()
    assert chat.is_sessions_loaded()
