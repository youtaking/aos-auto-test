# tests/pages/org_page.py
"""组织管理页面 Page Object — 基于真实 DOM 结构编写"""
from playwright.sync_api import Page
from tests.pages import locators as loc


class OrgPage:
    """组织管理页 /ctrl/agent/organizations"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/organizations"

    # ==================== 导航 ====================

    def goto(self):
        """通过侧边栏导航到组织管理页面"""
        for _attempt in range(2):
            try:
                self.page.goto(self.url, wait_until="domcontentloaded")
            except Exception:
                pass  # SPA 路由可能中断初始导航
            self.page.wait_for_load_state("domcontentloaded")
            # 等待 React 渲染 + 组织按钮列表渲染完成
            try:
                self.page.locator("div.agent-panel-content").first.wait_for(state="attached", timeout=8000)
            except Exception:
                pass
            if self.page.locator("div.agent-panel-content").count() > 0:
                break
            try:
                self.page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
            self.page.wait_for_timeout(500)
        # 降级：侧边栏 SPA 导航
        if self.page.locator("div.agent-panel-content").count() == 0:
            nav_btn = self.page.locator("button.agent-sidebar-nav-item").filter(has_text="组织")
            if nav_btn.count() > 0:
                nav_btn.first.wait_for(state="visible", timeout=5000)
                nav_btn.first.click()
                try:
                    self.page.locator("div.agent-panel-content").first.wait_for(state="attached", timeout=8000)
                except Exception:
                    pass
        try:
            self.page.locator("div.agent-panel-body button").first.wait_for(
                state="visible", timeout=5000
            )
        except Exception:
            pass

    def goto_via_sidebar(self):
        """通过侧边栏按钮导航"""
        btn = self.page.locator("button.agent-sidebar-nav-item").filter(has_text="组织")
        btn.first.wait_for(state="visible", timeout=5000)
        btn.first.click()
        self.page.wait_for_load_state("domcontentloaded")

    def is_loaded(self) -> bool:
        return "/ctrl/agent/organization" in self.page.url and self.page.locator("div.agent-panel-body").count() > 0

    # ==================== 组织列表 ====================

    def get_org_buttons(self):
        """左侧组织列表按钮"""
        body = self.page.locator("div.agent-panel-body")
        return body.locator("button").filter(has_text="拥有者").or_(
            body.locator("button").filter(has_text="成员").or_(
                body.locator("button").filter(has_text="管理员")
            )
        )

    def get_org_count(self) -> int:
        """组织数量"""
        body = self.page.locator("div.agent-panel-body")
        btns = body.locator("button")
        count = 0
        for i in range(btns.count()):
            text = btns.nth(i).inner_text()
            if "拥有者" in text or "成员" in text or "管理员" in text:
                # 排除成员列表中的角色文本（格式不同）
                lines = text.strip().split("\n")
                if len(lines) == 2 and lines[1].strip() in ("拥有者", "成员", "管理员"):
                    count += 1
        return count

    def has_org(self, name: str) -> bool:
        """列表中是否有指定组织"""
        body = self.page.locator("div.agent-panel-body")
        return name in body.inner_text()

    def click_org(self, name: str):
        """点击左侧组织"""
        body = self.page.locator("div.agent-panel-body")
        btn = body.locator("button").filter(has_text=name)
        if btn.count() > 0:
            btn.first.wait_for(state="visible", timeout=5000)
            btn.first.click()
            self.page.wait_for_timeout(1000)

    def get_org_names(self) -> list[str]:
        """获取组织名称列表"""
        body = self.page.locator("div.agent-panel-body")
        btns = body.locator("button")
        names = []
        for i in range(btns.count()):
            text = btns.nth(i).inner_text().strip()
            # 格式: "ORG_NAME\n角色"
            lines = text.split("\n")
            if len(lines) == 2 and lines[1].strip() in ("拥有者", "成员", "管理员"):
                names.append(lines[0].strip())
        return names

    # ==================== 创建组织 ====================

    def click_create_org(self):
        body = self.page.locator("div.agent-panel-body").first
        btn = body.get_by_role("button", name="创建组织")
        btn.wait_for(state="visible", timeout=5000)
        btn.click()
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
            inp.first.wait_for(state="visible", timeout=5000)
            inp.first.fill(value)
        else:
            # 尝试不带 placeholder 的 input
            inputs = dialog.locator("input[type=text]")
            if inputs.count() > 0:
                inputs.first.wait_for(state="visible", timeout=5000)
                inputs.first.fill(value)

    def submit_dialog(self):
        dialog = self.page.locator("[role=dialog]")
        btn = loc.save_or_submit_button(dialog).or_(
            dialog.get_by_role("button", name="确认")
        ).first
        btn.wait_for(state="visible", timeout=5000)
        btn.click()
        self.page.wait_for_timeout(1000)

    def cancel_dialog(self):
        dialog = self.page.locator("[role=dialog]")
        btn = dialog.get_by_role("button", name="取消")
        btn.wait_for(state="visible", timeout=5000)
        btn.click()
        self.page.wait_for_timeout(500)

    def close_dialog(self):
        dialog = self.page.locator("[role=dialog]")
        close_btn = dialog.locator("button").filter(has_text="Close")
        if close_btn.count() > 0:
            close_btn.first.wait_for(state="visible", timeout=5000)
            close_btn.first.click()
        else:
            self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(500)

    def get_form_validation_text(self) -> str:
        dialog = self.page.locator("[role=dialog]")
        errors = dialog.locator("[data-slot='form-message'], [role='alert']")
        if errors.count() == 0:
            errors = dialog.locator("p.text-red-500, p.text-destructive")
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
        btn = body.get_by_role("button", name="编辑")
        btn.wait_for(state="visible", timeout=5000)
        btn.click()
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
        btn = body.get_by_role("button", name="添加成员")
        btn.wait_for(state="visible", timeout=5000)
        btn.click()
        self.page.wait_for_timeout(1000)

    # ==================== 危险区域 ====================

    def has_delete_org_button(self) -> bool:
        body = self.page.locator("div.agent-panel-body").first
        return body.get_by_role("button", name="删除组织").count() > 0

    def click_delete_org(self):
        body = self.page.locator("div.agent-panel-body").first
        btn = body.get_by_role("button", name="删除组织")
        btn.wait_for(state="visible", timeout=5000)
        btn.click()
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
        btn = loc.confirm_button(dialog).first
        btn.wait_for(state="visible", timeout=5000)
        btn.click()
        self.page.wait_for_timeout(1000)

    def cancel_alert(self):
        dialog = self.page.locator("[role=alertdialog]")
        btn = dialog.get_by_role("button", name="取消")
        btn.wait_for(state="visible", timeout=5000)
        btn.click()
        self.page.wait_for_timeout(500)

    # ==================== API 拦截 ====================

    def intercept_api(self, url_pattern: str):
        # 移除之前的监听器，避免累积

        if hasattr(self, '_last_listener') and self._last_listener:

            try:

                self.page.remove_listener("response", self._last_listener)

            except Exception:

                pass

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

        self._last_listener = on_response
        self.page.on("response", on_response)
        return collected
