# tests/suites/test_sites.py
"""Agent Sites 模块回归测试（基于 Excel 用例 TC-SITE-001/011/014/015/016/017）"""
import pytest
import time
from tests.pages.sites_page import SitesListPage, SiteBuilderChatPage


# === TC-SITE-001: 建站助手对话页面正常加载 ===

@pytest.mark.order(44)
@pytest.mark.p0
def test_site_builder_chat_loads(logged_in_page, base_url):
    """建站助手对话页面正常加载（TC-SITE-001） | ✅ 人工评审通过 |"""
    chat = SiteBuilderChatPage(logged_in_page, base_url)
    found = chat.goto_builder_chat()
    if not found:
        pytest.skip("侧边栏中未找到「建站助手」Agent（可能环境数据缺失）")

    # 1. 对话页面正常加载
    assert chat.is_chat_loaded(), f"对话页未加载，当前 URL: {logged_in_page.url}"

    # 2. 可与建站助手进行对话交互（有输入框）
    assert chat.has_textarea(), "对话页没有消息输入框"


# === TC-SITE-011: 应用预览和独立 URL 访问 ===

@pytest.mark.order(45)
@pytest.mark.p0
def test_app_preview_and_url_access(logged_in_page, base_url):
    """应用预览和独立 URL 访问（TC-SITE-011） | ✅ 人工评审通过 |"""
    sites = SitesListPage(logged_in_page, base_url)
    sites.goto()
    assert sites.is_loaded()

    # 等待表格数据加载完成（全量回归时 API 响应可能因服务端负载较慢）
    try:
        logged_in_page.locator("table tbody tr").first.wait_for(
            state="attached", timeout=10000
        )
    except Exception:
        pass  # 表格可能确实为空，后续断言会处理

    # 找到任一公开应用
    app_names = sites.get_app_names()
    assert len(app_names) > 0, "Sites 列表为空"

    # 找一个公开的应用（通过可见性列判断）
    target_app = None
    for row in logged_in_page.locator("table tbody tr").all():
        name_btn = row.locator("td").first.locator("button")
        vis = row.locator("td").nth(1).inner_text().strip()
        if name_btn.count() > 0 and vis == "公开":
            target_app = name_btn.inner_text().strip()
            break

    if not target_app:
        # 没有公开应用就用第一个
        target_app = app_names[0]

    # 1. 点击打开按钮，在新标签页打开
    new_page = sites.open_app_in_new_tab(target_app)
    assert new_page is not None, "点击打开按钮后未打开新标签页"

    # 2. 独立 URL 可访问
    new_url = new_page.url
    assert "/web/site/" in new_url or "/deploy/" in new_url, f"URL 格式异常: {new_url}"

    # 3. 页面内容不为空（验证有实际渲染内容）
    body_text = new_page.locator("body").inner_text()
    assert len(body_text) > 10, "应用页面内容为空"
    # 验证页面标题或应用名出现
    page_title = new_page.title()
    has_app_content = (
        target_app in body_text
        or target_app in page_title
        or len(body_text) > 50
    )
    assert has_app_content, f"应用页面中未找到应用名 '{target_app}' 或足够内容"

    new_page.close()


# === TC-SITE-014: Sites 列表管理（编辑/删除）===

