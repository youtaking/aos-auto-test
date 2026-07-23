# tests/pages/org_page.py
"""组织管理页面 Page Object — 基于真实 DOM 结构编写"""
from playwright.sync_api import Page


class OrgPage:
    """组织管理页 /ctrl/agent/organizations"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/organizations"

    # ==================== 导航 ====================

    def goto(self):
        """通过侧边栏导航到组织管理页面"""
        self.page.goto(self.url)
        self.page.wait_for_load_state("networkidle")
        self.page.wait_for_timeout(2000)

    def goto_via_sidebar(self):
        """通过侧边栏按钮导航"""
        btn = self.page.locator("button.agent-sidebar-nav-item").filter(has_text="组织")
        btn.first.click()
        self.page.wait_for_load_state("networkidle")
        self.page.wait_for_timeout(2000)

    def is_loaded(self) -> bool:
        return self.page.locator("h1").filter(has_text="组织管理").count() > 0

    # ==================== 组织列表 ====================

    def get_org_buttons(self):
        """左侧组织列表按钮"""
        body = self.page.locator("div.agent-panel-body").first
        return body.locator("button").filter(has_text="拥有者").or_(
            body.locator("button").filter(has_text="成员").or_(
                body.locator("button").filter(has_text="管理员")
            )
        )

    def get_org_count(self) -> int:
        """组织数量"""
        body = self.page.locator("div.agent-panel-body").first
        # 组织按钮包含角色文本（拥有者/成员/管理员）
        btns = body.locator("div > div > button")
        count = 0
        for i in range(btns.count()):
            text = btns.nth(i).inner_text()
            if "拥有者" in text or "成员" in text or "管理员" in text:
                count += 1
        return count

    def has_org(self, name: str) -> bool:
        """列表中是否有指定组织"""
        body = self.page.locator("div.agent-panel-body").first
        return name in body.inner_text()

    def click_org(self, name: str):
        """点击左侧组织"""
        body = self.page.locator("div.agent-panel-body").first
        btn = body.locator("button").filter(has_text=name)
        if btn.count() > 0:
            btn.first.click()
            self.page.wait_for_timeout(1000)

    def get_org_names(self) -> list[str]:
        """获取组织名称列表"""
        body = self.page.locator("div.agent-panel-body").first
        btns = body.locator("div > div > button")
        names = []
        for i in range(btns.count()):
            text = btns.nth(i).inner_text().strip()
            # 格式: "ORG_NAME 角色"
            parts = text.split()
            if len(parts) >= 2 and parts[-1] in ("拥有者", "成员", "管理员"):
                names.append(parts[0])
        return names

    # ==================== 创建组织 ====================

    def click_create_org(self):
        body = self.page.locator("div.agent-panel-body").first
        body.get_by_role("button", name="创建组织").click()
        self.page.wait_for_timeout(1000)

    def has_create_button(self) -> bool:
        body = self.page.locator("div.agent-panel-body").first
        return body.get_by_role("button", name="创建组织").count() > 0

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

    def fill_dialog_input(self, placeholder: str, value: str):
        dialog = self.page.locator("[role=dialog]")
        inp = dialog.locator(f"input[placeholder*='{placeholder}']")
        if inp.count() > 0:
            inp.first.fill(value)
        else:
            # 尝试不带 placeholder 的 input
            inputs = dialog.locator("input[type=text]")
            if inputs.count() > 0:
                inputs.first.fill(value)

    def submit_dialog(self):
        dialog = self.page.locator("[role=dialog]")
        dialog.get_by_role("button", name="保存").or_(
            dialog.get_by_role("button", name="创建").or_(
                dialog.get_by_role("button", name="确认").or_(
                    dialog.locator("button[type=submit]")
                )
            )
        ).first.click()
        self.page.wait_for_timeout(2000)

    def cancel_dialog(self):
        dialog = self.page.locator("[role=dialog]")
        dialog.get_by_role("button", name="取消").click()
        self.page.wait_for_timeout(500)

    def close_dialog(self):
        dialog = self.page.locator("[role=dialog]")
        close_btn = dialog.locator("button").filter(has_text="Close")
        if close_btn.count() > 0:
            close_btn.first.click()
        else:
            self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(500)

    def get_form_validation_text(self) -> str:
        dialog = self.page.locator("[role=dialog]")
        errors = dialog.locator("[class*='text-red'], [class*='error'], [class*='Error']")
        if errors.count() > 0:
            return errors.first.text_content().strip()
        return ""

    # ==================== 组织详情面板 ====================

    def get_detail_text(self) -> str:
        """获取右侧详情面板文本"""
        body = self.page.locator("div.agent-panel-body").first
        return body.inner_text()

    def has_edit_button(self) -> bool:
        body = self.page.locator("div.agent-panel-body").first
        return body.get_by_role("button", name="编辑").count() > 0

    def click_edit(self):
        body = self.page.locator("div.agent-panel-body").first
        body.get_by_role("button", name="编辑").click()
        self.page.wait_for_timeout(1000)

    # ==================== 成员管理 ====================

    def get_member_count(self) -> int:
        """获取成员数量（从标题中提取）"""
        body = self.page.locator("div.agent-panel-body").first
        h3 = body.locator("h3").filter(has_text="成员")
        if h3.count() > 0:
            import re
            text = h3.first.text_content()
            match = re.search(r"(\d+)", text)
            if match:
                return int(match.group(1))
        return 0

    def has_add_member_button(self) -> bool:
        body = self.page.locator("div.agent-panel-body").first
        return body.get_by_role("button", name="添加成员").count() > 0

    def click_add_member(self):
        body = self.page.locator("div.agent-panel-body").first
        body.get_by_role("button", name="添加成员").click()
        self.page.wait_for_timeout(1000)

    # ==================== 危险区域 ====================

    def has_delete_org_button(self) -> bool:
        body = self.page.locator("div.agent-panel-body").first
        return body.get_by_role("button", name="删除组织").count() > 0

    def click_delete_org(self):
        body = self.page.locator("div.agent-panel-body").first
        body.get_by_role("button", name="删除组织").click()
        self.page.wait_for_timeout(1000)

    def has_danger_zone(self) -> bool:
        body = self.page.locator("div.agent-panel-body").first
        return "危险区域" in body.inner_text()

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
            dialog.get_by_role("button", name="删除")
        ).first.click()
        self.page.wait_for_timeout(2000)

    def cancel_alert(self):
        dialog = self.page.locator("[role=alertdialog]")
        dialog.get_by_role("button", name="取消").click()
        self.page.wait_for_timeout(500)

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
