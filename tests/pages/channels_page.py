# tests/pages/channels_page.py
"""消息通道页面 Page Object — 基于 2026-11-04 真实 DOM 探查（LangBot 通道）

页面结构：main > div.space-y-3 > div.rounded-xl > ul > li（每个 li 一个通道机器人）
li 第 1 个子 div 是机器人头部（对接智能体/测试发送/编辑/删除/收起路由），
第 2 个子 div 是路由列表（停用/编辑/删除）。
"""
import time

from playwright.sync_api import Page


class ChannelsPage:
    """消息通道页 /ctrl/agent/channels"""

    _BOT_ROWS = "main div.space-y-3 > div.rounded-xl > ul > li"
    _BOT_HEADER = "xpath=./div[1]"
    _ROUTE_BLOCK = "xpath=./div[2]"

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/channels"

    # ── 页面 ──

    def goto(self):
        for _attempt in range(2):
            try:
                self.page.goto(self.url, wait_until="domcontentloaded")
            except Exception:
                pass  # SPA 路由可能中断初始导航
            self.page.wait_for_load_state("domcontentloaded")
            try:
                self.page.get_by_role("heading", name="消息通道").wait_for(
                    state="attached", timeout=15000
                )
            except Exception:
                pass
            if self.is_loaded():
                break
            try:
                self.page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
            self.page.wait_for_timeout(500)

    def is_loaded(self) -> bool:
        return (
            "/ctrl/agent/channels" in self.page.url
            and self.page.get_by_role("heading", name="消息通道").count() > 0
        )

    # ── 创建按钮 / 弹窗 ──

    def click_create_button(self):
        btn = self.page.locator("main").get_by_role(
            "button", name="创建消息连接", exact=True
        )
        # 页面异步渲染：轮询等到按钮恰好一个再断言，避免 count 抖动误报
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and btn.count() != 1:
            self.page.wait_for_timeout(300)
        count = btn.count()
        assert count == 1, f"「创建消息连接」按钮应唯一，实际匹配 {count} 个"
        btn.wait_for(state="visible", timeout=5000)
        btn.click()
        self.page.wait_for_timeout(500)

    def is_dialog_open(self) -> bool:
        dialog = self.page.get_by_role("dialog")
        return dialog.count() > 0 and dialog.first.is_visible()

    def dialog_locator(self):
        dialog = self.page.get_by_role("dialog")
        assert dialog.count() > 0 and dialog.first.is_visible(), "创建通道弹窗未打开"
        return dialog.first

    def fill_bot_name(self, value: str):
        self.dialog_locator().locator("input#channel-bot-name").fill(value)

    def select_adapter(self, adapter_name: str):
        btn = self.dialog_locator().get_by_role(
            "button", name=adapter_name, exact=True
        )
        assert btn.count() == 1, \
            f"适配器「{adapter_name}」按钮应唯一，实际 {btn.count()} 个"
        btn.click()
        self.page.wait_for_timeout(500)

    def has_field(self, element_id: str) -> bool:
        return self.dialog_locator().locator(f"#{element_id}").count() > 0

    def click_save(self):
        btn = self.dialog_locator().get_by_role("button", name="保存", exact=True)
        assert btn.count() == 1, f"弹窗「保存」按钮应唯一，实际 {btn.count()} 个"
        btn.click()

    def click_cancel(self):
        btn = self.dialog_locator().get_by_role("button", name="取消", exact=True)
        assert btn.count() == 1, f"弹窗「取消」按钮应唯一，实际 {btn.count()} 个"
        btn.click()
        self.page.wait_for_timeout(300)

    def close_dialog(self):
        btn = self.dialog_locator().get_by_role("button", name="Close", exact=True)
        btn.click()

    # ── 通道列表 ──

    def bot_rows(self):
        return self.page.locator(self._BOT_ROWS)

    def get_binding_count(self) -> int:
        """通道机器人数量（每个 li 一个机器人，不含嵌套路由）"""
        return self.bot_rows().count()

    def find_bot_row(self, bot_name: str):
        row = self.bot_rows().filter(has_text=bot_name)
        assert row.count() == 1, \
            f"名称包含 {bot_name!r} 的通道行应唯一，实际匹配 {row.count()} 行"
        return row.first

    def has_binding(self, bot_name: str) -> bool:
        return self.bot_rows().filter(has_text=bot_name).count() == 1

    def bot_header(self, bot_name: str):
        return self.find_bot_row(bot_name).locator(self._BOT_HEADER)

    def bot_action(self, bot_name: str, action: str):
        """定位机器人头部操作按钮（对接智能体/测试发送/编辑/删除）"""
        btn = self.bot_header(bot_name).get_by_role(
            "button", name=action, exact=True
        )
        assert btn.count() == 1, \
            f"通道 {bot_name!r} 头部「{action}」按钮应唯一，实际 {btn.count()} 个"
        return btn

    def toggle_routes(self, bot_name: str):
        """收起/展开路由列表"""
        btn = self.bot_header(bot_name).locator("button[aria-label*='路由']")
        assert btn.count() == 1, \
            f"通道 {bot_name!r} 路由折叠按钮应唯一，实际 {btn.count()} 个"
        aria_before = btn.get_attribute("aria-label")
        btn.click()
        self.page.wait_for_timeout(500)
        return aria_before, btn.get_attribute("aria-label")

    def has_route_block(self, bot_name: str) -> bool:
        return self.find_bot_row(bot_name).locator(self._ROUTE_BLOCK).count() > 0

    # ── 删除确认弹窗 ──

    def delete_binding(self, bot_name: str):
        btn = self.bot_action(bot_name, "删除")
        btn.wait_for(state="visible", timeout=5000)
        btn.click()
        self.page.wait_for_timeout(500)

    def _confirm_dialog(self):
        dialog = self.page.locator("[role=alertdialog]")
        assert dialog.count() == 1, \
            f"删除确认弹窗应唯一，实际 {dialog.count()} 个"
        assert dialog.first.is_visible(), "删除确认弹窗不可见"
        return dialog.first

    def confirm_delete(self):
        dialog = self._confirm_dialog()
        assert "删除通道" in dialog.inner_text(), \
            f"确认弹窗标题不是「删除通道」: {dialog.inner_text()[:100]}"
        btn = dialog.get_by_role("button", name="删除", exact=True)
        assert btn.count() == 1, f"确认弹窗「删除」按钮应唯一，实际 {btn.count()} 个"
        btn.click()

    def cancel_delete(self):
        dialog = self._confirm_dialog()
        assert "删除通道" in dialog.inner_text(), \
            f"确认弹窗标题不是「删除通道」: {dialog.inner_text()[:100]}"
        btn = dialog.get_by_role("button", name="取消", exact=True)
        assert btn.count() == 1, f"确认弹窗「取消」按钮应唯一，实际 {btn.count()} 个"
        btn.click()