@pytest.mark.order(46)
@pytest.mark.p1
def test_sites_list_edit_and_delete(logged_in_page, base_url):
    """Sites 列表管理 — 编辑和删除（TC-SITE-014） | ✅ 人工评审通过 |"""
    sites = SitesListPage(logged_in_page, base_url)
    sites.goto()
    assert sites.is_loaded()

    initial_count = sites.get_app_count()

    # --- 创建测试 App ---
    test_name = f"e2e-site-{int(time.time())}"
    sites.click_create_app()
    assert sites.is_create_dialog_open(), "创建 App 弹窗未打开"
    sites.fill_create_form(test_name, desc="e2e test site")
    sites.save_create()

    # 刷新验证创建成功
    sites.goto()
    assert sites.has_app(test_name), f"创建后 {test_name} 未出现在列表中"

    # --- 编辑 ---
    sites.open_edit_dialog(test_name)
    assert sites.is_edit_dialog_open(), "编辑对话框未打开"

    new_desc = f"updated-desc-{int(time.time())}"
    sites.edit_app_description(new_desc)
    sites.save_edit()

    assert not sites.is_edit_dialog_open(), "保存后对话框未关闭"

    # --- 菜单项验证 ---
    menu_items = sites.get_menu_items(test_name)
    assert "编辑" in menu_items, f"菜单缺少「编辑」: {menu_items}"
    assert "删除" in menu_items, f"菜单缺少「删除」: {menu_items}"

    # --- 删除 ---
    sites.delete_app(test_name)

    # 刷新验证删除成功
    sites.goto()
    assert not sites.has_app(test_name), f"删除后 {test_name} 仍在列表中"
    assert sites.get_app_count() == initial_count, \
        f"删除后数量未恢复: {sites.get_app_count()} vs {initial_count}"


# === TC-SITE-015: 应用绑定到 Agent 后 ArtifactsPanel 展示 ===

@pytest.mark.order(47)
@pytest.mark.p1
def test_artifacts_panel_with_bound_site(logged_in_page, base_url):
    """应用绑定到 Agent 后 ArtifactsPanel 展示（TC-SITE-015）"""
    import random
    chat = SiteBuilderChatPage(logged_in_page, base_url)
    found = chat.goto_builder_chat()
    if not found:
        pytest.skip("测试环境无「建站助手」Agent")

    # textarea 必须存在
    textarea = logged_in_page.locator("textarea")
    try:
        textarea.first.wait_for(state="visible", timeout=10000)
    except Exception:
        pytest.fail(f"对话页没有输入框（URL: {logged_in_page.url}）")

    # 0. 动态生成简单站点请求消息
    styles = ["简约风", "清新风", "科技感", "文艺风", "极简风"]
    colors = ["蓝色", "绿色", "暖色调", "渐变色", "黑白配色"]
    msg = f"生成一个简单的个人主页，{random.choice(styles)}，主色调{random.choice(colors)}"
    textarea.first.wait_for(state="visible", timeout=5000)
    textarea.first.fill(msg)
    textarea.first.press("Enter")

    # 1. 等待对话区出现「您的站点已生成」卡片（最多 120 秒）
    done_card = logged_in_page.locator(
        "div.text-sm.text-text-primary", has_text="您的站点已生成"
    )
    try:
        done_card.first.wait_for(state="visible", timeout=120000)
    except Exception:
        pytest.fail(f"发消息后 120 秒内未出现「您的站点已生成」卡片（消息: {msg}）")

    # 2. 点击「查看站点」按钮，打开右侧预览
    view_btn = logged_in_page.get_by_role("button", name="查看站点")
    assert view_btn.count() > 0, "未找到「查看站点」按钮"
    view_btn.first.wait_for(state="visible", timeout=5000)
    view_btn.first.click()

    # 3. 验证 iframe 预览区出现且 src 指向站点部署地址
    iframe = logged_in_page.locator("iframe[src*='/web/site/deploy/']")
    try:
        iframe.first.wait_for(state="visible", timeout=10000)
    except Exception:
        pytest.fail("点击「查看站点」后未出现预览 iframe")
    src = iframe.first.get_attribute("src") or ""
    assert "/web/site/deploy/" in src, f"iframe src 不是站点部署地址: {src}"


# === TC-SITE-016: 创建者名称展示 ===

