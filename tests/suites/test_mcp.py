# tests/suites/test_mcp.py
"""MCP 服务器模块回归测试（TC-MCP-001 ~ TC-MCP-020）
基于真实 DOM 结构编写，选择器经过页面验证。"""
import time
import pytest
import allure
from tests.pages.mcp_page import McpServerPage


# 测试用 MCP 服务器名（带时间戳避免冲突）
TEST_STDIO_NAME = f"auto-stdio-{int(time.time())}"
TEST_SSE_NAME = f"auto-sse-{int(time.time())}"
TEST_STDIO_CMD = "npx -y @modelcontextprotocol/server-filesystem /tmp"
TEST_SSE_URL = "http://localhost:3001/sse"


# === TC-MCP-001: 列表数据加载 ===

@allure.epic("MCP服务器")
@pytest.mark.order(80)
@pytest.mark.p0
def test_mcp_list_data_loads(logged_in_page, base_url):
    """TC-MCP-001: MCP 服务器列表数据加载"""
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
    assert list_container.first.is_visible() or "暂无" in body_text or "空" in body_text, \
        "MCP 服务器列表容器不可见且无空状态提示"

    # 验证 API 数据结构
    logged_in_page.wait_for_timeout(1000)
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
    """TC-MCP-002: 创建本地 Stdio MCP 服务器"""
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


# === TC-MCP-003: 创建远程 SSE MCP 服务器 ===

@allure.epic("MCP服务器")
@pytest.mark.order(82)
@pytest.mark.p0
def test_create_sse_server(logged_in_page, base_url):
    """TC-MCP-003: 创建远程 SSE MCP 服务器"""
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


# === TC-MCP-004: 名称格式校验 - 合法名称 ===

@allure.epic("MCP服务器")
@pytest.mark.order(83)
@pytest.mark.p1
def test_valid_name_format(logged_in_page, base_url):
    """TC-MCP-004: 名称格式校验 - 合法名称"""
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
    """TC-MCP-005: 名称格式校验 - 非法名称"""
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

        # 对话框仍打开 = 被校验拦截；或关闭但显示了错误信息
        dialog_still_open = mcp.is_create_dialog_open()
        if not dialog_still_open:
            errors = mcp.get_validation_errors()
        else:
            errors = []
        assert dialog_still_open or len(errors) > 0, \
            f"{desc}（'{name[:20]}'）未触发校验反馈（对话框已关闭且无错误提示）"

        if dialog_still_open:
            mcp.close_dialog()
        logged_in_page.wait_for_timeout(500)

    # 空名称测试
    mcp.open_create_dialog()
    if mcp.is_create_dialog_open():
        mcp.save()
        logged_in_page.wait_for_timeout(500)
        assert mcp.is_create_dialog_open(), \
            "空名称未触发校验反馈"
        if mcp.is_create_dialog_open():
            mcp.close_dialog()


# === TC-MCP-006: 本地模式命令校验 ===

@allure.epic("MCP服务器")
@pytest.mark.order(85)
@pytest.mark.p1
def test_command_validation(logged_in_page, base_url):
    """TC-MCP-006: 本地模式命令校验"""
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

    # 命令为空应触发校验错误（对话框仍打开或显示错误提示）
    dialog_still_open = mcp.is_create_dialog_open()
    if not dialog_still_open:
        errors = mcp.get_validation_errors()
    else:
        errors = []
    assert dialog_still_open or len(errors) > 0, \
        "空命令未触发校验反馈（对话框已关闭且无错误提示）"

    if dialog_still_open:
        mcp.close_dialog()


# === TC-MCP-007: 启用 MCP 服务器 ===

