# tests/pages/views_page.py
"""发布视图 Page Object — Agent 详情页的「发布视图」Tab"""
from playwright.sync_api import Page


class ViewsPage:
    """发布视图（ProdView）— Agent 详情页的 Tab"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url

    def goto(self, agent_name: str = "my-auto-test"):
        """导航到指定 Agent 的发布视图 Tab"""
        # 1. 进入首页
        try:
            self.page.goto(f"{self.base_url}/ctrl/agent/home", wait_until="domcontentloaded")
        except Exception:
            pass
        self.page.wait_for_load_state("domcontentloaded")

        # 2. 等待 Agent 卡片出现并点击
        card = self.page.locator("button.agent-sidebar-agent-card").filter(has_text=agent_name)
        # 等待侧边栏加载（最多 10 秒）
        for _ in range(10):
            if card.count() > 0:
                break
            self.page.wait_for_timeout(1000)

        if card.count() == 0:
            return  # Agent 不存在

        card.first.scroll_into_view_if_needed()
        self.page.wait_for_timeout(300)
        card.first.click()
        self.page.wait_for_timeout(1000)

        # 如果普通点击没导航，用 JS 点击
        if "/chat/" not in self.page.url:
            card.first.evaluate("el => el.click()")
            self.page.wait_for_timeout(2000)

        # 3. 展开右侧 ArtifactsPanel（默认折叠）
        expand_btn = self.page.locator("button.agent-artifacts-expand-btn")
        if expand_btn.count() > 0 and expand_btn.first.is_visible():
            title = expand_btn.first.get_attribute("title") or ""
            if "show" in title.lower() or "显示" in title:
                expand_btn.first.click()
                self.page.wait_for_timeout(1500)
            else:
                # 面板已展开，等待 Tab 栏渲染
                self.page.wait_for_timeout(500)

        # 4. 点击「发布视图」Tab（等待可见后再点击，避免面板动画期间点击无效）
        prod_view_tab = self.page.get_by_role("button", name="发布视图")
        if prod_view_tab.count() == 0:
            return  # 没有发布视图 Tab

        try:
            prod_view_tab.first.wait_for(state="visible", timeout=5000)
        except Exception:
            pass

        # 使用 force=True 绕过 resizable-panel-group 遮挡（与 Artifacts 面板同一根因）
        prod_view_tab.first.click(force=True)
        self.page.wait_for_timeout(1500)

    def is_loaded(self) -> bool:
        """发布视图页面是否加载"""
        # 检查是否有「发布视图」标题或创建按钮或视图列表
        has_title = self.page.get_by_text("发布视图").count() > 0
        has_create = self.page.locator("button").filter(
            has=self.page.locator("svg.lucide-plus")
        ).count() > 0
        has_views = self.page.locator("text=/已启用|已禁用/").count() > 0
        return has_title or has_create or has_views

    def get_view_count(self) -> int:
        """获取视图卡片数量"""
        # 视图卡片是带有状态圆点的 div
        cards = self.page.locator("div.rounded-lg.border")
        return cards.count()

    def has_create_button(self) -> bool:
        """是否有创建视图按钮（+ 图标按钮）"""
        # 创建按钮在「发布视图」标题旁边
        title_area = self.page.locator("text=发布视图").locator("..")
        btn = title_area.locator("button").filter(has=self.page.locator("svg.lucide-plus"))
        return btn.count() > 0 and btn.first.is_visible()

    def click_create_button(self):
        """点击创建视图按钮"""
        title_area = self.page.locator("text=发布视图").locator("..")
        btn = title_area.locator("button").filter(has=self.page.locator("svg.lucide-plus"))
        if btn.count() > 0:
            btn.first.click()
            self.page.wait_for_timeout(1000)

    def get_page_text(self) -> str:
        """获取页面主内容文本"""
        body = self.page.locator("div.agent-panel-content")
        if body.count() > 0:
            return body.first.inner_text()
        return ""
