# tests/pages/config_pages.py
"""配置管理页面 Page Objects（模型、技能、MCP、Agent Sites）"""
from playwright.sync_api import Page


class ModelsPage:
    """服务商与模型管理页"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/models"

    # 页面就绪标识：搜索输入框
    _READY_SELECTOR = "input[placeholder*='搜索服务商']"

    def goto(self):
        for _attempt in range(2):
            try:
                self.page.goto(self.url, wait_until="domcontentloaded")
            except Exception:
                pass  # SPA 路由可能中断初始导航（net::ERR_ABORTED）
            self.page.wait_for_load_state("domcontentloaded")
            try:
                self.page.locator(self._READY_SELECTOR).first.wait_for(state="attached", timeout=15000)
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
            nav_btn = self.page.locator("button.agent-sidebar-nav-item").filter(has_text="模型库")
            if nav_btn.count() > 0:
                nav_btn.first.click()
                try:
                    self.page.locator(self._READY_SELECTOR).first.wait_for(state="attached", timeout=15000)
                except Exception:
                    pass

    def is_loaded(self) -> bool:
        return "/ctrl/agent/models" in self.page.url and \
            self.page.locator(self._READY_SELECTOR).count() > 0

    def has_model_list(self) -> bool:
        """是否有模型列表内容"""
        return self.page.locator("table tbody tr, div.grid > div").count() > 0

    def search(self, keyword: str):
        inp = self.page.locator("input[placeholder*='搜索服务商']")
        if inp.count() > 0:
            inp.first.fill(keyword)
            self.page.wait_for_timeout(500)

    def clear_search(self):
        inp = self.page.locator("input[placeholder*='搜索服务商']")
        if inp.count() > 0:
            inp.first.fill("")
            self.page.wait_for_timeout(500)

    def get_provider_count(self) -> int:
        """获取服务商卡片数量"""
        cards = self.page.locator(
            "div.agent-panel-content div.rounded-lg.border"
        )
        return cards.count()


class SkillsPage:
    """技能管理页"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/skills"

    # 页面就绪标识：搜索输入框
    _READY_SELECTOR = "input[placeholder*='搜索技能']"

    def goto(self):
        # SPA 导航优先（sidebar 测试已验证可靠），避免全页面刷新后 router 初始化问题
        nav_btn = self.page.locator("button.agent-sidebar-nav-item").filter(has_text="技能库")
        if nav_btn.count() > 0:
            nav_btn.first.click()
            try:
                self.page.locator(self._READY_SELECTOR).first.wait_for(state="attached", timeout=15000)
            except Exception:
                pass
            if self.is_loaded():
                return
        # 降级：全页面刷新（SPA 导航失败时）
        for _attempt in range(2):
            try:
                self.page.goto(self.url, wait_until="domcontentloaded")
            except Exception:
                pass
            self.page.wait_for_load_state("domcontentloaded")
            try:
                self.page.locator(self._READY_SELECTOR).first.wait_for(state="attached", timeout=15000)
            except Exception:
                pass
            if self.is_loaded():
                break
            try:
                self.page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
            self.page.wait_for_timeout(500)

    def is_loaded(self) -> bool:
        return "/ctrl/agent/skills" in self.page.url and \
            self.page.locator(self._READY_SELECTOR).count() > 0

    def reload(self) -> bool:
        """强制整页刷新并等待列表就绪。

        goto() 优先走侧边栏 SPA 导航，已在技能页时不会重新拉取列表；
        需要看到 API 预置/外部变更后的最新列表时必须先 reload。
        """
        for _attempt in range(2):
            try:
                self.page.reload(wait_until="domcontentloaded")
            except Exception:
                pass
            self.page.wait_for_load_state("domcontentloaded")
            try:
                self.page.locator(self._READY_SELECTOR).first.wait_for(state="attached", timeout=15000)
            except Exception:
                pass
            if self.is_loaded():
                return True
            try:
                self.page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
            self.page.wait_for_timeout(500)
        return self.is_loaded()

    def get_skill_count(self) -> int:
        """获取技能列表项数量（通过技能卡片容器计数，排除侧边栏智能体卡片）"""
        cards = self.page.locator("div.group.relative:not(.agent-sidebar-agent)")
        if cards.count() > 0:
            return cards.count()
        # fallback：搜索框存在说明页面已加载，用 API 返回数量
        return 0

    def get_skill_names(self) -> list[str]:
        """获取技能名称列表（从 API 拦截）"""
        skills_data = []

        def on_resp(r):
            if "/web/config/skills" in r.url and ".js" not in r.url:
                try:
                    data = r.json()
                    skills_data.extend(
                        s["name"] for s in data.get("data", {}).get("skills", [])
                    )
                except Exception:
                    pass

        self.page.on("response", on_resp)
        try:
            self.page.reload(wait_until="domcontentloaded")
        except Exception:
            pass
        self.page.wait_for_load_state("domcontentloaded")
        return skills_data

    def search(self, keyword: str):
        inp = self.page.locator("input[placeholder*='搜索技能']")
        if inp.count() > 0:
            inp.first.fill(keyword)
            self.page.wait_for_timeout(500)

    def clear_search(self):
        inp = self.page.locator("input[placeholder*='搜索技能']")
        if inp.count() > 0:
            inp.first.click()
            self.page.keyboard.press("Control+a")
            self.page.keyboard.press("Backspace")
            self.page.wait_for_timeout(500)

    def get_visible_skill_cards(self) -> int:
        """获取当前可见的技能卡片数量（搜索过滤后，仅计可见元素，排除侧边栏）"""
        cards = self.page.locator("div.group.relative:not(.agent-sidebar-agent):visible")
        if cards.count() > 0:
            return cards.count()
        return 0

    def has_upload_button(self) -> bool:
        return self.page.locator("button").filter(has_text="上传技能").count() > 0

    def has_skeleton_or_spinner(self) -> bool:
        """页面是否显示加载骨架屏或 Spinner"""
        skeleton = self.page.locator(
            "[role='progressbar'], [data-slot='skeleton'], "
            "div.animate-pulse, [data-slot='spinner']"
        )
        return skeleton.count() > 0

    # ─────────────────────────────────────────────────────────────
    # 新增方法（2026-08-26，任务四补充：文本创建/编辑/校验/取消）
    # 依据真实 DOM：新建技能按钮 → [role=menu] 菜单 → 原生 <dialog>
    # 表单字段 placeholder：my-skill / 可选，简要描述技能用途 / 输入 Markdown 内容...
    # ─────────────────────────────────────────────────────────────

    def _skill_dialog(self):
        """定位当前技能表单弹窗（Radix [role=dialog] + data-state=open，含「技能名称」标签）"""
        return self.page.locator("[role='dialog'][data-state='open']").filter(has_text="技能名称").last

    def has_skill_dialog(self, timeout: int = 5000) -> bool:
        """技能创建/编辑弹窗是否打开（wait_for 等待，禁止裸 count）"""
        try:
            self._skill_dialog().wait_for(state="visible", timeout=timeout)
            return True
        except Exception:
            return False

    def wait_skill_dialog_closed(self, timeout: int = 5000) -> bool:
        """等待技能弹窗关闭（data-state 变 closed 或从 DOM 移除）。

        与 has_skill_dialog 相反：has_skill_dialog 在弹窗可见时立即返回 True，
        不能用于断言"弹窗已关闭"（点击保存后弹窗仍在关闭中/请求未返回时会误判）。
        """
        try:
            self._skill_dialog().wait_for(state="hidden", timeout=timeout)
            return True
        except Exception:
            return False

    def open_manual_create_dialog(self) -> bool:
        """点击「新建技能」→ 菜单「手动创建」→ 打开创建弹窗"""
        new_btn = self.page.get_by_role("button", name="新建技能")
        new_btn.first.wait_for(state="visible", timeout=5000)
        new_btn.first.click()
        try:
            self.page.get_by_role("menuitem", name="手动创建").first.wait_for(state="visible", timeout=3000)
        except Exception:
            return False
        self.page.get_by_role("menuitem", name="手动创建").first.click()
        return self.has_skill_dialog(timeout=5000)

    def fill_create_form(self, name: str, description: str = "", content: str = ""):
        """填写创建弹窗表单（名称/描述/内容）"""
        dialog = self._skill_dialog()
        name_input = dialog.locator("input[placeholder*='my-skill']")
        name_input.first.wait_for(state="visible", timeout=5000)
        name_input.first.fill(name)
        if description:
            desc = dialog.locator("textarea[placeholder*='描述技能用途']")
            if desc.count() > 0:
                desc.first.fill(description)
        content_area = dialog.locator("textarea[placeholder*='输入 Markdown 内容']")
        if content_area.count() > 0:
            content_area.first.fill(content)

    def click_save(self, timeout: int = 5000):
        """点击弹窗「保存」按钮（限定技能弹窗容器，禁止全页面搜索）。"""
        # 先清空遗留 toast（session 级共享页面），确保后续 get_toast_text 读到本次操作产生的 toast
        try:
            self.page.locator("[data-sonner-toast]").first.wait_for(state="hidden", timeout=timeout)
        except Exception:
            pass
        btn = self._skill_dialog().get_by_role("button", name="保存")
        assert btn.count() > 0, "未找到「保存」按钮"
        btn.first.wait_for(state="visible", timeout=timeout)
        btn.first.click()

    def click_cancel(self, timeout: int = 5000) -> bool:
        """点击弹窗「取消」按钮（限定技能弹窗容器）；不存在则返回 False"""
        btn = self._skill_dialog().get_by_role("button", name="取消")
        try:
            btn.first.wait_for(state="visible", timeout=timeout)
            btn.first.click()
            return True
        except Exception:
            return False

    def get_last_toast_text(self, timeout: int = 5000) -> str:
        """读取本次操作触发的 sonner toast 文案。

        sonner 新 toast 插入 DOM 最前（.first=最新）；旧 toast 的清理等待
        由 click_save() 在点击前完成，这里只需等 .first 可见并返回其文本。
        """
        try:
            toasts = self.page.locator("[data-sonner-toast]")
            toasts.first.wait_for(state="visible", timeout=timeout)
            return toasts.first.inner_text()
        except Exception:
            return ""

    def _skill_card(self, name: str):
        """定位包含指定技能名的技能卡片容器（div.group.relative）"""
        return self.page.locator("div.group.relative:not(.agent-sidebar-agent)").filter(has_text=name).first

    def has_skill_card(self, name: str, timeout: int = 8000) -> bool:
        """技能卡片是否出现（wait_for 等待，禁止裸 count）"""
        try:
            self._skill_card(name).wait_for(state="visible", timeout=timeout)
            return True
        except Exception:
            return False

    def get_skill_card_action(self, name: str, action: str):
        """限定技能卡片容器内的操作按钮（下载/编辑/删除）"""
        return self._skill_card(name).get_by_role("button", name=action)


