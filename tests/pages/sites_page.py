# tests/pages/sites_page.py
"""Agent Sites 页面 Page Object（列表管理 + 建站助手对话）"""
from playwright.sync_api import Page


class SitesListPage:
    """Agent Sites 列表页 /ctrl/agent/sites"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/sites"

    def goto(self):
        for _attempt in range(2):
            try:
                self.page.goto(self.url, wait_until="domcontentloaded")
            except Exception:
                pass
            self.page.wait_for_load_state("domcontentloaded")
            try:
                self.page.locator("div.agent-panel-content").first.wait_for(state="attached", timeout=8000)
            except Exception:
                pass
            if self.page.locator("div.agent-panel-content").count() > 0:
                break
            self.page.wait_for_timeout(3000)
        # 降级：侧边栏 SPA 导航
        if self.page.locator("div.agent-panel-content").count() == 0:
            nav_btn = self.page.locator("button.agent-sidebar-nav-item").filter(has_text="AOS应用部署")
            if nav_btn.count() > 0:
                nav_btn.first.click()
                try:
                    self.page.locator("div.agent-panel-content").first.wait_for(state="attached", timeout=8000)
                except Exception:
                    pass

    def is_loaded(self) -> bool:
        return "/ctrl/agent/sites" in self.page.url and self.page.locator("div.agent-panel-content").count() > 0

    # === 列表基础 ===

    def has_table(self) -> bool:
        return self.page.locator("table").count() > 0

    def get_app_count(self) -> int:
        return self.page.locator("table tbody tr").count()

    def get_app_names(self) -> list[str]:
        names = []
        for row in self.page.locator("table tbody tr").all():
            name_btn = row.locator("td").first.locator("button")
            if name_btn.count() > 0:
                names.append(name_btn.inner_text().strip())
        return names

    def has_app(self, name: str) -> bool:
        return name in self.get_app_names()

    def get_table_headers(self) -> list[str]:
        return self.page.locator("table thead th").all_text_contents()

    # === 搜索 & Tab ===

    def search(self, keyword: str):
        inp = self.page.locator("input[placeholder*='搜索 app'], input[placeholder*='搜索app']")
        if inp.count() > 0:
            inp.first.fill(keyword)
            self.page.wait_for_timeout(500)

    def clear_search(self):
        inp = self.page.locator("input[placeholder*='搜索 app'], input[placeholder*='搜索app']")
        if inp.count() > 0:
            inp.first.fill("")
            self.page.wait_for_timeout(500)

    def get_filter_tabs(self) -> list[str]:
        return [t.strip() for t in self.page.locator("[role='tab']").all_text_contents() if t.strip()]

    def click_filter_tab(self, tab_name: str):
        tab = self.page.locator("[role='tab']").filter(has_text=tab_name)
        if tab.count() > 0:
            tab.first.click()
            self.page.wait_for_timeout(500)

    # === 创建者列 ===

    def _creator_col_index(self) -> int:
        """动态获取「创建者」列索引（0-based），默认回退 3"""
        headers = self.get_table_headers()
        for i, h in enumerate(headers):
            if "创建者" in h:
                return i
        return 3  # fallback

    def get_creator_text(self, app_name: str) -> str:
        """获取某应用的创建者列文本"""
        col = self._creator_col_index()
        for row in self.page.locator("table tbody tr").all():
            name_btn = row.locator("td").first.locator("button")
            if name_btn.count() > 0 and name_btn.inner_text().strip() == app_name:
                return row.locator("td").nth(col).inner_text().strip()
        return ""

    def get_all_creator_texts(self) -> list[str]:
        """获取所有应用的创建者文本"""
        col = self._creator_col_index()
        creators = []
        for row in self.page.locator("table tbody tr").all():
            creators.append(row.locator("td").nth(col).inner_text().strip())
        return creators

    def click_creator(self, app_name: str):
        """点击某应用的创建者名称"""
        col = self._creator_col_index()
        for row in self.page.locator("table tbody tr").all():
            name_btn = row.locator("td").first.locator("button")
            if name_btn.count() > 0 and name_btn.inner_text().strip() == app_name:
                creator_td = row.locator("td").nth(col)
                link = creator_td.locator("a, button").first
                if link.count() > 0:
                    link.click()
                    self.page.wait_for_timeout(1000)
                return

    def has_creator_link(self, app_name: str) -> bool:
        """某应用的创建者列是否有可点击链接"""
        col = self._creator_col_index()
        for row in self.page.locator("table tbody tr").all():
            name_btn = row.locator("td").first.locator("button")
            if name_btn.count() > 0 and name_btn.inner_text().strip() == app_name:
                creator_td = row.locator("td").nth(col)
                return creator_td.locator("a, button").count() > 0
        return False

    # === 创建应用 ===

    def click_create_app(self):
        """点击'创建 App'按钮"""
        btn = self.page.locator("button").filter(has_text="创建 App")
        if btn.count() > 0:
            btn.first.click()
            self.page.wait_for_timeout(1500)

    def is_create_dialog_open(self) -> bool:
        """创建弹窗是否打开"""
        d = self.page.locator('[role="dialog"]')
        if d.count() == 0:
            return False
        return "创建 App" in d.first.inner_text()

    def fill_create_form(self, name: str, desc: str = "", visibility: str = "仅自己"):
        """填写创建表单"""
        d = self.page.locator('[role="dialog"]')
        # 名称
        name_input = d.locator('input[placeholder*="kebab"]')
        if name_input.count() > 0:
            name_input.first.fill(name)
        # 描述
        if desc:
            desc_input = d.locator('textarea[placeholder*="可选"]')
            if desc_input.count() > 0:
                desc_input.first.fill(desc)
        # 可见性
        if visibility:
            sel = d.locator("select")
            if sel.count() > 0:
                sel.first.select_option(label=visibility)

    def save_create(self):
        """点击创建弹窗的保存按钮"""
        d = self.page.locator('[role="dialog"]')
        btn = d.locator("button").filter(has_text="保存")
        if btn.count() > 0:
            btn.first.click()
            self.page.wait_for_timeout(1000)

    # === 打开应用（独立 URL）===

    def get_open_url(self, app_name: str) -> str | None:
        """获取某应用的打开 URL（不点击）"""
        for row in self.page.locator("table tbody tr").all():
            name_btn = row.locator("td").first.locator("button")
            if name_btn.count() > 0 and name_btn.inner_text().strip() == app_name:
                open_btn = row.locator("button[title='打开']")
                if open_btn.count() > 0:
                    # 从 href 或 data 属性获取 URL
                    href = open_btn.get_attribute("href")
                    if href:
                        return href
        return None

    def open_app_in_new_tab(self, app_name: str):
        """点击打开按钮，在新标签页打开应用"""
        for row in self.page.locator("table tbody tr").all():
            name_btn = row.locator("td").first.locator("button")
            if name_btn.count() > 0 and name_btn.inner_text().strip() == app_name:
                open_btn = row.locator("button[title='打开']")
                if open_btn.count() > 0:
                    with self.page.context.expect_page() as new_page_info:
                        open_btn.click()
                    new_page = new_page_info.value
                    new_page.wait_for_load_state("domcontentloaded")
                    return new_page
        return None

    # === 编辑 ===

    def open_edit_dialog(self, app_name: str):
        """点击应用名打开编辑对话框"""
        for row in self.page.locator("table tbody tr").all():
            name_btn = row.locator("td").first.locator("button")
            if name_btn.count() > 0 and name_btn.inner_text().strip() == app_name:
                name_btn.click()
                self.page.wait_for_timeout(1000)
                return

    def is_edit_dialog_open(self) -> bool:
        dialog = self.page.locator("[role='dialog']")
        if dialog.count() == 0:
            return False
        return dialog.get_by_text("编辑").count() > 0 or dialog.locator("input").count() > 0

    def edit_app_name(self, new_name: str):
        """在编辑对话框中修改名称"""
        dialog = self.page.locator("[role='dialog']")
        name_input = dialog.locator("input").first
        name_input.fill(new_name)

    def edit_app_description(self, desc: str):
        """在编辑对话框中修改描述"""
        dialog = self.page.locator("[role='dialog']")
        textarea = dialog.locator("textarea").first
        textarea.fill(desc)

    def save_edit(self):
        dialog = self.page.locator("[role='dialog']")
        dialog.get_by_role("button", name="保存").click()
        self.page.wait_for_timeout(1500)

    def cancel_edit(self):
        dialog = self.page.locator("[role='dialog']")
        cancel = dialog.get_by_role("button", name="取消")
        if cancel.count() > 0:
            cancel.first.click()
            self.page.wait_for_timeout(500)

    # === 删除（三点菜单）===

    def open_row_menu(self, app_name: str):
        """打开某应用的三点菜单"""
        for row in self.page.locator("table tbody tr").all():
            name_btn = row.locator("td").first.locator("button")
            if name_btn.count() > 0 and name_btn.inner_text().strip() == app_name:
                # 第三个 button 是三点菜单
                btns = row.locator("button")
                if btns.count() >= 3:
                    btns.nth(2).click()
                    self.page.wait_for_timeout(500)
                    return

    def renew_token(self, app_name: str):
        """通过三点菜单重签 Token"""
        self.open_row_menu(app_name)
        renew_item = self.page.get_by_role("menuitem", name="重签 Token")
        if renew_item.count() > 0:
            renew_item.click()
            self.page.wait_for_timeout(1000)

    def delete_app(self, app_name: str):
        """通过三点菜单删除应用"""
        self.open_row_menu(app_name)
        delete_item = self.page.get_by_role("menuitem", name="删除")
        if delete_item.count() > 0:
            delete_item.click()
            self.page.wait_for_timeout(500)

            # 确认删除 — alertdialog 优先
            alert_confirm = self.page.locator("[role='alertdialog']").get_by_role("button", name="确认")
            dialog_confirm = self.page.locator("[role='dialog']").get_by_role("button", name="确认")
            confirm_btn = self.page.get_by_role("button", name="确认").or_(
                self.page.get_by_role("button", name="确定")
            )

            if alert_confirm.count() > 0:
                alert_confirm.first.click()
            elif dialog_confirm.count() > 0:
                dialog_confirm.first.click()
            elif confirm_btn.count() > 0:
                confirm_btn.first.click()

            # 等待删除完成：对话框关闭 + 列表更新
            self.page.wait_for_timeout(1000)

            # 等待对话框消失（确认删除成功）
            for _ in range(5):
                remaining = self.page.locator("[role='alertdialog'], [role='dialog']")
                if remaining.count() == 0 or not remaining.first.is_visible():
                    break
                self.page.wait_for_timeout(1000)

    def get_menu_items(self, app_name: str) -> list[str]:
        """获取某应用的菜单项列表"""
        self.open_row_menu(app_name)
        items = [m.strip() for m in self.page.locator("[role='menuitem']").all_text_contents()]
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(300)
        return items


class SiteBuilderChatPage:
    """建站助手对话页"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url

    def goto_builder_chat(self) -> bool:
        """进入建站助手对话页。返回是否找到并点击了建站助手。"""
        # 先到首页
        try:
            self.page.goto(f"{self.base_url}/ctrl/agent/home", wait_until="domcontentloaded")
        except Exception:
            pass  # SPA 路由可能中断初始导航
        self.page.wait_for_load_state("domcontentloaded")
        try:
            self.page.locator("div.agent-panel-content").first.wait_for(state="attached", timeout=8000)
        except Exception:
            pass

        # 滚动侧边栏找到建站助手（带重试，侧边栏可能懒加载）
        builder_card = self.page.locator("button.agent-sidebar-agent-card").filter(
            has_text="建站助手"
        )
        for _attempt in range(3):
            if builder_card.count() > 0:
                builder_card.first.scroll_into_view_if_needed()
                self.page.wait_for_timeout(300)
                builder_card.first.click()
                self.page.wait_for_timeout(1000)
                # 如果普通点击没导航，用 JS 点击
                if "/chat/" not in self.page.url:
                    builder_card.first.evaluate("el => el.click()")
                # 等待聊天输入框出现（WebSocket 连接需要时间）
                try:
                    self.page.locator("textarea").first.wait_for(
                        state="visible", timeout=20000
                    )
                except Exception:
                    self.page.wait_for_timeout(2000)
                return True
            # 侧边栏可能懒加载，滚动触发加载
            sidebar = self.page.locator("div.agent-sidebar-tree")
            if sidebar.count() > 0:
                sidebar.first.evaluate("el => el.scrollTop = el.scrollHeight")
                self.page.wait_for_timeout(800)
                sidebar.first.evaluate("el => el.scrollTop = 0")
                self.page.wait_for_timeout(500)
            else:
                self.page.wait_for_timeout(1000)
        return False

    def is_chat_loaded(self) -> bool:
        """对话页是否加载"""
        return "/chat/" in self.page.url

    def has_textarea(self) -> bool:
        """是否有消息输入框"""
        return self.page.locator("textarea").count() > 0

    def has_artifacts_panel(self) -> bool:
        """是否有 ArtifactsPanel（预览区）"""
        # ArtifactsPanel 可能是 iframe 或 data-slot='artifact'
        return (
            self.page.locator("iframe").count() > 0
            or self.page.locator("[data-slot='artifact'], iframe[src*='artifact']").count() > 0
        )

    def get_iframe_src(self) -> str:
        """获取 iframe 的 src"""
        iframe = self.page.locator("iframe").first
        if iframe.count() > 0:
            return iframe.get_attribute("src") or ""
        return ""

    def has_view_site_button(self) -> bool:
        """是否有「查看站点」按钮"""
        return self.page.get_by_role("button", name="查看站点").count() > 0

    def get_chat_url(self) -> str:
        return self.page.url
