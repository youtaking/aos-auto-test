# tests/suites/test_mcp.py
"""MCP 服务器模块回归测试（TC-MCP-001 ~ TC-MCP-020）
基于真实 DOM 结构编写，选择器经过页面验证。"""
import time
import pytest
import allure
from tests.pages.mcp_page import McpServerPage
from tests.pages import locators as loc


# 测试用 MCP 服务器名（带时间戳避免冲突）
TEST_STDIO_NAME = f"auto-stdio-{int(time.time())}"
TEST_SSE_NAME = f"auto-sse-{int(time.time())}"
TEST_STDIO_CMD = "npx -y @modelcontextprotocol/server-filesystem /tmp"
TEST_SSE_URL = "http://localhost:3001/sse"


# === 辅助函数 ===

def _create_test_server(mcp, name, server_type="Stdio", command="echo hello", url=""):
    """创建测试用 MCP 服务器"""
    mcp.goto()
    mcp.open_create_dialog()
    mcp.select_type(server_type)
    if server_type in ("Stdio", "Local"):
        mcp.fill_create_form(name=name, command=command)
    else:
        mcp.fill_create_form(name=name, url=url or TEST_SSE_URL)
    mcp.save()
    mcp.goto()


# === TC-MCP-001: 列表数据加载 ===

