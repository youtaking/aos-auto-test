# tests/suites/test_agent.py
"""Agent 管理模块回归测试"""
import pytest
from tests.pages.agent_page import AgentPage


@pytest.fixture
def logged_in_page(page, login_page, test_config):
    admin = test_config["fenixagent"]["admin"]
    login_page.goto()
    login_page.login(admin["email"], admin["password"])
    return page


@pytest.mark.p1
def test_agent_list_loads(logged_in_page, base_url):
    """Agent 列表页面能正常加载"""
    agent_page = AgentPage(logged_in_page, base_url)
    agent_page.goto()
    assert agent_page.is_loaded()
