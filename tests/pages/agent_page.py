# tests/pages/agent_page.py
"""智能体管理页面 Page Object"""
from playwright.sync_api import Page, expect


class AgentPage:
    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/agents"

    def goto(self):
        self.page.goto(self.url)
        self.page.wait_for_load_state("networkidle")

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
        """获取当前显示的智能体卡片数量"""
        return self.get_agent_cards().count()

    def search_agent(self, keyword: str):
        """搜索智能体"""
        search_input = self.page.locator("input[placeholder*='搜索']")
        search_input.fill(keyword)
        self.page.wait_for_timeout(500)

    def clear_search(self):
        """清空搜索"""
        search_input = self.page.locator("input[placeholder*='搜索']")
        search_input.fill("")
        self.page.wait_for_timeout(500)

    def filter_by_category(self, category: str):
        """按分类筛选（全部/通用助理/数据分析/搜索检索/监控告警/代码助手/自定义）"""
        self.page.get_by_role("button", name=category).click()
        self.page.wait_for_timeout(500)

    def click_create_button(self):
        """点击「创建智能体」按钮（页面内容区）"""
        btn = self.page.get_by_role("button", name="创建智能体")
        if btn.count() == 0:
            btn = self.page.get_by_role("button", name="新建智能体")
        btn.first.click()

    def is_create_dialog_open(self) -> bool:
        """创建对话框是否打开（导航到 agent/home 页面并显示 dialog）"""
        try:
            self.page.wait_for_url(lambda url: "/agent/home" in url, timeout=5000)
            self.page.wait_for_selector("[class*='agent-home-dialog']", timeout=5000)
            return True
        except Exception:
            return False

    def is_on_home_page(self) -> bool:
        """是否在 agent home 页面"""
        return "/agent/home" in self.page.url

    def fill_create_form(self, name: str, description: str = ""):
        """填写创建表单"""
        dialog = self.page.locator("[role='dialog']")
        dialog.locator("input").first.fill(name)
        if description:
            textarea = dialog.locator("textarea")
            if textarea.count() > 0:
                textarea.fill(description)

    def submit_create_form(self):
        """提交创建表单"""
        dialog = self.page.locator("[role='dialog']")
        # 点击对话框中的确认/创建按钮
        submit_btn = dialog.get_by_role("button", name="创建").or_(
            dialog.get_by_role("button", name="确定")
        ).or_(
            dialog.get_by_role("button", name="保存")
        )
        submit_btn.first.click()
        self.page.wait_for_load_state("networkidle")

    def close_dialog(self):
        """关闭对话框"""
        dialog_sel = "[role='dialog'], .ant-modal, .el-dialog, [class*='modal'], [class*='dialog'], [class*='Modal'], [class*='Dialog']"
        close_btn = self.page.locator(f"{dialog_sel} button").filter(has_text="取消").or_(
            self.page.locator(f"{dialog_sel} [aria-label*='close'], {dialog_sel} [aria-label*='关闭'], {dialog_sel} [class*='close']")
        )
        if close_btn.count() > 0:
            close_btn.first.click()
            self.page.wait_for_timeout(500)

    def has_agent(self, name: str) -> bool:
        """列表中是否包含指定名称的智能体（通过 data-badge-name 属性精确匹配）"""
        return self.page.locator(f"div.agent-badge[data-badge-name='{name}']").count() > 0

    def enter_agent(self, name: str):
        """进入某个智能体对话"""
        # 找到包含该名称的卡片，点击"进入对话"
        card = self.page.locator(f"text={name}").first
        card.click()
        self.page.wait_for_load_state("networkidle")

    def get_filter_buttons(self) -> list[str]:
        """获取所有分类筛选按钮的文字（从「全部」按钮的父容器中动态获取）"""
        all_btn = self.page.get_by_role("button", name="全部")
        if all_btn.count() == 0:
            return []
        parent = all_btn.first.locator("..")
        buttons = parent.locator("button")
        return [b.strip() for b in buttons.all_text_contents()]
