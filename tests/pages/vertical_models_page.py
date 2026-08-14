# tests/pages/vertical_models_page.py
"""垂直模型库页面 Page Object — 基于真实 DOM 结构编写"""
from playwright.sync_api import Page


class VerticalModelsPage:
    """垂直模型库页面 /ctrl/agent/vertical-models"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/vertical-models"

    def goto(self):
        try:
            self.page.goto(self.url, wait_until="domcontentloaded")
        except Exception:
            pass  # SPA 路由可能中断初始导航
        self.page.wait_for_load_state("networkidle")

    def is_loaded(self) -> bool:
        """页面标题「垂直模型库」可见"""
        return "/ctrl/agent/vertical" in self.page.url and self.page.locator("div.agent-panel-content").count() > 0

    # === 搜索 ===

    def search(self, keyword: str):
        """搜索模型"""
        inp = self.page.locator("input[placeholder*='搜索模型']")
        if inp.count() > 0:
            inp.first.fill(keyword)
            self.page.wait_for_timeout(500)

    def clear_search(self):
        """清空搜索"""
        inp = self.page.locator("input[placeholder*='搜索模型']")
        if inp.count() > 0:
            inp.first.fill("")
            self.page.wait_for_timeout(500)

    # === 列表 ===

    def get_model_cards(self):
        """获取所有模型卡片元素"""
        return self.page.locator("div.rounded-lg.border.bg-card.p-5")

    def get_model_count(self) -> int:
        """获取模型卡片数量"""
        return self.get_model_cards().count()

    def get_model_names(self) -> list[str]:
        """获取所有模型名称（从卡片文本中提取）"""
        cards = self.get_model_cards()
        names = []
        for i in range(cards.count()):
            text = cards.nth(i).inner_text()
            # 名称在第一行，跳过 emoji 前缀
            first_line = text.split("\n")[0].strip()
            # 去掉开头的 emoji（如 🚛🦺⚙️⚡）
            if first_line and len(first_line) > 1:
                names.append(first_line)
        return names

    def has_model(self, keyword: str) -> bool:
        """列表中是否包含包含关键词的模型"""
        body = self.page.locator("div.agent-panel-content")
        return keyword in body.inner_text()