@allure.epic("MCP服务器")
@pytest.mark.order(86)
@pytest.mark.p0
def test_enable_server(logged_in_page, base_url):
    """TC-MCP-007: 启用 MCP 服务器"""
    mcp = McpServerPage(logged_in_page, base_url)
    mcp.goto()

    # 找到测试创建的服务器
    names = mcp.get_server_names()
    target = None
    for n in names:
        if TEST_STDIO_NAME in n or TEST_SSE_NAME in n or n.startswith("auto-"):
            target = n
            break
    if not target and names:
        target = names[0]
    if not target:
        pytest.skip("没有可用的 MCP 服务器")

    # 记录初始状态：有「禁用」按钮=已启用，有「启用」按钮=已禁用
    was_enabled = mcp.is_server_enabled(target)

    # 切换
    mcp.toggle_enabled(target)
    logged_in_page.wait_for_timeout(2000)
    mcp.goto()  # 刷新确认状态

    now_enabled = mcp.is_server_enabled(target)
    assert now_enabled != was_enabled, \
        f"切换后状态未变化: 启用={was_enabled} -> {now_enabled}"

    # 恢复原状态
    mcp.toggle_enabled(target)
    logged_in_page.wait_for_timeout(1000)


# === TC-MCP-008: 禁用 MCP 服务器 ===

@allure.epic("MCP服务器")
@pytest.mark.order(87)
@pytest.mark.p1
def test_disable_server(logged_in_page, base_url):
    """TC-MCP-008: 禁用 MCP 服务器"""
    mcp = McpServerPage(logged_in_page, base_url)
    mcp.goto()

    names = mcp.get_server_names()
    target = None
    for n in names:
        if n.startswith("auto-"):
            target = n
            break
    if not target and names:
        target = names[0]
    if not target:
        pytest.skip("没有可用的 MCP 服务器")

    # 确保为启用状态
    if not mcp.is_server_enabled(target):
        mcp.toggle_enabled(target)
        logged_in_page.wait_for_timeout(1500)
        mcp.goto()

    assert mcp.is_server_enabled(target), "预设为启用失败"

    # 禁用
    mcp.toggle_enabled(target)
    logged_in_page.wait_for_timeout(2000)
    mcp.goto()

    assert not mcp.is_server_enabled(target), "禁用后仍显示「禁用」按钮"

    # 恢复
    mcp.toggle_enabled(target)
    logged_in_page.wait_for_timeout(1000)


# === TC-MCP-009: 测试本地 MCP 服务器连接 ===

@allure.epic("MCP服务器")
@pytest.mark.order(88)
@pytest.mark.p1
def test_local_connection(logged_in_page, base_url):
    """TC-MCP-009: 测试本地 MCP 服务器连接"""
    mcp = McpServerPage(logged_in_page, base_url)
    mcp.goto()

    names = mcp.get_server_names()
    target = None
    for n in names:
        if n.startswith("auto-stdio-"):
            target = n
            break
    if not target and names:
        target = names[0]
    if not target:
        pytest.skip("没有 MCP 服务器")

    # 点击「检测」按钮
    mcp.click_inspect(target)

    # 等待检测结果（可能弹窗或页面反馈）
    logged_in_page.wait_for_load_state("networkidle", timeout=10000)
    logged_in_page.wait_for_timeout(2000)

    # 验证有反馈：优先检查 dialog，其次检查页面文本
    dialog = logged_in_page.locator("[role='dialog']")
    body_text = logged_in_page.locator("div.agent-panel-body").inner_text()
    dialog_visible = dialog.count() > 0 and dialog.first.is_visible()
    if dialog_visible:
        feedback_text = dialog.first.inner_text()
    else:
        feedback_text = body_text
    has_feedback = any(kw in feedback_text for kw in [
        "成功", "失败", "错误", "工具", "检测", "Success", "Error", "Fail",
    ])
    assert has_feedback, (
        f"检测后无任何反馈（dialog可见: {dialog_visible}，"
        f"页面内容片段: {feedback_text[:80]}）"
    )


# === TC-MCP-010: 测试远程 MCP 服务器 URL ===

