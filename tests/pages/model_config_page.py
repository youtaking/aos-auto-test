# tests/pages/model_config_page.py
"""服务商与模型配置页面 Page Object — 新版双栏布局（左侧目录 + 右侧详情）。

真实 DOM 依据（探查于参照环境）：
- 页面: /ctrl/agent/models
- 工具栏: main header 内 h1=模型库 + 「新建服务商」按钮
- 搜索: input[placeholder='搜索服务商、模型或协议']
- 范围组: div[role=group][aria-label='资源范围'] 下 全部/本组织/公开
- 左目录: aside > nav[aria-label='服务商'] > button（每项内 strong=显示名）
- 右详情: main > header(协议/ID code + h2 显示名 + 编辑/删除) + article
    - article: Endpoint/密钥引用/组织共享 switch + section(已配置模型)
    - 组织共享: article button[role=switch]
    - 模型区: article > section，行内 strong=模型显示名 + code=模型ID + 测试/编辑/删除
- 新建/编辑服务商弹窗: 协议 label 内含 button[role=combobox]（选型弹出 [role=option]）+ API Key + Base URL + 可用模型列表 section
- 新增/编辑模型弹窗: 模型 ID(编辑时 disabled)/显示名称/上下文限制/输出限制
    + fieldset 输入模态(text,image,audio,video,pdf)/输出模态(text,image)（选中态 class=is-selected）+ 启用思考模式 switch
- 删除确认: [role=alertdialog]，服务商/模型标题区分，正文引用 服务商显示名/模型ID
- toast: li 含 Close 按钮（新增 prepend，取 [0]）
"""
import time
from playwright.sync_api import Page

URL_PATH = "/ctrl/agent/models"


