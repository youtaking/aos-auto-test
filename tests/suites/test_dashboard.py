# tests/suites/test_dashboard.py
"""Dashboard 模块回归测试"""
import pytest
from tests.pages.dashboard_page import DashboardPage


@pytest.fixture
def logged_in_page(page, login_page, test_config):
    """已登录的页面"""
    admin = test_config["fenixagent"]["admin"]
    login_page.goto()
    login_page.login(admin["email"], admin["password"])
    return page


@pytest.mark.p0
def test_dashboard_loads(logged_in_page, base_url):
    """Dashboard 页面能正常加载"""
    dashboard = DashboardPage(logged_in_page, base_url)
    dashboard.goto()
    assert dashboard.is_loaded()


@pytest.mark.p0
def test_dashboard_has_sidebar(logged_in_page, base_url):
    """Dashboard 包含侧边栏导航"""
    dashboard = DashboardPage(logged_in_page, base_url)
    dashboard.goto()
    assert dashboard.has_sidebar()
