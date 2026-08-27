# tests/suites/test_admin.py
"""Admin 管理面板 E2E 测试 — 基于真实 DOM 探查
覆盖 Observer 观察中心、人员管理、系统日志三个子页面
Master Key 认证流程 + 各子页面功能验证
"""
import pytest
import allure
from tests.pages.admin_page import AdminPage


@pytest.fixture
def master_key(test_config):
    """获取 Master Key"""
    key = test_config.get("fenixagent", {}).get("system_api_key", "")
    if not key:
        pytest.skip("test_data.yaml 中未配置 system_api_key")
    return key


@pytest.fixture
def admin_page_obj(logged_in_page, base_url):
    """创建 AdminPage 实例"""
    return AdminPage(logged_in_page, base_url)


def _ensure_authenticated(admin_page_obj, master_key):
    """确保 Admin 已通过 Master Key 认证"""
    admin_page_obj.goto()
    if admin_page_obj.is_master_key_gate_visible():
        admin_page_obj.authenticate(master_key)


# ═══════════════════════════════════════════════════════
# TC-ADMIN-001: Master Key 认证流程
# ═══════════════════════════════════════════════════════

@allure.epic("Admin")
@allure.feature("Master Key 认证")
@pytest.mark.order(90)
@pytest.mark.p0
def test_admin_001_master_key_gate(admin_page_obj, master_key):
    """TC-ADMIN-001: Master Key 认证 — 门禁展示、输入、进入"""
    admin_page_obj.goto()

    # 1. 门禁可见
    assert admin_page_obj.is_master_key_gate_visible(), \
        "Admin 页面未显示 Master Key 认证门禁"

    # 2. 未输入时按钮禁用
    assert admin_page_obj.is_enter_button_disabled(), \
        "未输入 Master Key 时'进入面板'按钮应为禁用状态"

    # 3. 输入 Master Key 后按钮启用
    admin_page_obj.enter_master_key(master_key)
    assert not admin_page_obj.is_enter_button_disabled(), \
        "输入 Master Key 后'进入面板'按钮应为启用状态"

    # 4. 点击进入，门禁消失
    admin_page_obj.click_enter()
    # 等待门禁消失（轮询检查，最多 5 秒）
    for _wait in range(10):
        if not admin_page_obj.is_master_key_gate_visible():
            break
        admin_page_obj.page.wait_for_timeout(500)
    assert not admin_page_obj.is_master_key_gate_visible(), \
        "Master Key 认证通过后门禁应消失"

    # 5. Observer 页面加载
    assert admin_page_obj.is_observer_loaded(), \
        "认证后未自动进入 Observer 观察中心"


# ═══════════════════════════════════════════════════════
# TC-ADMIN-002: Observer 观察中心
# ═══════════════════════════════════════════════════════

@allure.epic("Admin")
@allure.feature("Observer 观察中心")
@pytest.mark.order(91)
@pytest.mark.p0
def test_admin_002_observer_center(admin_page_obj, master_key):
    """TC-ADMIN-002: Observer 观察中心 — 统计卡片、Tab、刷新"""
    _ensure_authenticated(admin_page_obj, master_key)

    # 1. Observer 页面加载
    assert admin_page_obj.is_observer_loaded(), \
        "Observer 观察中心页面未加载"

    # 2. 统计卡片数据
    stats = admin_page_obj.get_observer_stats()
    assert "观察总数" in stats, "缺少'观察总数'统计卡片"
    assert "活跃 machine" in stats, "缺少'活跃 machine'统计卡片"
    assert "一致性问题" in stats, "缺少'一致性问题'统计卡片"
    assert "最后更新" in stats, "缺少'最后更新'统计卡片"

    # 3. Tab 列表
    tabs = admin_page_obj.get_observer_tabs()
    assert "归属树" in tabs, "缺少'归属树'Tab"
    assert "machine 树" in tabs, "缺少'machine 树'Tab"
    assert "全部观察" in tabs, "缺少'全部观察'Tab"

    # 4. 功能按钮
    assert admin_page_obj.has_refresh_button(), "缺少'刷新'按钮"
    assert admin_page_obj.has_exit_button(), "缺少'退出'按钮"

    # 5. 侧边栏导航
    nav_links = admin_page_obj.get_nav_links()
    assert len(nav_links) > 0, "侧边栏无任何导航链接"
    assert any(kw in link for link in nav_links for kw in ["Observer", "观察"]), \
        f"侧边栏缺少 Observer 导航链接，当前: {nav_links}"
    assert any("人员管理" in link for link in nav_links), \
        f"侧边栏缺少'人员管理'导航链接，当前: {nav_links}"
    assert any("系统日志" in link for link in nav_links), \
        f"侧边栏缺少'系统日志'导航链接，当前: {nav_links}"
    assert any("沙盒管理" in link for link in nav_links), \
        f"侧边栏缺少'沙盒管理'导航链接，当前: {nav_links}"

    # "返回主控制台"链接
    return_link = admin_page_obj.page.locator("a:has-text('返回')")
    assert return_link.count() > 0, \
        "缺少'返回'主控制台链接"


