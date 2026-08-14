# tests/pages/knowledge_page.py
"""知识库管理页面 Page Object — 基于真实 DOM 结构编写"""
from playwright.sync_api import Page
from tests.pages import locators as loc


class KnowledgePage:
    """知识库管理页 /ctrl/agent/knowledge-bases"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/knowledge-bases"

    # ==================== 导航 ====================

    def goto(self):
        try:
            self.page.goto(self.url, wait_until="domcontentloaded")
        except Exception:
            pass  # SPA 路由可能中断初始导航
        self.page.wait_for_load_state("networkidle")

    def goto_via_sidebar(self):
        btn = self.page.locator("button.agent-sidebar-nav-item").filter(has_text="知识库")
        btn.first.click()
        self.page.wait_for_load_state("networkidle")

    def is_loaded(self) -> bool:
        return "/ctrl/agent/knowledge" in self.page.url and self.page.locator("div.agent-panel-body").count() > 0

    # ==================== 搜索 ====================

    def search(self, keyword: str):
        body = self.page.locator("div.agent-panel-body").first
        inp = body.locator("input[placeholder*='搜索知识库']")
        if inp.count() > 0:
            inp.first.fill(keyword)
            self.page.wait_for_timeout(500)

    def clear_search(self):
        body = self.page.locator("div.agent-panel-body").first
        inp = body.locator("input[placeholder*='搜索知识库']")
        if inp.count() > 0:
            inp.first.fill("")
            self.page.wait_for_timeout(500)

    def has_search_input(self) -> bool:
        body = self.page.locator("div.agent-panel-body").first
        return body.locator("input[placeholder*='搜索知识库']").count() > 0

    # ==================== 知识库列表 ====================

    def get_kb_buttons(self):
        """知识库列表按钮"""
        body = self.page.locator("div.agent-panel-body").first
        return body.locator("button").filter(has_not_text="新建知识库").filter(
            has_not_text="文件").filter(has_not_text="站点").filter(
            has_not_text="定时任务").filter(has_not_text="发布视图")

    def get_kb_count(self) -> int:
        """知识库数量"""
        body = self.page.locator("div.agent-panel-body").first
        # KB 按钮在列表区域，排除导航按钮
        all_btns = body.locator("div > div > button")
        count = 0
        for i in range(all_btns.count()):
            text = all_btns.nth(i).inner_text().strip()
            # KB 按钮文本包含 KB 名称
            if text and "新建" not in text and "文件" not in text and "站点" not in text \
                    and "定时" not in text and "发布" not in text:
                count += 1
        return count

    def get_kb_names(self) -> list[str]:
        """获取知识库名称列表"""
        body = self.page.locator("div.agent-panel-body").first
        btns = body.locator("div > div > button")
        names = []
        for i in range(btns.count()):
            text = btns.nth(i).inner_text().strip()
            if text and "新建" not in text and "文件" not in text and "站点" not in text \
                    and "定时" not in text and "发布" not in text:
                # 名称在第一行
                name = text.split("\n")[0].strip()
                if name:
                    names.append(name)
        return names

    def has_kb(self, name: str) -> bool:
        body = self.page.locator("div.agent-panel-body").first
        return name in body.inner_text()

    def click_kb(self, name: str):
        """点击知识库"""
        body = self.page.locator("div.agent-panel-body").first
        btn = body.locator("button").filter(has_text=name)
        if btn.count() > 0:
            btn.first.click()
            self.page.wait_for_timeout(1000)

    # ==================== 创建知识库 ====================

    def click_create_kb(self):
        body = self.page.locator("div.agent-panel-body").first
        body.get_by_role("button", name="新建知识库").click()
        self.page.wait_for_timeout(1000)

    def has_create_button(self) -> bool:
        body = self.page.locator("div.agent-panel-body").first
        return body.get_by_role("button", name="新建知识库").count() > 0

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

    def fill_kb_form(self, name: str = "", description: str = "", slug: str = ""):
        """填写知识库表单"""
        dialog = self.page.locator("[role=dialog]")
        inputs = dialog.locator("input[type=text], textarea")
        # 尝试按 placeholder 填写
        name_inp = dialog.locator("input[placeholder*='名称']").or_(
            dialog.locator("input[placeholder*='知识库名称']")
        )
        if name_inp.count() > 0 and name:
            name_inp.first.fill(name)
        elif name and inputs.count() > 0:
            inputs.first.fill(name)

        desc_inp = dialog.locator("textarea[placeholder*='描述']").or_(
            dialog.locator("input[placeholder*='描述']")
        )
        if desc_inp.count() > 0 and description:
            desc_inp.first.fill(description)

        slug_inp = dialog.locator("input[placeholder*='slug']").or_(
            dialog.locator("input[placeholder*='标识']")
        )
        if slug_inp.count() > 0 and slug:
            slug_inp.first.fill(slug)

    def submit_dialog(self):
        dialog = self.page.locator("[role=dialog]")
        loc.save_or_submit_button(dialog).first.click()
        self.page.wait_for_timeout(1000)

    def cancel_dialog(self):
        dialog = self.page.locator("[role=dialog]")
        dialog.get_by_role("button", name="取消").click()
        self.page.wait_for_timeout(500)

    def close_dialog(self):
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

    # ==================== 详情面板 ====================

    def get_detail_text(self) -> str:
        """获取详情面板文本（全宽布局，内容在 agent-panel-body 中）"""
        body = self.page.locator("div.agent-panel-body").first
        return body.inner_text()

    def has_detail_placeholder(self) -> bool:
        """是否处于初始状态（未选中知识库时显示列表视图）"""
        body = self.page.locator("div.agent-panel-body").first
        text = body.inner_text()
        # 初始状态有新建按钮和 KB 列表，没有"返回知识库列表"
        return "新建知识库" in text and "返回知识库列表" not in text

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
        loc.confirm_button(dialog).first.click()
        self.page.wait_for_timeout(1000)

    def cancel_alert(self):
        dialog = self.page.locator("[role=alertdialog]")
        dialog.get_by_role("button", name="取消").click()
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
