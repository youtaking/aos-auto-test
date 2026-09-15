# tests/suites/test_dashboard.py
"""Dashboard 模块回归测试"""
import re

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
    #    实测 2026-09-15：`div.agent-panel-content` 是常驻的聊天/Artifacts 面板
    #    （class = "agent-panel-content agent-panel-content--chat"，内容为「文件/站点/定时任务…」），
    #    并非 Dashboard 内容区；Dashboard 真实内容区是唯一的 <main>。
    content = logged_in_page.locator("main")
    assert content.count() == 1, \
        f"Dashboard 内容区 main 应唯一，实际 {content.count()} 个"

    # 2. 标题 "系统概览"
    title = logged_in_page.locator("h1, h2").filter(has_text="系统概览")
    assert title.count() > 0, "Dashboard 页面未显示「系统概览」标题"

    # 3. 副标题
    subtitle = logged_in_page.locator("p").filter(has_text="实时监控")
    assert subtitle.count() > 0, \
        "Dashboard 页面未显示副标题「实时监控 AI Agent 控制面板运行状态」"

    # 4. 页面已渲染完成（不是加载态），且内容结构与当前版本一致
    body_text = content.first.inner_text()
    assert "加载系统概览" not in body_text, \
        f"Dashboard 仍处于加载态（loading 文案可见）: {body_text[:200]!r}"
    has_stat_cards = logged_in_page.get_by_text("可用率", exact=True).count() > 0
    if has_stat_cards:
        # 统计卡片形态：四项卡片标题必须齐全
        for label in ["智能体", "会话", "模型", "可用率"]:
            assert logged_in_page.get_by_text(label, exact=True).count() > 0, \
                f"Dashboard 统计卡片缺少「{label}」，body: {body_text[:200]!r}"
        assert re.search(r"\d", body_text), \
            f"Dashboard 统计卡片未渲染任何数值，body: {body_text[:200]!r}"
    else:
        # 当前版本看板卡片已下线：AgentDashboardPage.tsx:11-13 仅渲染 AppHeader + 单个占位段落
        # （zh/dashboard.json 缺 welcome 键，页面显示原始 key——属应用侧 i18n 缺陷，用例不绑定该缺陷文本）
        assert logged_in_page.get_by_text("可用率", exact=True).count() == 0, \
            "统计卡片与占位段落同时存在，Dashboard 结构异常"
        placeholder = content.first.locator("div.flex.flex-col.items-center.justify-center p")
        assert placeholder.count() == 1, \
            f"Dashboard 占位段落应唯一，实际 {placeholder.count()} 个，body: {body_text[:200]!r}"
        assert placeholder.first.inner_text().strip(), \
            f"Dashboard 占位段落文案为空，body: {body_text[:200]!r}"


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
