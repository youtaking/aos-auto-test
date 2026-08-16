# tests/pages/sidebar_pages.py
"""侧边栏新页面 Page Objects（智能体编排、记忆、知识库、定时任务、组织、API Key）"""
from playwright.sync_api import Page


class WorkflowPage:
    """智能体编排页 /ctrl/agent/workflow"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/workflow"

    # 页面就绪标识：副标题（仅工作流页面有，不依赖懒加载）
    _READY_SELECTOR = "text=管理工作流与运行历史"

    def goto(self):
        for _attempt in range(2):
            try:
                self.page.goto(self.url, wait_until="domcontentloaded")
            except Exception:
                pass  # SPA 路由可能中断初始导航
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
            nav_btn = self.page.locator("button.agent-sidebar-nav-item").filter(has_text="智能体编排")
            if nav_btn.count() > 0:
                nav_btn.first.click()
                try:
                    self.page.locator(self._READY_SELECTOR).first.wait_for(state="attached", timeout=15000)
                except Exception:
                    pass

    def is_loaded(self) -> bool:
        if "/ctrl/agent/workflow" not in self.page.url:
            return False
        return self.page.locator(self._READY_SELECTOR).count() > 0

    def search(self, keyword: str):
        """搜索工作流"""
        inp = self.page.locator("input[placeholder*='搜索工作流']")
        if inp.count() > 0:
            inp.first.fill(keyword)
            self.page.wait_for_timeout(500)

    def clear_search(self):
        inp = self.page.locator("input[placeholder*='搜索工作流']")
        if inp.count() > 0:
            inp.first.fill("")
            self.page.wait_for_timeout(500)

    def get_workflow_count(self) -> int:
        """获取工作流卡片数量"""
        # 工作流卡片可能在不同容器内
        cards = self.page.locator(
            "div.agent-panel-content div.rounded-lg.border, "
            "div.group.rounded-lg.border"
        )
        return cards.count()

    def has_create_button(self) -> bool:
        btn = self.page.get_by_role("button", name="新建工作流")
        try:
            btn.first.wait_for(state="visible", timeout=10000)
            return btn.first.is_enabled()
        except Exception:
            return False


class MemoryPage:
    """记忆页 /ctrl/agent/memories"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/memories"

    # 页面就绪标识：Tab 或"未开启"提示（记忆服务未配置时显示"记忆能力未开启..."）
    _READY_SELECTORS = "[role='tab'], :text('未开启'), :text('记忆能力'), :text('Hindsight')"

    def goto(self):
        for _attempt in range(2):
            try:
                self.page.goto(self.url, wait_until="domcontentloaded")
            except Exception:
                pass
            self.page.wait_for_load_state("domcontentloaded")
            try:
                self.page.locator(self._READY_SELECTORS).first.wait_for(state="attached", timeout=15000)
            except Exception:
                pass
            if self.is_loaded():
                break
            self.page.wait_for_timeout(3000)
        # 降级：侧边栏 SPA 导航
        if not self.is_loaded():
            nav_btn = self.page.locator("button.agent-sidebar-nav-item").filter(has_text="记忆")
            if nav_btn.count() > 0:
                nav_btn.first.click()
                try:
                    self.page.locator(self._READY_SELECTORS).first.wait_for(state="attached", timeout=15000)
                except Exception:
                    pass

    def is_loaded(self) -> bool:
        return "/ctrl/agent/memor" in self.page.url and \
            self.page.locator(self._READY_SELECTORS).count() > 0

    def get_tab_names(self) -> list[str]:
        """获取分类 Tab 名称列表"""
        tabs = self.page.locator("[role='tab']")
        return [t.strip() for t in tabs.all_text_contents() if t.strip()]

    def click_tab(self, name: str):
        """点击某个分类 Tab"""
        self.page.locator("[role='tab']").filter(has_text=name).first.click()
        self.page.wait_for_timeout(500)

    def is_tab_active(self, name: str) -> bool:
        """某个 Tab 是否处于激活状态"""
        tab = self.page.locator("[role='tab']").filter(has_text=name)
        if tab.count() == 0:
            return False
        cls = tab.first.get_attribute("class") or ""
        aria = tab.first.get_attribute("aria-selected") or ""
        return "active" in cls.lower() or aria == "true" or "selected" in cls.lower()

    def has_view_buttons(self) -> bool:
        """是否有视图切换按钮（星座图/图谱/表格/时间线）"""
        btns = self.page.get_by_role("button", name="星座图").or_(
            self.page.get_by_role("button", name="图谱")
        )
        return btns.count() > 0


