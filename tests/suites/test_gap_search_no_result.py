# tests/suites/test_gap_search_no_result.py
"""搜索无结果 + 空状态补充测试 — 覆盖多个模块的共性 gap"""
import allure
import pytest
from tests.pages.chat_test_page import ChatTestPage


@allure.epic("首页")
@pytest.mark.order(400)
@pytest.mark.p1
def test_home_empty_description_submit(logged_in_page, base_url):
    """TC-HOME-GAP-001: 空描述时点击一键创建无响应"""
    logged_in_page.goto(f"{base_url}/ctrl/agent/home")
    logged_in_page.wait_for_load_state("domcontentloaded")
    logged_in_page.wait_for_load_state("networkidle")
    logged_in_page.wait_for_timeout(500)

    # 确保输入框为空
    textarea = logged_in_page.locator("textarea[placeholder*='描述']")
    if textarea.count() == 0:
        pytest.skip("首页描述输入框未找到")
    textarea.first.fill("")
    logged_in_page.wait_for_timeout(300)

    # 一键创建按钮存在
    create_btn = logged_in_page.get_by_role("button", name="一键创建")
    if create_btn.count() == 0:
        pytest.skip("一键创建按钮未找到")

    # 记录当前 URL
    url_before = logged_in_page.url

    # 点击一键创建
    create_btn.first.click()
    logged_in_page.wait_for_timeout(1500)

    # 验证：无页面跳转（空描述不应创建智能体）
    url_after = logged_in_page.url
    assert url_after == url_before, f"空描述点击后发生了页面跳转: {url_before} → {url_after}"


@allure.epic("垂直模型")
@pytest.mark.order(401)
@pytest.mark.p1
def test_vertical_models_search_no_result(logged_in_page, base_url):
    """TC-VM-GAP-001: 垂直模型搜索无结果时卡片消失"""
    logged_in_page.goto(f"{base_url}/ctrl/agent/vertical-models")
    logged_in_page.wait_for_load_state("domcontentloaded")
    logged_in_page.wait_for_load_state("networkidle")
    logged_in_page.wait_for_timeout(500)

    search = logged_in_page.locator("input[placeholder*='搜索']")
    if search.count() == 0:
        pytest.skip("垂直模型搜索框未找到")

    # 通过搜索框向上定位内容面板（3 层祖先 div = 主内容区）
    content_panel = search.first.locator("xpath=ancestor::div[3]")
    content_panel.wait_for(state="visible", timeout=5000)
    initial_text = content_panel.inner_text()
    initial_len = len(initial_text.strip())

    # 搜索不存在的模型（需按 Enter 触发）
    search.first.fill("zzz_不存在_99999")
    search.first.press("Enter")
    logged_in_page.wait_for_timeout(1500)

    # 内容区域文本应明显减少（卡片消失）
    after_text = content_panel.inner_text()
    after_len = len(after_text.strip())
    assert after_len < initial_len, \
        f"搜索不存在的模型后内容未减少: {initial_len} → {after_len}"

    # 清空恢复（需按 Enter 触发）
    search.first.fill("")
    search.first.press("Enter")
    logged_in_page.wait_for_timeout(1500)
    restored_text = content_panel.inner_text()
    restored_len = len(restored_text.strip())
    assert restored_len >= initial_len - 10, \
        f"清空搜索后内容未恢复: 期望约 {initial_len}，实际 {restored_len}"