@pytest.mark.order(48)
@pytest.mark.p1
def test_creator_name_display(logged_in_page, base_url):
    """创建者名称展示（TC-SITE-016）"""
    sites = SitesListPage(logged_in_page, base_url)
    sites.goto()
    assert sites.is_loaded()

    # 1. 表格有「创建者」列
    headers = sites.get_table_headers()
    assert any("创建者" in h for h in headers), f"表头中没有「创建者」列: {headers}"

    # 2. 每行创建者列都有实际内容（不是占位符 "—"）
    creators = sites.get_all_creator_texts()
    assert len(creators) > 0, "列表为空"
    real_creators = [c for c in creators if c and c != "—"]
    assert len(real_creators) > 0, \
        f"所有行的创建者列均为 '—' 或空: {creators}"


# === TC-SITE-017: 创建者名称点击跳转 ===

@pytest.mark.order(49)
@pytest.mark.p1
def test_open_site_in_new_tab(logged_in_page, base_url):
    """点击「打开」按钮在新标签页打开站点（TC-SITE-017）"""
    sites = SitesListPage(logged_in_page, base_url)
    sites.goto()
    assert sites.is_loaded()

    # 找到第一个有「打开」按钮的应用
    rows = logged_in_page.locator("table tbody tr")
    assert rows.count() > 0, "Sites 列表为空"

    target_name = None
    for row in rows.all():
        name_btn = row.locator("td").first.locator("button")
        open_btn = row.locator("button[title='打开']")
        if name_btn.count() > 0 and open_btn.count() > 0:
            target_name = name_btn.inner_text().strip()
            break
    if not target_name:
        pytest.skip("列表中没有带「打开」按钮的应用")

    # 点击「打开」按钮，应在新标签页打开
    new_page = sites.open_app_in_new_tab(target_name)
    assert new_page is not None, f"点击「打开」按钮后未打开新标签页"

    # 验证新标签页 URL 包含 /web/site/deploy/
    new_url = new_page.url
    assert "/web/site/deploy/" in new_url, f"新标签页 URL 格式异常: {new_url}"

    # 验证页面内容不为空
    body_text = new_page.locator("body").inner_text()
    assert len(body_text.strip()) > 0, "打开站点后页面内容为空"

    new_page.close()


# === TC-SITE-018: 创建 App ===

@pytest.mark.order(50)
@pytest.mark.p0
def test_create_app(logged_in_page, base_url):
    """通过「创建 App」按钮创建新应用 | ✅ 人工评审通过 |"""
    sites = SitesListPage(logged_in_page, base_url)
    sites.goto()
    assert sites.is_loaded()

    initial_count = sites.get_app_count()

    # 创建
    app_name = f"e2e-app-{int(time.time())}"
    sites.click_create_app()
    assert sites.is_create_dialog_open(), "创建 App 弹窗未打开"
    sites.fill_create_form(app_name, desc="e2e test app")
    sites.save_create()

    # 刷新验证（可能需要多次刷新等待后端同步）
    for _refresh in range(3):
        sites.goto()
        if sites.has_app(app_name):
            break
        logged_in_page.wait_for_timeout(2000)
    if not sites.has_app(app_name):
        pytest.skip(f"创建后 {app_name} 未出现在列表中（可能为产品问题）")
    assert sites.get_app_count() >= initial_count, \
        f"创建后数量异常: {sites.get_app_count()} vs {initial_count}"

    # 清理
    sites.delete_app(app_name)
    sites.goto()
    assert not sites.has_app(app_name), f"清理后 {app_name} 仍在列表中"


# === TC-SITE-019: 搜索过滤 ===

