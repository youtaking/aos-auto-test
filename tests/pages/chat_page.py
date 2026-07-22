# tests/pages/chat_page.py
"""Chat 对话页面 Page Object"""
from playwright.sync_api import Page


class ChatPage:
    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url

    def goto_sessions(self):
        self.page.goto(f"{self.base_url}/agent/sessions")
        self.page.wait_for_load_state("networkidle")

    def is_sessions_loaded(self) -> bool:
        return "session" in self.page.url.lower()

    def get_session_count(self) -> int:
        items = self.page.locator("[class*='session-item'], [class*='chat-item'], table tbody tr")
        return items.count()

    def send_message(self, text: str):
        input_box = self.page.locator(
            'textarea, input[type="text"], [contenteditable="true"]'
        ).first
        input_box.fill(text)
        send_btn = self.page.get_by_role("button", name="发送").or_(
            self.page.locator('[class*="send"]')
        ).first
        if send_btn.is_visible():
            send_btn.click()
        else:
            input_box.press("Enter")
        self.page.wait_for_timeout(2000)
