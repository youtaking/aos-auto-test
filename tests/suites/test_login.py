# tests/suites/test_login.py
"""登录/认证模块回归测试"""
import pytest


@pytest.mark.p0
def test_login_page_loads(login_page):
    """登录页面能正常加载"""
    login_page.goto()
    assert login_page.is_on_login_page()


@pytest.mark.p0
def test_login_success(login_page, test_config):
    """管理员能正常登录"""
    admin = test_config["fenixagent"]["admin"]
    login_page.goto()
    login_page.login(admin["email"], admin["password"])
    assert login_page.is_logged_in()


@pytest.mark.p0
def test_login_wrong_password(login_page, test_config):
    """错误密码显示提示信息"""
    admin = test_config["fenixagent"]["admin"]
    login_page.goto()
    login_page.login(admin["email"], "wrong_password_123")
    assert not login_page.is_logged_in()


@pytest.mark.p0
def test_unauthenticated_redirect(page, base_url):
    """未登录用户访问受保护页面会跳转到登录页"""
    page.goto(f"{base_url}/agent/dashboard")
    page.wait_for_load_state("networkidle")
    assert "/login" in page.url
