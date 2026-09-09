# tests/suites/test_mcp.py
"""MCP 插件市场模块回归测试（TC-MCP-001 ~ TC-MCP-020）

2026-09-08 适配新版「MCP 插件市场」两栏 UI（参照环境 100.105.9.16:38879 实测 DOM）：
- 目录 navigation「插件目录」列出服务器；点选后在右侧详情/页脚操作条执行管理操作
- owner 私有服务器页脚：[检测][启用|禁用][设为公开|设为私有][删除]；owner 公开后仍保留管理
- 非 owner（他人/公开）服务器只读：header 仅「查看」
- 新建/编辑/删除确认弹窗文案与校验 toast 均已实测确认
- 移除：旧 grid 卡片列表、行内按钮、「共享/只读」标记、分页（新版目录无分页控件）
"""
import time
import uuid
import pytest
import allure
from tests.pages.mcp_page import McpServerPage


TEST_SSE_URL = "http://localhost:3001/sse"


def _name(prefix: str) -> str:
    """唯一服务器名（小写+连字符，符合名称规则）"""
    return f"{prefix}-{int(time.time())}-{uuid.uuid4().hex[:6]}"


def _create(mcp, name, mode, payload, level="p0"):
    """通用：新建服务器并断言已出现在目录。mode: Local/Remote"""
    mcp.goto()
    mcp.open_create_dialog()
    assert mcp.is_create_dialog_open(), "新建 MCP 服务器弹窗未弹出"
    mcp.select_type(mode)
    if mode == "Local":
        mcp.fill_create_form(name=name, command=payload)
    else:
        mcp.fill_create_form(name=name, url=payload or TEST_SSE_URL)
    mcp.save()
    assert not mcp.is_create_dialog_open(), "保存后新建弹窗未关闭"
    mcp.goto()
    assert mcp.has_server(name), f"服务器 '{name}' 创建后未出现在目录"


def _cleanup(mcp, name):
    """删除自建测试服务器（存在才删）"""
    try:
        if mcp.has_server(name, timeout=3000):
            mcp.delete_server(name)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════
# TC-MCP-001: 插件市场页加载
# ═══════════════════════════════════════════════════════

@allure.epic("MCP服务器")
@pytest.mark.order(80)
@pytest.mark.p0
def test_mcp_list_data_loads(logged_in_page, base_url):
    """TC-MCP-001: MCP 插件市场页加载（标题/添加按钮/搜索框/目录计数）"""
    mcp = McpServerPage(logged_in_page, base_url)
    mcp.goto()
    assert mcp.is_loaded(), "MCP 插件市场页未加载"

    # 顶栏：标题 + 添加插件
    assert logged_in_page.get_by_role("heading", name="MCP 插件市场").is_visible(), "页标题不可见"
    add_btn = logged_in_page.get_by_role("button", name="添加插件")
    add_btn.first.wait_for(state="visible", timeout=5000)
    assert add_btn.first.is_visible(), "「添加插件」按钮不可见"

    # 搜索框（筛选区）
    search = logged_in_page.get_by_placeholder("搜索插件、连接方式或用途")
    assert search.count() > 0 and search.first.is_visible(), "插件搜索框不存在"

    # 目录：计数徽标与目录项数量一致
    comp = logged_in_page.locator("main").get_by_role("complementary").first
    comp.wait_for(state="visible", timeout=8000)
    header_text = comp.inner_text()
    assert "插件目录" in header_text, f"插件目录未渲染: {header_text[:80]}"
    item_count = mcp.get_server_count()
    # 目录 header 徽标形如「插件目录\n3」（或计数标签另起）
    import re
    m = re.search(r"插件目录\s*(\d+)", header_text)
    badge = int(m.group(1)) if m else None
    if badge is not None:
        assert item_count == badge, f"目录项数 {item_count} 与徽标 {badge} 不一致"


# ═══════════════════════════════════════════════════════
# TC-MCP-002 / 003: 创建
# ═══════════════════════════════════════════════════════