# ═══════════════════════════════════════════════════════
# TC-ADMIN-003: 人员管理页面
# ═══════════════════════════════════════════════════════

@allure.epic("Admin")
@allure.feature("人员管理")
@pytest.mark.order(92)
@pytest.mark.p0
def test_admin_003_people_management(admin_page_obj, master_key):
    """TC-ADMIN-003: 人员管理 — 页面加载、功能按钮、人员树"""
    _ensure_authenticated(admin_page_obj, master_key)

    # 1. 导航到人员管理
    admin_page_obj.click_nav_link("人员管理")
    assert admin_page_obj.is_people_page_loaded(), \
        "人员管理页面未加载"

    # 2. 功能按钮
    buttons = admin_page_obj.has_people_buttons()
    assert any("刷新" in b for b in buttons), \
        f"人员管理页缺少'刷新'按钮，当前按钮: {buttons}"

    # 3. 页面内容非空（有人员树数据）
    main_text = admin_page_obj.page.locator("main").inner_text()
    assert len(main_text.strip()) > 0, "人员管理页面内容为空"

    # 4. 验证页面描述文本
    main_text_lower = main_text.lower()
    assert any(kw in text for kw, text in [("master key", main_text_lower), ("受", main_text)]), \
        f"人员管理页面缺少保护说明文本，main_text 前200字符: {main_text[:200]!r}"


# ═══════════════════════════════════════════════════════
# TC-ADMIN-004: 系统日志页面
# ═══════════════════════════════════════════════════════

@allure.epic("Admin")
@allure.feature("系统日志")
@pytest.mark.order(93)
@pytest.mark.p0
def test_admin_004_system_logs(admin_page_obj, master_key):
    """TC-ADMIN-004: 系统日志 — 页面加载、日志文件列表、搜索"""
    _ensure_authenticated(admin_page_obj, master_key)

    # 1. 导航到系统日志
    admin_page_obj.click_nav_link("系统日志")
    assert admin_page_obj.is_logs_page_loaded(), \
        "系统日志页面未加载"

    # 2. 刷新按钮
    assert admin_page_obj.has_refresh_button(), "缺少'刷新'按钮"

    # 3. 搜索输入框
    assert admin_page_obj.has_log_search_input(), \
        "缺少日志搜索输入框"

    # 4. 日志文件列表非空
    log_files = admin_page_obj.get_log_files()
    assert len(log_files) > 0, "日志文件列表为空"

    # 5. 验证有当日日志文件
    from datetime import date
    today = date.today().strftime("%Y-%m-%d")
    has_today = any(today in f for f in log_files)
    assert has_today, f"未找到当日 ({today}) 的日志文件，当前文件: {log_files[:5]}"

    # 6. 验证有错误日志文件
    has_error_logs = any("err" in f for f in log_files)
    # 错误日志可能存在也可能不存在，不做强制断言
    if has_error_logs:
        allure.attach(
            f"发现错误日志文件: {[f for f in log_files if 'err' in f][:5]}",
            name="错误日志",
            attachment_type=allure.attachment_type.TEXT,
        )


# ═══════════════════════════════════════════════════════
# TC-ADMIN-005: 退出功能
# ═══════════════════════════════════════════════════════