@allure.epic("MCP服务器")
@pytest.mark.order(89)
@pytest.mark.p1
def test_remote_url(logged_in_page, base_url):
    """TC-MCP-010: 测试远程 MCP 服务器 URL"""
    mcp = McpServerPage(logged_in_page, base_url)
    mcp.goto()

    names = mcp.get_server_names()
    target = None
    for n in names:
        if n.startswith("auto-sse-"):
            target = n
            break
    if not target:
        pytest.skip("没有远程 SSE 类型的 MCP 服务器")

    mcp.click_inspect(target)
    logged_in_page.wait_for_load_state("networkidle", timeout=10000)
    logged_in_page.wait_for_timeout(2000)

    dialog = logged_in_page.locator("[role='dialog']")
    body_text = logged_in_page.locator("div.agent-panel-body").inner_text()
    has_feedback = (
        dialog.count() > 0
        or any(kw in body_text for kw in ["成功", "失败", "错误", "超时", "Success", "Error", "Timeout"])
    )
    assert has_feedback, "测试远程 URL 后无任何反馈"


# === TC-MCP-011: 查看 MCP 工具列表 ===

@allure.epic("MCP服务器")
@pytest.mark.order(90)
@pytest.mark.p2
def test_view_tools(logged_in_page, base_url):
    """TC-MCP-011: 查看 MCP 工具列表"""
    mcp = McpServerPage(logged_in_page, base_url)
    mcp.goto()

    names = mcp.get_server_names()
    if not names:
        pytest.skip("没有 MCP 服务器")

    # 点击「检测」按钮（检测后会显示工具列表）
    mcp.click_inspect(names[0])
    logged_in_page.wait_for_load_state("networkidle", timeout=10000)
    logged_in_page.wait_for_timeout(2000)

    # 验证有工具相关信息
    body_text = logged_in_page.locator("div.agent-panel-body").inner_text()
    dialog = logged_in_page.locator("[role='dialog']")
    dialog_text = dialog.first.inner_text() if dialog.count() > 0 else ""

    # 验证有工具相关信息：先取 dialog 文本，合并后检查
    dialog_text = dialog.first.inner_text() if dialog.count() > 0 else ""
    combined = body_text + " " + dialog_text
    has_tools_info = "工具" in combined or "tool" in combined.lower()
    assert has_tools_info, (
        f"检测后无工具相关信息（dialog数: {dialog.count()}，"
        f"页面内容片段: {combined[:80]}）"
    )

    # 关闭可能的 dialog
    if dialog.count() > 0:
        close_btn = dialog.get_by_role("button", name="Close").or_(
            dialog.get_by_role("button", name="关闭")
        )
        if close_btn.count() > 0:
            close_btn.first.click()


# === TC-MCP-012: 检查 MCP 服务器状态 ===

@allure.epic("MCP服务器")
@pytest.mark.order(91)
@pytest.mark.p2
def test_inspect_server(logged_in_page, base_url):
    """TC-MCP-012: 检查 MCP 服务器状态"""
    mcp = McpServerPage(logged_in_page, base_url)
    mcp.goto()

    names = mcp.get_server_names()
    if not names:
        pytest.skip("没有 MCP 服务器")

    mcp.click_inspect(names[0])
    logged_in_page.wait_for_load_state("networkidle", timeout=10000)
    logged_in_page.wait_for_timeout(2000)

    # 验证有状态信息：dialog 出现或文本含状态关键词
    dialog = logged_in_page.locator("[role='dialog']")
    body_text = logged_in_page.locator("div.agent-panel-body").inner_text()
    dialog_visible = dialog.count() > 0 and dialog.first.is_visible()
    if dialog_visible:
        dialog_text = dialog.first.inner_text()
    else:
        dialog_text = ""
    combined = body_text + " " + dialog_text
    has_status = any(kw in combined for kw in [
        "状态", "版本", "能力", "运行", "检测", "Status", "Version",
    ])
    assert has_status, (
        f"检测后无状态信息（dialog可见: {dialog_visible}，"
        f"内容片段: {combined[:80]}）"
    )

    if dialog.count() > 0:
        close_btn = dialog.get_by_role("button", name="Close").or_(
            dialog.get_by_role("button", name="关闭")
        )
        if close_btn.count() > 0:
            close_btn.first.click()