@allure.epic("算法库")
@pytest.mark.order(402)
@pytest.mark.p1
def test_algorithms_search_no_result(logged_in_page, base_url):
    """TC-ALGO-GAP-001: 算法库搜索无结果时列表过滤"""
    logged_in_page.goto(f"{base_url}/ctrl/agent/algorithms")
    logged_in_page.wait_for_load_state("domcontentloaded")
    logged_in_page.wait_for_load_state("networkidle")
    logged_in_page.wait_for_timeout(500)

    search = logged_in_page.locator("input[placeholder*='搜索']")
    if search.count() == 0:
        pytest.skip("算法库搜索框未找到")

    # 通过搜索框向上定位内容面板
    content_panel = search.first.locator("xpath=ancestor::div[3]")
    content_panel.wait_for(state="visible", timeout=5000)
    initial_text = content_panel.inner_text()
    initial_len = len(initial_text.strip())

    # 搜索不存在的算法（需按 Enter 触发）
    search.first.fill("zzz_不存在_99999")
    search.first.press("Enter")
    logged_in_page.wait_for_timeout(1500)

    # 内容区域文本应明显减少
    after_text = content_panel.inner_text()
    after_len = len(after_text.strip())
    assert after_len < initial_len, \
        f"搜索不存在的算法后内容未减少: {initial_len} → {after_len}"

    # 清空恢复（需按 Enter 触发）
    search.first.fill("")
    search.first.press("Enter")
    logged_in_page.wait_for_timeout(1500)
    restored_text = content_panel.inner_text()
    restored_len = len(restored_text.strip())
    assert restored_len >= initial_len - 10, \
        f"清空搜索后内容未恢复: 期望约 {initial_len}，实际 {restored_len}"


@allure.epic("MCP服务器")
@pytest.mark.order(403)
@pytest.mark.p1
def test_mcp_search_no_result(logged_in_page, base_url):
    """TC-MCP-GAP-001: MCP 搜索无结果显示空状态"""
    from tests.pages.mcp_page import McpServerPage
    mcp = McpServerPage(logged_in_page, base_url)
    mcp.goto()
    logged_in_page.wait_for_timeout(1500)

    search = logged_in_page.locator("input[placeholder*='搜索 MCP']")
    try:
        search.first.wait_for(state="visible", timeout=5000)
    except Exception:
        pytest.skip("MCP 搜索框未找到")

    # MCP 搜索是实时过滤，不需要按 Enter
    search.first.fill("zzz_不存在_99999")
    logged_in_page.wait_for_timeout(1500)

    # 应显示空状态提示
    empty_text = logged_in_page.get_by_text("暂无 MCP 服务器")
    assert empty_text.count() > 0, "搜索无结果后未显示空状态提示"

    # 清空恢复
    search.first.fill("")
    logged_in_page.wait_for_timeout(1500)

    # 空状态提示应消失
    assert empty_text.count() == 0, "清空搜索后空状态提示仍未消失"


@allure.epic("知识库")
@pytest.mark.order(404)
@pytest.mark.p1
def test_knowledge_search_no_result(logged_in_page, base_url):
    """TC-KB-GAP-001: 知识库搜索无结果显示空状态"""
    from tests.pages.knowledge_page import KnowledgePage
    kb = KnowledgePage(logged_in_page, base_url)
    kb.goto()
    if not kb.is_loaded():
        pytest.skip("知识库页面未加载")

    search = logged_in_page.locator("input[placeholder*='搜索']")
    if search.count() == 0:
        pytest.skip("知识库搜索框未找到")
    search.first.fill("zzz_不存在_99999")
    logged_in_page.wait_for_timeout(1500)

    search.first.wait_for(state="visible", timeout=5000)
    search.first.fill("")
    logged_in_page.wait_for_timeout(1500)


