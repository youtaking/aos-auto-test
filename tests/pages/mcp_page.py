# tests/pages/mcp_page.py
"""MCP 服务器管理页面 Page Object — 基于真实 DOM 结构编写"""
from playwright.sync_api import Page
from tests.pages import locators as loc


class McpServerPage:
    """MCP 服务器管理页 /ctrl/agent/mcp"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/mcp"

    # === 导航 ===

    def goto(self):
        # SPA 导航优先（sidebar 测试已验证可靠），避免全页面刷新后 router 初始化问题
        nav_btn = self.page.locator("button.agent-sidebar-nav-item").filter(has_text="MCP")
        if nav_btn.count() > 0:
            nav_btn.first.click()
            try:
                self.page.locator("div.agent-panel-content").first.wait_for(state="attached", timeout=8000)
            except Exception:
                pass
            if self.is_loaded():
                return
        # 降级：全页面刷新（SPA 导航失败时）
        for _attempt in range(2):
            try:
                self.page.goto(self.url, wait_until="domcontentloaded")
            except Exception:
                pass
            self.page.wait_for_load_state("domcontentloaded")
            try:
                self.page.locator("div.agent-panel-content").first.wait_for(state="attached", timeout=8000)
            except Exception:
                pass
            if self.is_loaded():
                break
            self.page.wait_for_timeout(3000)

    def is_loaded(self) -> bool:
        """MCP 页面内容已加载"""
        return "/ctrl/agent/mcp" in self.page.url and self.page.locator("div.agent-panel-content").count() > 0

    # === 搜索 ===

    def search(self, keyword: str):
        """搜索 MCP 服务器"""
        inp = self.page.locator("input[placeholder*='搜索 MCP']")
        if inp.count() > 0:
            inp.first.fill(keyword)
            self.page.wait_for_timeout(500)

    def clear_search(self):
        """清空搜索"""
        inp = self.page.locator("input[placeholder*='搜索 MCP']")
        if inp.count() > 0:
            inp.first.fill("")
            self.page.wait_for_timeout(500)

    # === 列表 ===

    def get_server_rows(self):
        """获取所有 MCP 服务器卡片元素（grid 中的每个卡片）"""
        return self.page.locator("div.grid.gap-3 > div.rounded-lg.border")

    def get_server_count(self) -> int:
        """获取 MCP 服务器列表数量（通过「检测」按钮计数）"""
        return self.page.get_by_role("button", name="检测").count()

    def get_server_names(self) -> list[str]:
        """获取所有服务器名称（从 grid 卡片中提取）"""
        names = []
        rows = self.get_server_rows()
        for i in range(rows.count()):
            row = rows.nth(i)
            text = row.inner_text().strip()
            lines = text.split("\n")
            # 卡片文本格式：首字母\nORG_ID/名称\n类型(Local/Remote)\n...
            if len(lines) >= 2:
                full_name = lines[1].strip()
                # 去掉组织前缀（如 "ORG_001/"）
                if "/" in full_name:
                    full_name = full_name.split("/", 1)[-1].strip()
                if full_name and full_name not in ["检测", "启用", "禁用", "编辑", "删除", "Local", "Remote"]:
                    names.append(full_name)
        return names

    def has_server(self, name: str) -> bool:
        """列表中是否包含指定名称的服务器"""
        body = self.page.locator("div.agent-panel-body").inner_text()
        return name in body

    # === 创建 ===

    def open_create_dialog(self):
        """点击「新建服务器」按钮"""
        self.page.get_by_role("button", name="新建服务器").first.click()
        self.page.wait_for_timeout(1000)

    def is_create_dialog_open(self) -> bool:
        return self.page.locator("[role='dialog']").count() > 0

    def select_type(self, server_type: str):
        """选择服务器类型：Stdio(→Local) / SSE(→Remote) / Streamable HTTP
        实际 UI 是 Radix Select 下拉框（role=combobox），选项为 Local（命令行启动）/ Remote（URL 连接）"""
        dialog = self.page.locator("[role='dialog']")

        # 映射测试用语到实际选项文本（含括号说明）
        type_map = {
            "Stdio": "Local（命令行启动）",
            "Local": "Local（命令行启动）",
            "SSE": "Remote（URL 连接）",
            "Remote": "Remote（URL 连接）",
            "Streamable HTTP": "Remote（URL 连接）",
        }
        option_text = type_map.get(server_type, server_type)

        # 点击 combobox 触发器打开下拉列表
        trigger = dialog.locator("button[role='combobox'][data-slot='select-trigger']")
        if trigger.count() > 0:
            trigger.first.click()
            self.page.wait_for_timeout(800)

            # 精确匹配选项文本
            options = self.page.locator("[role='option']")
            for i in range(options.count()):
                txt = options.nth(i).inner_text().strip()
                if txt == option_text:
                    options.nth(i).click()
                    self.page.wait_for_timeout(800)
                    return

    def fill_create_form(self, name: str, command: str = "", url: str = ""):
        """填写创建表单"""
        dialog = self.page.locator("[role='dialog']")

        # 名称输入框（placeholder = my-mcp-server）
        name_input = dialog.locator("input[placeholder='my-mcp-server']").or_(
            dialog.locator("input[name='name']")
        )
        if name_input.count() > 0:
            name_input.first.fill(name)

        # 命令（Local/Stdio 模式，placeholder = npx @anthropic/mcp-server-xxx --arg1 val1）
        if command:
            cmd_input = dialog.locator("input[placeholder*='npx']").or_(
                dialog.locator("input[name='command']")
            )
            if cmd_input.count() > 0:
                cmd_input.first.fill(command)

        # URL（Remote/SSE 模式，placeholder = https://example.com/mcp）
        if url:
            url_input = dialog.locator("input[placeholder*='example.com']").or_(
                dialog.locator("input[name='url']")
            )
            if url_input.count() > 0:
                url_input.first.fill(url)

    def save(self):
        """点击保存/创建"""
        dialog = self.page.locator("[role='dialog']")
        save_btn = loc.save_or_submit_button(dialog)
        if save_btn.count() > 0:
            save_btn.first.click()
            self.page.wait_for_timeout(1000)

    def close_dialog(self):
        """关闭对话框"""
        dialog = self.page.locator("[role='dialog']")
        cancel = loc.cancel_button(dialog)
        if cancel.count() > 0:
            cancel.first.click()
            self.page.wait_for_timeout(500)

    # === 表单校验 ===

    def get_validation_errors(self) -> list[str]:
        """获取表单校验错误信息（包括 dialog 内联错误 + 页面 toast 通知）"""
        errors = []

        # 1. dialog 内联错误
        dialog = self.page.locator("[role='dialog']")
        inline_errors = dialog.locator(
            "[role='alert'], p.text-red-500, p.text-red-600, "
            "span.text-red-500, [data-slot='form-message']"
        )
        for e in inline_errors.all():
            txt = e.inner_text().strip()
            if txt and txt not in ["检测", "删除", "取消", "保存", "编辑"]:
                errors.append(txt)

        # 2. toast 通知（右上角，<li> 元素，自动消失）
        toasts = self.page.locator("ol > li, [data-slot='toast'] li, [data-sonner-toast] li")
        for t in toasts.all():
            txt = t.inner_text().strip()
            if txt:
                errors.append(txt)

        # 3. 兜底：在页面右上角区域查找 li 元素的文本
        if not errors:
            top_right_texts = self.page.evaluate("""() => {
                const results = [];
                const lis = document.querySelectorAll('li');
                for (const li of lis) {
                    const rect = li.getBoundingClientRect();
                    if (rect.top >= 0 && rect.top < 100 && rect.right > window.innerWidth - 500 && rect.height > 0) {
                        const text = li.textContent.trim();
                        if (text && text.length > 5) {
                            results.push(text);
                        }
                    }
                }
                return results;
            }""")
            errors.extend(top_right_texts)

        return errors

    # === 找到服务器行的辅助方法 ===

    def _get_server_row(self, name: str):
        """获取指定名称的服务器所在卡片"""
        rows = self.get_server_rows()
        for i in range(rows.count()):
            row = rows.nth(i)
            if name in row.inner_text():
                return row
        # 回退：在 agent-panel-body 内找包含名称的卡片
        body = self.page.locator("div.agent-panel-body")
        return body.locator("div.rounded-lg.border").filter(has_text=name).first

    # === 启用/禁用 ===

    def get_enable_disable_button(self, name: str):
        """获取指定服务器的启用/禁用按钮"""
        row = self._get_server_row(name)
        # 「启用」或「禁用」按钮
        btn = row.get_by_role("button", name="启用").or_(
            row.get_by_role("button", name="禁用")
        )
        return btn

    def is_server_enabled(self, name: str) -> bool:
        """检查服务器是否启用（有「禁用」按钮说明当前是启用状态）"""
        row = self._get_server_row(name)
        disable_btn = row.get_by_role("button", name="禁用")
        return disable_btn.count() > 0 and disable_btn.first.is_visible()

    def toggle_enabled(self, name: str):
        """切换启用/禁用"""
        btn = self.get_enable_disable_button(name)
        if btn.count() > 0:
            btn.first.click()
            self.page.wait_for_timeout(1500)

    # === 操作按钮 ===

    def click_inspect(self, name: str):
        """点击「检测」按钮"""
        row = self._get_server_row(name)
        btn = row.get_by_role("button", name="检测")
        if btn.count() > 0:
            btn.first.click()
            self.page.wait_for_load_state("domcontentloaded")

    def click_edit(self, name: str):
        """点击「编辑」按钮"""
        row = self._get_server_row(name)
        btn = row.get_by_role("button", name="编辑")
        if btn.count() > 0:
            btn.first.click()
            self.page.wait_for_timeout(1000)

    # === 删除 ===

    def delete_server(self, name: str):
        """删除 MCP 服务器（含确认）"""
        row = self._get_server_row(name)
        delete_btn = row.get_by_role("button", name="删除")
        if delete_btn.count() > 0:
            delete_btn.first.click()
            self.page.wait_for_timeout(500)

        # 确认删除弹窗
        confirm = loc.confirm_button(self.page)
        if confirm.count() > 0:
            confirm.first.click()
            self.page.wait_for_timeout(1000)

    # === 公开开关 ===

    def get_public_switch(self, name: str):
        """获取公开开关"""
        row = self._get_server_row(name)
        return row.locator("button[role='switch'][aria-label='公开']")

    def is_public(self, name: str) -> bool:
        """检查服务器是否公开"""
        switch = self.get_public_switch(name)
        if switch.count() > 0:
            return switch.first.get_attribute("aria-checked") == "true"
        return False

    def toggle_public(self, name: str):
        """切换公开状态"""
        switch = self.get_public_switch(name)
        if switch.count() > 0:
            switch.first.click()
            self.page.wait_for_timeout(1500)

    # === API 拦截辅助 ===

    def setup_api_interceptor(self, url_pattern: str) -> list:
        """设置 API 响应拦截器"""
        responses = []

        def on_response(r):
            if url_pattern in r.url and ".js" not in r.url and ".css" not in r.url:
                try:
                    data = {
                        "url": r.url,
                        "method": r.request.method,
                        "status": r.status,
                    }
                    try:
                        data["body"] = r.json()
                    except Exception:
                        data["body"] = None
                    responses.append(data)
                except Exception:
                    pass

        self.page.on("response", on_response)
        return responses
