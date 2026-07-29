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
    is_headless = os.environ.get("HEADLESS", "true").lower() == "true"
    launch_args = ["--start-maximized"] if not is_headless else []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=is_headless,
            slow_mo=slow_mo,
            args=launch_args,
        )
        yield browser
        browser.close()


@pytest.fixture(scope="session")
def context(browser_instance):
    """整个测试会话共享一个浏览器上下文（cookie/session 持久化）"""
    is_headless = os.environ.get("HEADLESS", "true").lower() == "true"
    ctx_kwargs = {"ignore_https_errors": True}
    if not is_headless:
        ctx_kwargs["no_viewport"] = True  # 有头模式下使用最大化窗口
    else:
        ctx_kwargs["viewport"] = {"width": 1920, "height": 1080}
    ctx = browser_instance.new_context(**ctx_kwargs)
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
    # 等待侧边栏渲染完成，确保后续用例可直接使用
    try:
        page.wait_for_selector(
            "button.agent-sidebar-nav-item", timeout=10000
        )
    except Exception:
        pass  # 非所有页面都有侧边栏，不阻断
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


@pytest.fixture(autouse=True)
def _page_error_monitor(page):
    """全局页面错误监听：自动捕获 console.error、API 4xx/5xx、JS 未捕获异常。
    每条用例结束后断言无错误。"""
    console_errors = []
    api_errors = []
    js_errors = []
    warnings = []  # 非致命警告，记录但不阻断测试

    def on_console(msg):
        if msg.type == "error":
            # 白名单：已知的瞬态错误，前端已处理，不影响功能
            if "web/organizations" in msg.text or "Failed to load org context" in msg.text:
                return
            # 白名单：测试 Provider 用假 URL 获取模型列表的已知错误
            if "CONFIG_TEST_REQUEST_FAILED" in msg.text or "fetch-models" in msg.text:
                return
            # 白名单：MCP 检测本地服务器返回"仅支持远程"的已知错误
            if "Inspect only supports remote" in msg.text or "检测失败" in msg.text:
                return
            # 白名单：页面导航切换时 AgentPanelLayout 轮询请求中断（SPA 瞬态错误）
            if "Failed to fetch" in msg.text and ("/web/config" in msg.text or "/web/environments" in msg.text):
                return
            if "网络异常" in msg.text and "ApiError" in msg.text:
                return
            # 白名单：MCP 检测远程服务器连接失败的已知错误（假 URL）
            if "SSE error" in msg.text or "Unable to connect" in msg.text:
                return
            # 白名单：浏览器原生的 500 资源加载失败（测试用假 URL 导致）
            if "Failed to load resource" in msg.text and "500" in msg.text:
                return
            # 白名单：建站助手轮询不存在 App 的 404
            if "Failed to load resource" in msg.text and "404" in msg.text:
                return
            # 白名单：建站助手请求不存在 App 的日志输出
            if "agent-sites/apps/by-remote" in msg.text and "not_found" in msg.text:
                return
            # 白名单：登录模块错误密码测试的预期 401 资源加载失败
            if "Failed to load resource" in msg.text and "401" in msg.text:
                return
            # 白名单：MCP inspect 本地服务器的 400 响应
            if "Failed to load resource" in msg.text and "400" in msg.text:
                return
            # 非致命：服务端并发限制，记为警告
            if "并发上限" in msg.text:
                warnings.append(f"[console.error] {msg.text}")
                return
            console_errors.append(msg.text)

    def on_response(response):
        if response.status >= 400:
            # 白名单：已知的非关键接口错误
            if "web/organizations" in response.url:
                return
            # 白名单：登录模块错误密码测试的预期 401
            if "auth/sign-in" in response.url and response.status == 401:
                return
            # 白名单：测试 Provider 用假 URL 获取模型列表的已知 500
            if "fetch-models" in response.url:
                return
            # 白名单：MCP 检测本地服务器返回 400（系统正确拒绝）
            if "mcp/actions/inspect" in response.url:
                return
            # 白名单：建站助手轮询已删除/不存在的 App 的 404
            if "agent-sites/apps/by-remote" in response.url and response.status == 404:
                return
            # 非致命：并发限制引发的 API 错误，记为警告
            if "environments" in response.url and "enter" in response.url:
                warnings.append(f"[API {response.status}] {response.request.method} {response.url}")
                return
            api_errors.append(
                f"[{response.status}] {response.request.method} {response.url}"
            )

    def on_pageerror(error):
        err_text = str(error)
        # 非致命：并发限制引发的 JS 异常，记为警告
        if "并发上限" in err_text or "WebSocket not connected" in err_text:
            warnings.append(f"[JS] {err_text}")
            return
        # 非致命：React 路由/查询分组瞬态错误，记为警告
        if "Group" in err_text and "not found" in err_text:
            warnings.append(f"[JS] {err_text}")
            return
        js_errors.append(err_text)

    page.on("console", on_console)
    page.on("response", on_response)
    page.on("pageerror", on_pageerror)

    yield

    # 清理监听器
    try:
        page.remove_listener("console", on_console)
        page.remove_listener("response", on_response)
        page.remove_listener("pageerror", on_pageerror)
    except Exception:
        pass

    # 汇总报告
    # 先输出警告（不阻断测试）
    if warnings:
        import logging
        logger = logging.getLogger("page_errors")
        for w in warnings:
            logger.warning(w)
        print(f"\n⚠️ 页面警告 ({len(warnings)}):")
        for w in warnings:
            print(f"  {w}")

    all_errors = []
    if js_errors:
        all_errors.append(f"JS 未捕获异常 ({len(js_errors)}):\n" + "\n".join(js_errors[:5]))
    if api_errors:
        all_errors.append(f"API 错误响应 ({len(api_errors)}):\n" + "\n".join(api_errors[:10]))
    if console_errors:
        all_errors.append(f"控制台错误 ({len(console_errors)}):\n" + "\n".join(console_errors[:5]))

    assert not all_errors, "页面检测到错误:\n\n" + "\n\n".join(all_errors)


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