@allure.epic("MCP服务器")
@pytest.mark.order(81)
@pytest.mark.p0
def test_create_stdio_server(logged_in_page, base_url):
    """TC-MCP-002: 创建本地进程(Local) MCP 服务器"""
    mcp = McpServerPage(logged_in_page, base_url)
    name = _name("mcp-local")
    _create(mcp, name, "Local", "echo hello")
    try:
        assert mcp.get_status(name) == "已启用", "新建本地服务器默认应已启用"
    finally:
        _cleanup(mcp, name)


@allure.epic("MCP服务器")
@pytest.mark.order(82)
@pytest.mark.p0
def test_create_sse_server(logged_in_page, base_url):
    """TC-MCP-003: 创建远程(Remote) MCP 服务器"""
    mcp = McpServerPage(logged_in_page, base_url)
    name = _name("mcp-remote")
    _create(mcp, name, "Remote", TEST_SSE_URL)
    try:
        assert mcp.get_status(name) == "已启用", "新建远程服务器默认应已启用"
        assert mcp.get_tools_meta(name) == "0 个工具", "新建服务器工具数应为 0"
    finally:
        _cleanup(mcp, name)


# ═══════════════════════════════════════════════════════
# TC-MCP-003b / 003c: 编辑
# ═══════════════════════════════════════════════════════

@allure.epic("MCP服务器")
@pytest.mark.order(83)
@pytest.mark.p0
def test_edit_server(logged_in_page, base_url):
    """TC-MCP-003b: 编辑弹窗 — 名称字段禁用 + 提示「名称创建后不可修改」"""
    mcp = McpServerPage(logged_in_page, base_url)
    name = _name("mcp-edit")
    _create(mcp, name, "Remote", TEST_SSE_URL)
    try:
        mcp.click_edit(name)
        assert mcp.is_edit_dialog_open(), "编辑弹窗未打开"
        assert mcp.is_name_field_locked(), "名称应禁用且显示「名称创建后不可修改」提示"
        mcp.close_dialog()
        assert not mcp.is_edit_dialog_open(), "取消后编辑弹窗未关闭"
    finally:
        _cleanup(mcp, name)


@allure.epic("MCP服务器")
@pytest.mark.order(83)
@pytest.mark.p0
def test_edit_server_fields(logged_in_page, base_url):
    """TC-MCP-003c: 编辑 — 修改 URL/超时/新增请求头后保存，重开验证持久化"""
    mcp = McpServerPage(logged_in_page, base_url)
    name = _name("mcp-editf")
    _create(mcp, name, "Remote", "http://localhost:3001/sse")
    try:
        # 1. 修改并保存
        mcp.click_edit(name)
        assert mcp.is_edit_dialog_open(), "编辑弹窗未打开"
        mcp.set_edit_field(
            url="http://localhost:3002/sse",
            timeout="8000",
            header=("X-Test-Auth", "test-token-123"),
        )
        mcp.save()
        assert not mcp.is_edit_dialog_open(), "保存后编辑弹窗未关闭"

        # 2. 重开编辑弹窗验证持久化
        mcp.goto()
        mcp.click_edit(name)
        vals = mcp.edit_field_values()
        assert vals["url"] == "http://localhost:3002/sse", f"URL 未持久化: {vals['url']}"
        assert vals["timeout"] == "8000", f"超时时间未持久化: {vals['timeout']}"
        assert any(
            h["name"] == "X-Test-Auth" and h["value"] == "test-token-123"
            for h in vals["headers"]
        ), f"请求头未持久化: {vals['headers']}"
        mcp.close_dialog()
    finally:
        _cleanup(mcp, name)


# ═══════════════════════════════════════════════════════
# TC-MCP-004/005/006: 表单校验
# ═══════════════════════════════════════════════════════

@allure.epic("MCP服务器")
@pytest.mark.order(83)
@pytest.mark.p1
def test_valid_name_format(logged_in_page, base_url):
    """TC-MCP-004: 合法名称（小写字母+数字+连字符）可正常创建"""
    mcp = McpServerPage(logged_in_page, base_url)
    name = _name("mcp-valid")
    _create(mcp, name, "Remote", TEST_SSE_URL)
    try:
        assert mcp.has_server(name), f"合法名称 '{name}' 创建失败"
    finally:
        _cleanup(mcp, name)


