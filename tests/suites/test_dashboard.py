# tests/suites/test_dashboard.py
"""Dashboard 模块回归测试"""
import allure
import pytest
from tests.pages.dashboard_page import DashboardPage


@pytest.mark.order(5)
@pytest.mark.p0
def test_dashboard_loads(logged_in_page, base_url):
    """Dashboard 页面能正常加载 | ✅ 人工评审通过（修复 is_loaded 选择器）|"""
    dashboard = DashboardPage(logged_in_page, base_url)
    dashboard.goto()
    assert dashboard.is_loaded()


@pytest.mark.order(5)
@pytest.mark.p0
def test_dashboard_has_title(logged_in_page, base_url):
    """Dashboard 显示「系统概览」标题 | ✅ 人工评审通过（修复选择器）|"""
    dashboard = DashboardPage(logged_in_page, base_url)
    dashboard.goto()
    title = logged_in_page.locator("h1, h2").filter(has_text="系统概览")
    assert title.count() > 0, "Dashboard 页面未显示「系统概览」标题"


@allure.epic("Dashboard")
@pytest.mark.order(5)
@pytest.mark.p1
def test_dashboard_stats_cards(logged_in_page, base_url):
    """TC-DASH-003: Dashboard 页面结构完整性（标题 + 副标题 + 内容区）"""
    dashboard = DashboardPage(logged_in_page, base_url)
    dashboard.goto()

    # 1. 内容区域存在
    content = logged_in_page.locator("div.agent-panel-content")
    assert content.count() > 0, "Dashboard 内容区域不存在"

    # 2. 标题 "系统概览"
    title = logged_in_page.locator("h1, h2").filter(has_text="系统概览")
    assert title.count() > 0, "Dashboard 页面未显示「系统概览」标题"

    # 3. 副标题
    subtitle = logged_in_page.locator("p").filter(has_text="实时监控")
    assert subtitle.count() > 0, \
        "Dashboard 页面未显示副标题「实时监控 AI Agent 控制面板运行状态」"

    # 4. 页面有可见文本内容（非空白页）
    body_text = content.first.inner_text()
    assert len(body_text.strip()) > 0, "Dashboard 内容区域为空白"


@allure.epic("Dashboard")
@pytest.mark.order(5)
@pytest.mark.p1
def test_dashboard_recent_agents(logged_in_page, base_url):
    """TC-DASH-004: Dashboard 页面侧边栏智能体列表可见"""
    dashboard = DashboardPage(logged_in_page, base_url)
    dashboard.goto()

    content = logged_in_page.locator("div.agent-panel-content")
    assert content.count() > 0, "Dashboard 内容区域不存在"

    # 等待侧边栏 agent 卡片加载（API 异步）
    sidebar_agents = logged_in_page.locator("button.agent-sidebar-agent-card")
    for _w in range(10):
        if sidebar_agents.count() > 0:
            break
        logged_in_page.wait_for_timeout(1000)

    assert sidebar_agents.count() > 0, \
        "Dashboard 页面侧边栏无智能体卡片（等待 10s 后仍未加载）"
    assert sidebar_agents.first.is_visible(), "侧边栏智能体卡片不可见"