@allure.epic("MCP服务器")
@pytest.mark.order(80)
@pytest.mark.p0
def test_mcp_list_data_loads(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-MCP-001: MCP 服务器列表数据加载"""
    mcp = McpServerPage(logged_in_page, base_url)

    # 拦截 API 响应
    api_data = mcp.setup_api_interceptor("mcp")
    mcp.goto()

    # 验证页面标题可见
    assert mcp.is_loaded(), "MCP 服务器管理页面未加载"

    # 验证搜索框存在
    search_input = logged_in_page.locator("input[placeholder='搜索 MCP 服务器...']")
    assert search_input.count() > 0, "搜索框不存在"

    # 验证列表容器可见（有服务器或空状态提示）
    list_container = logged_in_page.locator("div.flex-1.overflow-y-auto")
    body_text = logged_in_page.locator("div.agent-panel-body").inner_text()
    assert list_container.first.is_visible() or "暂无" in body_text or "没有" in body_text, \
        "MCP 服务器列表容器不可见且无空状态提示"

    # 验证 API 数据结构
    logged_in_page.wait_for_timeout(800)
    list_resps = [r for r in api_data if r["method"] == "GET" and r["status"] < 400]
    if list_resps:
        body = list_resps[0].get("body")
        if body and isinstance(body, dict):
            has_data = any(k in body for k in ["items", "data", "servers", "mcpServers", "success"])
            assert has_data, f"API 响应缺少数据字段: {list(body.keys())}"


# === TC-MCP-002: 创建本地 Stdio MCP 服务器 ===

@allure.epic("MCP服务器")
@pytest.mark.order(81)
@pytest.mark.p0
def test_create_stdio_server(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-MCP-002: 创建本地 Stdio MCP 服务器"""
    mcp = McpServerPage(logged_in_page, base_url)
    mcp.goto()

    # 点击「新建服务器」按钮
    mcp.open_create_dialog()
    assert mcp.is_create_dialog_open(), "新建 MCP 对话框未弹出"

    # 选择 Stdio 类型
    mcp.select_type("Stdio")

    # 填写名称和命令
    mcp.fill_create_form(name=TEST_STDIO_NAME, command=TEST_STDIO_CMD)
    mcp.save()

    # 验证创建成功 — 列表中出现新服务器
    mcp.goto()
    assert mcp.has_server(TEST_STDIO_NAME), \
        f"Stdio 服务器 '{TEST_STDIO_NAME}' 未出现在列表中"

    # 清理
    mcp.delete_server(TEST_STDIO_NAME)


# === TC-MCP-003: 创建远程 SSE MCP 服务器 ===

@allure.epic("MCP服务器")
@pytest.mark.order(82)
@pytest.mark.p0
def test_create_sse_server(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-MCP-003: 创建远程 SSE MCP 服务器"""
    mcp = McpServerPage(logged_in_page, base_url)
    mcp.goto()

    mcp.open_create_dialog()
    assert mcp.is_create_dialog_open(), "新建 MCP 对话框未弹出"

    mcp.select_type("SSE")
    mcp.fill_create_form(name=TEST_SSE_NAME, url=TEST_SSE_URL)
    mcp.save()

    mcp.goto()
    assert mcp.has_server(TEST_SSE_NAME), \
        f"SSE 服务器 '{TEST_SSE_NAME}' 未出现在列表中"

    # 清理
    mcp.delete_server(TEST_SSE_NAME)


# === TC-MCP-004: 名称格式校验 - 合法名称 ===

@allure.epic("MCP服务器")
@pytest.mark.order(83)
@pytest.mark.p1
def test_valid_name_format(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-MCP-004: 名称格式校验 - 合法名称"""
    mcp = McpServerPage(logged_in_page, base_url)
    mcp.goto()

    mcp.open_create_dialog()
    assert mcp.is_create_dialog_open(), "新建 MCP 对话框未弹出"

    # 输入合法名称：小写字母+数字+单连字符
    dialog = logged_in_page.locator("[role='dialog']")
    name_input = dialog.locator("input[name='name']").or_(
        dialog.locator("input").first
    )
    name_input.first.fill("my-mcp-server")
    logged_in_page.wait_for_timeout(500)

    # 不应出现校验错误
    errors = mcp.get_validation_errors()
    name_errors = [e for e in errors if "名称" in e or "name" in e.lower() or "格式" in e]
    assert len(name_errors) == 0, f"合法名称触发了校验错误: {name_errors}"

    mcp.close_dialog()


# === TC-MCP-005: 名称格式校验 - 非法名称 ===

@allure.epic("MCP服务器")
@pytest.mark.order(84)
@pytest.mark.p1
def test_invalid_name_format(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-MCP-005: 名称格式校验 - 非法名称"""
    mcp = McpServerPage(logged_in_page, base_url)
    mcp.goto()

    invalid_cases = [
        ("MyServer", "大写名称"),
        ("my--server", "连续连字符"),
        ("a" * 65, "超过 64 字符"),
    ]

    for name, desc in invalid_cases:
        mcp.open_create_dialog()
        assert mcp.is_create_dialog_open(), f"对话框未弹出（{desc}）"

        dialog = logged_in_page.locator("[role='dialog']")
        name_input = dialog.locator("input[name='name']").or_(dialog.locator("input").first)
        name_input.first.fill(name)

        # 尝试保存触发校验
        mcp.save()
        logged_in_page.wait_for_timeout(500)

        # 对话框仍打开 = 被校验拦截；同时检查 toast 错误提示
        dialog_still_open = mcp.is_create_dialog_open()
        errors = mcp.get_validation_errors()
        assert dialog_still_open or len(errors) > 0, \
            f"{desc}（'{name[:20]}'）未触发校验反馈: dialog_still_open={dialog_still_open}, errors={errors}"

        if dialog_still_open:
            mcp.close_dialog()
        logged_in_page.wait_for_timeout(500)

    # 空名称测试
    mcp.open_create_dialog()
    if mcp.is_create_dialog_open():
        mcp.save()
        logged_in_page.wait_for_timeout(500)
        dialog_still_open = mcp.is_create_dialog_open()
        errors = mcp.get_validation_errors()
        assert dialog_still_open or len(errors) > 0, \
            f"空名称未触发校验反馈: dialog_still_open={dialog_still_open}, errors={errors}"
        if mcp.is_create_dialog_open():
            mcp.close_dialog()


# === TC-MCP-006: 本地模式命令校验 ===

@allure.epic("MCP服务器")
@pytest.mark.order(85)
@pytest.mark.p1
def test_command_validation(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-MCP-006: 本地模式命令校验"""
    mcp = McpServerPage(logged_in_page, base_url)
    mcp.goto()

    mcp.open_create_dialog()
    assert mcp.is_create_dialog_open(), "新建 MCP 对话框未弹出"

    mcp.select_type("Stdio")

    # 填写名称但不填命令
    dialog = logged_in_page.locator("[role='dialog']")
    name_input = dialog.locator("input[name='name']").or_(dialog.locator("input").first)
    name_input.first.fill(f"cmd-test-{int(time.time())}")

    mcp.save()
    logged_in_page.wait_for_timeout(500)

    # 命令为空应触发校验错误（对话框仍打开 + toast 错误提示）
    dialog_still_open = mcp.is_create_dialog_open()
    errors = mcp.get_validation_errors()
    assert dialog_still_open or len(errors) > 0, \
        f"空命令未触发校验反馈: dialog_still_open={dialog_still_open}, errors={errors}"

    if dialog_still_open:
        mcp.close_dialog()


# === TC-MCP-007: 启用 MCP 服务器（Stdio） ===

@allure.epic("MCP服务器")
@pytest.mark.order(86)
@pytest.mark.p0
def test_enable_server(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-MCP-007: 启用 MCP 服务器（Stdio）"""
    mcp = McpServerPage(logged_in_page, base_url)

    # 前置：创建 Stdio 测试服务器
    enable_name = f"enable-test-{int(time.time())}"
    _create_test_server(mcp, enable_name, "Stdio", "echo hello")
    assert mcp.has_server(enable_name), f"测试服务器 '{enable_name}' 创建失败"

    # 记录初始状态
    was_enabled = mcp.is_server_enabled(enable_name)

    # 切换
    mcp.toggle_enabled(enable_name)

    # 检查错误 toast
    toast_texts = []
    for _ in range(6):
        logged_in_page.wait_for_timeout(500)
        errors = mcp.get_validation_errors()
        if errors:
            toast_texts.extend(errors)
            break
    error_toasts = [t for t in toast_texts if any(kw in t for kw in ["失败", "错误", "Error", "Fail"])]
    assert not error_toasts, f"切换启用状态后出现错误: {error_toasts}"

    # 刷新验证持久化
    mcp.goto()
    now_enabled = mcp.is_server_enabled(enable_name)
    assert now_enabled != was_enabled, \
        f"切换后状态未变化: 启用={was_enabled} -> {now_enabled}"

    # 恢复原状态
    mcp.toggle_enabled(enable_name)
    logged_in_page.wait_for_timeout(800)

    # 清理
    mcp.delete_server(enable_name)


# === TC-MCP-007b: 启用 MCP 服务器（SSE） ===

@allure.epic("MCP服务器")
@pytest.mark.order(86)
@pytest.mark.p0
def test_enable_sse_server(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-MCP-007b: 启用 MCP 服务器（SSE）"""
    mcp = McpServerPage(logged_in_page, base_url)

    # 前置：创建 SSE 测试服务器
    enable_sse_name = f"enable-sse-{int(time.time())}"
    _create_test_server(mcp, enable_sse_name, "SSE", url=TEST_SSE_URL)
    assert mcp.has_server(enable_sse_name), f"测试服务器 '{enable_sse_name}' 创建失败"

    # 记录初始状态
    was_enabled = mcp.is_server_enabled(enable_sse_name)

    # 切换
    mcp.toggle_enabled(enable_sse_name)

    # 检查错误 toast
    toast_texts = []
    for _ in range(6):
        logged_in_page.wait_for_timeout(500)
        errors = mcp.get_validation_errors()
        if errors:
            toast_texts.extend(errors)
            break
    error_toasts = [t for t in toast_texts if any(kw in t for kw in ["失败", "错误", "Error", "Fail"])]
    assert not error_toasts, f"切换启用状态后出现错误: {error_toasts}"

    # 刷新验证持久化
    mcp.goto()
    now_enabled = mcp.is_server_enabled(enable_sse_name)
    assert now_enabled != was_enabled, \
        f"切换后状态未变化: 启用={was_enabled} -> {now_enabled}"

    # 恢复原状态
    mcp.toggle_enabled(enable_sse_name)
    logged_in_page.wait_for_timeout(800)

    # 清理
    mcp.delete_server(enable_sse_name)


# === TC-MCP-008: 禁用 MCP 服务器（Stdio） ===

@allure.epic("MCP服务器")
@pytest.mark.order(87)
@pytest.mark.p1
def test_disable_server(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-MCP-008: 禁用 MCP 服务器（Stdio）"""
    mcp = McpServerPage(logged_in_page, base_url)

    # 前置：创建 Stdio 测试服务器
    disable_name = f"disable-test-{int(time.time())}"
    _create_test_server(mcp, disable_name, "Stdio", "echo hello")
    assert mcp.has_server(disable_name), f"测试服务器 '{disable_name}' 创建失败"

    # 确保为启用状态
    if not mcp.is_server_enabled(disable_name):
        mcp.toggle_enabled(disable_name)
        logged_in_page.wait_for_timeout(1500)
        mcp.goto()

    assert mcp.is_server_enabled(disable_name), "预设为启用失败"

    # 禁用
    mcp.toggle_enabled(disable_name)

    # 检查错误 toast
    toast_texts = []
    for _ in range(6):
        logged_in_page.wait_for_timeout(500)
        errors = mcp.get_validation_errors()
        if errors:
            toast_texts.extend(errors)
            break
    error_toasts = [t for t in toast_texts if any(kw in t for kw in ["失败", "错误", "Error", "Fail"])]
    assert not error_toasts, f"禁用后出现错误: {error_toasts}"

    # 刷新验证持久化
    mcp.goto()
    assert not mcp.is_server_enabled(disable_name), "禁用后仍显示「禁用」按钮"

    # 清理
    mcp.delete_server(disable_name)


# === TC-MCP-008b: 禁用 MCP 服务器（SSE） ===

@allure.epic("MCP服务器")
@pytest.mark.order(87)
@pytest.mark.p1
def test_disable_sse_server(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-MCP-008b: 禁用 MCP 服务器（SSE）"""
    mcp = McpServerPage(logged_in_page, base_url)

    # 前置：创建 SSE 测试服务器
    disable_sse_name = f"disable-sse-{int(time.time())}"
    _create_test_server(mcp, disable_sse_name, "SSE", url=TEST_SSE_URL)
    assert mcp.has_server(disable_sse_name), f"测试服务器 '{disable_sse_name}' 创建失败"

    # 确保为启用状态
    if not mcp.is_server_enabled(disable_sse_name):
        mcp.toggle_enabled(disable_sse_name)
        logged_in_page.wait_for_timeout(1500)
        mcp.goto()

    assert mcp.is_server_enabled(disable_sse_name), "预设为启用失败"

    # 禁用
    mcp.toggle_enabled(disable_sse_name)

    # 检查错误 toast
    toast_texts = []
    for _ in range(6):
        logged_in_page.wait_for_timeout(500)
        errors = mcp.get_validation_errors()
        if errors:
            toast_texts.extend(errors)
            break
    error_toasts = [t for t in toast_texts if any(kw in t for kw in ["失败", "错误", "Error", "Fail"])]
    assert not error_toasts, f"禁用后出现错误: {error_toasts}"

    # 刷新验证持久化
    mcp.goto()
    assert not mcp.is_server_enabled(disable_sse_name), "禁用后仍显示「禁用」按钮"

    # 清理
    mcp.delete_server(disable_sse_name)


# === TC-MCP-009: 测试本地 MCP 服务器连接 ===

@allure.epic("MCP服务器")
@pytest.mark.order(88)
@pytest.mark.p1
def test_local_connection(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-MCP-009: 本地 MCP 服务器检测应提示不支持"""
    mcp = McpServerPage(logged_in_page, base_url)

    # 前置：创建 Local 测试服务器
    local_name = f"local-test-{int(time.time())}"
    _create_test_server(mcp, local_name, "Stdio", "echo hello")
    assert mcp.has_server(local_name), f"测试服务器 '{local_name}' 创建失败"

    # 拦截控制台错误（系统会对 local 服务器返回 400）
    console_errors = []

    def on_console(msg):
        if msg.type == "error":
            console_errors.append(msg.text)

    logged_in_page.on("console", on_console)

    # 点击「检测」按钮
    mcp.click_inspect(local_name)
    logged_in_page.wait_for_timeout(1500)

    # 验证：应提示"仅支持远程"或类似错误反馈
    # 优先检查 toast / dialog
    dialog = logged_in_page.locator("[role='dialog']")
    errors = mcp.get_validation_errors()
    body_text = logged_in_page.locator("div.agent-panel-body").inner_text()
    dialog_text = dialog.first.inner_text() if dialog.count() > 0 and dialog.first.is_visible() else ""
    combined = " ".join(errors) + " " + body_text + " " + dialog_text

    # 也检查控制台错误
    console_combined = " ".join(console_errors)

    has_error_feedback = (
        any(kw in combined for kw in ["失败", "错误", "不支持", "仅支持", "Error", "remote", "Inspect"])
        or any(kw in console_combined for kw in ["Inspect only supports remote", "失败", "Error"])
    )
    assert has_error_feedback, (
        f"本地服务器检测未提示不支持错误（页面片段: {combined[:80]}，控制台: {console_combined[:80]}）"
    )

    # 关闭可能的 dialog
    if dialog.count() > 0 and dialog.first.is_visible():
        close_btn = loc.close_button(dialog)
        if close_btn.count() > 0:
            close_btn.first.click()

    # 清理
    mcp.delete_server(local_name)


# === TC-MCP-010: 测试远程 MCP 服务器 URL ===

@allure.epic("MCP服务器")
@pytest.mark.order(89)
@pytest.mark.p1
def test_remote_url(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-MCP-010: 测试远程 MCP 服务器 URL"""
    mcp = McpServerPage(logged_in_page, base_url)

    # 前置：创建远程测试服务器
    remote_name = f"remote-test-{int(time.time())}"
    _create_test_server(mcp, remote_name, "SSE", url=TEST_SSE_URL)
    assert mcp.has_server(remote_name), f"测试服务器 '{remote_name}' 创建失败"

    # 拦截 toast 通知和控制台错误
    console_errors = []
    toast_texts = []

    def on_console(msg):
        if msg.type == "error":
            console_errors.append(msg.text)

    logged_in_page.on("console", on_console)

    # 点击「检测」按钮
    mcp.click_inspect(remote_name)

    # 快速轮询抓取 toast（toast 自动消失，需要尽快捕获）
    for _ in range(10):
        logged_in_page.wait_for_timeout(500)
        errors = mcp.get_validation_errors()
        if errors:
            toast_texts.extend(errors)
            break

    logged_in_page.wait_for_load_state("networkidle", timeout=10000)

    # 验证有反馈
    dialog = logged_in_page.locator("[role='dialog']")
    body_text = logged_in_page.locator("div.agent-panel-body").inner_text()
    dialog_text = dialog.first.inner_text() if dialog.count() > 0 and dialog.first.is_visible() else ""
    combined = " ".join(toast_texts) + " " + body_text + " " + dialog_text
    console_combined = " ".join(console_errors)

    has_feedback = any(kw in combined for kw in ["成功", "失败", "错误", "超时", "Success", "Error", "Timeout", "工具", "tool", "SSE", "Unable"])
    has_console_feedback = any(kw in console_combined for kw in ["SSE error", "Unable to connect", "Error", "error", "失败"])
    assert has_feedback or has_console_feedback, (
        f"测试远程 URL 后无任何反馈: has_feedback={has_feedback}, has_console_feedback={has_console_feedback}"
        f"（页面片段: {combined[:80]}，控制台: {console_combined[:80]}）"
    )

    # 关闭可能的 dialog
    if dialog.count() > 0 and dialog.first.is_visible():
        close_btn = loc.close_button(dialog)
        if close_btn.count() > 0:
            close_btn.first.click()

    # 清理
    mcp.delete_server(remote_name)


# === TC-MCP-011: 查看 MCP 工具列表 ===

@allure.epic("MCP服务器")
@pytest.mark.order(90)
@pytest.mark.p2
def test_view_tools(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-MCP-011: 查看 MCP 工具列表（使用已有服务器 langtesttest）"""
    mcp = McpServerPage(logged_in_page, base_url)
    mcp.goto()

    target = "langtesttest"
    if not mcp.has_server(target):
        pytest.skip(f"已有 MCP 服务器 '{target}' 不存在")

    # 拦截工具列表相关 API
    tools_data = []

    def on_tools_resp(r):
        url_lower = r.url.lower()
        if ("tool" in url_lower or "inspect" in url_lower) and "mcp" in url_lower and ".js" not in url_lower:
            try:
                body = r.json()
                tools_data.append(body)
            except Exception:
                pass

    logged_in_page.on("response", on_tools_resp)

    # 点击「检测」按钮
    mcp.click_inspect(target)

    # 快速轮询抓取 toast（toast 自动消失）
    toast_texts = []
    for _ in range(10):
        logged_in_page.wait_for_timeout(500)
        errors = mcp.get_validation_errors()
        if errors:
            toast_texts.extend(errors)
            break

    logged_in_page.wait_for_load_state("networkidle", timeout=10000)

    # 验证有工具相关信息
    dialog = logged_in_page.locator("[role='dialog']")
    body_text = logged_in_page.locator("div.agent-panel-body").inner_text()
    dialog_text = dialog.first.inner_text() if dialog.count() > 0 and dialog.first.is_visible() else ""
    combined = " ".join(toast_texts) + " " + body_text + " " + dialog_text

    has_tools_info = (
        ("成功" in combined and "工具" in combined)
        or "tool" in combined.lower()
    )

    # 也检查 API 返回
    api_tools_count = 0
    if tools_data:
        for data in tools_data:
            tools = data.get("tools") or data.get("data", {}).get("tools") or data.get("items")
            if tools and isinstance(tools, list) and len(tools) > 0:
                has_tools_info = True
                api_tools_count = len(tools)
                break

    assert has_tools_info, (
        f"检测后无工具相关信息（toast: {toast_texts}，API 响应数: {len(tools_data)}，"
        f"页面片段: {combined[:80]}）"
    )

    # 额外校验：toast 应包含连接成功 + 工具数量
    toast_combined = " ".join(toast_texts)
    if toast_combined:
        assert "成功" in toast_combined, f"toast 未包含成功提示: {toast_combined[:80]}"

    # 关闭可能的 dialog
    if dialog.count() > 0 and dialog.first.is_visible():
        close_btn = loc.close_button(dialog)
        if close_btn.count() > 0:
            close_btn.first.click()


# === TC-MCP-012: 检查 MCP 服务器状态 ===

@allure.epic("MCP服务器")
@pytest.mark.order(91)
@pytest.mark.p2
def test_inspect_server(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-MCP-012: 检查 MCP 服务器状态（使用已有服务器 langtesttest）"""
    mcp = McpServerPage(logged_in_page, base_url)
    mcp.goto()

    target = "langtesttest"
    if not mcp.has_server(target):
        pytest.skip(f"已有 MCP 服务器 '{target}' 不存在")

    # 点击「检测」按钮
    mcp.click_inspect(target)

    # 快速轮询抓取 toast
    toast_texts = []
    for _ in range(10):
        logged_in_page.wait_for_timeout(500)
        errors = mcp.get_validation_errors()
        if errors:
            toast_texts.extend(errors)
            break

    logged_in_page.wait_for_load_state("networkidle", timeout=10000)

    # 验证有状态信息
    dialog = logged_in_page.locator("[role='dialog']")
    body_text = logged_in_page.locator("div.agent-panel-body").inner_text()
    dialog_text = dialog.first.inner_text() if dialog.count() > 0 and dialog.first.is_visible() else ""
    combined = " ".join(toast_texts) + " " + body_text + " " + dialog_text
    has_status = any(kw in combined for kw in [
        "状态", "版本", "能力", "运行", "成功", "连接", "Status", "Version", "server",
    ])
    assert has_status, (
        f"检测后无状态信息（toast: {toast_texts}，"
        f"内容片段: {combined[:80]}）"
    )

    # 关闭可能的 dialog
    if dialog.count() > 0 and dialog.first.is_visible():
        close_btn = loc.close_button(dialog)
        if close_btn.count() > 0:
            close_btn.first.click()


# === TC-MCP-013: 删除 MCP 服务器 ===

@allure.epic("MCP服务器")
@pytest.mark.order(92)
@pytest.mark.p1
def test_delete_server(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-MCP-013: 删除 MCP 服务器"""
    mcp = McpServerPage(logged_in_page, base_url)

    # 前置：创建测试服务器
    del_name = f"del-test-{int(time.time())}"
    _create_test_server(mcp, del_name, "Stdio", "echo hello")
    assert mcp.has_server(del_name), f"测试服务器 '{del_name}' 创建失败"

    # 记录当前数量
    initial = mcp.get_server_count()

    # 执行删除
    mcp.delete_server(del_name)
    mcp.goto()

    # 验证
    assert not mcp.has_server(del_name), f"删除后 '{del_name}' 仍在列表中"
    assert mcp.get_server_count() < initial, "删除后数量未减少"


# === TC-MCP-013b: 删除远程 SSE MCP 服务器 ===

@allure.epic("MCP服务器")
@pytest.mark.order(92)
@pytest.mark.p1
def test_delete_sse_server(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-MCP-013b: 删除远程 SSE MCP 服务器"""
    mcp = McpServerPage(logged_in_page, base_url)

    # 前置：创建远程 SSE 测试服务器
    del_sse_name = f"del-sse-{int(time.time())}"
    _create_test_server(mcp, del_sse_name, "SSE", url=TEST_SSE_URL)
    assert mcp.has_server(del_sse_name), f"测试服务器 '{del_sse_name}' 创建失败"

    # 记录当前数量
    initial = mcp.get_server_count()

    # 执行删除
    mcp.delete_server(del_sse_name)
    mcp.goto()

    # 验证
    assert not mcp.has_server(del_sse_name), f"删除后 '{del_sse_name}' 仍在列表中"
    assert mcp.get_server_count() < initial, "删除后数量未减少"


# === TC-MCP-014: 公开的 MCP 可读不可改 ===

@allure.epic("MCP服务器")
@pytest.mark.order(93)
@pytest.mark.p0
def test_public_mcp_readonly(logged_in_page, base_url):
    """⏭️ 跳过（需多账号） | TC-MCP-014: 公开的 MCP 可读不可改"""
    mcp = McpServerPage(logged_in_page, base_url)
    mcp.goto()

    # 查找有公开开关的服务器
    public_switches = logged_in_page.locator("button[role='switch'][aria-label='公开']")
    if public_switches.count() == 0:
        pytest.skip("当前页面没有公开开关")

    # 验证列表可见
    count = mcp.get_server_count()
    assert count > 0, "MCP 列表为空"

    # 跨用户验证编辑/删除按钮禁用需要多账号
    # TODO: 多账号环境下补充跨用户权限验证


# === TC-MCP-015: MCP 公开按钮 ===

@allure.epic("MCP服务器")
@pytest.mark.order(93)
@pytest.mark.p1
def test_mcp_make_public(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-MCP-015: MCP 公开按钮"""
    mcp = McpServerPage(logged_in_page, base_url)

    # 前置：创建测试服务器
    pub_name = f"pub-test-{int(time.time())}"
    _create_test_server(mcp, pub_name, "Stdio", "echo hello")
    assert mcp.has_server(pub_name), f"测试服务器 '{pub_name}' 创建失败"

    # 获取该服务器的公开开关
    pub_switch = mcp.get_public_switch(pub_name)
    if pub_switch.count() == 0:
        mcp.delete_server(pub_name)
        pytest.skip("该服务器没有公开开关")

    # 记录当前状态
    was_public = pub_switch.first.get_attribute("aria-checked") == "true"

    # 切换
    pub_switch.first.click()

    # 快速轮询抓取 toast（检查是否有错误）
    toast_texts = []
    for _ in range(6):
        logged_in_page.wait_for_timeout(500)
        errors = mcp.get_validation_errors()
        if errors:
            toast_texts.extend(errors)
            break

    # 不应有错误 toast
    error_toasts = [t for t in toast_texts if any(kw in t for kw in ["失败", "错误", "Error", "Fail"])]
    assert not error_toasts, f"切换公开开关后出现错误: {error_toasts}"

    # 验证前端状态变化
    now_public = pub_switch.first.get_attribute("aria-checked") == "true"
    assert now_public != was_public, \
        f"公开开关切换无效: {was_public} -> {now_public}"

    # 刷新页面验证持久化
    mcp.goto()
    assert mcp.has_server(pub_name), "刷新后服务器消失"
    refreshed_switch = mcp.get_public_switch(pub_name)
    if refreshed_switch.count() > 0:
        persisted = refreshed_switch.first.get_attribute("aria-checked") == "true"
        assert persisted == now_public, \
            f"公开状态未持久化: 切换后={now_public}, 刷新后={persisted}"

    # 切回原状态
    if refreshed_switch.count() > 0:
        refreshed_switch.first.click()
        logged_in_page.wait_for_timeout(800)

    # 清理
    mcp.delete_server(pub_name)


# === TC-MCP-015b: SSE MCP 公开按钮 ===

@allure.epic("MCP服务器")
@pytest.mark.order(93)
@pytest.mark.p1
def test_sse_mcp_make_public(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-MCP-015b: SSE MCP 公开按钮"""
    mcp = McpServerPage(logged_in_page, base_url)

    # 前置：创建远程 SSE 测试服务器
    pub_sse_name = f"pub-sse-{int(time.time())}"
    _create_test_server(mcp, pub_sse_name, "SSE", url=TEST_SSE_URL)
    assert mcp.has_server(pub_sse_name), f"测试服务器 '{pub_sse_name}' 创建失败"

    # 获取该服务器的公开开关
    pub_switch = mcp.get_public_switch(pub_sse_name)
    if pub_switch.count() == 0:
        mcp.delete_server(pub_sse_name)
        pytest.skip("该服务器没有公开开关")

    # 记录当前状态
    was_public = pub_switch.first.get_attribute("aria-checked") == "true"

    # 切换
    pub_switch.first.click()

    # 快速轮询抓取 toast（检查是否有错误）
    toast_texts = []
    for _ in range(6):
        logged_in_page.wait_for_timeout(500)
        errors = mcp.get_validation_errors()
        if errors:
            toast_texts.extend(errors)
            break

    # 不应有错误 toast
    error_toasts = [t for t in toast_texts if any(kw in t for kw in ["失败", "错误", "Error", "Fail"])]
    assert not error_toasts, f"切换公开开关后出现错误: {error_toasts}"

    # 验证前端状态变化
    now_public = pub_switch.first.get_attribute("aria-checked") == "true"
    assert now_public != was_public, \
        f"公开开关切换无效: {was_public} -> {now_public}"

    # 刷新页面验证持久化
    mcp.goto()
    assert mcp.has_server(pub_sse_name), "刷新后服务器消失"
    refreshed_switch = mcp.get_public_switch(pub_sse_name)
    if refreshed_switch.count() > 0:
        persisted = refreshed_switch.first.get_attribute("aria-checked") == "true"
        assert persisted == now_public, \
            f"公开状态未持久化: 切换后={now_public}, 刷新后={persisted}"

    # 切回原状态
    if refreshed_switch.count() > 0:
        refreshed_switch.first.click()
        logged_in_page.wait_for_timeout(800)

    # 清理
    mcp.delete_server(pub_sse_name)


# === TC-MCP-016: MCP CRUD API 验证 ===

@allure.epic("MCP服务器")
@pytest.mark.order(94)
@pytest.mark.p1
def test_mcp_api_crud(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-MCP-016: MCP CRUD API 验证（拦截内部 API /web/config/mcp）"""
    mcp = McpServerPage(logged_in_page, base_url)
    mcp.goto()

    crud_name = f"api-crud-{int(time.time())}"
    api_responses = mcp.setup_api_interceptor("/web/config/mcp")

    # 1. CREATE
    mcp.open_create_dialog()
    assert mcp.is_create_dialog_open(), "创建对话框未弹出"
    mcp.select_type("Stdio")
    mcp.fill_create_form(name=crud_name, command="echo hello")
    mcp.save()
    logged_in_page.wait_for_timeout(800)

    create_resps = [r for r in api_responses if r["method"] in ("POST", "PUT") and r["status"] < 400]
    assert len(create_resps) > 0, f"未拦截到 Create API 响应（共 {len(api_responses)} 条）"
    assert create_resps[-1]["status"] < 400, f"Create API 异常: {create_resps[-1]['status']}"

    # 2. READ
    mcp.goto()
    assert mcp.has_server(crud_name), f"CRUD 创建后 '{crud_name}' 未在列表中"

    read_resps = [r for r in api_responses if r["method"] == "GET" and r["status"] < 400]
    assert len(read_resps) > 0, "未拦截到 Read API 响应"

    # 3. DELETE
    mcp.delete_server(crud_name)
    mcp.goto()
    assert not mcp.has_server(crud_name), f"CRUD 删除后 '{crud_name}' 仍在列表中"

    del_resps = [r for r in api_responses if r["method"] == "DELETE" and r["status"] < 400]
    assert len(del_resps) > 0, "未拦截到 Delete API 响应"
    assert del_resps[-1]["status"] < 400, f"Delete API 异常: {del_resps[-1]['status']}"


# === TC-MCP-017: MCP 参数校验 ===

@allure.epic("MCP服务器")
@pytest.mark.order(95)
@pytest.mark.p1
def test_mcp_api_validation(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-MCP-017: MCP 参数校验（含 toast 检查）"""
    mcp = McpServerPage(logged_in_page, base_url)
    mcp.goto()

    # 1. 非法名称格式
    mcp.open_create_dialog()
    dialog = logged_in_page.locator("[role='dialog']")
    name_input = dialog.locator("input[name='name']").or_(dialog.locator("input").first)
    name_input.first.fill("INVALID_NAME!!")
    mcp.save()

    # 快速轮询抓取 toast
    toast1 = []
    for _ in range(6):
        logged_in_page.wait_for_timeout(500)
        errors = mcp.get_validation_errors()
        if errors:
            toast1.extend(errors)
            break

    dialog_still_open = mcp.is_create_dialog_open()
    assert dialog_still_open or len(toast1) > 0, \
        f"非法名称未触发校验: dialog_still_open={dialog_still_open}, toast1={toast1}"
    if dialog_still_open:
        mcp.close_dialog()
    logged_in_page.wait_for_timeout(300)

    # 2. 缺少必填字段
    mcp.open_create_dialog()
    mcp.save()

    toast2 = []
    for _ in range(6):
        logged_in_page.wait_for_timeout(500)
        errors = mcp.get_validation_errors()
        if errors:
            toast2.extend(errors)
            break

    dialog_still_open = mcp.is_create_dialog_open()
    assert dialog_still_open or len(toast2) > 0, \
        f"缺必填字段未触发校验: dialog_still_open={dialog_still_open}, toast2={toast2}"
    if dialog_still_open:
        mcp.close_dialog()
    logged_in_page.wait_for_timeout(300)

    # 3. 无效 URL（SSE 模式）
    mcp.open_create_dialog()
    mcp.select_type("SSE")
    mcp.fill_create_form(name=f"val-test-{int(time.time())}", url="not-a-valid-url")
    mcp.save()

    toast3 = []
    for _ in range(6):
        logged_in_page.wait_for_timeout(500)
        errors = mcp.get_validation_errors()
        if errors:
            toast3.extend(errors)
            break

    dialog_still_open = mcp.is_create_dialog_open()
    assert dialog_still_open or len(toast3) > 0, \
        f"无效 URL 未触发校验: dialog_still_open={dialog_still_open}, toast3={toast3}"
    if dialog_still_open:
        mcp.close_dialog()


# === TC-MCP-018: MCP 认证和权限 ===

@allure.epic("MCP服务器")
@pytest.mark.order(95)
@pytest.mark.p0
def test_mcp_api_auth(logged_in_page, base_url, browser_instance):
    """✅ 人工评审通过 | TC-MCP-018: MCP 认证和权限 — 已认证可访问，未认证被拒绝"""
    mcp = McpServerPage(logged_in_page, base_url)
    mcp.goto()

    # 1. 已认证：拦截内部 MCP API，验证返回 200
    api_responses = mcp.setup_api_interceptor("/web/config/mcp")
    logged_in_page.reload()
    logged_in_page.wait_for_load_state("networkidle")

    list_resps = [r for r in api_responses if r["method"] == "GET" and r["status"] < 400]
    assert len(list_resps) > 0, "已认证用户未能获取 MCP 列表 API 响应"
    assert list_resps[0]["status"] == 200, \
        f"已认证请求返回非 200: {list_resps[0]['status']}"

    # 2. 未认证：新建无 cookie 的 context，请求同一 API 应返回 401/403
    unauth_ctx = browser_instance.new_context()
    unauth_page = unauth_ctx.new_page()
    unauth_responses = []

    def on_unauth_resp(r):
        if "/web/config/mcp" in r.url and ".js" not in r.url and ".css" not in r.url:
            unauth_responses.append({"status": r.status, "url": r.url})

    unauth_page.on("response", on_unauth_resp)
    try:
        unauth_page.goto(f"{base_url}/ctrl/agent/mcp")
        unauth_page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass  # 可能被重定向到登录页

    # 验证：未认证请求要么被重定向到登录页，要么 API 返回 401/403
    is_redirected = "/login" in unauth_page.url
    api_blocked = any(r["status"] in (401, 403) for r in unauth_responses)
    assert is_redirected or api_blocked, (
        f"未认证请求未被拒绝: is_redirected={is_redirected}, api_blocked={api_blocked}, "
        f"URL={unauth_page.url}, API 响应={unauth_responses[:3]}"
    )

    unauth_page.close()
    unauth_ctx.close()


# === TC-MCP-019: 获取 MCP 工具列表 API 验证 ===

@allure.epic("MCP服务器")
@pytest.mark.order(96)
@pytest.mark.p2
def test_mcp_api_tools(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-MCP-019: 获取 MCP 工具列表 API 验证（使用 langtesttest）"""
    mcp = McpServerPage(logged_in_page, base_url)
    mcp.goto()

    target = "langtesttest"
    if not mcp.has_server(target):
        pytest.skip(f"已有 MCP 服务器 '{target}' 不存在")

    # 拦截 inspect API（内部 API 路径）
    tools_data = []

    def on_tools_resp(r):
        if "mcp/actions/inspect" in r.url and ".js" not in r.url:
            try:
                body = r.json()
                tools_data.append(body)
            except Exception:
                pass

    logged_in_page.on("response", on_tools_resp)

    # 点击「检测」按钮
    mcp.click_inspect(target)

    # 快速轮询抓取 toast
    toast_texts = []
    for _ in range(10):
        logged_in_page.wait_for_timeout(500)
        errors = mcp.get_validation_errors()
        if errors:
            toast_texts.extend(errors)
            break

    logged_in_page.wait_for_load_state("networkidle", timeout=10000)

    # 验证工具数据
    toast_combined = " ".join(toast_texts)
    if tools_data:
        data = tools_data[0]
        tools = data.get("tools") or data.get("data", {}).get("tools") or data.get("items")
        if tools and isinstance(tools, list) and len(tools) > 0:
            first_tool = tools[0]
            assert "name" in first_tool, f"工具缺少 name 字段: {list(first_tool.keys())}"
        else:
            # API 返回了但没有 tools 字段，用 toast 验证
            assert "工具" in toast_combined or "tool" in toast_combined.lower(), (
                f"API 返回无 tools 且 toast 无工具信息: {toast_combined[:80]}"
            )
    else:
        # 未拦截到 API，验证 toast 反馈
        assert "工具" in toast_combined or "成功" in toast_combined, (
            f"未拦截到 inspect API 且 toast 无反馈: {toast_combined[:80]}"
        )

    # 关闭 dialog
    dialog = logged_in_page.locator("[role='dialog']")
    if dialog.count() > 0 and dialog.first.is_visible():
        close_btn = loc.close_button(dialog)
        if close_btn.count() > 0:
            close_btn.first.click()


# === TC-MCP-020: 启用/禁用 MCP API 验证 ===

@allure.epic("MCP服务器")
@pytest.mark.order(97)
@pytest.mark.p1
def test_mcp_api_toggle(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-MCP-020: 启用/禁用 MCP API 验证"""
    mcp = McpServerPage(logged_in_page, base_url)

    # 前置：创建测试服务器
    toggle_name = f"toggle-test-{int(time.time())}"
    _create_test_server(mcp, toggle_name, "Stdio", "echo hello")
    assert mcp.has_server(toggle_name), f"测试服务器 '{toggle_name}' 创建失败"

    # 拦截内部 API
    toggle_resp = mcp.setup_api_interceptor("/web/config/mcp")

    initial_state = mcp.is_server_enabled(toggle_name)
    mcp.toggle_enabled(toggle_name)

    # 抓 toast
    toast_texts = []
    for _ in range(6):
        logged_in_page.wait_for_timeout(500)
        errors = mcp.get_validation_errors()
        if errors:
            toast_texts.extend(errors)
            break
    error_toasts = [t for t in toast_texts if any(kw in t for kw in ["失败", "错误", "Error", "Fail"])]
    assert not error_toasts, f"切换启用状态后出现错误: {error_toasts}"

    # 刷新验证持久化
    mcp.goto()
    new_state = mcp.is_server_enabled(toggle_name)
    assert new_state != initial_state, \
        f"启用/禁用切换无效: {initial_state} -> {new_state}"

    # 验证 API 有成功响应
    patch_resps = [r for r in toggle_resp if r["method"] in ("PATCH", "PUT", "POST") and r["status"] < 400]
    assert len(patch_resps) > 0, "未拦截到成功的切换 API 响应"

    # 恢复 + 清理
    mcp.toggle_enabled(toggle_name)
    logged_in_page.wait_for_timeout(800)
    mcp.delete_server(toggle_name)