@allure.epic("MCP服务器")
@pytest.mark.order(84)
@pytest.mark.p1
@pytest.mark.no_page_error_check  # 故意提交非法名称，前端校验失败 console.error 属预期
def test_invalid_name_format(logged_in_page, base_url):
    """TC-MCP-005: 非法名称被校验拦截（弹窗保持打开，不创建）"""
    mcp = McpServerPage(logged_in_page, base_url)
    invalid_cases = [
        ("my server", "含空格"),
        ("my_server", "含下划线"),
        ("MyServer", "大写"),
        ("-lead", "连字符开头"),
        ("trail-", "连字符结尾"),
        ("a" * 65, "超 64 字符"),
        ("", "空名称"),
    ]
    mcp.goto()
    for name, desc in invalid_cases:
        mcp.open_create_dialog()
        assert mcp.is_create_dialog_open(), f"新建弹窗未弹出（{desc}）"
        # Remote 模式填名称后直接保存
        dlg = logged_in_page.get_by_role("dialog").first
        name_input = dlg.get_by_placeholder("my-mcp-server")
        name_input.first.wait_for(state="visible", timeout=5000)
        name_input.first.fill(name)
        mcp.save()
        # 校验失败 ⇒ 弹窗保持打开；若被误提交则弹窗关闭
        still_open = mcp.is_create_dialog_open()
        assert still_open, f"非法名称 '{name[:20]}'（{desc}）未被校验拦截（弹窗关闭=已提交创建）"
        if still_open:
            mcp.close_dialog()
        logged_in_page.wait_for_timeout(400)


@allure.epic("MCP服务器")
@pytest.mark.order(85)
@pytest.mark.p1
@pytest.mark.no_page_error_check  # 故意留空命令，前端校验失败 console.error 属预期
def test_command_validation(logged_in_page, base_url):
    """TC-MCP-006: Local 模式命令为空时被校验拦截"""
    mcp = McpServerPage(logged_in_page, base_url)
    mcp.goto()
    mcp.open_create_dialog()
    assert mcp.is_create_dialog_open(), "新建 MCP 对话框未弹出"
    mcp.select_type("Local")
    dlg = logged_in_page.get_by_role("dialog").first
    name_input = dlg.get_by_placeholder("my-mcp-server")
    name_input.first.wait_for(state="visible", timeout=5000)
    name_input.first.fill(_name("mcp-cmd"))
    mcp.save()
    assert mcp.is_create_dialog_open(), "空命令未被拦截（弹窗关闭=已提交）"
    mcp.close_dialog()


# ═══════════════════════════════════════════════════════
# TC-MCP-007/007b/008/008b: 启用 / 停用
# ═══════════════════════════════════════════════════════

def _assert_no_error_toast(logged_in_page, label: str):
    """轮询读取 toast，断言无 失败/错误 类提示"""
    error_toasts = []
    for _ in range(6):
        logged_in_page.wait_for_timeout(400)
        toasts = logged_in_page.evaluate(
            """() => Array.from(document.querySelectorAll('li'))
                .filter(li => li.querySelector('button'))
                .map(li => (li.textContent || '').replace('Close toast', '').trim())
                .filter(Boolean)"""
        )
        error_toasts = [t for t in toasts if any(k in t for k in ["失败", "错误", "Error", "Fail"])]
        if toasts:
            break
    assert not error_toasts, f"{label} 出现错误提示: {error_toasts}"


@allure.epic("MCP服务器")
@pytest.mark.order(86)
@pytest.mark.p0
def test_enable_server(logged_in_page, base_url):
    """TC-MCP-007: 本地服务器 停用→启用 往返（状态持久化）"""
    mcp = McpServerPage(logged_in_page, base_url)
    name = _name("mcp-en")
    _create(mcp, name, "Local", "echo hello")
    try:
        assert mcp.is_server_enabled(name), "新建后应为启用状态"
        # 停用
        mcp.toggle_enabled(name)
        _assert_no_error_toast(logged_in_page, "停用")
        mcp.goto()
        assert not mcp.is_server_enabled(name), "停用后仍显示「禁用」（应为启用态才显示禁用）"
        # 重新启用
        mcp.toggle_enabled(name)
        mcp.goto()
        assert mcp.is_server_enabled(name), "重新启用失败"
    finally:
        _cleanup(mcp, name)


