# tests/pages/algorithms_page.py
"""算法库页面 Page Object — 基于真实 DOM 结构编写"""
from playwright.sync_api import Page


class AlgorithmsPage:
    """算法库页面 /ctrl/agent/algorithms"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/algorithms"

    def goto(self):
        self.page.goto(self.url)
        self.page.wait_for_load_state("networkidle")

    def is_loaded(self) -> bool:
        """页面加载完成"""
        return "/ctrl/agent/algorithms" in self.page.url and \
            self.page.locator("div.agent-panel-content").count() > 0

    # === 搜索 ===

    def search(self, keyword: str):
        """搜索算法（需按 Enter 触发）"""
        inp = self.page.locator("input[placeholder*='搜索算法']")
        if inp.count() > 0:
            inp.first.fill(keyword)
            inp.first.press("Enter")
            self.page.wait_for_timeout(1500)

    def clear_search(self):
        """清空搜索（选中全部 + 删除 + Enter，避免空字符串搜索异常）"""
        inp = self.page.locator("input[placeholder*='搜索算法']")
        if inp.count() > 0:
            inp.first.click()
            inp.first.press("Control+a")
            inp.first.press("Backspace")
            inp.first.press("Enter")
            self.page.wait_for_timeout(1500)

    # === 分类筛选 ===

    def get_category_tabs(self) -> list[str]:
        """获取所有分类筛选按钮文字"""
        tabs = self.page.locator("button.rounded-full").filter(
            has_text="全部"
        )
        # 获取所有同级别的分类按钮
        all_tabs = self.page.locator("div.flex.items-center.gap-1\\.5 button.rounded-full")
        return [all_tabs.nth(i).inner_text().strip() for i in range(all_tabs.count())]

    def filter_by_category(self, category: str):
        """按分类筛选"""
        self.page.locator("div.flex.items-center.gap-1\\.5").get_by_role(
            "button", name=category
        ).click()
        self.page.wait_for_timeout(500)

    # === 列表 ===

    def get_algo_cards(self):
        """获取所有算法卡片元素"""
        return self.page.locator("div.grid.grid-cols-3 > div.flex.flex-col.gap-3.rounded-lg")

    def get_algo_count(self) -> int:
        """获取算法卡片数量"""
        return self.get_algo_cards().count()

    def get_algo_names(self) -> list[str]:
        """获取所有算法名称"""
        cards = self.get_algo_cards()
        names = []
        for i in range(cards.count()):
            text = cards.nth(i).inner_text()
            # 名称在第一行，可能含 emoji 前缀
            first_line = text.split("\n")[0].strip()
            if first_line:
                names.append(first_line)
        return names

    def has_algo(self, keyword: str) -> bool:
        """列表中是否包含包含关键词的算法"""
        body = self.page.locator("div.agent-panel-content")
        return keyword in body.inner_text()

    # === 操作按钮 ===

    def click_view_detail(self, name: str):
        """点击某个算法的「查看详情」按钮"""
        card = self.get_algo_cards().filter(has_text=name)
        btn = card.first.get_by_role("button", name="查看详情")
        if btn.count() > 0:
            btn.click()
            self.page.wait_for_timeout(1000)

    def click_copy_code(self, name: str):
        """点击某个算法的「复制代码」按钮"""
        card = self.get_algo_cards().filter(has_text=name)
        btn = card.first.get_by_role("button", name="复制代码")
        if btn.count() > 0:
            btn.click()
            self.page.wait_for_timeout(1000)