@allure.epic("Admin")
@allure.feature("Master Key 认证")
@pytest.mark.order(94)
@pytest.mark.p1
def test_admin_005_exit_button(admin_page_obj, master_key):
    """TC-ADMIN-005: 退出 — 点击退出后清除认证状态"""
    _ensure_authenticated(admin_page_obj, master_key)

    # 1. 确认已认证
    assert admin_page_obj.is_observer_loaded(), \
        "Observer 观察中心未加载"

    # 2. 点击退出
    exit_btn = admin_page_obj.page.get_by_role("button", name="退出")
    exit_btn.click()
    admin_page_obj.page.wait_for_timeout(1500)

    # 3. 退出后应重新显示 Master Key 门禁
    assert admin_page_obj.is_master_key_gate_visible(), \
        "退出后未回到 Master Key 认证门禁"


# ═══════════════════════════════════════════════════════
# P1 补充: 管理面板子页面深度覆盖
# ═══════════════════════════════════════════════════════

@allure.epic("Admin")
@allure.feature("子页面导航")
@pytest.mark.order(95)
@pytest.mark.p1
def test_admin_subpages(admin_page_obj, master_key):
    """验证管理面板子页面深度覆盖 — 导航到 Observer/日志等子页面并验证加载"""
    _ensure_authenticated(admin_page_obj, master_key)

    # 确认 Observer 已加载
    assert admin_page_obj.is_observer_loaded(), \
        "Admin 认证后 Observer 观察中心未加载"

    # 获取侧边栏导航链接
    nav_links = admin_page_obj.get_nav_links()
    if not nav_links:
        pytest.skip("侧边栏无导航链接，无法进入子页面")

    # 尝试进入系统日志子页面
    entered_subpage = False

    if any("系统日志" in link for link in nav_links):
        admin_page_obj.click_nav_link("系统日志")
        admin_page_obj.page.wait_for_timeout(2000)

        if admin_page_obj.is_logs_page_loaded():
            entered_subpage = True
            # 验证日志页面功能元素
            log_files = admin_page_obj.get_log_files()
            has_search = admin_page_obj.has_log_search_input()

            allure.attach(
                f"日志文件数: {len(log_files)}, 搜索框: {has_search}",
                name="系统日志子页面",
                attachment_type=allure.attachment_type.TEXT,
            )

            # 至少有搜索框或日志文件列表
            assert len(log_files) > 0 or has_search, \
                "系统日志页面既无日志文件列表也无搜索框"

    if not entered_subpage and any("人员管理" in link for link in nav_links):
        admin_page_obj.click_nav_link("人员管理")
        admin_page_obj.page.wait_for_timeout(2000)

        if admin_page_obj.is_people_page_loaded():
            entered_subpage = True
            buttons = admin_page_obj.has_people_buttons()
            allure.attach(
                f"人员管理按钮: {buttons}",
                name="人员管理子页面",
                attachment_type=allure.attachment_type.TEXT,
            )

    if not entered_subpage:
        # 尝试点击其他可用的导航链接
        for link_text in nav_links:
            if link_text and link_text not in ("Observer", "观察中心"):
                try:
                    admin_page_obj.click_nav_link(link_text)
                    admin_page_obj.page.wait_for_timeout(2000)
                    # 验证页面有内容
                    body_text = admin_page_obj.page.locator("main, [role='main']").first.inner_text()
                    if len(body_text.strip()) > 10:
                        entered_subpage = True
                        allure.attach(
                            f"进入子页面: {link_text}, 内容长度: {len(body_text)}",
                            name="子页面导航",
                            attachment_type=allure.attachment_type.TEXT,
                        )
                        break
                except Exception:
                    continue

    assert entered_subpage, \
        f"无法进入任何 Admin 子页面，导航链接: {nav_links}"


# ═══════════════════════════════════════════════════════
# P0: 沙盒管理页（/ctrl/admin/sandbox）覆盖
# 数据安全：全部只读（导航/列表加载/弹窗字段校验），不创建/不提交/不删除
# ═══════════════════════════════════════════════════════

