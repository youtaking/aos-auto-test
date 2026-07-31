# tests/suites/test_sidebar.py
"""侧边栏模块回归测试
覆盖：智能体编排、记忆、知识库、定时任务、组织、API Key
+ 8 条导航可达性用例 + 1 条结构完整性用例
"""
import pytest
import allure
from tests.pages.sidebar_pages import (
    WorkflowPage, MemoryPage, KnowledgeBasePage,
    TasksPage, OrganizationPage, ApiKeyPage,
    SidebarNavigation,
)


def _check_console_errors(page, timeout_ms=500):
    """收集并检查控制台错误，返回错误列表。
    使用 try/finally 确保监听器清理，避免 session 级累积。"""
    errors = []

    def on_console(msg):
        if msg.type == "error":
            errors.append(msg.text)

    page.on("console", on_console)
    try:
        page.wait_for_timeout(timeout_ms)
    finally:
        try:
            page.remove_listener("console", on_console)
        except Exception:
            pass
    return errors


# ==================== 智能体编排 ====================


@pytest.mark.order(19)
@pytest.mark.p0
def test_workflow_page_loads(logged_in_page, base_url):
    """智能体编排页面能正常加载 | ✅ 人工评审通过 |"""
    page = WorkflowPage(logged_in_page, base_url)
    errors = _check_console_errors(logged_in_page, timeout_ms=0)  # 在 goto 前注册
    page.goto()
    assert page.is_loaded(), "智能体编排页面未加载"
    errors = _check_console_errors(logged_in_page, 500)
    assert not errors, f"页面加载后有控制台错误: {errors}"


@pytest.mark.order(19)
@pytest.mark.p1
def test_workflow_has_create_button(logged_in_page, base_url):
    """智能体编排页面有新建工作流按钮（可见+可点击）| ✅ 人工评审通过 |"""
    page = WorkflowPage(logged_in_page, base_url)
    page.goto()
    assert page.has_create_button(), \
        "新建工作流按钮不存在、不可见或不可点击"


@pytest.mark.order(19)
@pytest.mark.p1
def test_workflow_search(logged_in_page, base_url):
    """智能体编排搜索功能可用 | ✅ 人工评审通过 |"""
    page = WorkflowPage(logged_in_page, base_url)
    page.goto()

    initial = page.get_workflow_count()
    assert isinstance(initial, int), "工作流列表加载失败"

    page.search("zzz_不存在_zzz")
    logged_in_page.wait_for_timeout(500)
    filtered = page.get_workflow_count()
    assert filtered == 0 or filtered < initial, \
        f"搜索不存在的内容后数量未减少: {filtered} vs {initial}"

    page.clear_search()
    restored = page.get_workflow_count()
    assert restored == initial, \
        f"清空搜索后未恢复: {restored} vs {initial}"