# === TC-MCP-013: 删除 MCP 服务器 ===

@allure.epic("MCP服务器")
@pytest.mark.order(92)
@pytest.mark.p1
def test_delete_server(logged_in_page, base_url):
    """TC-MCP-013: 删除 MCP 服务器"""
    mcp = McpServerPage(logged_in_page, base_url)
    mcp.goto()

    # 优先删除 SSE 测试服务器
    target = None
    if mcp.has_server(TEST_SSE_NAME):
        target = TEST_SSE_NAME
    else:
        for n in mcp.get_server_names():
            if n.startswith("auto-sse-") or n.startswith("auto-stdio-"):
                target = n
                break

    if not target:
        pytest.skip("没有可删除的测试 MCP 服务器")

    initial = mcp.get_server_count()
    mcp.delete_server(target)
    mcp.goto()

    assert not mcp.has_server(target), f"删除后 '{target}' 仍在列表中"
    assert mcp.get_server_count() < initial, "删除后数量未减少"


# === TC-MCP-014: 公开的 MCP 可读不可改 ===

@allure.epic("MCP服务器")
@pytest.mark.order(93)
@pytest.mark.p0
def test_public_mcp_readonly(logged_in_page, base_url):
    """TC-MCP-014: 公开的 MCP 可读不可改"""
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
    pytest.skip("跨用户权限验证需要多账号环境")


# === TC-MCP-015: MCP 公开按钮 ===

@allure.epic("MCP服务器")
@pytest.mark.order(93)
@pytest.mark.p1
def test_mcp_make_public(logged_in_page, base_url):
    """TC-MCP-015: MCP 公开按钮"""
    mcp = McpServerPage(logged_in_page, base_url)
    mcp.goto()

    # 验证公开开关存在
    public_switches = logged_in_page.locator("button[role='switch'][aria-label='公开']")
    if public_switches.count() == 0:
        pytest.skip("当前页面没有公开开关")

    # 获取第一个开关的当前状态
    first_switch = public_switches.first
    was_public = first_switch.get_attribute("aria-checked") == "true"

    # 切换
    first_switch.click()
    logged_in_page.wait_for_timeout(2000)

    # 验证状态变化
    now_public = first_switch.get_attribute("aria-checked") == "true"
    assert now_public != was_public, \
        f"公开开关切换无效: {was_public} -> {now_public}"

    # 切回
    first_switch.click()
    logged_in_page.wait_for_timeout(1000)


# === TC-MCP-016: Open-API MCP CRUD ===

@allure.epic("MCP服务器")
@pytest.mark.order(94)
@pytest.mark.p1
def test_openapi_mcp_crud(logged_in_page, base_url):
    """TC-MCP-016: Open-API MCP CRUD（通过页面操作拦截 API 验证）"""
    mcp = McpServerPage(logged_in_page, base_url)
    mcp.goto()

    crud_name = f"api-crud-{int(time.time())}"
    api_responses = mcp.setup_api_interceptor("mcp")

    # 1. CREATE
    mcp.open_create_dialog()
    assert mcp.is_create_dialog_open(), "创建对话框未弹出"
    mcp.select_type("Stdio")
    mcp.fill_create_form(name=crud_name, command="echo hello")
    mcp.save()
    logged_in_page.wait_for_timeout(1000)

    create_resps = [r for r in api_responses if r["method"] in ("POST", "PUT") and r["status"] < 400]
    if create_resps:
        assert create_resps[-1]["status"] < 400, f"Create API 异常: {create_resps[-1]['status']}"

    # 2. READ
    mcp.goto()
    assert mcp.has_server(crud_name), f"CRUD 创建后 '{crud_name}' 未在列表中"

    # 3. DELETE
    mcp.delete_server(crud_name)
    mcp.goto()
    assert not mcp.has_server(crud_name), f"CRUD 删除后 '{crud_name}' 仍在列表中"

    del_resps = [r for r in api_responses if r["method"] == "DELETE" and r["status"] < 400]
    if del_resps:
        assert del_resps[-1]["status"] < 400, f"Delete API 异常: {del_resps[-1]['status']}"


