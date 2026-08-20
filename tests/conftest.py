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
    """被测应用 URL：优先 CLI 参数 > 环境变量 > 配置文件（统一去除尾斜杠，防止 URL 拼接出双斜杠）"""
    cli_url = request.config.getoption("--base-url")
    if cli_url:
        return cli_url.rstrip("/")
    env_url = os.environ.get("FENIX_URL")
    if env_url:
        return env_url.rstrip("/")
    return test_config["fenixagent"]["url"].rstrip("/")


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
    ctx_kwargs = {"ignore_https_errors": True, "locale": "zh-CN"}
    if not is_headless:
        ctx_kwargs["no_viewport"] = True  # 有头模式下配合 --start-maximized 使用实际窗口大小
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
    email = os.environ.get("FENIX_UI_EMAIL") or admin["email"]
    password = os.environ.get("FENIX_UI_PASSWORD") or admin["password"]
    login.login(email, password)
    assert login.is_logged_in(), "登录失败，后续用例无法继续"
    # 等待侧边栏渲染完成，确保后续用例可直接使用
    try:
        page.wait_for_selector(
            "button.agent-sidebar-nav-item", timeout=10000
        )
    except Exception:
        pass  # 非所有页面都有侧边栏，不阻断
    return page


@pytest.fixture(scope="session", autouse=True)
def _cleanup_leftover_test_providers(logged_in_page, base_url):
    """会话开始时清理遗留的测试 Provider（防止假模型污染模型库）。

    测试模型配置用例（test_model_config.py）创建 Provider 时以 'e2e-test-' 为前缀，
    若上次运行异常退出未能清理，遗留的假模型会被 Agent 一键创建选中导致测试失败。
    """
    try:
        resp = logged_in_page.request.get(f"{base_url}/web/config/providers")
        if resp.status != 200:
            return
        data = resp.json()
        providers = data.get("data", {}).get("providers", [])
        leftover = [p for p in providers if "e2e-test-" in p.get("id", "")]
        if leftover:
            print(f"\n[session-cleanup] 发现 {len(leftover)} 个遗留测试 Provider，正在清理...")
            for p in leftover:
                pid = p.get("id", "")
                del_resp = logged_in_page.request.delete(
                    f"{base_url}/web/config/providers?name={pid}"
                )
                status = "ok" if del_resp.status in (200, 204) else f"fail({del_resp.status})"
                print(f"  删除 '{pid}': {status}")
    except Exception as e:
        print(f"\n[session-cleanup] 清理遗留 Provider 失败（不影响测试）: {e}")


@pytest.fixture(scope="session")
def env_check(logged_in_page, base_url):
    """检查测试环境依赖的服务/数据是否可用，供测试用例按需 skip"""
    checks = {}
    # 1. 检查 embedding 模型（知识库依赖）
    try:
        resp = logged_in_page.request.get(f"{base_url}/web/knowledgeBases/form-options")
        if resp.status == 200:
            data = resp.json().get("data", {})
            checks["has_embedding_models"] = len(data.get("embeddingModels", [])) > 0
        else:
            checks["has_embedding_models"] = False
    except Exception:
        checks["has_embedding_models"] = False
    # 2. 检查 Hindsight 服务（记忆模块依赖）
    try:
        resp = logged_in_page.request.get(f"{base_url}/web/hindsight/status")
        if resp.status == 200:
            checks["hindsight_enabled"] = resp.json().get("data", {}).get("enabled", False)
        else:
            checks["hindsight_enabled"] = False
    except Exception:
        checks["hindsight_enabled"] = False
    return checks


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
def _pre_test_cleanup(request):
    """每条用例开始前轻量清理：关闭残留弹窗、停止 AI 回复，确保页面处于干净状态。"""
    markers = [m.name for m in request.node.iter_markers()]
    is_api_test = "no_browser" in markers or "api_suites" in str(request.fspath)
    if is_api_test:
        yield
        return
    try:
        page = request.getfixturevalue("page")
    except Exception:
        yield
        return
    if page.is_closed():
        yield
        return
    try:
        # 1. 按 Escape 关闭可能的残留弹窗
        dialog = page.locator("[role='dialog'], [role='alertdialog']")
        if dialog.count() > 0 and dialog.first.is_visible():
            page.keyboard.press("Escape")
            page.wait_for_timeout(300)
        # 2. 停止正在进行的 AI 回复（lucide-square = 停止图标）
        stop_btn = page.locator("button:has(svg.lucide-square)")
        if stop_btn.count() > 0 and stop_btn.first.is_visible():
            stop_btn.first.click()
            page.wait_for_timeout(500)
    except Exception:
        pass
    yield