class KnowledgeBasePage:
    """知识库页 /ctrl/agent/knowledge-bases"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/knowledge-bases"

    # 页面就绪标识：搜索输入框
    _READY_SELECTOR = "input[placeholder*='搜索知识库']"

    def goto(self):
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
        # 降级：侧边栏 SPA 导航
        if not self.is_loaded():
            nav_btn = self.page.locator("button.agent-sidebar-nav-item").filter(has_text="知识库")
            if nav_btn.count() > 0:
                nav_btn.first.click()
                try:
                    self.page.locator(self._READY_SELECTOR).first.wait_for(state="attached", timeout=15000)
                except Exception:
                    pass

    def is_loaded(self) -> bool:
        return "/ctrl/agent/knowledge" in self.page.url and \
            self.page.locator(self._READY_SELECTOR).count() > 0

    def search(self, keyword: str):
        inp = self.page.locator("input[placeholder*='搜索知识库']")
        if inp.count() > 0:
            inp.first.fill(keyword)
            self.page.wait_for_timeout(500)

    def clear_search(self):
        inp = self.page.locator("input[placeholder*='搜索知识库']")
        if inp.count() > 0:
            inp.first.fill("")
            self.page.wait_for_timeout(500)

    def get_kb_count(self) -> int:
        """获取知识库卡片数量"""
        cards = self.page.locator(
            "div.agent-panel-content div.rounded-lg.border"
        )
        return cards.count()

    def has_create_button(self) -> bool:
        btn = self.page.get_by_role("button", name="新建知识库")
        return btn.count() > 0 and btn.first.is_visible() and btn.first.is_enabled()


class TasksPage:
    """定时任务页 /ctrl/agent/tasks"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/tasks"

    # 页面就绪标识：搜索输入框或定时任务按钮
    _READY_SELECTOR = "input[placeholder*='搜索任务'], button:has-text('定时任务')"

    def goto(self):
        for _attempt in range(2):
            try:
                self.page.goto(self.url, wait_until="domcontentloaded")
            except Exception:
                pass  # SPA 路由可能中断初始导航
            self.page.wait_for_load_state("domcontentloaded")
            try:
                self.page.locator(self._READY_SELECTOR).first.wait_for(state="attached", timeout=15000)
            except Exception:
                pass
            if self.is_loaded():
                break
            self.page.wait_for_timeout(3000)

    def is_loaded(self) -> bool:
        return "/ctrl/agent/tasks" in self.page.url and \
            self.page.locator(self._READY_SELECTOR).count() > 0

    def get_tab_names(self) -> list[str]:
        tabs = self.page.locator("[role='tab']")
        return [t.strip() for t in tabs.all_text_contents() if t.strip()]

    def click_tab(self, name: str):
        self.page.locator("[role='tab']").filter(has_text=name).first.click()
        self.page.wait_for_timeout(500)

    def get_task_count(self) -> int:
        """表格中的任务行数"""
        rows = self.page.locator("table tbody tr")
        return rows.count()

    def has_table(self) -> bool:
        return self.page.locator("table").count() > 0

    def search(self, keyword: str):
        inp = self.page.locator("input[placeholder*='搜索任务']")
        if inp.count() > 0:
            inp.first.fill(keyword)
            self.page.wait_for_timeout(500)

    def clear_search(self):
        inp = self.page.locator("input[placeholder*='搜索任务']")
        if inp.count() > 0:
            inp.first.fill("")
            self.page.wait_for_timeout(500)

    def click_create(self):
        """点击「新建任务」按钮"""
        btn = self.page.get_by_role("button", name="新建任务")
        if btn.count() == 0:
            # 尝试其他可能的按钮文本
            btn = self.page.locator("button").filter(has_text="新建")
        if btn.count() > 0:
            btn.first.click()
            self.page.wait_for_timeout(1000)

    def is_dialog_open(self) -> bool:
        """检查新建/编辑任务弹窗是否打开"""
        dialog = self.page.locator("[role='dialog']")
        return dialog.count() > 0 and dialog.first.is_visible()


