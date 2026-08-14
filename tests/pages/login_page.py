# tests/pages/login_page.py
"""登录页面 Page Object"""
from playwright.sync_api import Page


class LoginPage:
    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/login"

    def goto(self):
        try:
            self.page.goto(self.url, wait_until="domcontentloaded")
        except Exception:
            pass  # SPA 路由可能中断初始导航
        self.page.wait_for_load_state("networkidle")

    def login(self, email: str, password: str):
        self.page.fill("#auth-email", email)
        self.page.fill("#auth-password", password)
        self.page.click("button.auth-light-submit")
        # 等待 SPA 导航完成，URL 不再是登录页
        try:
            self.page.wait_for_url(
                lambda url: "/ctrl/login" not in url, timeout=10000
            )
        except Exception:
            pass

    def is_logged_in(self) -> bool:
        return "/ctrl/login" not in self.page.url

    def get_error_message(self) -> str:
        error = self.page.locator(".auth-light-error").first
        if error.is_visible():
            return error.text_content() or ""
        return ""

    def is_on_login_page(self) -> bool:
        return "/ctrl/login" in self.page.url