@pytest.fixture(autouse=True)
def _cleanup_modal(request):
    """每条用例结束后关闭残留的 modal / dialog / overlay，避免遮挡后续测试。"""
    yield
    markers = [m.name for m in request.node.iter_markers()]
    is_api_test = "no_browser" in markers or "api_suites" in str(request.fspath)
    if is_api_test:
        return
    try:
        page = request.getfixturevalue("page")
    except Exception:
        return
    if page.is_closed():
        return
    try:
        # 先按 Escape 关闭可能的 modal / dialog / popover
        for _ in range(3):
            page.keyboard.press("Escape")
            page.wait_for_timeout(300)
        # 关闭 alert dialog overlay (data-slot='alert-dialog-overlay')
        alert_overlay = page.locator("[data-slot='alert-dialog-overlay']")
        if alert_overlay.count() > 0 and alert_overlay.first.is_visible():
            # 尝试点击 alert dialog 中的取消/关闭按钮
            alert_btns = page.locator("[data-slot='alert-dialog'] button, [role='alertdialog'] button")
            if alert_btns.count() > 0:
                # 安全检查：如果弹窗标题包含"删除"，只点取消/关闭，绝不点确认
                alert_text = page.locator("[data-slot='alert-dialog'], [role='alertdialog']").first.inner_text()
                is_delete_dialog = "删除" in alert_text
                safe_cancel = ("取消", "关闭", "Cancel", "Close")
                safe_confirm = ("确认", "确定", "Confirm", "OK")
                # 删除类弹窗：只接受取消按钮
                allowed = safe_cancel if is_delete_dialog else (*safe_cancel, *safe_confirm)
                for i in range(alert_btns.count()):
                    btn = alert_btns.nth(i)
                    txt = (btn.text_content() or "").strip()
                    if txt in allowed:
                        btn.click(force=True)
                        page.wait_for_timeout(500)
                        break
                # 不再 fallback 点击第一个按钮 — 未知按钮可能是危险操作（如 "删除智能体"）
            else:
                page.keyboard.press("Escape")
                page.wait_for_timeout(500)
        # 如果 Agent 编辑 modal 仍在 (div.absolute.inset-0.z-50)，强制关闭
        modal = page.locator("div.absolute.inset-0.z-50")
        if modal.count() > 0 and modal.first.is_visible():
            # 尝试多种关闭按钮
            close_btn = modal.locator(
                "button[data-slot='dialog-close'], "
                "button:has-text('✕'), "
                "button:has-text('×'), "
                "button:has-text('取消'), "
                "button:has-text('关闭'), "
                "button:has-text('Close'), "
                "button[aria-label*='close' i], "
                "button[aria-label*='关闭']"
            )
            if close_btn.count() > 0:
                close_btn.first.click(force=True)
                page.wait_for_timeout(500)
            else:
                # 最后手段：用 JS 移除 DOM 节点
                page.evaluate("""() => {
                    document.querySelectorAll('div.absolute.inset-0.z-50').forEach(el => el.remove());
                }""")
                page.wait_for_timeout(300)
        # 关闭其他 dialog / alertdialog
        for role in ["dialog", "alertdialog"]:
            dlg = page.locator(f"[role='{role}']")
            if dlg.count() > 0 and dlg.first.is_visible():
                close_btn = dlg.locator(
                    "button[data-slot='dialog-close'], "
                    "button:has-text('✕'), "
                    "button:has-text('关闭'), "
                    "button:has-text('取消'), "
                    "button[aria-label*='close' i]"
                )
                if close_btn.count() > 0:
                    close_btn.first.click(force=True)
                    page.wait_for_timeout(300)
                else:
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(300)
    except Exception:
        pass


# ==================== 测试数据清理 ====================

import logging as _logging
_cleanup_logger = _logging.getLogger("test_cleanup")


def register_cleanup(request, fn):
    """注册测试数据清理回调（在创建数据后调用）。

    用法：
        result = ac.create_agent_api(name=agent_name, ...)
        register_cleanup(request, lambda: ac.delete_agent_api(agent_name))

    清理函数在测试结束后逆序执行，失败只记 warning 不影响测试结果。
    """
    if hasattr(request.node, '_test_cleanup'):
        request.node._test_cleanup.append(fn)


@pytest.fixture(autouse=True)
def _test_data_cleanup(request):
    """每条用例结束后自动执行已注册的清理函数。"""
    cleanup_fns = []
    request.node._test_cleanup = cleanup_fns
    yield
    for fn in reversed(cleanup_fns):
        try:
            fn()
        except Exception as e:
            _cleanup_logger.warning(f"Cleanup failed: {e}")