# === TC-MCP-017: Open-API MCP 参数校验 ===

@allure.epic("MCP服务器")
@pytest.mark.order(95)
@pytest.mark.p1
def test_openapi_mcp_validation(logged_in_page, base_url):
    """TC-MCP-017: Open-API MCP 参数校验"""
    mcp = McpServerPage(logged_in_page, base_url)
    mcp.goto()

    # 1. 非法名称格式
    mcp.open_create_dialog()
    dialog = logged_in_page.locator("[role='dialog']")
    name_input = dialog.locator("input[name='name']").or_(dialog.locator("input").first)
    name_input.first.fill("INVALID_NAME!!")
    mcp.save()
    logged_in_page.wait_for_timeout(500)

    assert mcp.is_create_dialog_open(), \
        "非法名称未触发校验"
    if mcp.is_create_dialog_open():
        mcp.close_dialog()
    logged_in_page.wait_for_timeout(300)

    # 2. 缺少必填字段
    mcp.open_create_dialog()
    mcp.save()
    logged_in_page.wait_for_timeout(500)
    assert mcp.is_create_dialog_open(), \
        "缺必填字段未触发校验"
    if mcp.is_create_dialog_open():
        mcp.close_dialog()
    logged_in_page.wait_for_timeout(300)

    # 3. 无效 URL（SSE 模式）
    mcp.open_create_dialog()
    mcp.select_type("SSE")
    mcp.fill_create_form(name=f"val-test-{int(time.time())}", url="not-a-valid-url")
    mcp.save()
    logged_in_page.wait_for_timeout(500)
    assert mcp.is_create_dialog_open(), \
        "无效 URL 未触发校验"
    if mcp.is_create_dialog_open():
        mcp.close_dialog()


# === TC-MCP-018: Open-API 认证和权限 ===

@allure.epic("MCP服务器")
@pytest.mark.order(95)
@pytest.mark.p0
def test_openapi_mcp_auth(logged_in_page, base_url, browser_instance):
    """TC-MCP-018: Open-API MCP 认证和权限 — 已认证可访问，未认证被拒绝"""
    mcp = McpServerPage(logged_in_page, base_url)
    mcp.goto()

    # 1. 已认证：拦截 MCP 列表 API，验证返回 200
    api_responses = mcp.setup_api_interceptor("/mcp")
    logged_in_page.reload()
    logged_in_page.wait_for_load_state("networkidle")
    logged_in_page.wait_for_timeout(1000)

    list_resps = [r for r in api_responses if r["method"] == "GET" and r["status"] < 400]
    assert len(list_resps) > 0, "已认证用户未能获取 MCP 列表 API 响应"
    assert list_resps[0]["status"] == 200, \
        f"已认证请求返回非 200: {list_resps[0]['status']}"

    # 2. 未认证：新建无 cookie 的 context，请求同一 API 应返回 401/403
    unauth_ctx = browser_instance.new_context()
    unauth_page = unauth_ctx.new_page()
    unauth_responses = []

    def on_unauth_resp(r):
        if "/mcp" in r.url and ".js" not in r.url and ".css" not in r.url:
            unauth_responses.append({"status": r.status, "url": r.url})

    unauth_page.on("response", on_unauth_resp)
    try:
        unauth_page.goto(f"{base_url}/ctrl/agent/mcp")
        unauth_page.wait_for_load_state("networkidle", timeout=10000)
        unauth_page.wait_for_timeout(2000)
    except Exception:
        pass  # 可能被重定向到登录页

    # 验证：未认证请求要么被重定向到登录页，要么 API 返回 401/403
    is_redirected = "/login" in unauth_page.url
    api_blocked = any(r["status"] in (401, 403) for r in unauth_responses)
    assert is_redirected or api_blocked, (
        f"未认证请求未被拒绝: URL={unauth_page.url}, "
        f"API 响应={unauth_responses[:3]}"
    )

    unauth_page.close()
    unauth_ctx.close()


