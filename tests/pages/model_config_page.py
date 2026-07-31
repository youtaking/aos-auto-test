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

    def is_loaded(self) -> bool:
        """页面标题「模型库」可见"""
        return (
            self.page.locator("div.agent-panel-body")
            .locator("text=模型库")
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
        inp = self.page.locator("input[placeholder*='搜索服务商名称']")
        if inp.count() > 0:
            inp.first.fill(keyword)
            self.page.wait_for_timeout(500)

    def clear_search(self):
        inp = self.page.locator("input[placeholder*='搜索服务商名称']")
        if inp.count() > 0:
            inp.first.fill("")
            self.page.wait_for_timeout(500)

    def has_search_input(self) -> bool:
        return self.page.locator("input[placeholder*='搜索服务商名称']").count() > 0

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
        """获取所有 Provider 显示名称（从卡片文本第2行提取）"""
        cards = self.get_provider_cards()
        names = []
        for i in range(cards.count()):
            text = cards.nth(i).inner_text().strip()
            # 卡片文本格式：首字母\n名称\nORG_ID\n...
            lines = text.split("\n")
            if len(lines) >= 2:
                names.append(lines[1].strip())
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
        self.page.wait_for_timeout(1000)

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
        errors = dialog.locator("[data-slot='form-message'], [role='alert']")
        if errors.count() == 0:
            errors = dialog.locator("p.text-red-500, p.text-destructive")
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
            self.page.wait_for_timeout(1000)

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

    def get_edit_provider_protocol(self) -> str:
        """获取编辑弹窗中的协议文本"""
        dialog = self.page.locator("[role=dialog]")
        combobox = dialog.locator("button[role=combobox]")
        if combobox.count() > 0:
            return combobox.first.inner_text().strip()
        return ""

    def has_model_list_section(self) -> bool:
        """编辑弹窗中是否存在「可用模型列表」区域"""
        dialog = self.page.locator("[role=dialog]")
        return "可用模型列表" in dialog.inner_text()

    def has_fetch_models_in_dialog(self) -> bool:
        """编辑弹窗中是否有「获取模型列表」按钮"""
        dialog = self.page.locator("[role=dialog]")
        btn = dialog.get_by_role("button", name="获取模型列表")
        return btn.count() > 0

    def click_fetch_models_in_dialog(self):
        """点击编辑弹窗中的「获取模型列表」按钮"""
        dialog = self.page.locator("[role=dialog]")
        btn = dialog.get_by_role("button", name="获取模型列表")
        if btn.count() > 0:
            btn.first.click()
            self.page.wait_for_timeout(1000)

    def get_dialog_model_list_text(self) -> str:
        """获取编辑弹窗中可用模型列表区域的文本"""
        dialog = self.page.locator("[role=dialog]")
        full_text = dialog.inner_text()
        # 提取"可用模型列表"之后的文本
        if "可用模型列表" in full_text:
            idx = full_text.index("可用模型列表")
            return full_text[idx:idx + 500]
        return ""

    # ==================== 编辑模型弹窗 — 高级字段 ====================

    def set_context_limit(self, value: int):
        """设置上下文限制"""
        dialog = self.page.locator("[role=dialog]")
        number_inputs = dialog.locator("input[type=number]")
        if number_inputs.count() >= 1:
            number_inputs.nth(0).fill(str(value))

    def set_output_limit(self, value: int):
        """设置输出限制"""
        dialog = self.page.locator("[role=dialog]")
        number_inputs = dialog.locator("input[type=number]")
        if number_inputs.count() >= 2:
            number_inputs.nth(1).fill(str(value))

    def get_context_limit(self) -> str:
        """获取上下文限制值"""
        dialog = self.page.locator("[role=dialog]")
        number_inputs = dialog.locator("input[type=number]")
        if number_inputs.count() >= 1:
            return number_inputs.nth(0).input_value()
        return ""

    def get_output_limit(self) -> str:
        """获取输出限制值"""
        dialog = self.page.locator("[role=dialog]")
        number_inputs = dialog.locator("input[type=number]")
        if number_inputs.count() >= 2:
            return number_inputs.nth(1).input_value()
        return ""

    def _get_modality_buttons(self, section: str = "input"):
        """获取模态切换按钮列表。section: 'input' 或 'output'"""
        dialog = self.page.locator("[role=dialog]")
        # 输入模态: text, image, audio, video, pdf (前5个按钮)
        # 输出模态: text, image (按钮5-6)
        all_btns = dialog.locator("button")
        input_mods = ["text", "image", "audio", "video", "pdf"]
        output_mods = ["text", "image"]
        result = []
        count = all_btns.count()
        if section == "input":
            for i in range(min(5, count)):
                txt = all_btns.nth(i).inner_text().strip()
                if txt in input_mods:
                    result.append(all_btns.nth(i))
        else:
            # 输出模态按钮在索引 5-6
            for i in range(5, min(7, count)):
                txt = all_btns.nth(i).inner_text().strip()
                if txt in output_mods:
                    result.append(all_btns.nth(i))
        return result

    def is_modality_selected(self, modality: str, section: str = "input") -> bool:
        """模态按钮是否被选中（通过 CSS class 判断：bg-indigo/bg-emerald 表示选中）"""
        btns = self._get_modality_buttons(section)
        for btn in btns:
            if btn.inner_text().strip() == modality:
                cls = btn.get_attribute("class") or ""
                return "bg-indigo" in cls or "bg-emerald" in cls
        return False

    def click_modality(self, modality: str, section: str = "input"):
        """点击模态切换按钮"""
        btns = self._get_modality_buttons(section)
        for btn in btns:
            if btn.inner_text().strip() == modality:
                btn.click()
                self.page.wait_for_timeout(300)
                return True
        return False

    def get_selected_input_modalities(self) -> list:
        """获取已选中的输入模态"""
        btns = self._get_modality_buttons("input")
        selected = []
        for btn in btns:
            cls = btn.get_attribute("class") or ""
            if "bg-indigo" in cls:
                selected.append(btn.inner_text().strip())
        return selected

    def get_selected_output_modalities(self) -> list:
        """获取已选中的输出模态"""
        btns = self._get_modality_buttons("output")
        selected = []
        for btn in btns:
            cls = btn.get_attribute("class") or ""
            if "bg-emerald" in cls:
                selected.append(btn.inner_text().strip())
        return selected

    def has_expand_advanced_button(self) -> bool:
        """是否有「展开高级参数」按钮"""
        dialog = self.page.locator("[role=dialog]")
        btn = dialog.get_by_role("button", name="展开高级参数")
        return btn.count() > 0

    def click_expand_advanced(self):
        """点击「展开高级参数」"""
        dialog = self.page.locator("[role=dialog]")
        btn = dialog.get_by_role("button", name="展开高级参数")
        if btn.count() > 0:
            btn.click()
            self.page.wait_for_timeout(500)

    def has_thinking_mode_checkbox(self) -> bool:
        """展开高级参数后，是否有「启用思考模式」开关"""
        dialog = self.page.locator("[role=dialog]")
        switch = dialog.locator("button[role=switch]")
        return switch.count() > 0

    def is_thinking_mode_checked(self) -> bool:
        """思考模式是否已启用"""
        dialog = self.page.locator("[role=dialog]")
        switch = dialog.locator("button[role=switch]")
        if switch.count() > 0:
            return switch.first.get_attribute("aria-checked") == "true"
        return False

    def toggle_thinking_mode(self):
        """切换思考模式（点击 role=switch 按钮）"""
        dialog = self.page.locator("[role=dialog]")
        switch = dialog.locator("button[role=switch]")
        if switch.count() > 0:
            switch.first.click()
            self.page.wait_for_timeout(300)

    def set_input_cost(self, value: str):
        """设置输入费用（通过 label 文本定位）"""
        dialog = self.page.locator("[role=dialog]")
        label = dialog.locator("label").filter(has_text="输入费用")
        if label.count() > 0:
            inp = label.locator("xpath=following-sibling::input | ./input")
            if inp.count() > 0:
                inp.first.fill(value)
            else:
                # label 和 input 在同一个父 div 中
                parent = label.locator("xpath=..")
                num_inp = parent.locator("input[type=number]")
                if num_inp.count() > 0:
                    num_inp.first.fill(value)

    def set_output_cost(self, value: str):
        """设置输出费用（通过 label 文本定位）"""
        dialog = self.page.locator("[role=dialog]")
        label = dialog.locator("label").filter(has_text="输出费用")
        if label.count() > 0:
            parent = label.locator("xpath=..")
            num_inp = parent.locator("input[type=number]")
            if num_inp.count() > 0:
                num_inp.first.fill(value)

    def get_input_cost(self) -> str:
        """获取输入费用值"""
        dialog = self.page.locator("[role=dialog]")
        label = dialog.locator("label").filter(has_text="输入费用")
        if label.count() > 0:
            parent = label.locator("xpath=..")
            num_inp = parent.locator("input[type=number]")
            if num_inp.count() > 0:
                return num_inp.first.input_value()
        return ""

    def get_output_cost(self) -> str:
        """获取输出费用值"""
        dialog = self.page.locator("[role=dialog]")
        label = dialog.locator("label").filter(has_text="输出费用")
        if label.count() > 0:
            parent = label.locator("xpath=..")
            num_inp = parent.locator("input[type=number]")
            if num_inp.count() > 0:
                return num_inp.first.input_value()
        return ""

    def has_thinking_budget_input(self) -> bool:
        """是否有「思考预算」输入框（仅在思考模式开启时出现）"""
        dialog = self.page.locator("[role=dialog]")
        label = dialog.locator("label").filter(has_text="思考预算")
        return label.count() > 0

    def set_thinking_budget(self, value: str):
        """设置思考预算"""
        dialog = self.page.locator("[role=dialog]")
        label = dialog.locator("label").filter(has_text="思考预算")
        if label.count() > 0:
            parent = label.locator("xpath=..")
            num_inp = parent.locator("input[type=number]")
            if num_inp.count() > 0:
                num_inp.first.fill(value)

    def get_thinking_budget(self) -> str:
        """获取思考预算值"""
        dialog = self.page.locator("[role=dialog]")
        label = dialog.locator("label").filter(has_text="思考预算")
        if label.count() > 0:
            parent = label.locator("xpath=..")
            num_inp = parent.locator("input[type=number]")
            if num_inp.count() > 0:
                return num_inp.first.input_value()
        return ""

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
        inputs = dialog.locator("input[data-slot='input']")
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
                            self.page.wait_for_timeout(500)
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

    def is_edit_model_id_disabled(self) -> bool:
        """编辑模型弹窗中模型 ID 是否不可修改"""
        dialog = self.page.locator("[role=dialog]")
        inputs = dialog.locator("input[data-slot='input']")
        if inputs.count() > 0:
            return inputs.nth(0).is_disabled()
        return False

    def fill_edit_model_form(self, display_name: str = ""):
        """填写编辑模型表单（弹窗须已打开）"""
        dialog = self.page.locator("[role=dialog]")
        inputs = dialog.locator("input[data-slot='input']")
        if display_name and inputs.count() >= 2:
            inputs.nth(1).fill(display_name)

    def get_edit_model_display_name(self) -> str:
        """获取编辑模型弹窗中的显示名称"""
        dialog = self.page.locator("[role=dialog]")
        inputs = dialog.locator("input[data-slot='input']")
        if inputs.count() >= 2:
            return inputs.nth(1).input_value()
        return ""

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
        self.page.wait_for_timeout(1000)

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
            "[role='progressbar'], [data-slot='skeleton'], "
            "div.animate-pulse, [data-slot='spinner']"
        )
        return loading.count() > 0

    # ==================== Network 拦截辅助 ====================

    def intercept_api_responses(self, url_pattern: str):
        """设置 API 响应拦截，返回收集列表"""
        # 移除之前的监听器，避免累积

        if hasattr(self, '_last_listener') and self._last_listener:

            try:

                self.page.remove_listener("response", self._last_listener)

            except Exception:

                pass

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

        self._last_listener = on_response
        self.page.on("response", on_response)
        return collected