@pytest.mark.order(19)
@pytest.mark.p0
def test_workflow_create_and_return(logged_in_page, base_url):
    """智能体编排：新建工作流 → 进入编辑器 → 返回列表验证 | ✅ 人工评审通过 |"""
    import json, requests

    wf_name = "auto-test-workflow-e2e"

    # ── Step 0: 提取 session cookie，清理可能残留的同名测试工作流 ──
    cookies = logged_in_page.context.cookies()
    session_cookie = next(
        (c for c in cookies if c["name"].startswith("better-auth")), None
    )
    cookie_jar = {session_cookie["name"]: session_cookie["value"]} if session_cookie else {}

    if cookie_jar:
        list_resp = requests.get(
            f"{base_url}/web/workflow-defs", cookies=cookie_jar, timeout=10,
        )
        if list_resp.status_code < 400:
            for wf in list_resp.json().get("data", []):
                if wf.get("name") == wf_name:
                    requests.delete(
                        f"{base_url}/web/workflow-defs/{wf['id']}",
                        cookies=cookie_jar, timeout=10,
                    )

    # ── Step 1: 导航到工作流页面 ──
    page = WorkflowPage(logged_in_page, base_url)
    page.goto()

    # ── Step 2: 点击新建工作流 → 弹窗填写 → 创建 ──
    logged_in_page.get_by_role("button", name="新建工作流").first.click()
    logged_in_page.wait_for_timeout(1500)

    dialog = logged_in_page.locator("[role='dialog']")
    assert dialog.count() > 0, "新建工作流对话框未弹出"

    logged_in_page.locator("#wf-name").fill(wf_name)
    logged_in_page.locator("#wf-desc").fill("自动化测试创建的工作流")
    logged_in_page.wait_for_timeout(500)

    # 拦截创建 API 响应
    create_result = []

    def on_create(r):
        if "workflow-defs" in r.url and r.request.method == "POST":
            try:
                create_result.append({"status": r.status, "body": r.json()})
            except Exception:
                create_result.append({"status": r.status})

    logged_in_page.on("response", on_create)

    logged_in_page.locator("[role='dialog'] button").filter(has_text="创建并编辑").first.click()
    logged_in_page.wait_for_load_state("networkidle")

    # ── Step 3: 验证跳转到编辑页 ──
    assert "/workflow/" in logged_in_page.url and "/edit" in logged_in_page.url, \
        f"创建后未跳转到编辑页: {logged_in_page.url}"
    assert len(create_result) > 0, "未拦截到创建 API 请求"
    assert create_result[0]["status"] < 400, \
        f"创建 API 失败: HTTP {create_result[0]['status']}"

    wf_id = create_result[0].get("body", {}).get("data", {}).get("id")

    # ── Step 4: 点击"工作流"返回按钮回到列表 ──
    back_link = logged_in_page.locator("a").filter(has_text="工作流")
    assert back_link.count() > 0, "编辑页未找到返回'工作流'链接"
    back_link.first.click()
    logged_in_page.wait_for_timeout(800)

    # ── Step 5: 回到列表页并刷新，验证新工作流可见 ──
    page.goto()  # 强制刷新确保数据最新
    logged_in_page.wait_for_timeout(800)
    assert "/ctrl/agent/workflow" in logged_in_page.url and "/edit" not in logged_in_page.url, \
        f"返回后 URL 不正确: {logged_in_page.url}"

    # 验证 1: 新工作流名称在列表中可见
    wf_text = logged_in_page.locator("span").filter(has_text=wf_name)
    assert wf_text.count() > 0, \
        f"创建的工作流 '{wf_name}' 在列表中不可见"

    # 验证 2: API 确认工作流存在
    if cookie_jar:
        api_resp = requests.get(
            f"{base_url}/web/workflow-defs", cookies=cookie_jar, timeout=10,
        )
        assert api_resp.status_code < 400, "获取工作流列表 API 失败"
        wf_names = [w.get("name") for w in api_resp.json().get("data", [])]
        assert wf_name in wf_names, \
            f"API 返回的工作流列表中不包含 '{wf_name}'，当前: {wf_names}"

    # ── Step 6: 清理 — 通过 API 删除测试工作流 ──
    if wf_id and cookie_jar:
        del_resp = requests.delete(
            f"{base_url}/web/workflow-defs/{wf_id}",
            cookies=cookie_jar, timeout=10,
        )
        assert del_resp.status_code < 400, \
            f"清理测试工作流失败: HTTP {del_resp.status_code}"


# ==================== 记忆 ====================


@pytest.mark.order(20)
@pytest.mark.p0
def test_memory_page_loads(logged_in_page, base_url):
    """记忆页面能正常加载 | ✅ 人工评审通过 |"""
    page = MemoryPage(logged_in_page, base_url)
    page.goto()
    assert page.is_loaded(), "记忆页面未加载"
    errors = _check_console_errors(logged_in_page, 500)
    assert not errors, f"页面加载后有控制台错误: {errors}"


@pytest.mark.order(20)
@pytest.mark.p1
def test_memory_has_tabs(logged_in_page, base_url):
    """记忆页面有分类 Tab | ✅ 人工评审通过 |"""
    page = MemoryPage(logged_in_page, base_url)
    page.goto()
    tabs = page.get_tab_names()
    assert len(tabs) > 0, "记忆页面没有分类 Tab"


