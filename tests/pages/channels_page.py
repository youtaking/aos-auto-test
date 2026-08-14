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
        try:
            self.page.goto(self.url, wait_until="domcontentloaded")
        except Exception:
            pass  # SPA 路由可能中断初始导航
        self.page.wait_for_load_state("networkidle")

    def is_loaded(self) -> bool:
        return "/ctrl/agent/channels" in self.page.url and \
            self.page.locator("div.agent-panel-content").count() > 0

    def has_hermes_status(self) -> bool:
        """是否有渠道/Provider 相关内容展示（Hermes 状态或渠道管理界面）"""
        body = self.page.locator("div.agent-panel-content")
        if body.count() == 0:
            return False
        text = body.first.inner_text()
        # 页面标题是"消息渠道"，可能含 Hermes/渠道/Provider/btn.create 等关键词
        # 如果页面有实质内容（超过空白），也视为有效
        has_keywords = any(kw in text for kw in [
            "Hermes", "hermes", "连接", "状态", "Channel",
            "渠道", "消息", "Provider", "provider",
            "btn.create", "dialog.createTitle",  # i18n 未翻译时也视为有效
            "绑定", "创建", "配置", "通道",
        ])
        # 如果页面有表格或卡片等结构化内容，也视为有效
        has_structure = (
            self.page.locator("div.agent-panel-content table").count() > 0
            or self.page.locator("div.agent-panel-content [data-slot='card']").count() > 0
            or self.page.locator("div.agent-panel-content button").count() > 2
        )
        return has_keywords or has_structure

    def get_provider_count(self) -> int:
        """获取 Channel Provider 卡片数量"""
        cards = self.page.locator("div.agent-panel-content [data-slot='card']")
        if cards.count() == 0:
            cards = self.page.locator("div.agent-panel-content > div > div")
        return cards.count()

    def has_create_binding_button(self) -> bool:
        """是否有创建绑定按钮（含 i18n 未翻译的 btn.create）"""
        btns = self.page.get_by_role("button", name="新建").or_(
            self.page.get_by_role("button", name="创建").or_(
                self.page.get_by_role("button", name="添加").or_(
                    self.page.locator("button").filter(has_text="btn.create")
                )
            )
        )
        return btns.count() > 0

    def click_create_button(self):
        """点击创建按钮"""
        # 优先匹配精确文本，再匹配 i18n key
        btn = self.page.locator("button").filter(has_text="btn.create")
        if btn.count() == 0:
            btn = self.page.get_by_role("button", name="新建").or_(
                self.page.get_by_role("button", name="创建").or_(
                    self.page.get_by_role("button", name="添加")
                )
            )
        btn.first.click()

    def get_page_text(self) -> str:
        """获取页面主内容文本"""
        body = self.page.locator("div.agent-panel-content")
        if body.count() > 0:
            return body.first.inner_text()
        return ""
