# tests/pages/sites_page.py
"""Agent Sites 应用部署页 Page Object（新版卡片布局）+ 建站助手对话"""
from playwright.sync_api import Page


class SitesListPage:
    """应用部署列表页 /ctrl/agent/sites（新版：卡片布局，非旧表格）
    真实 DOM（2026-09-08 探查）：
      main h1「应用部署」 + button「新建应用」
      region[aria-label='应用搜索与可见性筛选']：搜索框(placeholder=搜索应用、远程 ID 或创建者) + 访问范围按钮组
      h2「已部署应用」 + article 卡片列表：卡片含 strong(名称)+ remoteId、button「更多应用操作」、
      描述 paragraph、状态/可见性 badge、创建者(有则显示)、link「打开」(/web/site/deploy/...)
    """

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
                self.page.locator("main h1").first.wait_for(state="attached", timeout=15000)
            except Exception:
                pass
            if self.is_loaded():
                break
            try:
                self.page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
            self.page.wait_for_timeout(500)
        # 降级：侧边栏 SPA 导航
        if not self.is_loaded():
            nav_btn = self.page.locator("button.agent-sidebar-nav-item").filter(has_text="应用部署")
            if nav_btn.count() > 0:
                nav_btn.first.click()
                try:
                    self.page.locator("main h1").first.wait_for(state="attached", timeout=15000)
                except Exception:
                    pass

    def is_loaded(self) -> bool:
        if "/ctrl/agent/sites" not in self.page.url:
            return False
        h1 = self.page.locator("main h1").first
        if h1.count() == 0:
            return False
        try:
            return "应用部署" in h1.inner_text()
        except Exception:
            return False

    # === 列表（卡片）===

    def _cards(self):
        return self.page.locator("main article")

    def _card(self, app_name: str):
        """返回名称精确匹配的卡片 locator；找不到返回 count==0 的 locator"""
        cards = self._cards().filter(has=self.page.locator(
            "strong", has_text=app_name))
        # strong 需精确匹配，避免子串误中
        for i in range(self._cards().count()):
            card = self._cards().nth(i)
            strong = card.locator("strong").first
            if strong.count() > 0 and strong.inner_text().strip() == app_name:
                return card
        return cards.first

    def get_app_count(self) -> int:
        return self._cards().count()

    def get_app_names(self) -> list[str]:
        names = []
        for card in self._cards().all():
            strong = card.locator("strong").first
            if strong.count() > 0:
                t = strong.inner_text().strip()
                if t:
                    names.append(t)
        return names

    def has_app(self, name: str) -> bool:
        return name in self.get_app_names()

    def get_card_text(self, app_name: str) -> str:
        """某应用的卡片文本（用于校验创建者/说明等）"""
        card = self._card(app_name)
        if card.count() > 0:
            return card.inner_text()
        return ""

    # === 搜索 & 可见性筛选 ===

    def _search_input(self):
        return self.page.locator(
            "input[placeholder*='搜索应用'], input[placeholder*='搜索远程']"
        ).first

    def search(self, keyword: str):
        inp = self._search_input()
        if inp.count() > 0:
            inp.wait_for(state="visible", timeout=5000)
            inp.fill("")
            inp.fill(keyword)
            self.page.wait_for_timeout(800)

    def clear_search(self):
        inp = self._search_input()
        if inp.count() > 0:
            try:
                inp.wait_for(state="visible", timeout=3000)
            except Exception:
                return
            inp.fill("")
            self.page.wait_for_timeout(800)

    def _filter_group(self):
        return self.page.locator("main [role='group'][aria-label='访问范围']").first

    def get_filter_tabs(self) -> list[str]:
        grp = self._filter_group()
        if grp.count() == 0:
            return []
        return [b.inner_text().strip() for b in grp.locator("button").all()]

    def click_filter_tab(self, tab_name: str):
        grp = self._filter_group()
        if grp.count() == 0:
            return
        btn = grp.locator("button").filter(has_text=tab_name).first
        if btn.count() > 0:
            btn.wait_for(state="visible", timeout=5000)
            btn.click()
            self.page.wait_for_timeout(1000)

    # === 创建应用 ===

    def click_create_app(self):
        """点击「新建应用」按钮（新版按钮名，非旧「创建 App」）"""
        btn = self.page.locator("main button").filter(has_text="新建应用")
        if btn.count() == 0:
            btn = self.page.get_by_role("button", name="创建 App")
        if btn.count() > 0:
            btn.first.wait_for(state="visible", timeout=5000)
            btn.first.click()
            self.page.wait_for_timeout(1500)

    def is_create_dialog_open(self) -> bool:
        d = self.page.locator('[role="dialog"]')
        if d.count() == 0 or not d.first.is_visible():
            return False
        return "新建应用" in d.first.inner_text().split("\n")[0]

    def _dialog(self):
        return self.page.locator('[role="dialog"]').first

    def fill_create_form(self, name: str, desc: str = "", visibility: str = "仅自己"):
        """填写创建表单：名称 input(placeholder 例如 my-app)、描述 textarea(placeholder 可选描述)、访问范围 combobox"""
        d = self._dialog()
        name_input = d.locator('input[placeholder*="my-app"]').or_(
            d.locator('input[placeholder*="例如"]'))
        if name_input.count() > 0:
            name_input.first.wait_for(state="visible", timeout=5000)
            name_input.first.fill(name)
        if desc:
            desc_input = d.locator('textarea[placeholder*="可选"]')
            if desc_input.count() > 0:
                desc_input.first.fill(desc)
        if visibility:
            self._select_visibility(d, visibility)

    def _select_visibility(self, d, visibility: str):
        cb = d.locator('button[role="combobox"]').first
        if cb.count() == 0:
            return
        cb.wait_for(state="visible", timeout=5000)
        cb.click()
        self.page.wait_for_timeout(400)
        opt = self.page.get_by_role("option", name=visibility).first
        if opt.count() > 0:
            opt.wait_for(state="visible", timeout=5000)
            opt.click()
            self.page.wait_for_timeout(300)

    def save_create(self):
        """点击保存，等弹窗关闭（远程创建可能较慢，轮询最多 30s）"""
        d = self._dialog()
        if d.count() == 0:
            return
        btn = d.locator("button").filter(has_text="保存")
        if btn.count() > 0:
            btn.first.click()
        try:
            d.wait_for(state="hidden", timeout=30000)
        except Exception:
            pass

    # === 编辑 ===

    def open_edit_dialog(self, app_name: str):
        """通过卡片菜单「编辑」打开编辑弹窗（新版无表格行名点击，需菜单进入）"""
        self.open_row_menu(app_name)
        menu = self.page.locator('[role="menu"]').first
        if menu.count() > 0:
            item = menu.locator('[role="menuitem"]').filter(has_text="编辑").first
            if item.count() > 0:
                item.wait_for(state="visible", timeout=5000)
                item.click()
                self.page.wait_for_timeout(1200)

    def is_edit_dialog_open(self) -> bool:
        d = self.page.locator('[role="dialog"]')
        if d.count() == 0 or not d.first.is_visible():
            return False
        return "编辑应用" in d.first.inner_text()

    def edit_app_name(self, new_name: str):
        d = self._dialog()
        name_input = d.locator('input[placeholder*="my-app"]').or_(
            d.locator('input[placeholder*="例如"]'))
        if name_input.count() > 0:
            name_input.first.wait_for(state="visible", timeout=5000)
            name_input.first.fill(new_name)

    def edit_app_description(self, desc: str):
        d = self._dialog()
        textarea = d.locator('textarea[placeholder*="可选"]')
        if textarea.count() > 0:
            textarea.first.wait_for(state="visible", timeout=5000)
            textarea.first.fill(desc)

    def save_edit(self):
        d = self._dialog()
        save_btn = d.locator("button").filter(has_text="保存")
        if save_btn.count() > 0:
            save_btn.first.click()
        try:
            d.wait_for(state="hidden", timeout=15000)
        except Exception:
            pass

    def cancel_edit(self):
        d = self._dialog()
        cancel = d.locator("button").filter(has_text="取消")
        if cancel.count() > 0:
            cancel.first.click()
            self.page.wait_for_timeout(500)

    # === 卡片菜单 ===

    def open_row_menu(self, app_name: str):
        """打开某应用卡片的「更多应用操作」菜单"""
        card = self._card(app_name)
        if card.count() == 0:
            return
        btn = card.locator('button[aria-label="更多应用操作"]').or_(
            card.get_by_role("button", name="更多应用操作"))
        if btn.count() > 0:
            btn.first.wait_for(state="visible", timeout=5000)
            btn.first.click()
            self.page.wait_for_timeout(700)

    def get_menu_items(self, app_name: str) -> list[str]:
        self.open_row_menu(app_name)
        menu = self.page.locator('[role="menu"]').first
        items = []
        if menu.count() > 0:
            items = [m.strip() for m in menu.locator('[role="menuitem"]').all_text_contents()]
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(300)
        return items

    def renew_token(self, app_name: str):
        self.open_row_menu(app_name)
        item = self.page.locator('[role="menuitem"]').filter(has_text="重签 Token")
        if item.count() > 0:
            item.first.wait_for(state="visible", timeout=5000)
            item.first.click()
            self.page.wait_for_timeout(1500)

    def delete_app(self, app_name: str):
        """菜单 → 删除 → alertdialog「确认删除」→ 确认"""
        self.open_row_menu(app_name)
        del_item = self.page.locator('[role="menuitem"]').filter(has_text="删除")
        if del_item.count() > 0:
            del_item.first.wait_for(state="visible", timeout=5000)
            del_item.first.click()
            self.page.wait_for_timeout(800)
        alert = self.page.locator('[role="alertdialog"]')
        if alert.count() > 0:
            confirm = alert.locator("button").filter(has_text="确认")
            if confirm.count() > 0:
                confirm.first.wait_for(state="visible", timeout=5000)
                confirm.first.click()
        # 等弹窗/确认框关闭
        for _ in range(10):
            vis = self.page.locator('[role="alertdialog"], [role="dialog"]')
            if vis.count() == 0 or not vis.first.is_visible():
                break
            self.page.wait_for_timeout(1000)
        self.page.wait_for_timeout(500)

    # === 打开应用（独立 URL）===

    def _open_link(self, app_name: str):
        """某应用卡片中的「打开」链接"""
        card = self._card(app_name)
        if card.count() > 0:
            return card.locator("a").filter(has_text="打开").first
        return self.page.locator("a", has_text="打开").first

    def open_app_in_new_tab(self, app_name: str):
        """点击「打开」链接（target=_blank），在新标签页打开应用"""
        lnk = self._open_link(app_name)
        if lnk.count() == 0:
            return None
        lnk.wait_for(state="visible", timeout=5000)
        with self.page.context.expect_page() as new_page_info:
            lnk.click()
        new_page = new_page_info.value
        new_page.wait_for_load_state("domcontentloaded")
        return new_page


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
