# tests/pages/sidebar_pages.py
"""侧边栏新页面 Page Objects（智能体编排、记忆、知识库、定时任务、组织、API Key）"""
from playwright.sync_api import Page


class WorkflowPage:
    """智能体编排页 /ctrl/agent/workflow"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/workflow"

    def goto(self):
        self.page.goto(self.url)
        self.page.wait_for_load_state("networkidle")

    def is_loaded(self) -> bool:
        return self.page.locator("h1").filter(has_text="智能体编排").count() > 0

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
        # 排除侧边栏卡片
        cards = self.page.locator(
            "[class*='workflow'] [class*='card'], "
            "main [class*='card'], "
            "[class*='content'] [class*='card']"
        )
        return cards.count()

    def has_create_button(self) -> bool:
        return self.page.get_by_role("button", name="新建工作流").count() > 0


class MemoryPage:
    """记忆页 /ctrl/agent/memories"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/memories"

    def goto(self):
        self.page.goto(self.url)
        self.page.wait_for_load_state("networkidle")

    def is_loaded(self) -> bool:
        return self.page.locator("h1").filter(has_text="记忆").count() > 0

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
        ).or_(
            self.page.get_by_role("button", name="表格")
        )
        return btns.count() > 0


class KnowledgeBasePage:
    """知识库页 /ctrl/agent/knowledge-bases"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/knowledge-bases"

    def goto(self):
        self.page.goto(self.url)
        self.page.wait_for_load_state("networkidle")

    def is_loaded(self) -> bool:
        return self.page.locator("h1").filter(has_text="知识库").count() > 0

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
            "main [class*='card'], [class*='content'] [class*='card']"
        )
        return cards.count()

    def has_create_button(self) -> bool:
        return self.page.get_by_role("button", name="新建知识库").count() > 0


class TasksPage:
    """定时任务页 /ctrl/agent/tasks"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/tasks"

    def goto(self):
        self.page.goto(self.url)
        self.page.wait_for_load_state("networkidle")

    def is_loaded(self) -> bool:
        return self.page.locator("h1").filter(has_text="定时任务").count() > 0

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


class OrganizationPage:
    """组织管理页 /ctrl/agent/organizations"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/organizations"

    def goto(self):
        self.page.goto(self.url)
        self.page.wait_for_load_state("networkidle")

    def is_loaded(self) -> bool:
        return self.page.locator("h1").filter(has_text="组织管理").count() > 0

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

    def goto(self):
        self.page.goto(self.url)
        self.page.wait_for_load_state("networkidle")

    def is_loaded(self) -> bool:
        return self.page.locator("h1").filter(has_text="API 密钥").count() > 0

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
        return self.page.get_by_role("button", name="创建密钥").count() > 0