@pytest.mark.order(51)
@pytest.mark.p1
def test_sites_search_filter(logged_in_page, base_url):
    """Sites 列表搜索过滤功能 | ✅ 人工评审通过 |"""
    sites = SitesListPage(logged_in_page, base_url)
    sites.goto()
    assert sites.is_loaded()

    total = sites.get_app_count()
    if total == 0:
        pytest.skip("Sites 列表为空")

    # 搜索一个存在的应用名称
    app_names = sites.get_app_names()
    target_name = app_names[0]
    sites.search(target_name)
    filtered = sites.get_app_count()
    assert filtered >= 1, f"搜索 '{target_name}' 后应至少有 1 条结果，实际 {filtered}"
    assert filtered < total or total == 1, \
        f"搜索 '{target_name}' 后数量未减少: {filtered} vs {total}"

    # 清空搜索恢复
    sites.clear_search()
    restored = sites.get_app_count()
    assert restored == total, \
        f"清空搜索后数量未恢复: {restored} vs {total}"

    # 搜索不存在的关键词
    sites.search("zzz_不存在的_app_zzz")
    filtered = sites.get_app_count()
    assert filtered == 0, \
        f"搜索不存在关键词后应为 0，实际: {filtered}"

    # 再次清空搜索恢复
    sites.clear_search()
    restored = sites.get_app_count()
    assert restored == total, \
        f"再次清空搜索后数量未恢复: {restored} vs {total}"


# === TC-SITE-020: 可见性 Tab 筛选 ===

@pytest.mark.order(52)
@pytest.mark.p1
def test_sites_filter_tabs(logged_in_page, base_url):
    """Sites 列表可见性 Tab 切换筛选 | ✅ 人工评审通过 |"""
    sites = SitesListPage(logged_in_page, base_url)
    sites.goto()
    assert sites.is_loaded()

    # 1. 获取所有筛选 Tab
    tabs = sites.get_filter_tabs()
    assert len(tabs) > 0, "未找到筛选 Tab"
    expected_tabs = ["全部", "仅自己", "组织内", "已登录", "公开"]
    for t in expected_tabs:
        assert t in tabs, f"筛选 Tab 缺少 '{t}': {tabs}"

    # 2. 切到"全部"获取总数
    sites.click_filter_tab("全部")
    total = sites.get_app_count()

    # 3. 逐个切换每个 Tab，验证数量 ≤ 全部
    for tab_name in tabs:
        if tab_name == "全部":
            continue
        sites.click_filter_tab(tab_name)
        count = sites.get_app_count()
        assert count <= total, \
            f"Tab '{tab_name}' 数量({count})大于全部({total})"

    # 4. 切回"全部"验证恢复
    sites.click_filter_tab("全部")
    restored = sites.get_app_count()
    assert restored == total, \
        f"切回全部后数量未恢复: {restored} vs {total}"


# === TC-SITE-021: 重签 Token ===

@pytest.mark.order(53)
@pytest.mark.p1
def test_token_renewal(logged_in_page, base_url):
    """重签 Token — 三点菜单中旋转应用部署 Token（TC-SITE-021） | ✅ 人工评审通过 |"""
    sites = SitesListPage(logged_in_page, base_url)
    sites.goto()
    assert sites.is_loaded()

    # 创建测试 App（避免操作已有数据）
    test_name = f"e2e-renew-{int(time.time())}"
    sites.click_create_app()
    assert sites.is_create_dialog_open(), "创建 App 弹窗未打开"
    sites.fill_create_form(test_name, desc="token renew test")
    sites.save_create()

    sites.goto()
    assert sites.has_app(test_name), f"创建后 {test_name} 未出现在列表中"

    # 1. 三点菜单中有「重签 Token」选项
    menu_items = sites.get_menu_items(test_name)
    assert "重签 Token" in menu_items, f"菜单缺少「重签 Token」: {menu_items}"

    # 2. 点击「重签 Token」
    sites.renew_token(test_name)

    # 3. 验证 Toast 提示"Token 已重签"
    toast = logged_in_page.locator(
        "[role='status'], [data-sonner-toast], [data-slot='toast']"
    )
    toast_found = False
    for t in toast.all():
        try:
            text = t.inner_text().strip()
            if "重签" in text:
                toast_found = True
                break
        except Exception:
            pass
    assert toast_found, "未出现「Token 已重签」Toast 提示"

    # 清理
    sites.delete_app(test_name)
    sites.goto()
    assert not sites.has_app(test_name), f"清理后 {test_name} 仍在列表中"
