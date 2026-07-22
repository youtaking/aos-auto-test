# tests/pages/agent_page.py
"""Agent 管理页面 Page Object"""
from playwright.sync_api import Page


class AgentPage:
    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/agent/agents"

    def goto(self):
        self.page.goto(self.url)
        self.page.wait_for_load_state("networkidle")

    def is_loaded(self) -> bool:
        return "agent" in self.page.url.lower()

    def get_agent_count(self) -> int:
        rows = self.page.locator("table tbody tr, [class*='agent-card'], [class*='list-item']")
        return rows.count()

    def click_create_agent(self):
        self.page.get_by_role("button", name="创建").or_(
            self.page.get_by_text("Create", exact=False)
        ).first.click()
        self.page.wait_for_load_state("networkidle")