def _goto_sandbox(admin_page_obj, master_key):
    """认证 + 导航到沙盒管理页"""
    _ensure_authenticated(admin_page_obj, master_key)
    admin_page_obj.click_nav_link("沙盒管理")
    assert admin_page_obj.is_sandbox_page_loaded(), \
        "沙盒管理页未加载"


@allure.epic("Admin")
@allure.feature("沙盒管理")
@pytest.mark.order(96)
@pytest.mark.p0
def test_admin_006_sandbox_navigation(admin_page_obj, master_key):
    """TC-ADMIN-006: 沙盒管理 — 侧边栏导航 + 页面结构（h1/双Tab/新建资源池/刷新）"""
    _goto_sandbox(admin_page_obj, master_key)

    # 1. h1 标题
    assert admin_page_obj.is_sandbox_page_loaded(), "沙盒管理页标题未显示"

    # 2. 双 Tab（沙盒管理 / Cluster 管理）
    tabs = admin_page_obj.get_sandbox_tabs()
    assert "沙盒管理" in tabs, f"缺少'沙盒管理'Tab，当前: {tabs}"
    assert "Cluster 管理" in tabs, f"缺少'Cluster 管理'Tab，当前: {tabs}"

    # 3. 新建资源池按钮 + 刷新按钮
    assert admin_page_obj.has_sandbox_create_pool_button(), "缺少'新建资源池'按钮"
    assert admin_page_obj.has_refresh_button(), "缺少'刷新'按钮"


@allure.epic("Admin")
@allure.feature("沙盒管理")
@pytest.mark.order(97)
@pytest.mark.p1
def test_admin_007_sandbox_pools_list(admin_page_obj, master_key):
    """TC-ADMIN-007: 沙盒管理 — 资源池列表 + 实例状态点（只读）"""
    _goto_sandbox(admin_page_obj, master_key)

    # 前置：等待资源池树加载完成（新建按钮出现 = 加载结束），再判断是否有资源池
    assert admin_page_obj.has_sandbox_create_pool_button(), "资源池列表未加载"
    cards = admin_page_obj.get_sandbox_pool_cards()
    if cards.count() == 0:
        pytest.skip("沙盒环境无资源池，跳过资源池列表校验")

    # 1. 每个资源池摘要含名称与实例数
    summaries = admin_page_obj.get_sandbox_pool_summaries()
    assert len(summaries) > 0, "资源池摘要为空"
    for s in summaries:
        assert "个实例" in s, f"资源池摘要缺少实例数: {s[:60]}"

    # 2. 首个资源池卡片操作按钮（详情/删除）
    btns = admin_page_obj.get_sandbox_pool_card_buttons()
    assert "详情" in btns, f"资源池卡片缺少'详情'按钮: {btns}"
    assert "删除" in btns, f"资源池卡片缺少'删除'按钮: {btns}"

    # 3. 实例状态点存在（可点击查看 Provider Payload）
    assert admin_page_obj.has_sandbox_status_dot(), "未找到实例状态圆点"

    # 4. 点击状态点打开 Provider Payload 弹窗（只读 JSON）
    admin_page_obj.page.locator("button[title*='状态']").first.click()
    assert admin_page_obj.is_sandbox_dialog_open(), "点击状态点后未弹出 Provider Payload"
    assert "Provider Payload" in admin_page_obj.get_sandbox_dialog_title(), \
        f"弹窗标题应为 Provider Payload: {admin_page_obj.get_sandbox_dialog_title()}"
    admin_page_obj.close_sandbox_dialog()


