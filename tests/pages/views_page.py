# tests/pages/views_page.py
"""发布视图 ProdView Page Object — Agent 内容面板的「发布视图」Tab

新版双栏 UI：Artifacts 内容面板默认折叠，需通过 button.artifacts-open-button
展开（aside.artifacts-shell），模式切换用 button.artifacts-mode-tab（激活类 is-active）。
视图卡片在 aside.artifacts-shell 内为 div.rounded-lg.border。
"""
from playwright.sync_api import Page


class ViewsPage:
    """发布视图（ProdView）— Agent 内容面板的「发布视图」Tab"""

    SHELL = "aside.artifacts-shell"
    EMPTY_TEXT = "点击 + 创建发布视图"

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url

    # ---------- 面板控制 ----------

    def _shell(self):
        return self.page.locator(self.SHELL)

    def _cards(self):
        return self._shell().locator("div.rounded-lg.border")

    def _empty_state(self):
        return self.page.get_by_text(self.EMPTY_TEXT)

    def _empty_create_btn(self):
        """无视图时居中的创建入口（按钮文本即空状态提示）"""
        return self.page.get_by_role("button", name=self.EMPTY_TEXT)

    def _header_create_btn(self):
        """有视图时头部行的 + 新建按钮"""
        row = self._header_row()
        if row.count() == 0:
            return None
        return row.first.locator("button").filter(
            has=self.page.locator("svg.lucide-plus")
        )

    def _prod_view_tab(self):
        return self._shell().locator("button.artifacts-mode-tab").filter(has_text="发布视图")

    def _open_artifacts_panel(self) -> bool:
        """展开 ArtifactsPanel（折叠时显示 button.artifacts-open-button）"""
        shell = self._shell()
        open_btn = self.page.locator("button.artifacts-open-button")
        for _ in range(4):
            if shell.count() > 0 and shell.first.is_visible():
                return True
            if open_btn.count() > 0 and open_btn.first.is_visible():
                open_btn.first.click()
                self.page.wait_for_timeout(900)
                continue
            self.page.wait_for_timeout(700)
        return shell.count() > 0 and shell.first.is_visible()

    def _activate_prod_view(self) -> bool:
        """展开面板并激活「发布视图」Tab，直到列表或空状态就绪"""
        if not self._open_artifacts_panel():
            return False
        for _ in range(8):
            tab = self._prod_view_tab()
            if tab.count() > 0:
                is_active = tab.first.evaluate(
                    "el => el.classList.contains('is-active')"
                )
                if not is_active:
                    tab.first.click(force=True)
                    self.page.wait_for_timeout(1200)
                if self._tab_content_ready():
                    return True
            else:
                self._open_artifacts_panel()
            self.page.wait_for_timeout(700)
        return False

    def _tab_content_ready(self) -> bool:
        """发布视图 Tab 已激活且有内容（视图卡片或空状态提示）"""
        shell = self._shell()
        if not (shell.count() > 0 and shell.first.is_visible()):
            return False
        active = shell.locator("button.artifacts-mode-tab.is-active")
        if active.count() == 0:
            return False
        if "发布视图" not in active.first.inner_text():
            return False
        return self._cards().count() > 0 or self._empty_state().count() > 0

    # ---------- 对外接口 ----------

    def goto(self, agent_name: str = "my-auto-test"):
        """导航到指定 Agent 内容面板的「发布视图」Tab"""
        try:
            self.page.goto(
                f"{self.base_url}/ctrl/agent/home", wait_until="domcontentloaded"
            )
        except Exception:
            pass
        self.page.wait_for_load_state("domcontentloaded")

        # 点击 Agent 卡片进入其内容/聊天页
        card = self.page.locator("button.agent-sidebar-agent-card").filter(has_text=agent_name)
        for _ in range(12):
            if card.count() > 0:
                break
            self.page.wait_for_timeout(1000)
        if card.count() == 0:
            return
        card.first.scroll_into_view_if_needed()
        self.page.wait_for_timeout(300)
        card.first.click()
        self.page.wait_for_timeout(1500)
        if "/chat/" not in self.page.url:
            card.first.evaluate("el => el.click()")
            self.page.wait_for_timeout(2500)

        # 展开 ArtifactsPanel 并激活「发布视图」Tab
        self._activate_prod_view()

    def is_loaded(self) -> bool:
        """「发布视图」Tab 内容是否已就绪"""
        return self._tab_content_ready()

    def refresh(self):
        """切换到其它 Tab 再切回，强制发布视图列表重新拉取"""
        shell = self._shell()
        other = shell.locator("button.artifacts-mode-tab").filter(has_text="文件")
        if other.count() > 0:
            other.first.click()
            self.page.wait_for_timeout(600)
        self._activate_prod_view()

    def get_view_count(self) -> int:
        """视图卡片数量"""
        return self._cards().count()

    def _header_row(self):
        """发布视图内容头部行（div...border-b 内含 发布视图 标题 span 与 + 按钮）"""
        shell = self._shell()
        return shell.locator("div.flex.items-center.justify-between.border-b").filter(
            has=shell.locator("span.text-xs.font-medium").filter(has_text="发布视图")
        )

    def has_create_button(self) -> bool:
        if not self._tab_content_ready():
            return False
        empty_btn = self._empty_create_btn()
        if empty_btn.count() > 0 and empty_btn.first.is_visible():
            return True
        btn = self._header_create_btn()
        return btn is not None and btn.count() > 0 and btn.first.is_visible()

    def click_create_button(self):
        empty_btn = self._empty_create_btn()
        if empty_btn.count() > 0 and empty_btn.first.is_visible():
            empty_btn.first.click()
            self.page.wait_for_timeout(900)
            return
        btn = self._header_create_btn()
        if btn is not None and btn.count() > 0:
            btn.first.click()
            self.page.wait_for_timeout(900)

    def get_page_text(self) -> str:
        """获取内容面板文本"""
        shell = self._shell()
        if shell.count() > 0:
            return shell.first.inner_text()
        return ""