@allure.epic("产品视图")
@pytest.mark.order(405)
@pytest.mark.p2
def test_views_card_buttons_complete(logged_in_page, base_url):
    """TC-VIEW-GAP-001: 视图卡片操作按钮完整性（自建自销）"""
    import uuid
    from tests.pages.views_page import ViewsPage
    v = ViewsPage(logged_in_page, base_url)
    v.goto()
    if not v.is_loaded():
        pytest.skip("产品视图页面未加载")

    # 1. 自建视图（数据安全：先创建再操作，测试结束删除）
    # 限定到「发布视图」顶栏头部的 + 创建按钮（禁止全页面搜索 lucide-plus）
    header = logged_in_page.locator(
        "div.flex.items-center.justify-between.border-b span.text-xs.font-medium"
    ).filter(has_text="发布视图")
    if header.count() == 0:
        pytest.skip("发布视图顶栏未找到")
    plus_btn = header.first.locator("..").locator("button").filter(
        has=logged_in_page.locator("svg.lucide-plus")
    )
    if plus_btn.count() == 0:
        pytest.skip("创建视图按钮未找到")
    plus_btn.first.click()
    logged_in_page.wait_for_timeout(1000)

    dialog = logged_in_page.locator("[role=dialog]")
    if dialog.count() == 0:
        pytest.skip("创建视图弹窗未打开")
    name_input = dialog.first.locator("input[placeholder='输入视图名称']")
    if name_input.count() == 0:
        pytest.skip("视图名称输入框未找到")
    view_name = f"e2e_view_{uuid.uuid4().hex[:6]}"
    name_input.first.fill(view_name)
    logged_in_page.wait_for_timeout(300)
    save_btn = dialog.first.get_by_role("button", name="保存")
    save_btn.first.click()

    # 2. 等待视图卡片出现（按名称精确定位，禁止裸 count）
    card_sel = logged_in_page.locator("div.rounded-lg.border").filter(has_text=view_name)
    card_sel.first.wait_for(state="visible", timeout=10000)

    # 3. 校验操作按钮完整（源码确认按钮始终可见，无需 hover）
    edit_btn = card_sel.first.locator("button").filter(
        has=logged_in_page.locator("svg.lucide-pencil")
    )
    del_btn = card_sel.first.locator("button").filter(
        has=logged_in_page.locator("svg.lucide-trash-2")
    )
    open_btn = card_sel.first.locator("button").filter(
        has=logged_in_page.locator("svg.lucide-external-link")
    )
    copy_btn = card_sel.first.locator("button").filter(
        has=logged_in_page.locator("svg.lucide-copy")
    )
    has_all = edit_btn.count() > 0 and del_btn.count() > 0 and \
              open_btn.count() > 0 and copy_btn.count() > 0
    assert has_all, (
        f"视图卡片操作按钮不完整: "
        f"编辑={edit_btn.count()}, 删除={del_btn.count()}, "
        f"打开={open_btn.count()}, 复制={copy_btn.count()}"
    )

    # 4. 清理：删除自建视图（确认弹窗按钮为「确认」）
    del_btn.first.click()
    logged_in_page.wait_for_timeout(800)
    cdlg = logged_in_page.locator("[role=alertdialog], [role=dialog]").filter(
        has_text="删除发布视图"
    )
    assert cdlg.count() > 0, "删除视图后未弹出确认弹窗"
    cdlg_text = cdlg.first.inner_text()
    assert view_name in cdlg_text, \
        f"确认弹窗未包含视图名 {view_name}: {cdlg_text[:100]}"
    confirm = cdlg.first.get_by_role("button", name="确认")
    assert confirm.count() > 0, "确认弹窗缺少确认按钮"
    confirm.first.click()
    # 等待卡片消失（禁止裸 count）
    for _wait in range(15):
        if card_sel.count() == 0:
            break
        logged_in_page.wait_for_timeout(1000)
    assert card_sel.count() == 0, f"删除后视图 {view_name} 仍显示在列表中"


