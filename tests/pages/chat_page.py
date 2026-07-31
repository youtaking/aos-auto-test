# tests/pages/chat_page.py
"""对话页面 Page Object"""
from playwright.sync_api import Page


class ChatPage:
    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url

    def goto_home(self):
        """进入首页（对话创建页）"""
        self.page.goto(f"{self.base_url}/ctrl/agent/home")
        self.page.wait_for_load_state("networkidle")

    def is_home_loaded(self) -> bool:
        """首页是否加载完成"""
        url = self.page.url
        has_url = "/agent/home" in url or "/chat/" in url
        has_input = self.page.locator("textarea").count() > 0
        return has_url and has_input

    def get_sidebar_agents(self) -> list[str]:
        """获取左侧边栏的智能体列表（滚动到底部确保获取完整列表）"""
        # 实际可滚动容器是 div.agent-sidebar-tree
        container = self.page.locator("div.agent-sidebar-tree")
        if container.count() > 0:
            # 验证侧边栏可滚动（内容高度 > 可视高度）
            scroll_info = container.first.evaluate("""el => ({
                scrollHeight: el.scrollHeight,
                clientHeight: el.clientHeight
            })""")
            self._sidebar_scrollable = scroll_info["scrollHeight"] > scroll_info["clientHeight"]
            self._sidebar_scroll_info = scroll_info

            # 滚动到底部以触发懒加载
            container.first.evaluate("el => el.scrollTop = el.scrollHeight")
            self.page.wait_for_timeout(800)
            # 滚回顶部
            container.first.evaluate("el => el.scrollTop = 0")
            self.page.wait_for_timeout(300)
        else:
            self._sidebar_scrollable = False
            self._sidebar_scroll_info = {}

        items = self.page.locator("button.agent-sidebar-agent-card").all()
        return [i.inner_text().strip() for i in items if i.inner_text().strip()]

    def is_sidebar_scrollable(self) -> bool:
        """侧边栏是否有下拉滚动条"""
        return getattr(self, "_sidebar_scrollable", False)

    def get_sidebar_scroll_info(self) -> dict:
        """获取侧边栏滚动信息"""
        return getattr(self, "_sidebar_scroll_info", {})

    def get_sidebar_agent_count(self) -> int:
        """获取侧边栏智能体数量"""
        return self.page.locator("button.agent-sidebar-agent-card").count()

    def click_sidebar_agent(self, name: str):
        """点击侧边栏的某个智能体"""
        card = self.page.locator("button.agent-sidebar-agent-card").filter(has_text=name)
        if card.count() > 0:
            card.first.scroll_into_view_if_needed()
            self.page.wait_for_timeout(300)
            card.first.click()
            self.page.wait_for_timeout(1000)

    def send_message(self, text: str):
        """发送消息"""
        # 查找文本输入区域
        input_area = self.page.locator("textarea").first
        if not input_area.is_visible():
            input_area = self.page.locator("[contenteditable='true']").first
        input_area.fill(text)

        # 发送（Enter 键或发送按钮）
        send_btn = self.page.get_by_role("button", name="发送").or_(
            self.page.locator("button[type='submit']")
        ).or_(
            self.page.locator("button").filter(has_text="Send")
        )
        if send_btn.count() > 0 and send_btn.first.is_visible():
            send_btn.first.click()
        else:
            input_area.press("Enter")

        self.page.wait_for_timeout(1000)

    def has_response(self) -> bool:
        """是否收到了回复（页面上有除输入框以外的文本内容变化）"""
        # 检查是否有消息气泡或回复区域
        messages = self.page.locator("div[role='log']")
        if messages.count() == 0:
            messages = self.page.locator("div.agent-chat-area")
        return messages.count() > 0

    def get_connection_status(self) -> str:
        """获取连接状态"""
        text = self.page.locator("body").inner_text()
        if "connecting" in text.lower() or "连接中" in text:
            return "connecting"
        if "error" in text.lower() or "错误" in text:
            return "error"
        return "connected"

    def goto_sessions(self):
        """进入会话列表：先进入 agent 对话 → 再打开会话列表弹窗"""
        # 先到首页
        self.goto_home()
        agents = self.get_sidebar_agents()
        if agents:
            self.click_sidebar_agent(agents[0])
            self.page.wait_for_timeout(1000)
            # 打开会话列表弹窗
            self.open_session_dialog()

    def open_session_dialog(self):
        """点击会话头部打开会话列表对话框"""
        trigger = self.page.locator(".chat-header-card button[data-slot='popover-trigger']")
        if trigger.count() > 0:
            trigger.first.click()
            self.page.wait_for_timeout(1500)
        else:
            header = self.page.locator(".chat-header-card")
            if header.count() > 0:
                header.first.click()
                self.page.wait_for_timeout(1500)

    def is_session_dialog_open(self) -> bool:
        return self.page.locator("[role='dialog']").count() > 0

    def get_session_titles(self) -> list[str]:
        """获取会话列表中的标题"""
        dialog = self.page.locator("[role='dialog']")
        if dialog.count() == 0:
            return []
        items = dialog.locator("button, [role='option'], a").all()
        return [t.inner_text().strip() for t in items if t.inner_text().strip()]

    def get_session_count(self) -> int:
        """获取会话实例数量"""
        dialog = self.page.locator("[role='dialog']")
        if dialog.count() == 0:
            return 0
        items = dialog.locator("button[title]").all()
        return len(items) if items else 0