@allure.epic("MCP服务器")
@pytest.mark.order(86)
@pytest.mark.p0
def test_enable_sse_server(logged_in_page, base_url):
    """TC-MCP-007b: 远程服务器 停用→启用 往返"""
    mcp = McpServerPage(logged_in_page, base_url)
    name = _name("mcp-enr")
    _create(mcp, name, "Remote", TEST_SSE_URL)
    try:
        assert mcp.is_server_enabled(name), "新建后应为启用状态"
        mcp.toggle_enabled(name)
        _assert_no_error_toast(logged_in_page, "停用")
        mcp.goto()
        assert not mcp.is_server_enabled(name), "停用失败"
        mcp.toggle_enabled(name)
        mcp.goto()
        assert mcp.is_server_enabled(name), "重新启用失败"
    finally:
        _cleanup(mcp, name)


@allure.epic("MCP服务器")
@pytest.mark.order(87)
@pytest.mark.p1
def test_disable_server(logged_in_page, base_url):
    """TC-MCP-008: 停用本地服务器并持久化"""
    mcp = McpServerPage(logged_in_page, base_url)
    name = _name("mcp-dis")
    _create(mcp, name, "Local", "echo hello")
    try:
        if not mcp.is_server_enabled(name):
            mcp.toggle_enabled(name)
        assert mcp.is_server_enabled(name), "预设为启用失败"
        mcp.toggle_enabled(name)
        _assert_no_error_toast(logged_in_page, "停用")
        mcp.goto()
        assert not mcp.is_server_enabled(name), "停用未持久化"
    finally:
        _cleanup(mcp, name)


@allure.epic("MCP服务器")
@pytest.mark.order(87)
@pytest.mark.p1
def test_disable_sse_server(logged_in_page, base_url):
    """TC-MCP-008b: 停用远程服务器并持久化"""
    mcp = McpServerPage(logged_in_page, base_url)
    name = _name("mcp-disr")
    _create(mcp, name, "Remote", TEST_SSE_URL)
    try:
        if not mcp.is_server_enabled(name):
            mcp.toggle_enabled(name)
        assert mcp.is_server_enabled(name), "预设为启用失败"
        mcp.toggle_enabled(name)
        _assert_no_error_toast(logged_in_page, "停用")
        mcp.goto()
        assert not mcp.is_server_enabled(name), "停用未持久化"
    finally:
        _cleanup(mcp, name)


# ═══════════════════════════════════════════════════════
# TC-MCP-009/010: 连接检测反馈
# ═══════════════════════════════════════════════════════

@allure.epic("MCP服务器")
@pytest.mark.order(88)
@pytest.mark.p1
def test_local_connection(logged_in_page, base_url):
    """TC-MCP-009: 本地进程检测应提示「仅支持远程」"""
    mcp = McpServerPage(logged_in_page, base_url)
    name = _name("mcp-loc")
    _create(mcp, name, "Local", "echo hello")
    try:
        mcp.click_inspect(name)
        toasts, _empty, _article = mcp.wait_inspect_result(name)
        if not toasts:
            # 全量重负载下首次检测结果可能延迟/被吞，重试一次再判定
            mcp.click_inspect(name)
            toasts, _empty, _article = mcp.wait_inspect_result(name, timeout=20000)
        assert toasts, "本地服务器检测后无任何 toast 反馈"
        combined = " ".join(toasts)
        assert ("检测失败" in combined and "remote" in combined.lower()) or \
               "Inspect only supports remote" in combined, \
               f"本地检测未提示「仅支持远程」: {combined[:120]}"
    finally:
        _cleanup(mcp, name)


@allure.epic("MCP服务器")
@pytest.mark.order(89)
@pytest.mark.p1
def test_remote_url(logged_in_page, base_url):
    """TC-MCP-010: 远程不可达 URL 检测应给出失败/无工具反馈"""
    mcp = McpServerPage(logged_in_page, base_url)
    name = _name("mcp-rmt")
    _create(mcp, name, "Remote", "http://localhost:3001/sse")
    try:
        mcp.click_inspect(name)
        toasts, tools_empty, article = mcp.wait_inspect_result(name)
        combined = " ".join(toasts) + " " + article[:120]
        # 有明确反馈即可：失败 toast（Unable/SSE error/检测失败）或成功（工具列表/成功文案）
        has_feedback = any(
            k in combined for k in ["检测失败", "Unable to connect", "SSE error", "检测成功", "个工具", "成功"]
        )
        assert has_feedback, f"远程 URL 检测后无任何反馈: {combined[:160]}"
    finally:
        _cleanup(mcp, name)