@pytest.fixture(autouse=True)
def _page_error_monitor(request):
    """全局页面错误监听：自动捕获 console.error、API 4xx/5xx、JS 未捕获异常。
    每条用例结束后断言无错误。
    API 测试（标记 no_browser 或位于 api_suites/ 目录）跳过浏览器初始化。"""
    # 检查是否应跳过浏览器
    markers = [m.name for m in request.node.iter_markers()]
    is_api_test = "no_browser" in markers or "api_suites" in str(request.fspath)
    if is_api_test:
        yield
        return

    # 非 API 测试：获取 page fixture 进行错误监听
    try:
        page = request.getfixturevalue("page")
    except Exception:
        yield
        return

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
            # 白名单：页面导航切换时轮询请求中断（SPA 瞬态错误）
            if "Failed to fetch" in msg.text and (
                "/web/config" in msg.text
                or "/web/environments" in msg.text
                or "/web/sidebar-config" in msg.text
                or "/web/agent-sites" in msg.text
            ):
                return
            if "网络异常" in msg.text and "ApiError" in msg.text:
                return
            # 白名单：MCP 检测远程服务器连接失败的已知错误（假 URL）
            if "SSE error" in msg.text or "Unable to connect" in msg.text:
                return
            # 白名单：文件服务不可用（workspace 文件服务 503，环境限制）
            if "file_service_unavailable" in msg.text or "文件服务不可用" in msg.text:
                warnings.append(f"[console.error] {msg.text}")
                return
            # 白名单：文件树 revalidate 失败（文件服务 503 级联）
            if "Failed to revalidate file tree" in msg.text or "Tree revalidate failed" in msg.text:
                warnings.append(f"[console.error] {msg.text}")
                return
            # 白名单：浏览器原生的 500/503 资源加载失败（测试用假 URL 或 workspace 服务不可用）
            if "Failed to load resource" in msg.text and ("500" in msg.text or "503" in msg.text):
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
            # 白名单：新建 Agent 环境初始化期间的瞬态 404
            if "环境不存在" in msg.text or "Failed to load file tree" in msg.text:
                return
            # 白名单：Workspace not found（新建 Agent 环境 workspace 未初始化）
            if "Workspace not found" in msg.text:
                warnings.append(f"[console.error] {msg.text}")
                return
            # 白名单：新建 Agent 配置加载期间的瞬态 404
            if "Failed to load agent config" in msg.text:
                return
            # 白名单：知识库删除后轮询 resources 返回"知识库不存在"
            if "知识库不存在" in msg.text and "knowledgeBases" in msg.text:
                return
            # 白名单：知识库删除后详情页加载失败
            if "Failed to load detail" in msg.text and "知识库不存在" in msg.text:
                return
            # 非致命：服务端并发限制，记为警告
            if "并发上限" in msg.text:
                warnings.append(f"[console.error] {msg.text}")
                return
            # 白名单：429 限流控制台日志
            if "RATE_LIMITED" in msg.text or "Too many requests" in msg.text:
                warnings.append(f"[console.error] {msg.text}")
                return
            # 白名单：浏览器级 429 资源加载失败
            if "Failed to load resource" in msg.text and "429" in msg.text:
                warnings.append(f"[console.error] {msg.text}")
                return
            # 白名单：429 限流导致的 JS 异常（ApiError 级联）
            if "ApiError" in msg.text and "Too many requests" in msg.text:
                warnings.append(f"[console.error] {msg.text}")
                return
            # 白名单：429 限流导致的前端网络异常（rate limit 拦截后 fetch 报网络错误）
            if "网络异常" in msg.text and "[request]" in msg.text:
                warnings.append(f"[console.error] {msg.text}")
                return
            # 白名单：Failed to enter instance（并发限制导致环境无法进入）
            if "Failed to enter instance" in msg.text:
                warnings.append(f"[console.error] {msg.text}")
                return
            # 白名单：CONFIG_WRITE_ERROR（服务端并发/写入限制）
            if "CONFIG_WRITE_ERROR" in msg.text:
                warnings.append(f"[console.error] {msg.text}")
                return
            # 白名单：Agent 配置保存失败（modal 自动触发 PUT 500）
            if "保存失败" in msg.text and "ApiError" in msg.text:
                warnings.append(f"[console.error] {msg.text}")
                return
            console_errors.append(msg.text)

    def on_response(response):
        if response.status >= 400:
            # 白名单：429 限流（后台轮询消耗配额，非测试代码问题）
            if response.status == 429:
                warnings.append(f"[API 429] {response.request.method} {response.url}")
                return
            # 白名单：已知的非关键接口错误
            if "web/organizations" in response.url:
                return
            # 白名单：views 环境接口 404（服务端未实现）
            if "web/environments/views" in response.url and response.status == 404:
                return
            # 白名单：登录模块错误密码测试的预期 401
            if "auth/sign-in" in response.url and response.status == 401:
                return
            # 白名单：测试 Provider 用假 URL 获取模型列表的已知 500
            if "fetch-models" in response.url:
                return
            # 白名单：模型连通性测试用假 URL 的预期 500
            if "actions/test-model" in response.url:
                return
            # 白名单：MCP 检测本地服务器返回 400（系统正确拒绝）
            if "mcp/actions/inspect" in response.url:
                return
            # 白名单：建站助手轮询已删除/不存在的 App 的 404
            if "agent-sites/apps/by-remote" in response.url and response.status == 404:
                return
            # 白名单：新建 Agent 环境初始化期间的瞬态 404（fs/tree, instances）
            if response.status == 404 and (
                "/fs/tree" in response.url or "/instances" in response.url
                or "/web/environments/env_" in response.url
            ):
                return
            # 白名单：环境 workspace 未就绪的 503
            if response.status == 503 and "/web/environments/" in response.url:
                return
            # 白名单：新建 Agent 配置加载期间的瞬态 404
            if response.status == 404 and "/web/config/agents" in response.url:
                return
            # 白名单：知识库删除后页面轮询 resources 的 404
            if response.status == 404 and "/web/knowledgeBases/" in response.url and "/resources" in response.url:
                return
            # 白名单：知识库删除后页面轮询 KB 详情的 404
            if response.status == 404 and "/web/knowledgeBases/" in response.url:
                return
            # 非致命：并发限制引发的 API 错误，记为警告
            if "environments" in response.url and "enter" in response.url:
                warnings.append(f"[API {response.status}] {response.request.method} {response.url}")
                return
            # 白名单：Agent 配置自动保存 PUT 500（modal 打开时前端自动保存）
            if response.status == 500 and "/web/config/agents" in response.url:
                warnings.append(f"[API 500] {response.request.method} {response.url}")
                return
            # 白名单：environment 创建/进入 500（并发限制）
            if response.status == 500 and "/web/environments/" in response.url:
                warnings.append(f"[API 500] {response.request.method} {response.url}")
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
        # 非致命：429 限流引发的 JS 异常级联
        if "Too many requests" in err_text or "RATE_LIMITED" in err_text:
            warnings.append(f"[JS] {err_text}")
            return
        # 非致命：React 路由/查询分组瞬态错误，记为警告
        if "Group" in err_text and "not found" in err_text:
            warnings.append(f"[JS] {err_text}")
            return
        # 非致命：新建 Agent 环境初始化期间的瞬态错误
        if "环境不存在" in err_text or "Failed to load file tree" in err_text:
            warnings.append(f"[JS] {err_text}")
            return
        # 非致命：新建 Agent 配置加载期间的瞬态错误
        if "Failed to load agent config" in err_text:
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

    # 若测试主体已失败，teardown 不再重复断言（避免 Allure 中同一错误出现两次）
    if all_errors:
        test_failed = getattr(request.node, "_test_call_failed", False)
        if not test_failed:
            assert False, "页面检测到错误:\n\n" + "\n\n".join(all_errors)
        else:
            # 测试已失败，仅打印错误信息作为补充
            print(f"\n⚠️ 页面错误（测试已失败，不再重复断言）:")
            for e in all_errors:
                print(f"  {e[:200]}")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """每条用例结束后截图并附加到 Allure 报告"""
    outcome = yield
    report = outcome.get_result()

    # 记录测试主体是否失败，供 fixture teardown 判断是否需要重复断言
    if report.when == "call" and report.failed:
        item._test_call_failed = True

    if report.when == "call":
        page = item.funcargs.get("logged_in_page") or item.funcargs.get("page")
        if page and not page.is_closed():
            try:
                screenshot = page.screenshot(full_page=False, timeout=5000)
                name = "失败截图" if report.failed else "页面截图"
                allure.attach(
                    screenshot,
                    name=name,
                    attachment_type=allure.attachment_type.PNG,
                )
            except Exception as e:
                # 截图失败不影响测试结果
                import logging
                logging.getLogger("screenshot").warning(f"截图失败: {e}")