class McpPage:
    """MCP 服务器管理页"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/mcp"

    # 页面就绪标识：搜索输入框
    _READY_SELECTOR = "input[placeholder*='搜索 MCP'], input[placeholder*='搜索MCP']"

    def goto(self):
        for _attempt in range(2):
            try:
                self.page.goto(self.url, wait_until="domcontentloaded")
            except Exception:
                pass  # SPA 路由可能中断初始导航（net::ERR_ABORTED）
            self.page.wait_for_load_state("domcontentloaded")
            try:
                self.page.locator(self._READY_SELECTOR).first.wait_for(state="attached", timeout=15000)
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
            nav_btn = self.page.locator("button.agent-sidebar-nav-item").filter(has_text="MCP")
            if nav_btn.count() > 0:
                nav_btn.first.click()
                try:
                    self.page.locator(self._READY_SELECTOR).first.wait_for(state="attached", timeout=15000)
                except Exception:
                    pass

    def is_loaded(self) -> bool:
        return "/ctrl/agent/mcp" in self.page.url and \
            self.page.locator(self._READY_SELECTOR).count() > 0

    def search(self, keyword: str):
        inp = self.page.locator("input[placeholder*='搜索 MCP'], input[placeholder*='搜索MCP']")
        if inp.count() > 0:
            inp.first.fill(keyword)
            self.page.wait_for_timeout(500)

    def clear_search(self):
        inp = self.page.locator("input[placeholder*='搜索 MCP'], input[placeholder*='搜索MCP']")
        if inp.count() > 0:
            inp.first.fill("")
            self.page.wait_for_timeout(500)

    def get_server_count(self) -> int:
        """获取 MCP 服务器列表数量"""
        items = self.page.locator(
            "div.agent-panel-content div.rounded-lg.border, "
            "table tbody tr"
        )
        return items.count()


class SitesPage:
    """Agent Sites 管理页"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/sites"

    # 页面就绪标识：搜索输入框
    _READY_SELECTOR = "input[placeholder*='搜索 app'], input[placeholder*='搜索app']"

    def goto(self):
        for _attempt in range(2):
            try:
                self.page.goto(self.url, wait_until="domcontentloaded")
            except Exception:
                pass  # SPA 路由可能中断初始导航（net::ERR_ABORTED）
            self.page.wait_for_load_state("domcontentloaded")
            try:
                self.page.locator(self._READY_SELECTOR).first.wait_for(state="attached", timeout=15000)
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
            nav_btn = self.page.locator("button.agent-sidebar-nav-item").filter(has_text="AOS应用部署")
            if nav_btn.count() > 0:
                nav_btn.first.click()
                try:
                    self.page.locator(self._READY_SELECTOR).first.wait_for(state="attached", timeout=15000)
                except Exception:
                    pass

    def is_loaded(self) -> bool:
        return "/ctrl/agent/sites" in self.page.url and \
            self.page.locator(self._READY_SELECTOR).count() > 0

    def get_filter_tabs(self) -> list[str]:
        """获取筛选 Tab 列表"""
        tabs = self.page.locator("[role='tab']").all_text_contents()
        return [t.strip() for t in tabs if t.strip()]

    def click_filter_tab(self, tab_name: str):
        """点击筛选 Tab"""
        tab = self.page.get_by_text(tab_name, exact=True)
        tab.wait_for(state="visible", timeout=5000)
        tab.click()
        self.page.wait_for_timeout(500)

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

    def get_app_count(self) -> int:
        """获取 App 数量（表格行数）"""
        rows = self.page.locator("table tbody tr")
        return rows.count()