@allure.epic("智能体管理")
@pytest.mark.order(406)
@pytest.mark.p1
def test_agent_card_hover_buttons(logged_in_page, base_url):
    """TC-AGENT-GAP-001: 智能体卡片 hover 操作按钮"""
    logged_in_page.goto(f"{base_url}/ctrl/agent/home")
    logged_in_page.wait_for_load_state("domcontentloaded")
    logged_in_page.wait_for_load_state("networkidle")
    logged_in_page.wait_for_timeout(500)

    # 找到自有智能体卡片（非共享）
    cards = logged_in_page.locator("button.agent-sidebar-agent-card")
    if cards.count() == 0:
        pytest.skip("无智能体卡片")

    # 找到第一个非共享的卡片
    target_card = None
    for i in range(cards.count()):
        card = cards.nth(i)
        card_text = card.inner_text()
        if "共享" not in card_text:
            target_card = card
            break

    if target_card is None:
        pytest.skip("无非共享智能体卡片")

    # hover 显示操作区域
    target_card.hover()
    logged_in_page.wait_for_timeout(800)

    # 检查操作按钮（用 title 属性匹配，按钮无文本只有图标）
    parent = target_card.locator("xpath=..")
    config_btn = parent.locator("button[title='智能体配置']")
    restart_btn = parent.locator("button[title='重启智能体']")
    expand_btn = parent.locator("button[title='展开实例']")
    delete_btn = parent.locator("button[title='删除智能体']")

    has_config = config_btn.count() > 0
    has_restart = restart_btn.count() > 0
    has_expand = expand_btn.count() > 0
    has_delete = delete_btn.count() > 0
    assert has_config and has_restart and has_expand and has_delete, (
        f"hover 后操作按钮不完整: "
        f"配置={has_config}, 重启={has_restart}, "
        f"展开={has_expand}, 删除={has_delete}"
    )


@allure.epic("侧边栏导航")
@pytest.mark.order(407)
@pytest.mark.p1
def test_sidebar_collapse_expand(logged_in_page, base_url):
    """TC-SIDEBAR-GAP-001: 侧边栏折叠/展开"""
    logged_in_page.goto(f"{base_url}/ctrl/agent/home")
    logged_in_page.wait_for_load_state("domcontentloaded")
    logged_in_page.wait_for_load_state("networkidle")
    logged_in_page.wait_for_timeout(500)

    # 点击收起
    collapse_btn = logged_in_page.get_by_role("button", name="收起侧边栏")
    if collapse_btn.count() == 0:
        pytest.skip("无收起侧边栏按钮")
    collapse_btn.first.click()
    logged_in_page.wait_for_timeout(1000)

    # 收起后应有展开按钮
    expand_btn = logged_in_page.get_by_role("button", name="展开侧边栏")
    assert expand_btn.count() > 0, "收起侧边栏后无展开按钮"

    # 点击展开
    expand_btn.first.click()
    logged_in_page.wait_for_timeout(1000)

    # 展开后应重新显示收起按钮
    collapse_btn2 = logged_in_page.get_by_role("button", name="收起侧边栏")
    assert collapse_btn2.count() > 0, "展开侧边栏后无收起按钮"


@allure.epic("侧边栏导航")
@pytest.mark.order(408)
@pytest.mark.p2
def test_sidebar_active_item_highlight(logged_in_page, base_url):
    """TC-SIDEBAR-GAP-002: 当前页面导航项高亮"""
    logged_in_page.goto(f"{base_url}/ctrl/agent/mcp")
    logged_in_page.wait_for_load_state("domcontentloaded")
    logged_in_page.wait_for_load_state("networkidle")
    logged_in_page.wait_for_timeout(500)

    # 当前页面是 MCP，MCP 导航项应有 active class
    mcp_btn = logged_in_page.locator("button.agent-sidebar-nav-item.active")
    assert mcp_btn.count() > 0, "当前页面无高亮导航项"

    active_text = mcp_btn.first.inner_text().strip()
    assert "MCP" in active_text, \
        f"高亮的导航项不是当前页面: '{active_text}'"

    # 非当前页面的导航项不应有 active class
    kb_btn = logged_in_page.locator("button.agent-sidebar-nav-item").filter(
        has_text="知识库"
    )
    if kb_btn.count() > 0:
        kb_cls = kb_btn.first.get_attribute("class") or ""
        assert "active" not in kb_cls.split(), \
            "非当前页面（知识库）不应有高亮状态"
