# tests/pages/dashboard_page.py
"""Dashboard 页面 Page Object"""
from playwright.sync_api import Page


class DashboardPage:
    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/dashboard"

    def goto(self):
        try:
            self.page.goto(self.url, wait_until="domcontentloaded")
        except Exception:
            pass  # SPA 路由可能中断初始导航
        self.page.wait_for_load_state("domcontentloaded")

    def is_loaded(self) -> bool:
        return (
            "dashboard" in self.page.url.lower()
            and self.page.locator("h1, h2").filter(has_text="系统概览").count() > 0
        )

    def has_sidebar(self) -> bool:
        return self.page.locator("nav, aside, aside.agent-sidebar").first.is_visible()

    def navigate_to(self, menu_text: str):
        self.page.get_by_text(menu_text).click()
        self.page.wait_for_load_state("domcontentloaded")
