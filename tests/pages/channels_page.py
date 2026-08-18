# tests/pages/channels_page.py
"""渠道管理页面 Page Object — 基于 2026-08-17 真实 DOM 探查"""
from playwright.sync_api import Page


class ChannelsPage:
    """渠道管理页 /ctrl/agent/channels"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/channels"

    def goto(self):
        for _attempt in range(2):
            try:
                self.page.goto(self.url, wait_until="domcontentloaded")
            except Exception:
                pass  # SPA 路由可能中断初始导航
            self.page.wait_for_load_state("domcontentloaded")
            try:
                self.page.get_by_role("heading", name="消息渠道").wait_for(
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
            and self.page.get_by_role("heading", name="消息渠道").count() > 0
        )

    # ── 创建按钮 ──

    def click_create_button(self):
        """点击创建绑定按钮"""
        # 真实 DOM: button "btn.create"（i18n key）或翻译后的文本
        btn = self.page.locator("button").filter(has_text="btn.create")
        if btn.count() == 0:
            btn = self.page.get_by_role("button", name="新建").or_(
                self.page.get_by_role("button", name="创建")
            )
        btn.first.wait_for(state="visible", timeout=5000)
        btn.first.click()

    # ── 创建弹窗 ──

    def is_dialog_open(self) -> bool:
        return self.page.get_by_role("dialog").count() > 0

    def fill_platform(self, value: str):
        """填写平台名称（placeholder='telegram'）"""
        input_el = self.page.get_by_role("dialog").get_by_placeholder("telegram")
        input_el.wait_for(state="visible", timeout=5000)
        input_el.fill(value)

    def fill_chat_id(self, value: str):
        """填写 chatId（弹窗内第二个 textbox）"""
        dialog = self.page.get_by_role("dialog")
        inputs = dialog.get_by_role("textbox")
        # 第一个是 platform（placeholder=telegram），第二个是 chatId
        inputs.nth(1).wait_for(state="visible", timeout=5000)
        inputs.nth(1).fill(value)

    def select_agent(self, agent_name: str):
        """在 Agent 下拉中选择"""
        dialog = self.page.get_by_role("dialog")
        dialog.get_by_role("combobox").first.wait_for(state="visible", timeout=5000)
        dialog.get_by_role("combobox").first.click()
        self.page.wait_for_timeout(500)
        # 在下拉选项中选择匹配的项
        option = self.page.locator("[role='option']").filter(has_text=agent_name).first
        option.wait_for(state="visible", timeout=5000)
        option.click()

    def click_save(self):
        """点击保存按钮"""
        self.page.get_by_role("dialog").get_by_role("button", name="保存").wait_for(state="visible", timeout=5000)
        self.page.get_by_role("dialog").get_by_role("button", name="保存").click()

    def click_cancel(self):
        """点击取消按钮"""
        self.page.get_by_role("dialog").get_by_role("button", name="取消").wait_for(state="visible", timeout=5000)
        self.page.get_by_role("dialog").get_by_role("button", name="取消").click()

    def close_dialog(self):
        """关闭弹窗（X 按钮）"""
        self.page.get_by_role("dialog").get_by_role("button", name="Close").wait_for(state="visible", timeout=5000)
        self.page.get_by_role("dialog").get_by_role("button", name="Close").click()

    # ── 列表操作 ──

    def get_binding_count(self) -> int:
        """获取绑定卡片数量"""
        # 每个绑定是一个带 hover 效果的卡片，包含 Badge(platform) + agentName
        return self.page.locator("div.group").count()

    def has_binding(self, platform: str) -> bool:
        """列表中是否有指定平台的绑定"""
        return (
            self.page.locator("div.group")
            .filter(has_text=platform)
            .count()
            > 0
        )

    def delete_binding(self, platform: str):
        """删除指定平台的绑定（点击删除按钮）"""
        card = self.page.locator("div.group").filter(has_text=platform).first
        card.hover()  # 删除按钮 hover 时才显示
        delete_btn = card.get_by_role("button", name="btn.delete").or_(
            card.get_by_role("button", name="删除")
        )
        delete_btn.wait_for(state="visible", timeout=5000)
        delete_btn.click()

    def confirm_delete(self):
        """确认删除弹窗"""
        # ConfirmDialog 的确认按钮
        confirm_btn = self.page.get_by_role("button", name="确认").or_(
            self.page.get_by_role("button", name="Continue")
        )
        confirm_btn.first.wait_for(state="visible", timeout=5000)
        confirm_btn.first.click()

    def cancel_delete(self):
        """取消删除弹窗"""
        cancel_btn = self.page.get_by_role("button", name="取消").or_(
            self.page.get_by_role("button", name="Cancel")
        )
        cancel_btn.first.wait_for(state="visible", timeout=5000)
        cancel_btn.first.click()

    # ── 搜索 ──

    def search(self, query: str):
        """在搜索框输入关键词"""
        search_input = self.page.get_by_role("textbox").filter(
            has=self.page.locator("[placeholder='searchPlaceholder']")
        ).or_(
            self.page.locator("[placeholder='searchPlaceholder']")
        )
        search_input.wait_for(state="visible", timeout=5000)
        search_input.fill(query)

    def clear_search(self):
        search_input = self.page.get_by_role("textbox").filter(
            has=self.page.locator("[placeholder='searchPlaceholder']")
        ).or_(
            self.page.locator("[placeholder='searchPlaceholder']")
        )
        search_input.wait_for(state="visible", timeout=5000)
        search_input.fill("")

    # ── 空状态 ──

    def has_empty_state(self) -> bool:
        return self.page.get_by_text("emptyMessage").or_(
            self.page.get_by_text("暂无")
        ).count() > 0

    # ── API 辅助 ──

    def list_bindings_api(self):
        """通过 API 获取绑定列表"""
        r = self.page.request.get(f"{self.base_url}/web/channels/bindings")
        if r.status == 200:
            data = r.json()
            return data if isinstance(data, list) else data.get("data", [])
        return []

    def create_binding_api(self, platform: str, chat_id: str, agent_id: str):
        """通过 API 创建绑定"""
        import json
        return self.page.request.post(
            f"{self.base_url}/web/channels/bindings",
            data=json.dumps({
                "platform": platform,
                "chatId": chat_id,
                "agentId": agent_id,
            }),
            headers={"Content-Type": "application/json"},
        )

    def delete_binding_api(self, binding_id: str):
        """通过 API 删除绑定"""
        return self.page.request.delete(
            f"{self.base_url}/web/channels/bindings/{binding_id}"
        )