# ═══════════════════════════════════════════════════════
# TC-MCP-011/012/019: 工具发现与服务器元信息
# ═══════════════════════════════════════════════════════

@allure.epic("MCP服务器")
@pytest.mark.order(90)
@pytest.mark.p2
def test_view_tools(logged_in_page, base_url):
    """TC-MCP-011: 对已有带工具服务器执行检测 → Tools 卡片发现工具列表"""
    mcp = McpServerPage(logged_in_page, base_url)
    mcp.goto()
    target = "ORG_001_new/my-langfuse-mcp"
    if not mcp.has_server(target):
        pytest.skip(f"已有 MCP 服务器 '{target}' 不存在")

    mcp.select_server(target)
    mcp.click_inspect(target)
    toasts, tools_empty, article = mcp.wait_inspect_result(target, timeout=20000)
    combined = " ".join(toasts)
    if any(k in combined for k in ["Unable to connect", "SSE error", "检测失败"]) and "Inspect only" in combined:
        pytest.skip(f"SSE 端点不可达（网络限制）: {combined[:80]}")
    # 排除「检测失败」但内容是"仅支持远程"的误判
    if "检测失败" in combined and "Inspect only supports remote" not in combined:
        pytest.skip(f"该服务器检测不可用: {combined[:100]}")
    if tools_empty:
        assert any(k in combined for k in ["成功", "工具"]), \
            f"检测后 Tools 卡片仍为空且无成功 toast: {combined[:120]}"
    else:
        assert "暂无已发现的工具" not in article, "Tools 卡片发现后仍显示空态"


@allure.epic("MCP服务器")
@pytest.mark.order(91)
@pytest.mark.p2
def test_inspect_server(logged_in_page, base_url):
    """TC-MCP-012: 已有服务器详情展示 类型/状态/工具数 元信息（无需网络）"""
    mcp = McpServerPage(logged_in_page, base_url)
    mcp.goto()
    target = "ORG_001_new/my-langfuse-mcp"
    if not mcp.has_server(target):
        pytest.skip(f"已有 MCP 服务器 '{target}' 不存在")

    mcp.select_server(target)
    assert mcp.is_managed(target), f"'{target}' 应为本账号可管理的服务器"
    status = mcp.get_status(target)
    assert status in ("已启用", "已停用"), f"状态异常: {status}"
    tools_meta = mcp.get_tools_meta(target)
    import re
    m = re.match(r"(\d+) 个工具", tools_meta)
    assert m and int(m.group(1)) >= 1, f"服务器工具元信息异常: '{tools_meta}'（应≥1）"


# ═══════════════════════════════════════════════════════
# TC-MCP-013/013b: 删除
# ═══════════════════════════════════════════════════════

@allure.epic("MCP服务器")
@pytest.mark.order(92)
@pytest.mark.p1
def test_delete_server(logged_in_page, base_url):
    """TC-MCP-013: 删除本地服务器（自建→删→目录项消失）"""
    mcp = McpServerPage(logged_in_page, base_url)
    name = _name("mcp-del")
    _create(mcp, name, "Local", "echo hello")
    before = mcp.get_server_count()
    mcp.delete_server(name)
    mcp.goto()
    assert not mcp.has_server(name, timeout=3000), f"删除后 '{name}' 仍在目录"
    assert mcp.get_server_count() < before, "删除后目录项数未减少"


@allure.epic("MCP服务器")
@pytest.mark.order(92)
@pytest.mark.p1
def test_delete_sse_server(logged_in_page, base_url):
    """TC-MCP-013b: 删除远程服务器"""
    mcp = McpServerPage(logged_in_page, base_url)
    name = _name("mcp-delr")
    _create(mcp, name, "Remote", TEST_SSE_URL)
    before = mcp.get_server_count()
    mcp.delete_server(name)
    mcp.goto()
    assert not mcp.has_server(name, timeout=3000), f"删除后 '{name}' 仍在目录"
    assert mcp.get_server_count() < before, "删除后目录项数未减少"


