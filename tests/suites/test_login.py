# tests/suites/test_login.py
"""登录/认证模块回归测试（最先执行，失败案例先跑，成功案例最后）"""
import pytest


@pytest.mark.order(1)
@pytest.mark.p0
def test_login_page_loads(login_page):
    """登录页面能正常加载"""
    login_page.goto()
    assert login_page.is_on_login_page()
    # 验证登录表单关键元素已渲染（防止 500 白屏也 PASS）
    assert login_page.page.locator("#auth-email").is_visible(), "登录邮箱输入框未渲染"
    assert login_page.page.locator("#auth-password").is_visible(), "登录密码输入框未渲染"


@pytest.mark.order(2)
@pytest.mark.p0
def test_login_wrong_password(login_page, test_config):
    """错误密码显示提示信息"""
    admin = test_config["fenixagent"]["admin"]
    login_page.goto()
    login_page.login(admin["email"], "wrong_password_123")
    assert not login_page.is_logged_in()
    # 验证错误提示信息出现（核心预期）
    login_page.page.wait_for_timeout(1000)
    error = login_page.get_error_message()
    assert error, "错误密码后未显示错误提示信息"


@pytest.mark.order(3)
@pytest.mark.p0
def test_unauthenticated_redirect(browser_instance, base_url):
    """未登录用户访问受保护页面会跳转到登录页"""
    # 使用独立浏览器上下文，确保没有登录 cookie
    context = browser_instance.new_context()
    page = context.new_page()
    try:
        page.goto(f"{base_url}/ctrl/agent/dashboard")
        page.wait_for_load_state("networkidle")
        assert "/ctrl/login" in page.url, \
            f"未登录用户访问受保护页面未重定向到登录页: {page.url}"
    finally:
        context.close()


@pytest.mark.order(4)
@pytest.mark.p0
def test_login_success(login_page, test_config):
    """管理员登录成功（最后跑，登录后保持会话给后续模块）"""
    admin = test_config["fenixagent"]["admin"]
    login_page.goto()
    login_page.login(admin["email"], admin["password"])
    assert login_page.is_logged_in()
