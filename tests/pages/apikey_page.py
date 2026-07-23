# tests/pages/apikey_page.py
"""API 密钥管理页面 Page Object — 基于真实 DOM 结构编写"""
from playwright.sync_api import Page


class ApiKeyPage:
    """API 密钥管理页 /ctrl/agent/apikeys"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/apikeys"

    # ==================== 导航 ====================

    def goto(self):
        self.page.goto(self.url)
        self.page.wait_for_load_state("networkidle")
        self.page.wait_for_timeout(2000)

    def goto_via_sidebar(self):
        btn = self.page.locator("button.agent-sidebar-nav-item").filter(has_text="API Key")
        btn.first.click()
        self.page.wait_for_load_state("networkidle")
        self.page.wait_for_timeout(2000)

    def is_loaded(self) -> bool:
        return self.page.locator("h1").filter(has_text="API 密钥").count() > 0

    # ==================== 搜索 ====================

    def search(self, keyword: str):
        body = self.page.locator("div.agent-panel-body").first
        inp = body.locator("input[placeholder*='搜索密钥']")
        if inp.count() > 0:
            inp.first.fill(keyword)
            self.page.wait_for_timeout(500)

    def clear_search(self):
        body = self.page.locator("div.agent-panel-body").first
        inp = body.locator("input[placeholder*='搜索密钥']")
        if inp.count() > 0:
            inp.first.fill("")
            self.page.wait_for_timeout(500)

    def has_search_input(self) -> bool:
        body = self.page.locator("div.agent-panel-body").first
        return body.locator("input[placeholder*='搜索密钥']").count() > 0

    # ==================== 密钥列表 ====================

    def get_key_count(self) -> int:
        """密钥数量（通过吊销按钮数量）"""
        body = self.page.locator("div.agent-panel-body").first
        return body.get_by_role("button", name="吊销").count()

    def get_key_items(self):
        """获取密钥卡片元素"""
        body = self.page.locator("div.agent-panel-body").first
        # 每个密钥卡片包含名称、前缀、创建时间和吊销按钮
        return body.locator("div").filter(has=body.get_by_role("button", name="吊销"))

    def has_key(self, name: str) -> bool:
        body = self.page.locator("div.agent-panel-body").first
        return name in body.inner_text()

    def get_key_prefixes(self) -> list[str]:
        """获取所有密钥前缀（如 rcs_...）"""
        body = self.page.locator("div.agent-panel-body").first
        text = body.inner_text()
        import re
        return re.findall(r"[a-z]{3,5}_\.{3}", text)

    def get_body_text(self) -> str:
        body = self.page.locator("div.agent-panel-body").first
        return body.inner_text()

    # ==================== 创建密钥 ====================

    def click_create_key(self):
        body = self.page.locator("div.agent-panel-body").first
        body.get_by_role("button", name="创建密钥").click()
        self.page.wait_for_timeout(1000)

    def has_create_button(self) -> bool:
        body = self.page.locator("div.agent-panel-body").first
        return body.get_by_role("button", name="创建密钥").count() > 0

    # ==================== 弹窗操作 ====================

    def is_dialog_open(self) -> bool:
        dialog = self.page.locator("[role=dialog]")
        return dialog.count() > 0 and dialog.first.is_visible()

    def get_dialog_title(self) -> str:
        dialog = self.page.locator("[role=dialog]")
        h2 = dialog.locator("h2")
        if h2.count() > 0:
            return h2.first.text_content().strip()
        return ""

    def get_dialog_text(self) -> str:
        dialog = self.page.locator("[role=dialog]")
        if dialog.count() > 0:
            return dialog.first.inner_text().strip()
        return ""

    def fill_key_name(self, name: str):
        dialog = self.page.locator("[role=dialog]")
        inp = dialog.locator("input[type=text]")
        if inp.count() > 0:
            inp.first.fill(name)

    def submit_dialog(self):
        dialog = self.page.locator("[role=dialog]")
        dialog.get_by_role("button", name="创建").or_(
            dialog.get_by_role("button", name="保存").or_(
                dialog.locator("button[type=submit]")
            )
        ).first.click()
        self.page.wait_for_timeout(2000)

    def cancel_dialog(self):
        dialog = self.page.locator("[role=dialog]")
        dialog.get_by_role("button", name="取消").click()
        self.page.wait_for_timeout(500)

    def close_dialog(self):
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(500)

    def get_form_validation_text(self) -> str:
        dialog = self.page.locator("[role=dialog]")
        errors = dialog.locator("[class*='text-red'], [class*='error'], [class*='Error']")
        if errors.count() > 0:
            return errors.first.text_content().strip()
        return ""

    # ==================== 密钥展示（创建后） ====================

    def get_shown_key(self) -> str:
        """获取弹窗中展示的完整密钥"""
        dialog = self.page.locator("[role=dialog]")
        if dialog.count() == 0:
            return ""
        text = dialog.first.inner_text()
        # 密钥通常以 rcs_ 开头
        import re
        match = re.search(r"rcs_[a-zA-Z0-9]+", text)
        return match.group(0) if match else ""

    def has_copy_button(self) -> bool:
        dialog = self.page.locator("[role=dialog]")
        if dialog.count() == 0:
            return False
        # 复制按钮
        return (
            dialog.get_by_role("button", name="复制").count() > 0
            or dialog.locator("button").filter(has_text="Copy").count() > 0
            or dialog.locator("button[aria-label*='copy']").count() > 0
            or dialog.locator("button[aria-label*='复制']").count() > 0
        )

    def click_copy(self):
        dialog = self.page.locator("[role=dialog]")
        dialog.get_by_role("button", name="复制").or_(
            dialog.locator("button").filter(has_text="Copy").or_(
                dialog.locator("button[aria-label*='copy']").or_(
                    dialog.locator("button[aria-label*='复制']")
                )
            )
        ).first.click()
        self.page.wait_for_timeout(500)

    def has_security_warning(self) -> bool:
        """创建流程中是否有安全警告"""
        dialog = self.page.locator("[role=dialog]")
        if dialog.count() == 0:
            return False
        text = dialog.first.inner_text()
        return any(kw in text for kw in [
            "仅显示一次", "仅一次", "妥善保管", "不要", "安全",
            "警告", "注意", "重要",
        ])

    # ==================== 吊销/删除 ====================

    def click_revoke(self, name: str = ""):
        """点击吊销按钮（如果指定 name，则点击对应密钥的吊销按钮）"""
        body = self.page.locator("div.agent-panel-body").first
        if name:
            # 找到包含该名称的卡片，然后点击其吊销按钮
            cards = body.locator("div").filter(has_text=name)
            for i in range(cards.count()):
                revoke_btn = cards.nth(i).get_by_role("button", name="吊销")
                if revoke_btn.count() > 0:
                    revoke_btn.first.click()
                    self.page.wait_for_timeout(500)
                    return True
        else:
            # 点击第一个吊销按钮
            revoke_btns = body.get_by_role("button", name="吊销")
            if revoke_btns.count() > 0:
                revoke_btns.first.click()
                self.page.wait_for_timeout(500)
                return True
        return False

    # ==================== 确认弹窗 ====================

    def is_alert_dialog_open(self) -> bool:
        dialog = self.page.locator("[role=alertdialog]")
        return dialog.count() > 0 and dialog.first.is_visible()

    def get_alert_dialog_text(self) -> str:
        dialog = self.page.locator("[role=alertdialog]")
        if dialog.count() > 0:
            return dialog.first.inner_text().strip()
        return ""

    def confirm_alert(self):
        dialog = self.page.locator("[role=alertdialog]")
        dialog.get_by_role("button", name="确认").or_(
            dialog.get_by_role("button", name="吊销").or_(
                dialog.get_by_role("button", name="删除")
            )
        ).first.click()
        self.page.wait_for_timeout(2000)

    def cancel_alert(self):
        dialog = self.page.locator("[role=alertdialog]")
        dialog.get_by_role("button", name="取消").click()
        self.page.wait_for_timeout(500)

    # ==================== 加载状态 ====================

    def has_skeleton_or_spinner(self) -> bool:
        body = self.page.locator("div.agent-panel-body").first
        loading = body.locator(
            "[class*='skeleton'], [class*='Skeleton'], "
            "[class*='spinner'], [class*='Spinner'], "
            "[class*='animate-pulse']"
        )
        return loading.count() > 0

    # ==================== API 拦截 ====================

    def intercept_api(self, url_pattern: str):
        collected = []

        def on_response(resp):
            if url_pattern in resp.url:
                try:
                    body = resp.json() if "json" in resp.headers.get("content-type", "") else None
                    collected.append({
                        "url": resp.url, "status": resp.status,
                        "method": resp.request.method, "body": body,
                    })
                except Exception:
                    pass

        self.page.on("response", on_response)
        return collected
