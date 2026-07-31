# tests/pages/views_page.py
"""产品视图页面 Page Object"""
from playwright.sync_api import Page


class ViewsPage:
    """产品视图页 /ctrl/agent/views"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/views"

    def goto(self):
        self.page.goto(self.url)
        self.page.wait_for_load_state("networkidle")

    def is_loaded(self) -> bool:
        return "/ctrl/agent/views" in self.page.url and \
            self.page.locator("div.agent-panel-content").count() > 0

    def search(self, keyword: str):
        """搜索视图"""
        inp = self.page.locator("input[placeholder='输入视图名称']")
        if inp.count() > 0:
            inp.first.fill(keyword)
            self.page.wait_for_timeout(500)

    def clear_search(self):
        """清空搜索"""
        inp = self.page.locator("input[placeholder='输入视图名称']")
        if inp.count() > 0:
            inp.first.fill("")
            self.page.wait_for_timeout(500)

    def get_view_count(self) -> int:
        """获取视图卡片数量"""
        cards = self.page.locator("div.agent-panel-content [data-slot='card']")
        if cards.count() == 0:
            cards = self.page.locator("div.agent-panel-content > div > div")
        return cards.count()

    def has_create_button(self) -> bool:
        """是否有新建按钮（"创建 ProdView" 或 "新建"）"""
        btns = self.page.get_by_role("button", name="新建").or_(
            self.page.locator("button").filter(has_text="创建")
        )
        return btns.count() > 0

    def click_create_button(self):
        """点击创建 ProdView 按钮"""
        btn = self.page.locator("button").filter(has_text="创建 ProdView")
        if btn.count() == 0:
            btn = self.page.get_by_role("button", name="新建").or_(
                self.page.locator("button").filter(has_text="创建")
            )
        btn.first.click()

    def get_page_text(self) -> str:
        """获取页面主内容文本"""
        body = self.page.locator("div.agent-panel-content")
        if body.count() > 0:
            return body.first.inner_text()
        return ""
