# tests/pages/login_page.py
"""登录页面 Page Object"""
from playwright.sync_api import Page


class LoginPage:
    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/login"

    def goto(self):
        self.page.goto(self.url)
        self.page.wait_for_load_state("networkidle")

    def login(self, email: str, password: str):
        self.page.fill('input[name="email"], input[type="email"]', email)
        self.page.fill('input[name="password"], input[type="password"]', password)
        self.page.click('button[type="submit"]')
        self.page.wait_for_load_state("networkidle")

    def is_logged_in(self) -> bool:
        return "/login" not in self.page.url

    def get_error_message(self) -> str:
        error = self.page.locator('[role="alert"], .error-message, .text-red-500').first
        if error.is_visible():
            return error.text_content() or ""
        return ""

    def is_on_login_page(self) -> bool:
        return "/login" in self.page.url