class ModelConfigPage:
    """服务商与模型配置页 Page Object"""

    # 目录相关
    _NAV_BTN = "nav[aria-label='服务商'] button"
    _SEARCH = "input[placeholder='搜索服务商、模型或协议']"
    # 详情相关
    _ARTICLE = "main article"
    _MODEL_SECTION = "main article section"

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}{URL_PATH}"

    # ==================== 页面加载 ====================

    def goto(self):
        """直接导航到模型库页面并等待目录渲染。"""
        try:
            self.page.goto(self.url, wait_until="domcontentloaded")
        except Exception:
            pass
        try:
            self.page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass
        # 等待目录出现（双栏首屏渲染依赖异步数据）
        try:
            self.page.locator(self._NAV_BTN).first.wait_for(
                state="attached", timeout=12000)
        except Exception:
            pass
        self.page.wait_for_timeout(500)

    def is_loaded(self) -> bool:
        """页面是否已加载出服务商目录。"""
        return URL_PATH in self.page.url and self.page.locator(self._NAV_BTN).count() > 0

    def page_title(self) -> str:
        h1 = self.page.locator("main h1")
        return h1.first.inner_text().strip() if h1.count() else ""

    # ==================== 搜索 ====================

    def has_search_input(self) -> bool:
        return self.page.locator(self._SEARCH).count() > 0

    def search(self, keyword: str):
        inp = self.page.locator(self._SEARCH).first
        inp.wait_for(state="visible", timeout=5000)
        inp.fill(keyword)
        self.page.wait_for_timeout(600)

    def clear_search(self):
        inp = self.page.locator(self._SEARCH)
        if inp.count():
            inp.first.fill("")
            self.page.wait_for_timeout(600)

    # ==================== 资源范围（替代旧分页/排序） ====================

    _SCOPE_GROUP = "div[role=group][aria-label='资源范围']"

    def scope_names(self) -> list[str]:
        """资源范围分组内按钮（如 全部/本组织/公开）文本。"""
        grp = self.page.locator(self._SCOPE_GROUP)
        if grp.count() == 0:
            return []
        btns = grp.first.locator("button")
        return [b.inner_text().strip() for b in btns.all()]

    def click_scope(self, name: str):
        """点击资源范围某档（全部/本组织/公开），name 用前缀即可。"""
        grp = self.page.locator(self._SCOPE_GROUP).first
        btn = grp.locator("button", has_text=name).first
        btn.wait_for(state="visible", timeout=5000)
        btn.click()
        self.page.wait_for_timeout(700)

    # ==================== 服务商目录 ====================

    def _buttons(self):
        return self.page.locator(self._NAV_BTN)

    def _display_of(self, button_idx: int) -> str:
        """读取目录按钮的显示名（strong）。"""
        btn = self._buttons().nth(button_idx)
        strong = btn.locator("strong")
        if strong.count():
            return strong.first.inner_text().strip()
        return btn.inner_text().split("\n")[0].strip()

    def catalog_names(self) -> list[str]:
        """全部服务商显示名（目录顺序）。"""
        out = []
        for i in range(self._buttons().count()):
            try:
                out.append(self._display_of(i))
            except Exception:
                pass
        return out

    def provider_count(self) -> int:
        return self._buttons().count()

    def has_provider(self, display: str, timeout: float = 15000) -> bool:
        """等待并判断目录中是否存在指定显示名的服务商。"""
        deadline = time.time() + timeout / 1000
        while time.time() < deadline:
            if display in self.catalog_names():
                return True
            self.page.wait_for_timeout(400)
        return False

    def _find_button(self, display: str) -> "object":
        buttons = self._buttons()
        for i in range(buttons.count()):
            if self._display_of(i) == display:
                return buttons.nth(i)
        return None

    def open_provider(self, display: str):
        """点击目录服务商，进入右侧详情。"""
        btn = self._find_button(display)
        if btn is None:
            raise AssertionError(f"目录中未找到服务商 '{display}'")
        btn.click()
        # 等待详情区渲染（h2 == 显示名）
        h2 = self.page.locator("main h2")
        try:
            h2.first.wait_for(state="visible", timeout=8000)
        except Exception:
            pass

    # ==================== 详情区（服务商） ====================

    def _provider_header(self):
        """定位服务商详情头部（含「删除」按钮的 main header）。

        新版双栏布局中 main 下 header 依序为：工具栏(0)、次卡头(1)、
        服务商详情头(2，含 编辑/删除)、模型区头(3)。用「含删除按钮」过滤更稳，
        共享(external)服务商无该头 → 返回空。
        """
        return self.page.locator("main header").filter(
            has=self.page.get_by_role("button", name="删除", exact=True))

    def detail_h2(self) -> str:
        h2 = self.page.locator("main h2")
        return h2.first.inner_text().strip() if h2.count() else ""

    def detail_has_edit_delete(self) -> bool:
        """自建/可管理服务商详情头部有编辑+删除按钮。"""
        hdr = self._provider_header()
        if hdr.count() == 0:
            return False
        return (hdr.first.get_by_role("button", name="编辑", exact=True).count() > 0
                and hdr.first.get_by_role("button", name="删除", exact=True).count() > 0)

    def has_new_provider_button(self) -> bool:
        """工具栏「新建服务商」按钮是否存在。"""
        return self.page.get_by_role("main").get_by_role(
            "button", name="新建服务商", exact=True).count() > 0

    def click_provider_edit(self):
        """点击详情头部「编辑」。"""
        hdr = self._provider_header().first
        hdr.get_by_role("button", name="编辑", exact=True).first.click()

    def click_provider_delete(self):
        """点击详情头部「删除」。"""
        hdr = self._provider_header().first
        hdr.get_by_role("button", name="删除", exact=True).first.click()

    def article_text(self) -> str:
        art = self.page.locator(self._ARTICLE)
        return art.first.inner_text() if art.count() else ""

    def org_share_checked(self) -> bool:
        """详情页组织共享 switch 状态（None=无开关）。"""
        sw = self.page.locator(f"{self._ARTICLE} [role=switch]").first
        return sw.get_attribute("aria-checked") == "true" if sw.count() else None

    def org_share_switch_disabled(self) -> bool:
        """详情页组织共享开关是否只读禁用（共享 external 服务商为禁用展示）。"""
        sw = self.page.locator(f"{self._ARTICLE} [role=switch]").first
        return sw.is_disabled() if sw.count() else False

    def toggle_org_share(self):
        sw = self.page.locator(f"{self._ARTICLE} [role=switch]").first
        sw.wait_for(state="visible", timeout=5000)
        sw.click()

    def key_hint_in_detail(self) -> str:
        """详情页「密钥引用」掩码文本（无则该元素为空）。"""
        art = self.page.locator(self._ARTICLE).first
        # article 内 code 标签：第一个为 Endpoint，第二个为密钥
        codes = art.locator("code")
        if codes.count() >= 2:
            return codes.nth(1).inner_text().strip()
        return ""

    # ==================== 模型区 ====================

    def model_section_text(self) -> str:
        sec = self.page.locator(self._MODEL_SECTION)
        return sec.first.inner_text() if sec.count() else ""

    def model_names_visible(self) -> list[str]:
        """模型区可见的模型显示名列表（strong 文本）。"""
        sec = self.page.locator(self._MODEL_SECTION).first
        if not sec.count():
            return []
        return [s.strip() for s in sec.locator("strong").all_inner_texts() if s.strip()]

    def model_row(self, display: str):
        """定位指定显示名的模型行（含 测试/编辑/删除 按钮的最外层行）。"""
        sec = self.page.locator(self._MODEL_SECTION).first
        return sec.locator("div", has_text=display).first

    def model_row_text(self, display: str) -> str:
        """模型行的完整文本（含行内连通性结果标记，如 失败/成功）。"""
        row = self.model_row(display)
        if row.count() == 0:
            return ""
        try:
            return row.inner_text()
        except Exception:
            return ""

    def has_section_add_model(self) -> bool:
        sec = self.page.locator(self._MODEL_SECTION).first
        return sec.get_by_role("button", name="添加模型", exact=True).count() > 0

    def has_section_fetch_models(self) -> bool:
        sec = self.page.locator(self._MODEL_SECTION).first
        return sec.get_by_role("button", name="获取模型列表", exact=True).count() > 0

    def click_add_model(self):
        """模型区头部「添加模型」。"""
        sec = self.page.locator(self._MODEL_SECTION).first
        sec.get_by_role("button", name="添加模型", exact=True).first.click()

    def click_section_fetch_models(self):
        """模型区头部「获取模型列表」（连接探测/发现）。"""
        sec = self.page.locator(self._MODEL_SECTION).first
        sec.get_by_role("button", name="获取模型列表", exact=True).first.click()

    def click_model_edit(self, display: str):
        self.model_row(display).get_by_role("button", name="编辑", exact=True).first.click()

    def click_model_delete(self, display: str):
        self.model_row(display).get_by_role("button", name="删除", exact=True).first.click()

    def click_model_test(self, display: str):
        self.model_row(display).get_by_role("button", name="测试", exact=True).first.click()

    # ==================== 弹窗通用 ====================

    def is_dialog_open(self) -> bool:
        try:
            d = self.page.locator("[role=dialog]").first
            d.wait_for(state="visible", timeout=2500)
            return True
        except Exception:
            return False

    def _dialog(self):
        return self.page.locator("[role=dialog]").first

    def dialog_title(self) -> str:
        d = self._dialog()
        h2 = d.locator("h2")
        return h2.first.inner_text().strip() if h2.count() else ""

    def submit_dialog(self):
        d = self._dialog()
        d.get_by_role("button", name="保存", exact=True).first.click()

    def close_dialog(self):
        d = self._dialog()
        d.get_by_role("button", name="关闭", exact=True).first.click()
        self.page.wait_for_timeout(300)

    def alert_dialog_text(self) -> str:
        ad = self.page.locator("[role=alertdialog]").first
        return ad.inner_text() if ad.count() else ""

    def confirm_alert(self):
        ad = self.page.locator("[role=alertdialog]").first
        ad.get_by_role("button", name="确认", exact=True).first.click()

    def cancel_alert(self):
        ad = self.page.locator("[role=alertdialog]").first
        ad.get_by_role("button", name="取消", exact=True).first.click()

    # ==================== 新建服务商弹窗 ====================

    def click_new_provider(self):
        self.page.get_by_role("main").get_by_role(
            "button", name="新建服务商", exact=True).first.click()
        try:
            self._dialog().wait_for(state="visible", timeout=5000)
        except Exception:
            pass

    def fill_provider_form(self, provider_id: str = "", display_name: str = "",
                           api_key: str = "", base_url: str = ""):
        """填充新建/编辑服务商表单（留空字段不填）。"""
        d = self._dialog()
        if provider_id:
            self._fill_label(d, "ID（标识符）", provider_id)
        if display_name:
            self._fill_label(d, "显示名称", display_name)
        if api_key:
            self._fill_label(d, "API Key", api_key)
        if base_url:
            self._fill_label(d, "Base URL", base_url)

    @staticmethod
    def _fill_label(dialog, label: str, value: str):
        inp = dialog.locator("label", has_text=label).first.locator("input").first
        inp.wait_for(state="visible", timeout=5000)
        inp.fill(value)

    def select_protocol(self, protocol: str):
        """协议 combobox：点开并从 [role=option] 选择。"""
        d = self._dialog()
        cb = d.locator("label", has_text="协议").first.locator("button[role=combobox]")
        cb.first.wait_for(state="visible", timeout=5000)
        cb.first.click()
        self.page.wait_for_timeout(400)
        opt = self.page.get_by_role("option", name=protocol).first
        opt.wait_for(state="visible", timeout=5000)
        opt.click()
        self.page.wait_for_timeout(300)

    def selected_protocol(self) -> str:
        d = self._dialog()
        cb = d.locator("label", has_text="协议").first.locator("button[role=combobox]")
        return cb.first.inner_text().strip() if cb.count() else ""

    def available_models_text(self) -> str:
        """弹窗内「可用模型列表」区文本。"""
        d = self._dialog()
        sec = d.locator("section", has_text="可用模型列表").first
        return sec.inner_text() if sec.count() else ""

    def click_dialog_fetch_models(self):
        """弹窗内「可用模型列表」的「获取模型列表」按钮。"""
        d = self._dialog()
        sec = d.locator("section", has_text="可用模型列表").first
        sec.get_by_role("button", name="获取模型列表", exact=True).first.click()

    def edit_id_disabled(self) -> bool:
        d = self._dialog()
        inp = d.locator("label", has_text="ID（标识符）").first.locator("input").first
        return inp.count() > 0 and inp.is_disabled()

    def get_form_base_url(self) -> str:
        d = self._dialog()
        inp = d.locator("label", has_text="Base URL").first.locator("input").first
        return inp.input_value() if inp.count() else ""

    def edit_api_key_placeholder(self) -> str:
        d = self._dialog()
        inp = d.locator("label", has_text="API Key").first.locator("input").first
        return inp.get_attribute("placeholder") or "" if inp.count() else ""

    # ==================== 新增/编辑模型弹窗 ====================

    def model_dialog_set_id_name(self, model_id: str = "", display_name: str = ""):
        d = self._dialog()
        if model_id:
            inp = d.locator("label", has_text="模型 ID").first.locator("input").first
            if not inp.is_disabled():
                inp.fill(model_id)
        if display_name:
            self._fill_label(d, "显示名称", display_name)

    def model_id_disabled(self) -> bool:
        d = self._dialog()
        inp = d.locator("label", has_text="模型 ID").first.locator("input").first
        return inp.count() > 0 and inp.is_disabled()

    def set_context_limit(self, value: str):
        d = self._dialog()
        d.locator("label", has_text="上下文限制").first.locator("input").first.fill(str(value))

    def set_output_limit(self, value: str):
        d = self._dialog()
        d.locator("label", has_text="输出限制").first.locator("input").first.fill(str(value))

    def get_context_limit(self) -> str:
        d = self._dialog()
        inp = d.locator("label", has_text="上下文限制").first.locator("input").first
        return inp.input_value() if inp.count() else ""

    def get_output_limit(self) -> str:
        d = self._dialog()
        inp = d.locator("label", has_text="输出限制").first.locator("input").first
        return inp.input_value() if inp.count() else ""

    def click_modality(self, modality: str, kind: str):
        """点击输入/输出模态按钮。kind ∈ {输入模态, 输出模态}"""
        d = self._dialog()
        btn = d.locator("fieldset", has_text=kind).first.get_by_role(
            "button", name=modality).first
        btn.wait_for(state="visible", timeout=5000)
        btn.click()
        self.page.wait_for_timeout(200)

    def selected_modalities(self, kind: str) -> list[str]:
        """选中模态（class 含 is-selected）。kind ∈ {输入模态, 输出模态}"""
        d = self._dialog()
        fs = d.locator("fieldset", has_text=kind).first
        out = []
        for b in fs.locator("button").all():
            if "is-selected" in (b.get_attribute("class") or ""):
                out.append(b.inner_text().strip())
        return out

    def thinking_checked(self):
        d = self._dialog()
        sw = d.locator("[role=switch]").first
        return sw.get_attribute("aria-checked") == "true" if sw.count() else None

    def toggle_thinking(self):
        d = self._dialog()
        sw = d.locator("[role=switch]").first
        sw.wait_for(state="visible", timeout=5000)
        sw.click()
        self.page.wait_for_timeout(200)

    # ==================== toast ====================

    def read_toast_texts(self) -> list[str]:
        """右上角通知区全部 toast 文本（新 toast 在 index 0）。"""
        return self.page.evaluate("""() => {
            const out = [];
            for (const li of document.querySelectorAll('li')) {
                if (!li.querySelector('button')) continue;
                const t = (li.textContent || '').replace('Close toast', '').trim();
                if (t) out.push(t);
            }
            return out;
        }""")

    def get_last_toast_text(self, timeout: float = 6000) -> str:
        deadline = time.time() + timeout / 1000
        while time.time() < deadline:
            toasts = self.read_toast_texts()
            if toasts:
                return toasts[0]
            self.page.wait_for_timeout(200)
        return ""

    # ==================== Network 拦截辅助 ====================

    def intercept_api_responses(self, url_pattern: str) -> list:
        """设置 API 响应拦截，返回收集列表。"""
        if getattr(self, '_last_listener', None):
            try:
                self.page.remove_listener("response", self._last_listener)
            except Exception:
                pass
        collected = []

        def on_response(resp):
            if url_pattern in resp.url:
                try:
                    body = resp.json() if "json" in resp.headers.get(
                        "content-type", "") else None
                except Exception:
                    body = None
                collected.append({
                    "url": resp.url,
                    "status": resp.status,
                    "method": resp.request.method,
                    "body": body,
                })

        self._last_listener = on_response
        self.page.on("response", on_response)
        return collected