class OrganizationPage:
    """组织管理页 /ctrl/agent/organizations"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/organizations"

    # 页面就绪标识：h2 标题
    _READY_SELECTOR = "h2"

    def goto(self):
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
        # 降级：侧边栏 SPA 导航
        if not self.is_loaded():
            nav_btn = self.page.locator("button.agent-sidebar-nav-item").filter(has_text="组织")
            if nav_btn.count() > 0:
                nav_btn.first.click()
                try:
                    self.page.locator(self._READY_SELECTOR).first.wait_for(state="attached", timeout=15000)
                except Exception:
                    pass

    def is_loaded(self) -> bool:
        return "/ctrl/agent/organization" in self.page.url and \
            self.page.locator(self._READY_SELECTOR).count() > 0

    def get_org_name(self) -> str:
        """获取当前组织名称"""
        h2 = self.page.locator("h2")
        if h2.count() > 0:
            return h2.first.inner_text().strip()
        return ""

    def has_member_section(self) -> bool:
        """是否有成员区域"""
        return self.page.locator("h3").filter(has_text="成员").count() > 0

    def get_member_count_text(self) -> str:
        """获取成员数文本，如 '成员 (42)'"""
        h3 = self.page.locator("h3").filter(has_text="成员")
        if h3.count() > 0:
            return h3.first.inner_text().strip()
        return ""


class ApiKeyPage:
    """API 密钥页 /ctrl/agent/apikeys"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/apikeys"

    # 页面就绪标识：搜索输入框
    _READY_SELECTOR = "input[placeholder*='搜索密钥']"

    def goto(self):
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
        # 降级：侧边栏 SPA 导航
        if not self.is_loaded():
            nav_btn = self.page.locator("button.agent-sidebar-nav-item").filter(has_text="API Key")
            if nav_btn.count() > 0:
                nav_btn.first.click()
                try:
                    self.page.locator(self._READY_SELECTOR).first.wait_for(state="attached", timeout=15000)
                except Exception:
                    pass

    def is_loaded(self) -> bool:
        return "/ctrl/agent/apikeys" in self.page.url and \
            self.page.locator(self._READY_SELECTOR).count() > 0

    def search(self, keyword: str):
        inp = self.page.locator("input[placeholder*='搜索密钥']")
        if inp.count() > 0:
            inp.first.fill(keyword)
            inp.first.press("Enter")
            self.page.wait_for_timeout(1500)

    def clear_search(self):
        inp = self.page.locator("input[placeholder*='搜索密钥']")
        if inp.count() > 0:
            inp.first.fill("")
            inp.first.press("Enter")
            self.page.wait_for_timeout(1500)

    def get_key_count(self) -> int:
        """获取密钥列表项数量（grid 卡片布局）"""
        return self.page.locator("div.grid.gap-3 > div").count()

    def has_create_button(self) -> bool:
        btn = self.page.get_by_role("button", name="创建密钥")
        return btn.count() > 0 and btn.first.is_visible() and btn.first.is_enabled()


class SidebarNavigation:
    """侧边栏导航通用操作"""

    # 侧边栏菜单项 → 预期 URL 路径
    NAV_ITEMS = {
        "新建智能体": "/ctrl/agent/home",
        "智能体管理": "/ctrl/agent/agents",
        "智能体编排": "/ctrl/agent/workflow",
        "记忆": "/ctrl/agent/memor",
        "知识库": "/ctrl/agent/knowledge",
        "定时任务": "/ctrl/agent/tasks",
        "组织": "/ctrl/agent/organization",
        "API Key": "/ctrl/agent/apikeys",
        "模型库": "/ctrl/agent/models",
        "垂直模型库": "/ctrl/agent/vertical-models",
        "算法库": "/ctrl/agent/algorithms",
        "技能库": "/ctrl/agent/skills",
        "MCP": "/ctrl/agent/mcp",
        "Agent Sites": "/ctrl/agent/sites",
    }

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url

    def get_nav_items(self) -> list[str]:
        """获取所有侧边栏导航项名称"""
        items = self.page.locator("button.agent-sidebar-nav-item")
        return [t.strip() for t in items.all_text_contents() if t.strip()]

    def get_nav_count(self) -> int:
        return self.page.locator("button.agent-sidebar-nav-item").count()

    def click_nav(self, name: str):
        """点击侧边栏导航项"""
        btn = self.page.locator("button.agent-sidebar-nav-item").filter(
            has_text=name
        )
        if btn.count() > 0:
            btn.first.click()
            self.page.wait_for_load_state("domcontentloaded")

    def is_nav_active(self, name: str) -> bool:
        """某导航项是否处于激活状态"""
        btn = self.page.locator("button.agent-sidebar-nav-item").filter(
            has_text=name
        )
        if btn.count() == 0:
            return False
        cls = btn.first.get_attribute("class") or ""
        return "active" in cls.lower() or "selected" in cls.lower()

    def get_group_labels(self) -> list[str]:
        """获取侧边栏分组标签（如 '核心'、'配置'）"""
        groups = self.page.locator("aside.agent-sidebar span, aside.agent-sidebar h3, aside.agent-sidebar h4")
        return [t.strip() for t in groups.all_text_contents() if t.strip()]

    def has_nav_item(self, name: str) -> bool:
        return self.page.locator("button.agent-sidebar-nav-item").filter(
            has_text=name
        ).count() > 0

    def has_panel_content(self) -> bool:
        return self.page.locator("div.agent-panel-content").count() > 0
