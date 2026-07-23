# tests/pages/model_config_page.py
"""服务商与模型配置页面 Page Object — 基于真实 DOM 结构编写"""
import allure
from playwright.sync_api import Page, expect


class ModelConfigPage:
    """服务商与模型配置页 /ctrl/agent/models"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/models"

    # ==================== 页面加载 ====================

    def goto(self):
        self.page.goto(self.url)
        self.page.wait_for_load_state("networkidle")
        self.page.wait_for_timeout(1500)

    def is_loaded(self) -> bool:
        """页面标题「服务商与模型」可见"""
        return (
            self.page.locator("div.agent-panel-body")
            .locator("text=服务商与模型")
            .count()
            > 0
        )

    def get_page_title(self) -> str:
        body = self.page.locator("div.agent-panel-body")
        h = body.locator("div.mb-3").first
        if h.count() > 0:
            return h.inner_text().split("\n")[0].strip()
        return ""

    # ==================== 搜索 ====================

    def search(self, keyword: str):
        inp = self.page.locator("input[placeholder*='搜索服务商']")
        if inp.count() > 0:
            inp.first.fill(keyword)
            self.page.wait_for_timeout(500)

    def clear_search(self):
        inp = self.page.locator("input[placeholder*='搜索服务商']")
        if inp.count() > 0:
            inp.first.fill("")
            self.page.wait_for_timeout(500)

    def has_search_input(self) -> bool:
        return self.page.locator("input[placeholder*='搜索服务商']").count() > 0

    # ==================== Provider 列表 ====================

    def get_provider_cards(self):
        """获取所有 Provider 卡片"""
        return self.page.locator("div.group.flex.h-full.flex-col")

    def get_provider_count(self) -> int:
        """Provider 卡片数量"""
        return self.get_provider_cards().count()

    def has_provider(self, name: str) -> bool:
        """是否存在指定名称的 Provider"""
        cards = self.get_provider_cards()
        for i in range(cards.count()):
            if name in cards.nth(i).inner_text():
                return True
        return False

    def get_provider_names(self) -> list[str]:
        """获取所有 Provider 显示名称"""
        cards = self.get_provider_cards()
        names = []
        for i in range(cards.count()):
            header = cards.nth(i).locator("div.flex-1.min-w-0").first
            if header.count() > 0:
                text = header.inner_text().strip()
                # 第一行通常是 "name ORG_ID" 格式
                name_part = text.split("\n")[0].strip()
                names.append(name_part)
        return names

    def get_provider_card_text(self, name: str) -> str:
        """获取指定 Provider 卡片的完整文本"""
        cards = self.get_provider_cards()
        for i in range(cards.count()):
            text = cards.nth(i).inner_text()
            if name in text:
                return text
        return ""

    def get_provider_protocol(self, name: str) -> str:
        """获取 Provider 的协议类型文本"""
        card_text = self.get_provider_card_text(name)
        if "Anthropic" in card_text:
            return "Anthropic"
        if "OpenAI" in card_text:
            return "OpenAI 兼容"
        return ""

    def get_model_count_for_provider(self, name: str) -> int:
        """获取指定 Provider 下的模型数量"""
        card_text = self.get_provider_card_text(name)
        # 文本中包含 "模型 (N)" 格式
        import re
        match = re.search(r"模型\s*\((\d+)\)", card_text)
        if match:
            return int(match.group(1))
        return 0

    def is_api_key_masked_in_ui(self, name: str) -> bool:
        """UI 中 API Key 是否以掩码显示（不应有明文）"""
        card_text = self.get_provider_card_text(name)
        # 不应包含 "sk-" 开头的明文 key
        import re
        return not bool(re.search(r"\bsk-[a-zA-Z0-9]{8,}", card_text))

    # ==================== 新建 Provider 弹窗 ====================

    def click_add_provider(self):
        self.page.get_by_role("button", name="新建服务商").click()
        self.page.wait_for_timeout(1000)

    def has_add_provider_button(self) -> bool:
        return self.page.get_by_role("button", name="新建服务商").count() > 0

    def fill_provider_form(
        self,
        provider_id: str = "",
        display_name: str = "",
        api_key: str = "",
        base_url: str = "",
    ):
        """填写新建 Provider 表单（弹窗须已打开）"""
        dialog = self.page.locator("[role=dialog]")
        if provider_id:
            dialog.locator("input[placeholder='bailian-token-plan']").fill(provider_id)
        if display_name:
            dialog.locator("input[placeholder='例如 阿里百炼']").fill(display_name)
        if api_key:
            dialog.locator("input[placeholder='输入 API Key']").fill(api_key)
        if base_url:
            dialog.locator("input[placeholder*='默认使用服务商']").fill(base_url)

    def select_protocol(self, protocol: str):
        """选择协议（'OpenAI 兼容' 或 'Anthropic'）"""
        dialog = self.page.locator("[role=dialog]")
        # 点击 combobox 按钮打开下拉
        combobox = dialog.locator("button[role=combobox]")
        if combobox.count() > 0:
            combobox.click()
            self.page.wait_for_timeout(300)
            # 在下拉中选择
            self.page.locator("[role=option]").filter(has_text=protocol).click()
            self.page.wait_for_timeout(300)

    def submit_form(self):
        """点击保存按钮"""
        dialog = self.page.locator("[role=dialog]")
        dialog.get_by_role("button", name="保存").click()
        self.page.wait_for_timeout(2000)

    def cancel_form(self):
        """点击取消按钮"""
        dialog = self.page.locator("[role=dialog]")
        dialog.get_by_role("button", name="取消").click()
        self.page.wait_for_timeout(500)

    def close_dialog(self):
        """关闭弹窗"""
        dialog = self.page.locator("[role=dialog]")
        close_btn = dialog.locator("button").filter(has_text="Close")
        if close_btn.count() > 0:
            close_btn.first.click()
        else:
            self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(500)

    def is_dialog_open(self) -> bool:
        dialog = self.page.locator("[role=dialog]")
        return dialog.count() > 0 and dialog.first.is_visible()

    def get_dialog_title(self) -> str:
        dialog = self.page.locator("[role=dialog]")
        h2 = dialog.locator("h2")
        if h2.count() > 0:
            return h2.first.text_content().strip()
        return ""

    def get_form_validation_text(self) -> str:
        """获取表单校验错误文本"""
        dialog = self.page.locator("[role=dialog]")
        # 校验错误通常以红色或特定 class 出现
        errors = dialog.locator("[class*='text-red'], [class*='error'], [class*='Error']")
        if errors.count() > 0:
            return errors.first.text_content().strip()
        return ""

    # ==================== Provider 级别操作（footer 区域）====================

    def _get_provider_footer(self, name: str):
        """获取 Provider 卡片的 footer 区域"""
        cards = self.get_provider_cards()
        for i in range(cards.count()):
            if name in cards.nth(i).inner_text():
                return cards.nth(i).locator("div.mt-auto")
        return None

    def click_provider_edit(self, name: str):
        """点击 Provider 级别的编辑按钮"""
        footer = self._get_provider_footer(name)
        if footer:
            footer.get_by_role("button", name="编辑").click()
            self.page.wait_for_timeout(1000)

    def click_provider_delete(self, name: str):
        """点击 Provider 级别的删除按钮"""
        footer = self._get_provider_footer(name)
        if footer:
            footer.get_by_role("button", name="删除").click()
            self.page.wait_for_timeout(1000)

    def click_fetch_models(self, name: str):
        """点击「获取模型列表」按钮"""
        footer = self._get_provider_footer(name)
        if footer:
            footer.get_by_role("button", name="获取模型列表").click()
            self.page.wait_for_timeout(3000)

    def get_public_switch(self, name: str):
        """获取 Provider 的公开开关元素"""
        footer = self._get_provider_footer(name)
        if footer:
            sw = footer.locator("[role=switch][aria-label='公开']")
            if sw.count() > 0:
                return sw.first
        return None

    def is_public(self, name: str) -> bool:
        """Provider 是否已公开"""
        sw = self.get_public_switch(name)
        if sw:
            return sw.get_attribute("aria-checked") == "true"
        return False

    def toggle_public(self, name: str):
        """切换公开状态"""
        sw = self.get_public_switch(name)
        if sw:
            sw.click()
            self.page.wait_for_timeout(1000)

    # ==================== 编辑 Provider 弹窗 ====================

    def fill_edit_provider_form(
        self,
        display_name: str = "",
        api_key: str = "",
        base_url: str = "",
    ):
        """填写编辑 Provider 表单（弹窗须已打开）"""
        dialog = self.page.locator("[role=dialog]")
        if display_name:
            dialog.locator("input[placeholder='例如 阿里百炼']").fill(display_name)
        if api_key:
            dialog.locator("input[placeholder='留空表示不修改']").fill(api_key)
        if base_url:
            dialog.locator("input[placeholder*='默认使用服务商']").fill(base_url)

    def get_edit_form_base_url(self) -> str:
        """获取编辑弹窗中的 Base URL 当前值"""
        dialog = self.page.locator("[role=dialog]")
        inp = dialog.locator("input[placeholder*='默认使用服务商']")
        if inp.count() > 0:
            return inp.input_value()
        return ""

    def is_edit_id_disabled(self) -> bool:
        """编辑弹窗中 ID 字段是否不可修改"""
        dialog = self.page.locator("[role=dialog]")
        id_input = dialog.locator("input[placeholder='bailian-token-plan']")
        if id_input.count() > 0:
            return id_input.is_disabled()
        return False

    # ==================== 模型操作 ====================

    def click_add_model(self, provider_name: str):
        """点击指定 Provider 的「+ 添加模型」按钮"""
        cards = self.get_provider_cards()
        for i in range(cards.count()):
            if provider_name in cards.nth(i).inner_text():
                btn = cards.nth(i).locator("button").filter(has_text="+ 添加模型")
                if btn.count() > 0:
                    btn.first.click()
                    self.page.wait_for_timeout(1000)
                    return True
        return False

    def fill_model_form(self, model_id: str, display_name: str):
        """填写新增模型表单（弹窗须已打开）"""
        dialog = self.page.locator("[role=dialog]")
        inputs = dialog.locator("input[type=text]")
        if inputs.count() >= 2:
            inputs.nth(0).fill(model_id)
            inputs.nth(1).fill(display_name)

    def get_model_names_for_provider(self, provider_name: str) -> list[str]:
        """获取指定 Provider 下的所有模型名称"""
        cards = self.get_provider_cards()
        for i in range(cards.count()):
            if provider_name in cards.nth(i).inner_text():
                body = cards.nth(i).locator("div.space-y-2")
                if body.count() == 0:
                    return []
                rows = body.locator("> div")
                names = []
                for j in range(rows.count()):
                    text = rows.nth(j).inner_text()
                    # 模型名称通常在行首
                    first_line = text.split("\n")[0].strip()
                    if first_line:
                        names.append(first_line)
                return names
        return []

    def click_model_test(self, provider_name: str, model_name: str):
        """点击模型级别的「测试」按钮"""
        cards = self.get_provider_cards()
        for i in range(cards.count()):
            if provider_name in cards.nth(i).inner_text():
                rows = cards.nth(i).locator("div.space-y-2 > div")
                for j in range(rows.count()):
                    if model_name in rows.nth(j).inner_text():
                        btn = rows.nth(j).locator("button").filter(has_text="测试")
                        if btn.count() > 0:
                            btn.first.click()
                            self.page.wait_for_timeout(3000)
                            return True
        return False

    def click_model_edit(self, provider_name: str, model_name: str):
        """点击模型级别的「编辑」按钮"""
        cards = self.get_provider_cards()
        for i in range(cards.count()):
            if provider_name in cards.nth(i).inner_text():
                rows = cards.nth(i).locator("div.space-y-2 > div")
                for j in range(rows.count()):
                    if model_name in rows.nth(j).inner_text():
                        btn = rows.nth(j).locator("button").filter(has_text="编辑")
                        if btn.count() > 0:
                            btn.first.click()
                            self.page.wait_for_timeout(1000)
                            return True
        return False

    def click_model_delete(self, provider_name: str, model_name: str):
        """点击模型级别的「删除」按钮"""
        cards = self.get_provider_cards()
        for i in range(cards.count()):
            if provider_name in cards.nth(i).inner_text():
                rows = cards.nth(i).locator("div.space-y-2 > div")
                for j in range(rows.count()):
                    if model_name in rows.nth(j).inner_text():
                        btn = rows.nth(j).locator("button").filter(has_text="删除")
                        if btn.count() > 0:
                            btn.first.click()
                            self.page.wait_for_timeout(500)
                            return True
        return False

    # ==================== 确认弹窗 ====================

    def is_alert_dialog_open(self) -> bool:
        dialog = self.page.locator("[role=alertdialog]")
        return dialog.count() > 0 and dialog.first.is_visible()

    def get_alert_dialog_text(self) -> str:
        dialog = self.page.locator("[role=alertdialog]")
        if dialog.count() > 0:
            return dialog.first.inner_text().strip()
        return ""

    def confirm_alert_dialog(self):
        """点击确认弹窗的「确认」按钮"""
        dialog = self.page.locator("[role=alertdialog]")
        dialog.get_by_role("button", name="确认").click()
        self.page.wait_for_timeout(2000)

    def cancel_alert_dialog(self):
        """点击确认弹窗的「取消」按钮"""
        dialog = self.page.locator("[role=alertdialog]")
        dialog.get_by_role("button", name="取消").click()
        self.page.wait_for_timeout(500)

    # ==================== 加载状态 ====================

    def has_skeleton_or_spinner(self) -> bool:
        """是否有加载骨架屏或 Spinner"""
        body = self.page.locator("div.agent-panel-body")
        loading = body.locator(
            "[class*='skeleton'], [class*='Skeleton'], "
            "[class*='spinner'], [class*='Spinner'], "
            "[class*='animate-pulse'], [class*='loading']"
        )
        return loading.count() > 0

    # ==================== Network 拦截辅助 ====================

    def intercept_api_responses(self, url_pattern: str):
        """设置 API 响应拦截，返回收集列表"""
        collected = []

        def on_response(resp):
            if url_pattern in resp.url:
                try:
                    body = resp.json() if "json" in resp.headers.get("content-type", "") else None
                    collected.append({
                        "url": resp.url,
                        "status": resp.status,
                        "method": resp.request.method,
                        "body": body,
                    })
                except Exception:
                    collected.append({
                        "url": resp.url,
                        "status": resp.status,
                        "method": resp.request.method,
                        "body": None,
                    })

        self.page.on("response", on_response)
        return collected