@allure.epic("Admin")
@allure.feature("沙盒管理")
@pytest.mark.order(98)
@pytest.mark.p1
def test_admin_008_sandbox_create_pool_dialog(admin_page_obj, master_key):
    """TC-ADMIN-008: 沙盒管理 — 新建资源池弹窗字段校验（只读，不提交）"""
    _goto_sandbox(admin_page_obj, master_key)

    # 1. 打开新建资源池弹窗
    admin_page_obj.open_sandbox_create_pool_dialog()
    assert admin_page_obj.is_sandbox_dialog_open(), "新建资源池弹窗未打开"
    assert admin_page_obj.get_sandbox_dialog_title() == "新建资源池", \
        f"弹窗标题应为'新建资源池': {admin_page_obj.get_sandbox_dialog_title()}"

    # 2. 字段完整
    labels = admin_page_obj.get_sandbox_dialog_labels()
    for required in ("ID", "名称", "Provider", "镜像", "默认资源配置 JSON"):
        assert required in labels, f"新建资源池弹窗缺少字段'{required}'，当前: {labels}"

    # 3. 新建模式下字段可编辑（readonly=0）
    assert admin_page_obj.get_sandbox_dialog_readonly_count() == 0, \
        "新建资源池弹窗字段应为可编辑状态"

    # 4. 关闭（不提交）
    admin_page_obj.close_sandbox_dialog()
    assert not admin_page_obj.is_sandbox_dialog_open(), "弹窗未关闭"


@allure.epic("Admin")
@allure.feature("沙盒管理")
@pytest.mark.order(99)
@pytest.mark.p1
def test_admin_009_sandbox_pool_detail_dialog(admin_page_obj, master_key):
    """TC-ADMIN-009: 沙盒管理 — 资源池详情弹窗只读校验（不编辑/不保存）"""
    _goto_sandbox(admin_page_obj, master_key)

    # 前置：等待资源池树加载完成，再判断是否有资源池
    assert admin_page_obj.has_sandbox_create_pool_button(), "资源池列表未加载"
    cards = admin_page_obj.get_sandbox_pool_cards()
    if cards.count() == 0:
        pytest.skip("沙盒环境无资源池，跳过详情弹窗校验")

    # 1. 打开第一个资源池详情
    admin_page_obj.open_sandbox_first_pool_detail()
    assert admin_page_obj.is_sandbox_dialog_open(), "资源池详情弹窗未打开"

    # 2. 标题为资源池名称
    pool_name = admin_page_obj.get_sandbox_pool_summaries()[0].split()[0]
    assert admin_page_obj.get_sandbox_dialog_title() == pool_name, \
        f"详情弹窗标题应为资源池名称'{pool_name}': {admin_page_obj.get_sandbox_dialog_title()}"

    # 3. 字段完整
    labels = admin_page_obj.get_sandbox_dialog_labels()
    for required in ("ID", "名称", "Provider", "默认资源配置 JSON"):
        assert required in labels, f"详情弹窗缺少字段'{required}'，当前: {labels}"

    # 4. 只读模式（readonly > 0），不进入编辑态
    assert admin_page_obj.get_sandbox_dialog_readonly_count() > 0, \
        "资源池详情弹窗应处于只读模式"

    # 5. 关闭
    admin_page_obj.close_sandbox_dialog()
    assert not admin_page_obj.is_sandbox_dialog_open(), "弹窗未关闭"


@allure.epic("Admin")
@allure.feature("沙盒管理")
@pytest.mark.order(100)
@pytest.mark.p1
@pytest.mark.no_page_error_check  # 已知问题：外部 cluster 服务返回的 transportMode 非 direct/tunnel 触发 400（见评审报告），本用例校验 tab 切换两种状态均可
def test_admin_010_sandbox_cluster_tab(admin_page_obj, master_key):
    """TC-ADMIN-010: 沙盒管理 — Cluster 管理 Tab 切换（环境无 cluster 数据时允许重试态）"""
    _goto_sandbox(admin_page_obj, master_key)

    # 1. 切换到 Cluster 管理
    admin_page_obj.click_sandbox_tab("Cluster 管理")
    admin_page_obj.page.wait_for_timeout(1500)

    # 2. Cluster 面板加载（Cluster Pool 卡片 或 错误重试卡片，取决于环境配置）
    status = admin_page_obj.get_sandbox_cluster_status()
    assert status in ("loaded", "retry"), \
        f"Cluster 面板既未加载也未显示重试，status={status}"

    # 3. 切回沙盒管理 Tab，确认可往返
    admin_page_obj.click_sandbox_tab("沙盒管理")
    admin_page_obj.page.wait_for_timeout(800)
    assert admin_page_obj.is_sandbox_page_loaded(), "切回沙盒管理 Tab 后页面异常"
