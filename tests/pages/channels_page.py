# tests/pages/channels_page.py
"""渠道管理页面 Page Object"""
from playwright.sync_api import Page


class ChannelsPage:
    """渠道管理页 /ctrl/agent/channels"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/channels"

    def goto(self):
        self.page.goto(self.url)
        self.page.wait_for_load_state("networkidle")
        self.page.wait_for_timeout(2000)

    def is_loaded(self) -> bool:
        return "/ctrl/agent/channels" in self.page.url and \
            self.page.locator("div.agent-panel-content").count() > 0

    def has_hermes_status(self) -> bool:
        """是否有 Hermes 连接状态展示"""
        body = self.page.locator("div.agent-panel-content")
        if body.count() == 0:
            return False
        text = body.first.inner_text()
        return any(kw in text for kw in ["Hermes", "hermes", "连接", "状态", "Channel"])

    def get_provider_count(self) -> int:
        """获取 Channel Provider 卡片数量"""
        cards = self.page.locator("div.agent-panel-content [data-slot='card']")
        if cards.count() == 0:
            cards = self.page.locator("div.agent-panel-content > div > div")
        return cards.count()

    def has_create_binding_button(self) -> bool:
        """是否有创建绑定按钮"""
        btns = self.page.get_by_role("button", name="新建").or_(
            self.page.get_by_role("button", name="创建").or_(
                self.page.get_by_role("button", name="添加")
            )
        )
        return btns.count() > 0

    def get_page_text(self) -> str:
        """获取页面主内容文本"""
        body = self.page.locator("div.agent-panel-content")
        if body.count() > 0:
            return body.first.inner_text()
        return ""