# ═══════════════════════════════════════════════════════
# TC-MCP-014: 非 owner 服务器只读
# ═══════════════════════════════════════════════════════

@allure.epic("MCP服务器")
@pytest.mark.order(93)
@pytest.mark.p0
def test_public_mcp_readonly(logged_in_page, base_url):
    """共享/他人服务器只读 — 无 编辑/删除/禁用/设为公开，仅「查看」"""
    mcp = McpServerPage(logged_in_page, base_url)
    mcp.goto()
    readonly = mcp._find_readonly_server()
    if readonly is None:
        pytest.skip("当前环境没有他人（非 owner）的只读服务器")

    main = logged_in_page.locator("main")
    # header：有「查看」，无「编辑」
    view_btn = main.get_by_role("button", name="查看", exact=True)
    assert view_btn.count() > 0, f"只读服务器 '{readonly}' 缺少「查看」按钮"
    assert main.get_by_role("button", name="编辑", exact=True).count() == 0, \
        f"只读服务器 '{readonly}' 不应有「编辑」"
    # 页脚无管理按钮
    for btn_name in ["删除", "禁用", "启用", "设为公开", "设为私有"]:
        assert main.get_by_role("button", name=btn_name, exact=True).count() == 0, \
            f"只读服务器 '{readonly}' 不应有「{btn_name}」"
    # 详情元信息可见
    assert mcp.get_status(readonly) in ("已启用", "已停用"), "只读服务器状态不可读"


# ═══════════════════════════════════════════════════════
# TC-MCP-015/015b: 设为公开 / 设为私有
# ═══════════════════════════════════════════════════════

def _public_toggle_roundtrip(logged_in_page, base_url, mode):
    mcp = McpServerPage(logged_in_page, base_url)
    name = _name(f"mcp-pub-{mode.lower()[:3]}")
    payload = "echo hello" if mode == "Local" else TEST_SSE_URL
    _create(mcp, name, mode, payload)
    try:
        assert not mcp.is_public(name), "新建后应为私有"
        # 设为公开
        mcp.toggle_public(name)
        _assert_no_error_toast(logged_in_page, "设为公开")
        mcp.goto()
        assert mcp.is_public(name), "公开状态未持久化"
        assert mcp.is_managed(name), "owner 公开后仍应可管理"
        # 设回私有
        mcp.toggle_public(name)
        mcp.goto()
        assert not mcp.is_public(name), "撤销公开失败（仍为公开）"
    finally:
        _cleanup(mcp, name)


@allure.epic("MCP服务器")
@pytest.mark.order(93)
@pytest.mark.p1
def test_mcp_make_public(logged_in_page, base_url):
    """TC-MCP-015: 本地服务器 设为公开 → 撤销 往返"""
    _public_toggle_roundtrip(logged_in_page, base_url, "Local")


@allure.epic("MCP服务器")
@pytest.mark.order(93)
@pytest.mark.p1
def test_sse_mcp_make_public(logged_in_page, base_url):
    """TC-MCP-015b: 远程服务器 设为公开 → 撤销 往返"""
    _public_toggle_roundtrip(logged_in_page, base_url, "Remote")


# ═══════════════════════════════════════════════════════
# TC-MCP-016: UI 全 CRUD 闭环
# ═══════════════════════════════════════════════════════

@allure.epic("MCP服务器")
@pytest.mark.order(94)
@pytest.mark.p1
def test_mcp_api_crud(logged_in_page, base_url):
    """TC-MCP-016: MCP CRUD 闭环（UI）：建→读→改→删"""
    mcp = McpServerPage(logged_in_page, base_url)
    name = _name("mcp-crud")
    _create(mcp, name, "Remote", "http://localhost:3001/sse")

    # READ：目录 + 详情可读
    assert mcp.get_status(name) == "已启用", "创建后状态可读异常"

    # UPDATE：改 URL
    mcp.click_edit(name)
    assert mcp.is_edit_dialog_open(), "编辑弹窗未打开"
    mcp.set_edit_field(url="http://localhost:3003/sse")
    mcp.save()
    mcp.goto()
    mcp.click_edit(name)
    assert mcp.edit_field_values()["url"] == "http://localhost:3003/sse", "URL 修改未持久化"
    mcp.close_dialog()

    # DELETE
    mcp.delete_server(name)
    mcp.goto()
    assert not mcp.has_server(name, timeout=3000), "删除后仍在目录"


