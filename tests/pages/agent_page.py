# tests/pages/agent_page.py
"""智能体管理页面 Page Object"""
from playwright.sync_api import Page, expect


class AgentPage:
    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/agents"

    def goto(self):
        for _attempt in range(2):
            try:
                self.page.goto(self.url, wait_until="domcontentloaded")
            except Exception:
                pass  # SPA 路由可能中断初始导航
            self.page.wait_for_load_state("domcontentloaded")
            # 等待 React 渲染完成
            try:
                self.page.locator("h1, h2").filter(has_text="智能体管理").first.wait_for(
                    state="visible", timeout=8000
                )
                break  # 页面加载成功
            except Exception:
                pass
            # React.lazy 加载 _panel layout 需要额外时间
            if self.page.locator("div.agent-panel-content").count() > 0:
                break
            try:
                self.page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
            self.page.wait_for_timeout(500)
        # 降级：侧边栏 SPA 导航
        if self.page.locator("div.agent-panel-content").count() == 0:
            nav_btn = self.page.locator("button.agent-sidebar-nav-item").filter(has_text="智能体管理")
            if nav_btn.count() > 0:
                nav_btn.first.wait_for(state="visible", timeout=5000)
                nav_btn.first.click()
                try:
                    self.page.locator("div.agent-panel-content").first.wait_for(state="attached", timeout=8000)
                except Exception:
                    pass

    def is_loaded(self) -> bool:
        """页面标题「智能体管理」可见"""
        return self.page.locator("h1, h2").filter(has_text="智能体管理").count() > 0

    def get_agent_cards(self):
        """获取主内容区所有智能体卡片元素（div.agent-badge）"""
        return self.page.locator("div.agent-badge")

    def get_agent_names(self) -> list[str]:
        """获取当前显示的智能体名称列表（从 div.agent-badge-name 提取）"""
        name_elements = self.page.locator("div.agent-badge-name")
        return [name_elements.nth(i).inner_text().strip() for i in range(name_elements.count())]

    def get_agent_count(self) -> int:
        """获取当前显示的智能体卡片数量（等待加载完成）"""
        # 等待加载状态消失（"加载智能体..." 不再可见）
        loading = self.page.locator("text=加载智能体")
        try:
            loading.first.wait_for(state="hidden", timeout=10000)
        except Exception:
            pass  # 可能已经加载完成
        return self.get_agent_cards().count()

    def search_agent(self, keyword: str):
        """搜索智能体"""
        search_input = self.page.locator("input[placeholder*='搜索']")
        search_input.wait_for(state="visible", timeout=5000)
        search_input.fill(keyword)
        self.page.wait_for_timeout(500)

    def clear_search(self):
        """清空搜索"""
        search_input = self.page.locator("input[placeholder*='搜索']")
        search_input.wait_for(state="visible", timeout=5000)
        search_input.fill("")
        self.page.wait_for_timeout(500)

    def filter_by_category(self, category: str):
        """按分类筛选（全部/通用助理/数据分析/搜索检索/监控告警/代码助手/自定义）"""
        btn = self.page.get_by_role("button", name=category)
        btn.wait_for(state="visible", timeout=5000)
        btn.click()
        self.page.wait_for_timeout(500)

    def click_create_button(self):
        """点击「创建智能体」按钮（页面内容区）"""
        btn = self.page.get_by_role("button", name="创建智能体")
        if btn.count() == 0:
            btn = self.page.get_by_role("button", name="新建智能体")
        btn.first.wait_for(state="visible", timeout=5000)
        btn.first.click()

    def is_create_dialog_open(self) -> bool:
        """创建对话框是否打开（导航到 agent/home 页面并显示 dialog）"""
        try:
            self.page.wait_for_url(lambda url: "/agent/home" in url, timeout=5000)
            self.page.wait_for_selector("[role='dialog']", timeout=5000)
            return True
        except Exception:
            return False

    def is_on_home_page(self) -> bool:
        """是否在 agent home 页面"""
        return "/agent/home" in self.page.url

    def fill_create_form(self, name: str, description: str = ""):
        """填写创建表单"""
        dialog = self.page.locator("[role='dialog']")
        name_input = dialog.locator("input").first
        name_input.wait_for(state="visible", timeout=5000)
        name_input.fill(name)
        if description:
            textarea = dialog.locator("textarea")
            if textarea.count() > 0:
                textarea.wait_for(state="visible", timeout=5000)
                textarea.fill(description)

    def submit_create_form(self):
        """提交创建表单"""
        dialog = self.page.locator("[role='dialog']")
        # 点击对话框中的确认/创建按钮
        submit_btn = dialog.get_by_role("button", name="创建").or_(
            dialog.get_by_role("button", name="确定")
        )
        submit_btn.first.wait_for(state="visible", timeout=5000)
        submit_btn.first.click()
        self.page.wait_for_load_state("domcontentloaded")

    def close_dialog(self):
        """关闭对话框"""
        dialog = self.page.locator("[role='dialog']")
        close_btn = dialog.get_by_role("button", name="取消").or_(
            dialog.locator("button[aria-label*='close' i], button[aria-label*='关闭']")
        )
        if close_btn.count() > 0:
            close_btn.first.wait_for(state="visible", timeout=5000)
            close_btn.first.click()
            self.page.wait_for_timeout(500)

    def has_agent(self, name: str) -> bool:
        """列表中是否包含指定名称的智能体（通过 data-badge-name 属性精确匹配）"""
        return self.page.locator(f"div.agent-badge[data-badge-name='{name}']").count() > 0

    def enter_agent(self, name: str):
        """进入某个智能体对话"""
        # 找到包含该名称的卡片，点击"进入对话"
        card = self.page.locator(f"text={name}").first
        card.wait_for(state="visible", timeout=5000)
        card.click()
        self.page.wait_for_load_state("domcontentloaded")

    def get_filter_buttons(self) -> list[str]:
        """获取所有分类筛选按钮的文字（从「全部」按钮的父容器中动态获取）"""
        all_btn = self.page.get_by_role("button", name="全部")
        if all_btn.count() == 0:
            return []
        parent = all_btn.first.locator("..")
        buttons = parent.locator("button")
        return [b.strip() for b in buttons.all_text_contents()]
