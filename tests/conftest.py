# tests/conftest.py
"""pytest 全局 fixtures：浏览器、页面、登录状态"""
import os
import pytest
import allure
import yaml
from pathlib import Path
from playwright.sync_api import sync_playwright


def pytest_addoption(parser):
    try:
        parser.addoption("--step-delay", action="store", default="0",
                         help="每步操作后延迟秒数（用于有头模式观察）")
    except ValueError:
        pass  # 已被其他插件注册


@pytest.fixture(scope="session")
def step_delay(request):
    """每步操作后的延迟秒数"""
    return float(request.config.getoption("--step-delay", default="0"))


@pytest.fixture(scope="session")
def test_config():
    """加载测试配置"""
    config_path = Path(__file__).parent / "fixtures" / "test_data.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="session")
def base_url(request, test_config):
    """被测应用 URL：优先使用 --base-url 命令行参数，否则读配置文件"""
    cli_url = request.config.getoption("--base-url")
    if cli_url:
        return cli_url
    return test_config["fenixagent"]["url"]


@pytest.fixture(scope="session")
def browser_instance():
    """整个测试会话共享一个浏览器实例"""
    delay = float(os.environ.get("STEP_DELAY", "0"))
    slow_mo = int(delay * 1000)  # 秒转毫秒
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=os.environ.get("HEADLESS", "true").lower() == "true",
            slow_mo=slow_mo,
        )
        yield browser
        browser.close()


@pytest.fixture(scope="session")
def context(browser_instance):
    """整个测试会话共享一个浏览器上下文（cookie/session 持久化）"""
    ctx = browser_instance.new_context(
        viewport={"width": 1920, "height": 1080},
        ignore_https_errors=True,
    )
    yield ctx
    ctx.close()


@pytest.fixture(scope="session")
def page(context):
    """整个测试会话共享一个页面"""
    p = context.new_page()
    yield p
    p.close()


@pytest.fixture(scope="session")
def logged_in_page(page, base_url, test_config, step_delay):
    """登录一次，后续所有用例共享登录状态。
    如果 test_login_success 已经登录过，则直接复用。"""
    from tests.pages.login_page import LoginPage

    login = LoginPage(page, base_url)
    login.goto()
    if login.is_logged_in():
        return page

    admin = test_config["fenixagent"]["admin"]
    login.login(admin["email"], admin["password"])
    assert login.is_logged_in(), "登录失败，后续用例无法继续"
    return page


@pytest.fixture
def login_page(page, base_url):
    """LoginPage 实例（用于登录模块自身的测试）"""
    from tests.pages.login_page import LoginPage
    return LoginPage(page, base_url)


@pytest.fixture(autouse=True)
def _step_pause(step_delay):
    """每个测试用例之间暂停指定秒数"""
    yield
    if step_delay > 0:
        import time
        time.sleep(step_delay)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """每条用例结束后截图并附加到 Allure 报告"""
    outcome = yield
    report = outcome.get_result()

    if report.when == "call":
        page = item.funcargs.get("logged_in_page") or item.funcargs.get("page")
        if page and not page.is_closed():
            screenshot = page.screenshot(full_page=True)
            name = "失败截图" if report.failed else "页面截图"
            allure.attach(
                screenshot,
                name=name,
                attachment_type=allure.attachment_type.PNG,
            )