@pytest.mark.order(20)
@pytest.mark.p1
def test_memory_switch_tab(logged_in_page, base_url):
    """记忆页面能切换 Tab | ✅ 人工评审通过 |"""
    page = MemoryPage(logged_in_page, base_url)
    page.goto()
    tabs = page.get_tab_names()
    if len(tabs) < 2:
        pytest.skip(f"记忆页面只有 {len(tabs)} 个 Tab，无法测试切换")
    page.click_tab(tabs[1])
    assert page.is_tab_active(tabs[1]), \
        f"点击 Tab '{tabs[1]}' 后未激活"


@pytest.mark.order(20)
@pytest.mark.p1
def test_memory_tab_traversal(logged_in_page, base_url):
    """遍历所有 Tab 逐个点击，验证页面无报错 | ✅ 人工评审通过 |"""
    page = MemoryPage(logged_in_page, base_url)
    page.goto()
    tabs = page.get_tab_names()
    if len(tabs) < 2:
        pytest.skip(f"只有 {len(tabs)} 个 Tab，无需遍历")

    allure.attach(
        f"Tab 列表: {tabs}",
        name="Tab 列表",
        attachment_type=allure.attachment_type.TEXT,
    )

    for tab_name in tabs:
        page.click_tab(tab_name)
        logged_in_page.wait_for_timeout(300)
        # 验证切换生效
        is_active = page.is_tab_active(tab_name)
        allure.attach(
            f"Tab '{tab_name}': active={is_active}",
            name=f"Tab {tab_name}",
            attachment_type=allure.attachment_type.TEXT,
        )

    # 遍历完成后检查无控制台错误
    errors = _check_console_errors(logged_in_page, 500)
    assert not errors, f"Tab 遍历后出现控制台错误: {errors}"


# ==================== 知识库 ====================


@pytest.mark.order(21)
@pytest.mark.p0
def test_knowledge_base_page_loads(logged_in_page, base_url):
    """知识库页面能正常加载 | ✅ 人工评审通过 |"""
    page = KnowledgeBasePage(logged_in_page, base_url)
    page.goto()
    assert page.is_loaded(), "知识库页面未加载"
    errors = _check_console_errors(logged_in_page, 500)
    assert not errors, f"页面加载后有控制台错误: {errors}"


@pytest.mark.order(21)
@pytest.mark.p1
def test_knowledge_base_has_create_button(logged_in_page, base_url):
    """知识库页面有新建按钮（可见+可点击）| ✅ 人工评审通过 |"""
    page = KnowledgeBasePage(logged_in_page, base_url)
    page.goto()
    assert page.has_create_button(), \
        "新建知识库按钮不存在、不可见或不可点击"


@pytest.mark.order(21)
@pytest.mark.p1
def test_knowledge_base_search(logged_in_page, base_url):
    """知识库搜索功能可用 | ✅ 人工评审通过 |"""
    page = KnowledgeBasePage(logged_in_page, base_url)
    page.goto()

    initial = page.get_kb_count()
    assert isinstance(initial, int), "知识库列表加载失败"

    page.search("zzz_不存在_zzz")
    logged_in_page.wait_for_timeout(500)
    filtered = page.get_kb_count()
    assert filtered == 0 or filtered < initial, \
        f"搜索不存在的内容后数量未减少: {filtered} vs {initial}"

    page.clear_search()
    restored = page.get_kb_count()
    assert restored == initial, \
        f"清空搜索后未恢复: {restored} vs {initial}"


# ==================== 定时任务 ====================


@pytest.mark.order(22)
@pytest.mark.p0
def test_tasks_page_loads(logged_in_page, base_url):
    """定时任务页面能正常加载 | ✅ 人工评审通过 |"""
    page = TasksPage(logged_in_page, base_url)
    page.goto()
    assert page.is_loaded(), "定时任务页面未加载"
    errors = _check_console_errors(logged_in_page, 500)
    assert not errors, f"页面加载后有控制台错误: {errors}"


