# tests/pages/dashboard_page.py
"""Dashboard 页面 Page Object"""
from playwright.sync_api import Page, TimeoutError


class DashboardPage:
    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/dashboard"

    def goto(self):
        for _attempt in range(2):
            try:
                self.page.goto(self.url, wait_until="domcontentloaded")
            except Exception:
                pass  # SPA 路由可能中断初始导航
            self.page.wait_for_load_state("domcontentloaded")
            try:
                self.page.get_by_role("heading", name="系统概览", exact=True).wait_for(timeout=15000)
            except TimeoutError:
                pass
            if self.is_loaded():
                break
            try:
                self.page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
            self.page.wait_for_timeout(500)

    def is_loaded(self) -> bool:
        if "/ctrl/agent/dashboard" not in self.page.url:
            return False
        try:
            self.page.get_by_role("heading", name="系统概览", exact=True).wait_for(timeout=15000)
            return True
        except TimeoutError:
            return False

    def has_sidebar(self) -> bool:
        return self.page.locator("nav, aside, aside.agent-sidebar").first.is_visible()

    def navigate_to(self, menu_text: str):
        self.page.get_by_text(menu_text).click()
        self.page.wait_for_load_state("domcontentloaded")
