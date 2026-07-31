# tests/pages/config_pages.py
"""配置管理页面 Page Objects（模型、技能、MCP、Agent Sites）"""
from playwright.sync_api import Page


class ModelsPage:
    """服务商与模型管理页"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/models"

    def goto(self):
        self.page.goto(self.url)
        self.page.wait_for_load_state("networkidle")

    def is_loaded(self) -> bool:
        return self.page.locator("h1, h2").filter(has_text="模型库").count() > 0

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

    def goto(self):
        self.page.goto(self.url)
        self.page.wait_for_load_state("networkidle")

    def is_loaded(self) -> bool:
        return self.page.locator("h1, h2").filter(has_text="技能管理").count() > 0

    def get_skill_count(self) -> int:
        """获取技能列表项数量（通过删除按钮数量判断）"""
        return self.page.locator("button").filter(has_text="删除").count()

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
        self.page.reload()
        self.page.wait_for_load_state("networkidle")
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
        return self.page.locator("button").filter(has_text="删除").count()

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

    def goto(self):
        self.page.goto(self.url)
        self.page.wait_for_load_state("networkidle")

    def is_loaded(self) -> bool:
        return self.page.locator("h1, h2").filter(has_text="MCP").count() > 0

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

    def goto(self):
        self.page.goto(self.url)
        self.page.wait_for_load_state("networkidle")

    def is_loaded(self) -> bool:
        return self.page.locator("h1, h2").filter(has_text="Agent Sites").count() > 0

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
