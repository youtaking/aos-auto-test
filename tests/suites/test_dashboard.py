# tests/suites/test_dashboard.py
"""Dashboard 模块回归测试"""
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
