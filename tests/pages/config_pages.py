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
            self.page.wait_for_timeout(3000)
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
            self.page.wait_for_timeout(3000)

    def is_loaded(self) -> bool:
        return "/ctrl/agent/skills" in self.page.url and \
            self.page.locator(self._READY_SELECTOR).count() > 0

    def get_skill_count(self) -> int:
        """获取技能列表项数量（通过技能卡片容器计数）"""
        cards = self.page.locator("div.group.relative")
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
            inp.first.fill("")
            self.page.wait_for_timeout(500)

    def get_visible_skill_cards(self) -> int:
        """获取当前可见的技能卡片数量（搜索过滤后）"""
        cards = self.page.locator("div.group.relative")
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
            self.page.wait_for_timeout(3000)
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
            self.page.wait_for_timeout(3000)
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
        self.page.get_by_text(tab_name, exact=True).click()
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