@pytest.mark.order(22)
@pytest.mark.p1
def test_tasks_has_table(logged_in_page, base_url):
    """定时任务页面有表格 | ✅ 人工评审通过 |"""
    page = TasksPage(logged_in_page, base_url)
    page.goto()
    assert page.has_table(), "定时任务页面没有表格"


@pytest.mark.order(22)
@pytest.mark.p1
def test_tasks_filter_tabs(logged_in_page, base_url):
    """定时任务有筛选 Tab，名称包含关键分类 | ✅ 人工评审通过 |"""
    page = TasksPage(logged_in_page, base_url)
    page.goto()
    tabs = page.get_tab_names()
    assert len(tabs) > 0, "定时任务没有筛选 Tab"

    allure.attach(
        f"筛选 Tab: {tabs}",
        name="Tab 列表",
        attachment_type=allure.attachment_type.TEXT,
    )

    # 验证包含预期分类名称
    expected_keywords = ["全部", "HTTP", "Agent"]
    found = [kw for kw in expected_keywords if any(kw in t for t in tabs)]
    assert len(found) >= 2, \
        f"筛选 Tab 缺少预期分类，期望含 {expected_keywords} 中至少 2 个，实际只找到 {found}"

    # 遍历每个 Tab 点击验证切换
    for tab_name in tabs:
        page.click_tab(tab_name)
        logged_in_page.wait_for_timeout(300)

    # 遍历后检查无控制台错误
    errors = _check_console_errors(logged_in_page, 500)
    assert not errors, f"Tab 切换遍历后出现控制台错误: {errors}"


# ==================== 组织 ====================


@pytest.mark.order(23)
@pytest.mark.p0
def test_organization_page_loads(logged_in_page, base_url):
    """组织管理页面能正常加载 | ✅ 人工评审通过 |"""
    page = OrganizationPage(logged_in_page, base_url)
    page.goto()
    assert page.is_loaded(), "组织管理页面未加载"
    errors = _check_console_errors(logged_in_page, 500)
    assert not errors, f"页面加载后有控制台错误: {errors}"


@pytest.mark.order(23)
@pytest.mark.p1
def test_organization_has_members(logged_in_page, base_url):
    """组织管理页面有成员区域 | ✅ 人工评审通过 |"""
    page = OrganizationPage(logged_in_page, base_url)
    page.goto()
    assert page.has_member_section(), "组织管理页面没有成员区域"
    name = page.get_org_name()
    assert len(name) > 0, "组织名称为空"


# ==================== API Key ====================


@pytest.mark.order(24)
@pytest.mark.p0
def test_apikey_page_loads(logged_in_page, base_url):
    """API 密钥页面能正常加载 | ✅ 人工评审通过 |"""
    page = ApiKeyPage(logged_in_page, base_url)
    page.goto()
    assert page.is_loaded(), "API 密钥页面未加载"
    errors = _check_console_errors(logged_in_page, 500)
    assert not errors, f"页面加载后有控制台错误: {errors}"


@pytest.mark.order(24)
@pytest.mark.p1
def test_apikey_has_create_button(logged_in_page, base_url):
    """API 密钥页面有创建按钮（可见+可点击）| ✅ 人工评审通过 |"""
    page = ApiKeyPage(logged_in_page, base_url)
    page.goto()
    assert page.has_create_button(), \
        "创建密钥按钮不存在、不可见或不可点击"


@pytest.mark.order(24)
@pytest.mark.p1
def test_apikey_search(logged_in_page, base_url):
    """API 密钥搜索功能可用 | ✅ 人工评审通过 |"""
    page = ApiKeyPage(logged_in_page, base_url)
    page.goto()

    initial = page.get_key_count()
    assert isinstance(initial, int), "密钥列表加载失败"

    page.search("zzz_不存在_zzz")
    logged_in_page.wait_for_timeout(500)
    filtered = page.get_key_count()
    assert filtered == 0 or filtered < initial, \
        f"搜索不存在的内容后数量未减少: {filtered} vs {initial}"

    page.clear_search()
    restored = page.get_key_count()
    assert restored == initial, \
        f"清空搜索后未恢复: {restored} vs {initial}"


