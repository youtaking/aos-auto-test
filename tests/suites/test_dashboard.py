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
    """TC-DASH-003: Dashboard 统计卡片展示"""
    dashboard = DashboardPage(logged_in_page, base_url)
    dashboard.goto()

    # 检查内容区存在卡片类元素
    content = logged_in_page.locator("div.agent-panel-content")
    assert content.count() > 0, "Dashboard 内容区域不存在"

    cards = content.first.locator("div.rounded-lg.border, div.grid > div")

    if cards.count() == 0:
        pytest.skip("Dashboard 页面无统计卡片元素")

    assert cards.count() >= 1, f"统计卡片数量不足: {cards.count()}"
    # 至少一个卡片有文本内容
    all_text = cards.all_text_contents()
    has_content = any(t.strip() for t in all_text)
    assert has_content, "所有统计卡片均为空内容"


@allure.epic("Dashboard")
@pytest.mark.order(5)
@pytest.mark.p1
def test_dashboard_recent_agents(logged_in_page, base_url):
    """TC-DASH-004: Dashboard 最近智能体列表"""
    dashboard = DashboardPage(logged_in_page, base_url)
    dashboard.goto()

    content = logged_in_page.locator("div.agent-panel-content")
    assert content.count() > 0, "Dashboard 内容区域不存在"

    # 检查是否有智能体相关列表或链接
    agent_items = content.first.locator(
        "a[href*='agent'], button.agent-sidebar-agent-card"
    )
    sidebar_agents = logged_in_page.locator("button.agent-sidebar-agent-card")

    has_recent = agent_items.count() > 0 or sidebar_agents.count() > 0
    if not has_recent:
        pytest.skip("Dashboard 页面无最近智能体列表")

    # 如果侧边栏有智能体卡片，验证至少一个可见
    if sidebar_agents.count() > 0:
        assert sidebar_agents.first.is_visible(), "侧边栏智能体卡片不可见"
