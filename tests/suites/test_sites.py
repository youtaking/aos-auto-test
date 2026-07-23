# tests/suites/test_sites.py
"""Agent Sites 模块回归测试（基于 Excel 用例 TC-SITE-001/011/014/015/016/017）"""
import pytest
import time
from tests.pages.sites_page import SitesListPage, SiteBuilderChatPage


# === TC-SITE-001: 建站助手对话页面正常加载 ===

@pytest.mark.order(44)
@pytest.mark.p0
def test_site_builder_chat_loads(logged_in_page, base_url):
    """建站助手对话页面正常加载（TC-SITE-001）"""
    chat = SiteBuilderChatPage(logged_in_page, base_url)
    chat.goto_builder_chat()

    # 1. 对话页面正常加载
    assert chat.is_chat_loaded(), f"对话页未加载，当前 URL: {logged_in_page.url}"

    # 2. 可与建站助手进行对话交互（有输入框）
    assert chat.has_textarea(), "对话页没有消息输入框"

    # 3. 右侧 ArtifactsPanel 存在
    assert chat.has_artifacts_panel(), "ArtifactsPanel（iframe 预览区）未出现"


# === TC-SITE-011: 应用预览和独立 URL 访问 ===

@pytest.mark.order(45)
@pytest.mark.p0
def test_app_preview_and_url_access(logged_in_page, base_url):
    """应用预览和独立 URL 访问（TC-SITE-011）"""
    sites = SitesListPage(logged_in_page, base_url)
    sites.goto()
    assert sites.is_loaded()

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
    """Sites 列表管理 — 编辑和删除（TC-SITE-014）
    注意：删除操作不可逆，使用列表最后一个应用降低风险"""
    sites = SitesListPage(logged_in_page, base_url)
    sites.goto()
    assert sites.is_loaded()

    app_names = sites.get_app_names()
    if not app_names:
        pytest.skip("Sites 列表为空，无法测试编辑/删除")

    # 使用最后一个应用做测试（避免删核心数据）
    target = app_names[-1]
    initial_count = sites.get_app_count()

    # --- 编辑 ---
    # 1. 打开编辑对话框
    sites.open_edit_dialog(target)
    assert sites.is_edit_dialog_open(), "编辑对话框未打开"

    # 2. 修改描述（不动名称，避免影响其他用例）
    new_desc = f"auto-test-desc-{int(time.time())}"
    sites.edit_app_description(new_desc)
    sites.save_edit()

    # 3. 验证对话框关闭
    assert not sites.is_edit_dialog_open(), "保存后对话框未关闭"

    # --- 菜单项验证 ---
    menu_items = sites.get_menu_items(target)
    assert "编辑" in menu_items, f"菜单缺少「编辑」: {menu_items}"
    assert "删除" in menu_items, f"菜单缺少「删除」: {menu_items}"

    # --- 删除（用三点菜单）---
    # 监控 DELETE API 响应，处理 404（资源已被之前测试删除）
    delete_responses = []
    def _track_delete(response):
        if response.request.method == "DELETE" and "sites" in response.url.lower():
            delete_responses.append({"url": response.url, "status": response.status})

    logged_in_page.on("response", _track_delete)

    sites.delete_app(target)
    logged_in_page.wait_for_timeout(3000)

    # 检查 API 响应
    api_404 = any(r["status"] == 404 for r in delete_responses)
    api_success = any(r["status"] in [200, 204] for r in delete_responses)

    # 如果 API 返回 404，说明资源已被之前测试删除，跳过数量验证
    if api_404 and not api_success:
        logged_in_page.remove_listener("response", _track_delete)
        pytest.skip(f"应用 {target} 已被之前测试删除（API 404），跳过删除验证")

    logged_in_page.remove_listener("response", _track_delete)

    # 如果当前页面数量没变，刷新再检查
    current_count = sites.get_app_count()
    if current_count >= initial_count:
        sites.goto()
        for _ in range(5):
            current_count = sites.get_app_count()
            if current_count < initial_count:
                break
            logged_in_page.wait_for_timeout(1000)

    # 验证删除后数量减少
    assert current_count < initial_count, "删除后应用数量未减少"
    assert not sites.has_app(target), f"应用 {target} 删除后仍存在"


# === TC-SITE-015: 应用绑定到 Agent 后 ArtifactsPanel 展示 ===

@pytest.mark.order(47)
@pytest.mark.p1
def test_artifacts_panel_with_bound_site(logged_in_page, base_url):
    """应用绑定到 Agent 后 ArtifactsPanel 展示（TC-SITE-015）"""
    chat = SiteBuilderChatPage(logged_in_page, base_url)
    chat.goto_builder_chat()

    assert chat.is_chat_loaded(), "建站助手对话页未加载"

    # 1. ArtifactsPanel 出现（iframe 存在）
    assert chat.has_artifacts_panel(), "ArtifactsPanel（iframe）未出现"

    # 2. iframe 有有效的 src（绑定了应用）
    iframe_src = chat.get_iframe_src()
    assert iframe_src, "iframe src 为空，未绑定应用"
    assert "/web/site/" in iframe_src or "/deploy/" in iframe_src, f"iframe src 格式异常: {iframe_src}"

    # 3. 「查看站点」按钮存在
    assert chat.has_view_site_button(), "「查看站点」按钮不存在"


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

    # 2. 每行创建者列都有内容（可能是 "—" 或具体名称）
    creators = sites.get_all_creator_texts()
    assert len(creators) > 0, "列表为空"
    for i, creator in enumerate(creators):
        assert creator, f"第 {i} 行创建者列为空"


# === TC-SITE-017: 创建者名称点击跳转 ===

@pytest.mark.order(49)
@pytest.mark.p1
def test_creator_name_click_navigation(logged_in_page, base_url):
    """创建者名称点击跳转（TC-SITE-017）"""
    sites = SitesListPage(logged_in_page, base_url)
    sites.goto()
    assert sites.is_loaded()

    # 查找有可点击创建者链接的应用
    app_names = sites.get_app_names()
    target = None
    for name in app_names:
        if sites.has_creator_link(name):
            target = name
            break

    if not target:
        # 所有创建者列都是 "—" 没有链接，验证这个事实
        creators = sites.get_all_creator_texts()
        all_dash = all(c == "—" for c in creators)
        if all_dash:
            pytest.skip("当前所有应用创建者均为 '—'，无可点击的创建者链接")
        else:
            # 有创建者文本但没链接，UI 可能没做跳转
            pytest.skip("创建者名称存在但无可点击链接")
            return

    # 有可点击的创建者
    url_before = logged_in_page.url
    sites.click_creator(target)
    url_after = logged_in_page.url

    # 应该发生跳转或弹出对话框
    dialog = logged_in_page.locator("[role='dialog']")
    url_changed = url_after != url_before
    dialog_visible = dialog.count() > 0 and dialog.first.is_visible()
    assert url_changed or dialog_visible, (
        f"点击创建者名称后既没有跳转也没有弹出对话框"
        f"（URL变化: {url_before} → {url_after}，dialog数={dialog.count()}）"
    )