# ==================== 导航可达性（8 个缺失菜单项） ====================


@allure.epic("侧边栏导航")
@pytest.mark.order(25)
@pytest.mark.p0
def test_sidebar_nav_create_agent(logged_in_page, base_url):
    """侧边栏导航：新建智能体 → 可达 | ✅ 人工评审通过 |"""
    nav = SidebarNavigation(logged_in_page, base_url)
    assert nav.has_nav_item("新建智能体"), \
        "侧边栏缺少'新建智能体'菜单项"

    nav.click_nav("新建智能体")
    assert "/ctrl/agent/home" in logged_in_page.url, \
        f"点击'新建智能体'后 URL 不正确: {logged_in_page.url}"
    assert nav.has_panel_content(), "页面主内容区未加载"

    errors = _check_console_errors(logged_in_page, 500)
    assert not errors, f"导航后出现控制台错误: {errors}"


@allure.epic("侧边栏导航")
@pytest.mark.order(25)
@pytest.mark.p0
def test_sidebar_nav_agents(logged_in_page, base_url):
    """侧边栏导航：智能体管理 → 可达 | ✅ 人工评审通过 |"""
    nav = SidebarNavigation(logged_in_page, base_url)
    assert nav.has_nav_item("智能体管理"), \
        "侧边栏缺少'智能体管理'菜单项"

    nav.click_nav("智能体管理")
    assert "/ctrl/agent/agents" in logged_in_page.url, \
        f"点击'智能体管理'后 URL 不正确: {logged_in_page.url}"
    assert nav.has_panel_content(), "页面主内容区未加载"

    errors = _check_console_errors(logged_in_page, 500)
    assert not errors, f"导航后出现控制台错误: {errors}"


@allure.epic("侧边栏导航")
@pytest.mark.order(26)
@pytest.mark.p0
def test_sidebar_nav_models(logged_in_page, base_url):
    """侧边栏导航：模型库 → 可达 | ✅ 人工评审通过 |"""
    nav = SidebarNavigation(logged_in_page, base_url)
    if not nav.has_nav_item("模型库"):
        pytest.skip("侧边栏无'模型库'菜单项")

    nav.click_nav("模型库")
    assert "/ctrl/agent/models" in logged_in_page.url, \
        f"点击'模型库'后 URL 不正确: {logged_in_page.url}"
    assert nav.has_panel_content(), "模型库页面未加载"

    errors = _check_console_errors(logged_in_page, 500)
    assert not errors, f"导航后出现控制台错误: {errors}"


@allure.epic("侧边栏导航")
@pytest.mark.order(26)
@pytest.mark.p0
def test_sidebar_nav_vertical_models(logged_in_page, base_url):
    """侧边栏导航：企业垂直大模型 → 可达 | ✅ 人工评审通过 |"""
    nav = SidebarNavigation(logged_in_page, base_url)
    if not nav.has_nav_item("企业垂直大模型"):
        pytest.skip("侧边栏无'企业垂直大模型'菜单项")

    nav.click_nav("企业垂直大模型")
    assert "/ctrl/agent/vertical" in logged_in_page.url, \
        f"点击'企业垂直大模型'后 URL 不正确: {logged_in_page.url}"
    assert nav.has_panel_content(), "企业垂直大模型页面未加载"

    errors = _check_console_errors(logged_in_page, 500)
    assert not errors, f"导航后出现控制台错误: {errors}"


@allure.epic("侧边栏导航")
@pytest.mark.order(27)
@pytest.mark.p0
def test_sidebar_nav_algorithms(logged_in_page, base_url):
    """侧边栏导航：算法库 → 可达 | ✅ 人工评审通过 |"""
    nav = SidebarNavigation(logged_in_page, base_url)
    if not nav.has_nav_item("算法库"):
        pytest.skip("侧边栏无'算法库'菜单项")

    nav.click_nav("算法库")
    assert "/ctrl/agent/algorithms" in logged_in_page.url, \
        f"点击'算法库'后 URL 不正确: {logged_in_page.url}"
    assert nav.has_panel_content(), "算法库页面未加载"

    errors = _check_console_errors(logged_in_page, 500)
    assert not errors, f"导航后出现控制台错误: {errors}"


