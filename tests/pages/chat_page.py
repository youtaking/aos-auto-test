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
        self.page.wait_for_timeout(2000)

    def is_home_loaded(self) -> bool:
        """首页是否加载完成"""
        url = self.page.url
        has_url = "/agent/home" in url or "/chat/" in url
        has_input = self.page.locator("textarea").count() > 0
        return has_url and has_input

    def get_sidebar_agents(self) -> list[str]:
        """获取左侧边栏的智能体列表"""
        items = self.page.locator("button.agent-sidebar-agent-card").all()
        return [i.inner_text().strip() for i in items if i.inner_text().strip()]

    def click_sidebar_agent(self, name: str):
        """点击侧边栏的某个智能体"""
        self.page.get_by_role("button", name=name).first.click()
        self.page.wait_for_timeout(2000)

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

        self.page.wait_for_timeout(3000)

    def has_response(self) -> bool:
        """是否收到了回复（页面上有除输入框以外的文本内容变化）"""
        # 检查是否有消息气泡或回复区域
        messages = self.page.locator("[class*='message'], [class*='chat'], [class*='prose'], [class*='markdown']")
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
        """访问会话管理页"""
        self.page.goto(f"{self.base_url}/ctrl/agent/sessions")
        self.page.wait_for_load_state("networkidle")

    def get_session_count(self) -> int:
        """获取会话实例数量"""
        items = self.page.locator("[class*='instance'], [class*='session']").all()
        return len(items) if items else 0