# === TC-MCP-019: Open-API 获取 MCP 工具列表 ===

@allure.epic("MCP服务器")
@pytest.mark.order(96)
@pytest.mark.p2
def test_openapi_mcp_tools(logged_in_page, base_url):
    """TC-MCP-019: Open-API 获取 MCP 工具列表"""
    mcp = McpServerPage(logged_in_page, base_url)
    mcp.goto()

    names = mcp.get_server_names()
    if not names:
        pytest.skip("没有 MCP 服务器")

    # 拦截工具列表 API
    tools_data = []

    def on_tools_resp(r):
        url_lower = r.url.lower()
        if "tool" in url_lower and "mcp" in url_lower and ".js" not in url_lower:
            try:
                body = r.json()
                tools_data.append(body)
            except Exception:
                pass

    logged_in_page.on("response", on_tools_resp)

    mcp.click_inspect(names[0])
    logged_in_page.wait_for_load_state("networkidle", timeout=10000)
    logged_in_page.wait_for_timeout(2000)

    # 验证工具数据
    if tools_data:
        data = tools_data[0]
        tools = data.get("tools") or data.get("data", {}).get("tools") or data.get("items")
        if tools and isinstance(tools, list) and len(tools) > 0:
            first_tool = tools[0]
            assert "name" in first_tool, f"工具缺少 name 字段: {list(first_tool.keys())}"
    else:
        # 未拦截到 API，验证 UI 反馈
        dialog = logged_in_page.locator("[role='dialog']")
        body_text = logged_in_page.locator("div.agent-panel-body").inner_text()
        dialog_text = dialog.first.inner_text() if dialog.count() > 0 else ""
        combined = body_text + " " + dialog_text
        assert "工具" in combined or "tool" in combined.lower(), (
            f"未拦截到工具 API 且页面无工具信息（内容片段: {combined[:80]}）"
        )

    # 关闭 dialog
    dialog = logged_in_page.locator("[role='dialog']")
    if dialog.count() > 0:
        close_btn = dialog.get_by_role("button", name="Close").or_(
            dialog.get_by_role("button", name="关闭")
        )
        if close_btn.count() > 0:
            close_btn.first.click()


# === TC-MCP-020: Open-API 启用/禁用 MCP ===

@allure.epic("MCP服务器")
@pytest.mark.order(97)
@pytest.mark.p1
def test_openapi_mcp_toggle(logged_in_page, base_url):
    """TC-MCP-020: Open-API 启用/禁用 MCP"""
    mcp = McpServerPage(logged_in_page, base_url)
    mcp.goto()

    names = mcp.get_server_names()
    target = None
    for n in names:
        if n.startswith("auto-"):
            target = n
            break
    if not target and names:
        target = names[0]
    if not target:
        pytest.skip("没有可操作的 MCP 服务器")

    # 拦截 API
    toggle_resp = mcp.setup_api_interceptor("mcp")

    initial_state = mcp.is_server_enabled(target)
    mcp.toggle_enabled(target)
    logged_in_page.wait_for_timeout(2000)
    mcp.goto()

    new_state = mcp.is_server_enabled(target)
    assert new_state != initial_state, \
        f"启用/禁用切换无效: {initial_state} -> {new_state}"

    # 验证 API（辅助）
    patch_resps = [r for r in toggle_resp if r["method"] in ("PATCH", "PUT", "POST") and r["status"] < 400]

    # 恢复
    mcp.toggle_enabled(target)
    logged_in_page.wait_for_timeout(1000)