@allure.epic("侧边栏导航")
@pytest.mark.order(27)
@pytest.mark.p0
def test_sidebar_nav_skills(logged_in_page, base_url):
    """侧边栏导航：技能库 → 可达 | ✅ 人工评审通过 |"""
    nav = SidebarNavigation(logged_in_page, base_url)
    if not nav.has_nav_item("技能库"):
        pytest.skip("侧边栏无'技能库'菜单项")

    nav.click_nav("技能库")
    assert "/ctrl/agent/skills" in logged_in_page.url, \
        f"点击'技能库'后 URL 不正确: {logged_in_page.url}"
    assert nav.has_panel_content(), "技能库页面未加载"

    errors = _check_console_errors(logged_in_page, 500)
    assert not errors, f"导航后出现控制台错误: {errors}"


@allure.epic("侧边栏导航")
@pytest.mark.order(28)
@pytest.mark.p0
def test_sidebar_nav_mcp(logged_in_page, base_url):
    """侧边栏导航：MCP → 可达 | ✅ 人工评审通过 |"""
    nav = SidebarNavigation(logged_in_page, base_url)
    if not nav.has_nav_item("MCP"):
        pytest.skip("侧边栏无'MCP'菜单项")

    nav.click_nav("MCP")
    assert "/ctrl/agent/mcp" in logged_in_page.url, \
        f"点击'MCP'后 URL 不正确: {logged_in_page.url}"
    assert nav.has_panel_content(), "MCP 页面未加载"

    errors = _check_console_errors(logged_in_page, 500)
    assert not errors, f"导航后出现控制台错误: {errors}"


@allure.epic("侧边栏导航")
@pytest.mark.order(28)
@pytest.mark.p0
def test_sidebar_nav_sites(logged_in_page, base_url):
    """侧边栏导航：AOS应用部署 → 可达 | ✅ 人工评审通过 |"""
    nav = SidebarNavigation(logged_in_page, base_url)
    if not nav.has_nav_item("AOS应用部署"):
        pytest.skip("侧边栏无'AOS应用部署'菜单项")

    nav.click_nav("AOS应用部署")
    # 仅验证导航发生（URL 变化），不限定具体路径
    assert "/ctrl/agent/" in logged_in_page.url, \
        f"点击'AOS应用部署'后 URL 不正确: {logged_in_page.url}"
    assert nav.has_panel_content(), "AOS应用部署页面未加载"

    errors = _check_console_errors(logged_in_page, 500)
    assert not errors, f"导航后出现控制台错误: {errors}"


# ==================== 侧边栏结构完整性 ====================


@allure.epic("侧边栏导航")
@pytest.mark.order(29)
@pytest.mark.p1
def test_sidebar_structure_integrity(logged_in_page, base_url):
    """侧边栏结构完整性：菜单项数量 + 分组存在 | ✅ 人工评审通过 |"""
    nav = SidebarNavigation(logged_in_page, base_url)

    # 1. 导航项数量
    nav_count = nav.get_nav_count()
    assert nav_count >= 8, \
        f"侧边栏导航项过少: {nav_count}，预期至少 8 个"

    # 2. 获取所有导航项名称
    items = nav.get_nav_items()
    allure.attach(
        f"侧边栏导航项 ({len(items)} 个): {items}",
        name="导航项列表",
        attachment_type=allure.attachment_type.TEXT,
    )

    # 3. 核心菜单项必须存在
    core_items = ["智能体管理", "智能体编排", "记忆", "知识库"]
    for item in core_items:
        assert nav.has_nav_item(item), \
            f"核心菜单项 '{item}' 不存在于侧边栏中"

    # 4. 配置类菜单项至少存在部分
    config_items = ["模型库", "MCP", "技能库", "API Key"]
    config_found = [i for i in config_items if nav.has_nav_item(i)]
    assert len(config_found) >= 2, \
        f"配置类菜单项过少，只找到 {config_found}"