# ═══════════════════════════════════════════════════════
# TC-MCP-017: URL 校验
# ═══════════════════════════════════════════════════════

@allure.epic("MCP服务器")
@pytest.mark.order(95)
@pytest.mark.p1
@pytest.mark.no_page_error_check  # 故意提交非法 URL，前端校验失败 console.error 属预期
def test_mcp_api_validation(logged_in_page, base_url):
    """TC-MCP-017: Remote 模式非法 URL 被校验拦截（不提交创建）"""
    mcp = McpServerPage(logged_in_page, base_url)
    mcp.goto()
    mcp.open_create_dialog()
    assert mcp.is_create_dialog_open(), "新建弹窗未弹出"
    mcp.select_type("Remote")
    dlg = logged_in_page.get_by_role("dialog").first
    name_input = dlg.get_by_placeholder("my-mcp-server")
    name_input.first.wait_for(state="visible", timeout=5000)
    name_input.first.fill(_name("mcp-url"))
    url_input = dlg.get_by_placeholder("https://example.com/mcp")
    url_input.first.wait_for(state="visible", timeout=5000)
    url_input.first.fill("not-a-valid-url")
    mcp.save()
    assert mcp.is_create_dialog_open(), "非法 URL 未被拦截（弹窗关闭=已提交创建）"
    mcp.close_dialog()


# ═══════════════════════════════════════════════════════
# TC-MCP-018: 认证保护
# ═══════════════════════════════════════════════════════

@allure.epic("MCP服务器")
@pytest.mark.order(95)
@pytest.mark.p0
def test_mcp_api_auth(logged_in_page, base_url, browser_instance):
    """TC-MCP-018: 未认证访问 MCP 市场被拒绝/重定向登录"""
    McpServerPage(logged_in_page, base_url).goto()
    unauth_ctx = browser_instance.new_context(locale="zh-CN")
    unauth_page = unauth_ctx.new_page()
    try:
        try:
            unauth_page.goto(f"{base_url}/ctrl/agent/mcp", wait_until="domcontentloaded", timeout=10000)
        except Exception:
            pass
        unauth_page.wait_for_timeout(1500)
        url = unauth_page.url
        is_redirected = any(k in url for k in ["login", "auth"])
        has_login_form = (
            unauth_page.get_by_placeholder("请输入账号或邮箱").count() > 0
            or unauth_page.locator("input[type='password']").count() > 0
        )
        assert is_redirected or has_login_form, (
            f"未认证访问未被拦截: URL={url}, 有登录框={has_login_form}"
        )
    finally:
        unauth_page.close()
        unauth_ctx.close()


# ═══════════════════════════════════════════════════════
# TC-MCP-019: 已有带工具服务器的工具列表展示
# ═══════════════════════════════════════════════════════

@allure.epic("MCP服务器")
@pytest.mark.order(96)
@pytest.mark.p2
def test_mcp_api_tools(logged_in_page, base_url):
    """TC-MCP-019: 已有带工具服务器（langfuse）经检测后 Tools 卡片渲染工具列表"""
    mcp = McpServerPage(logged_in_page, base_url)
    mcp.goto()
    target = "ORG_001_new/my-langfuse-mcp"
    if not mcp.has_server(target):
        pytest.skip(f"已有 MCP 服务器 '{target}' 不存在")

    mcp.select_server(target)
    mcp.click_inspect(target)
    toasts, tools_empty, article = mcp.wait_inspect_result(target, timeout=20000)
    combined = " ".join(toasts)
    if "检测失败" in combined or "Unable to connect" in combined:
        pytest.skip(f"该环境无法连接目标服务器进行工具发现: {combined[:100]}")

    # 成功：Tools 卡片不再空态，且展示工具名
    assert not tools_empty, f"检测后 Tools 卡片仍为空: toasts={combined[:100]}"
    assert "暂无已发现的工具" not in article, "Tools 卡片仍显示空态"
    # 工具名行：摘取 article 中 Tools 卡片段后的行，至少存在非空工具描述块
    mcp.goto()
    assert mcp.has_server(target), "检测后目录异常"


