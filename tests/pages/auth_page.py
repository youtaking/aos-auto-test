# tests/pages/auth_page.py
"""认证登录模块 Page Object — 基于真实 DOM 结构编写"""
from playwright.sync_api import Page


class AuthPage:
    """登录页 /ctrl/login"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/login"

    # ==================== 导航 ====================

    def goto(self):
        self.page.goto(self.url)
        self.page.wait_for_load_state("networkidle")

    def is_on_login_page(self) -> bool:
        return "/ctrl/login" in self.page.url

    def is_logged_in(self) -> bool:
        return "/ctrl/login" not in self.page.url

    # ==================== 登录表单 ====================

    def fill_email(self, email: str):
        self.page.fill("#auth-email", email)

    def fill_password(self, password: str):
        self.page.fill("#auth-password", password)

    def click_login(self):
        self.page.click("button.auth-light-submit")

    def login(self, email: str, password: str):
        self.fill_email(email)
        self.fill_password(password)
        self.click_login()
        try:
            self.page.wait_for_url(
                lambda url: "/ctrl/login" not in url, timeout=10000
            )
        except Exception:
            pass

    def get_email_value(self) -> str:
        return self.page.locator("#auth-email").input_value()

    def get_password_value(self) -> str:
        return self.page.locator("#auth-password").input_value()

    def get_email_validation(self) -> str:
        return self.page.evaluate("""() => {
            const el = document.querySelector('#auth-email');
            return el ? el.validationMessage : '';
        }""")

    def get_password_validation(self) -> str:
        return self.page.evaluate("""() => {
            const el = document.querySelector('#auth-password');
            return el ? el.validationMessage : '';
        }""")

    def is_email_required(self) -> bool:
        return self.page.evaluate("""() => {
            const el = document.querySelector('#auth-email');
            return el ? el.required : false;
        }""")

    def is_password_required(self) -> bool:
        return self.page.evaluate("""() => {
            const el = document.querySelector('#auth-password');
            return el ? el.required : false;
        }""")

    # ==================== 密码可见性 ====================

    def get_password_type(self) -> str:
        return self.page.locator("#auth-password").get_attribute("type") or ""

    def toggle_password_visibility(self):
        self.page.click("button.auth-light-toggle")
        self.page.wait_for_timeout(300)

    def get_toggle_aria_label(self) -> str:
        btn = self.page.locator("button.auth-light-toggle")
        if btn.count() > 0:
            return btn.get_attribute("aria-label") or ""
        return ""

    # ==================== 错误信息 ====================

    def get_error_message(self) -> str:
        error = self.page.locator(".auth-light-error")
        if error.count() > 0 and error.first.is_visible():
            return error.first.text_content().strip()
        return ""

    def has_error_message(self) -> bool:
        return len(self.get_error_message()) > 0

    # ==================== 登录 API 拦截 ====================

    def intercept_login_api(self):
        collected = []

        def on_response(resp):
            if "/api/auth/sign-in" in resp.url:
                try:
                    body = resp.json()
                except Exception:
                    body = None
                collected.append({
                    "url": resp.url,
                    "status": resp.status,
                    "method": resp.request.method,
                    "body": body,
                    "post_data": resp.request.post_data,
                })

        self.page.on("response", on_response)
        return collected

    def intercept_all_auth_api(self):
        collected = []

        def on_response(resp):
            if "/api/auth/" in resp.url:
                try:
                    body = resp.json()
                except Exception:
                    body = None
                collected.append({
                    "url": resp.url,
                    "status": resp.status,
                    "method": resp.request.method,
                    "body": body,
                    "post_data": resp.request.post_data,
                })

        self.page.on("response", on_response)
        return collected

    # ==================== 存储 ====================

    def get_session_cookie(self) -> str:
        cookies = self.page.context.cookies()
        for c in cookies:
            if "session" in c["name"].lower():
                return c["value"]
        return ""

    def has_session_cookie(self) -> bool:
        return len(self.get_session_cookie()) > 0

    def get_local_storage(self) -> dict:
        return self.page.evaluate("""() => {
            const ls = {};
            for (let i = 0; i < localStorage.length; i++) {
                const k = localStorage.key(i);
                ls[k] = localStorage.getItem(k).slice(0, 100);
            }
            return ls;
        }""")

    def clear_cookies(self):
        self.page.context.clear_cookies()

    # ==================== 用户菜单 ====================

    def click_user_button(self):
        btn = self.page.locator("button.agent-sidebar-user-button")
        btn.first.click(timeout=8000)   # Playwright 自动等待元素可见
        self.page.wait_for_timeout(1000)

    def get_user_name(self) -> str:
        btn = self.page.locator("button.agent-sidebar-user-button")
        if btn.count() > 0:
            return btn.first.text_content().strip()
        return ""

    def has_menu_item(self, text: str) -> bool:
        return self.page.get_by_role("menuitem", name=text).count() > 0

    def click_menu_item(self, text: str, fallback: str = ""):
        item = self.page.get_by_role("menuitem", name=text)
        try:
            item.first.click(timeout=5000)
        except Exception as e:
            if fallback:
                item = self.page.get_by_role("menuitem", name=fallback)
                try:
                    item.first.click(timeout=5000)
                except Exception:
                    raise RuntimeError(
                        f"菜单项 '{text}' 和 fallback '{fallback}' 均未找到或点击失败"
                    ) from e
            else:
                raise RuntimeError(f"菜单项 '{text}' 未找到或点击失败") from e
        self.page.wait_for_timeout(1500)

    def click_logout(self):
        self.click_user_button()
        self.click_menu_item("退出登录", "Logout")
        self.page.wait_for_timeout(1000)

    def click_change_password(self):
        self.click_user_button()
        self.click_menu_item("修改密码", "Change password")
        self.page.wait_for_timeout(1500)

    # ==================== 密码修改弹窗 ====================

    def is_dialog_open(self) -> bool:
        dialog = self.page.locator("[role=dialog]")
        return dialog.count() > 0 and dialog.first.is_visible()

    def get_dialog_title(self) -> str:
        dialog = self.page.locator("[role=dialog]")
        if dialog.count() > 0:
            h2 = dialog.locator("h2, h3")
            if h2.count() > 0:
                return h2.first.text_content().strip()
            return dialog.first.inner_text().split("\n")[0].strip()
        return ""

    def get_dialog_text(self) -> str:
        dialog = self.page.locator("[role=dialog]")
        if dialog.count() > 0:
            return dialog.first.inner_text().strip()
        return ""

    def get_password_inputs(self):
        dialog = self.page.locator("[role=dialog]")
        return dialog.locator("input[type=password]")

    def fill_change_password(self, old_pw: str, new_pw: str, confirm_pw: str):
        inputs = self.get_password_inputs()
        if inputs.count() >= 3:
            inputs.nth(0).fill(old_pw)
            inputs.nth(1).fill(new_pw)
            inputs.nth(2).fill(confirm_pw)

    def submit_change_password(self):
        dialog = self.page.locator("[role=dialog]")
        btn = dialog.get_by_role("button", name="修改密码")
        if btn.count() > 0:
            btn.first.click()
            self.page.wait_for_timeout(1000)

    def close_dialog(self):
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(500)

    def get_dialog_error(self) -> str:
        dialog = self.page.locator("[role=dialog]")
        errors = dialog.locator(".auth-light-error")
        if errors.count() == 0:
            errors = dialog.locator("[data-slot='form-message'], [role='alert']")
        if errors.count() > 0:
            return errors.first.text_content().strip()
        return ""

    # ==================== 侧边栏 ====================

    def has_sidebar(self) -> bool:
        return self.page.locator("button.agent-sidebar-user-button").count() > 0

    def get_sidebar_text(self) -> str:
        sidebar = self.page.locator("aside, nav, aside.agent-sidebar").first
        if sidebar.count() > 0:
            return sidebar.inner_text()
        return ""