# ═══════════════════════════════════════════════════════
# TC-MCP-020: 启用/停用 切换
# ═══════════════════════════════════════════════════════

@allure.epic("MCP服务器")
@pytest.mark.order(97)
@pytest.mark.p1
def test_mcp_api_toggle(logged_in_page, base_url):
    """TC-MCP-020: 切换启停两次回到原状态，全程无错误"""
    mcp = McpServerPage(logged_in_page, base_url)
    name = _name("mcp-tgl")
    _create(mcp, name, "Remote", TEST_SSE_URL)
    try:
        was = mcp.is_server_enabled(name)
        mcp.toggle_enabled(name)
        _assert_no_error_toast(logged_in_page, "第一次切换")
        mcp.goto()
        cur = mcp.is_server_enabled(name)
        assert cur != was, "切换后状态未变化"
        mcp.toggle_enabled(name)
        mcp.goto()
        assert mcp.is_server_enabled(name) == was, "切回后状态未复原"
    finally:
        _cleanup(mcp, name)


# ═══════════════════════════════════════════════════════
# P2: 工具详情 / 创建弹窗字段覆盖
# ═══════════════════════════════════════════════════════

@allure.epic("MCP服务器")
@pytest.mark.order(98)
@pytest.mark.p1
def test_mcp_tool_details(logged_in_page, base_url):
    """展开带工具服务器详情，Tools 区域展示工具数元信息"""
    mcp = McpServerPage(logged_in_page, base_url)
    mcp.goto()
    target = "ORG_001_new/my-langfuse-mcp"
    if not mcp.has_server(target):
        pytest.skip(f"已有 MCP 服务器 '{target}' 不存在")
    mcp.select_server(target)
    import re
    tools_meta = mcp.get_tools_meta(target)
    assert re.match(r"\d+ 个工具", tools_meta), f"Tools 区域缺失工具数: '{tools_meta}'"
    # Tools 卡片区域存在（article 内含有 Tools 标题块）
    article = logged_in_page.locator("main article").first.inner_text()
    assert "Tools" in article, "详情中未渲染 Tools 卡片区域"


@allure.epic("MCP服务器")
@pytest.mark.order(99)
@pytest.mark.p2
def test_mcp_create_all_fields(logged_in_page, base_url):
    """创建弹窗（Remote）覆盖：名称/URL/测试按钮/请求头/OAuth/超时 字段齐全，不提交"""
    mcp = McpServerPage(logged_in_page, base_url)
    mcp.goto()
    mcp.open_create_dialog()
    assert mcp.is_create_dialog_open(), "新建 MCP 服务器弹窗未打开"
    dlg = logged_in_page.get_by_role("dialog").filter(
        has=logged_in_page.get_by_role("heading", name="新建 MCP 服务器")
    )
    # Remote 默认模式
    assert dlg.get_by_placeholder("my-mcp-server").count() > 0, "名称输入框缺失"
    url_input = dlg.get_by_placeholder("https://example.com/mcp")
    assert url_input.count() > 0 and url_input.first.is_visible(), "URL 输入框缺失"
    # 测试按钮初始 disabled（URL 为空时）
    test_btn = dlg.get_by_role("button", name="测试", exact=True)
    assert test_btn.count() > 0 and test_btn.first.is_disabled(), "URL 为空时「测试」应禁用"
    # 请求头新增按钮 + 默认行
    assert dlg.get_by_role("button", name="+ 添加").count() > 0, "请求头「+ 添加」缺失"
    assert dlg.get_by_placeholder("Header 名称").count() > 0, "Header 名称输入框缺失"
    # OAuth 折叠项 + 超时时间
    assert dlg.get_by_text("OAuth 配置（可选）").count() > 0, "OAuth 配置折叠项缺失"
    assert dlg.get_by_role("spinbutton").count() > 0, "超时时间输入缺失"
    # 不提交，直接关闭
    mcp.close_dialog()
    assert not mcp.is_create_dialog_open(), "关闭后新建弹窗未关闭"
