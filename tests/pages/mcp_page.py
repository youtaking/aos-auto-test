# tests/pages/mcp_page.py
"""MCP 服务器管理页面 Page Object — 基于真实 DOM 结构编写"""
from playwright.sync_api import Page


class McpServerPage:
    """MCP 服务器管理页 /ctrl/agent/mcp"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/mcp"

    # === 导航 ===

    def goto(self):
        self.page.goto(self.url)
        self.page.wait_for_load_state("networkidle")
        self.page.wait_for_timeout(1500)

    def is_loaded(self) -> bool:
        """页面标题「MCP 服务器」可见"""
        return self.page.locator("h1").filter(has_text="MCP 服务器").count() > 0

    # === 搜索 ===

    def search(self, keyword: str):
        """搜索 MCP 服务器"""
        inp = self.page.locator("input[placeholder='搜索 MCP 服务器...']")
        if inp.count() > 0:
            inp.first.fill(keyword)
            self.page.wait_for_timeout(500)

    def clear_search(self):
        """清空搜索"""
        inp = self.page.locator("input[placeholder='搜索 MCP 服务器...']")
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
            # 卡片头部区域包含名称（border-b 子 div）
            header = row.locator("div.border-b").first
            if header.count() > 0:
                text = header.inner_text().strip()
                # 去掉组织前缀（首字母 + 组织名，如 "LORG_001/"）
                if "/" in text:
                    text = text.split("/", 1)[-1].strip()
                # 取第一行作为名称
                name = text.split("\n")[0].strip()
                if name and name not in ["检测", "启用", "禁用", "编辑", "删除"]:
                    names.append(name)
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
        实际 UI 是 Radix Select 下拉框（role=combobox），选项为 Local / Remote"""
        dialog = self.page.locator("[role='dialog']")

        # 映射测试用语到实际选项文本
        type_map = {
            "Stdio": "Local",
            "Local": "Local",
            "SSE": "Remote",
            "Remote": "Remote",
            "Streamable HTTP": "Remote",
        }
        option_text = type_map.get(server_type, server_type)

        # 点击 combobox 触发器打开下拉列表
        trigger = dialog.locator("button[role='combobox'][data-slot='select-trigger']")
        if trigger.count() > 0:
            trigger.first.click()
            self.page.wait_for_timeout(800)

            # 点击选项
            option = self.page.locator(f"[role='option']").filter(has_text=option_text)
            if option.count() > 0:
                option.first.click()
                self.page.wait_for_timeout(800)
                return

        # 回退：尝试 tab / radio
        tab = dialog.get_by_role("tab", name=server_type).or_(
            dialog.get_by_role("radio", name=server_type)
        ).or_(
            dialog.locator(f"button:has-text('{server_type}')")
        )
        if tab.count() > 0:
            tab.first.click()
            self.page.wait_for_timeout(500)

    def fill_create_form(self, name: str, command: str = "", url: str = ""):
        """填写创建表单"""
        dialog = self.page.locator("[role='dialog']")

        # 名称输入框（placeholder = my-mcp-server）
        name_input = dialog.locator("input[placeholder='my-mcp-server']").or_(
            dialog.locator("input[name='name']")
        ).or_(
            dialog.locator("input[placeholder*='名称']")
        ).or_(
            dialog.locator("input").first
        )
        if name_input.count() > 0:
            name_input.first.fill(name)

        # 命令（Local/Stdio 模式，placeholder = npx @anthropic/mcp-server-xxx --arg1 val1）
        if command:
            cmd_input = dialog.locator("input[placeholder*='npx']").or_(
                dialog.locator("input[name='command']")
            ).or_(
                dialog.locator("input[placeholder*='命令']")
            ).or_(
                dialog.locator("input[placeholder*='command']")
            ).or_(
                dialog.locator("textarea[name='command']")
            )
            if cmd_input.count() > 0:
                cmd_input.first.fill(command)

        # URL（Remote/SSE 模式，placeholder = https://example.com/mcp）
        if url:
            url_input = dialog.locator("input[placeholder*='example.com']").or_(
                dialog.locator("input[name='url']")
            ).or_(
                dialog.locator("input[placeholder*='URL']")
            ).or_(
                dialog.locator("input[type='url']")
            )
            if url_input.count() > 0:
                url_input.first.fill(url)

    def save(self):
        """点击保存/创建"""
        dialog = self.page.locator("[role='dialog']")
        save_btn = dialog.get_by_role("button", name="保存").or_(
            dialog.get_by_role("button", name="创建")
        ).or_(
            dialog.get_by_role("button", name="确定")
        )
        if save_btn.count() > 0:
            save_btn.first.click()
            self.page.wait_for_timeout(2000)

    def close_dialog(self):
        """关闭对话框"""
        dialog = self.page.locator("[role='dialog']")
        cancel = dialog.get_by_role("button", name="取消").or_(
            dialog.get_by_role("button", name="Close")
        )
        if cancel.count() > 0:
            cancel.first.click()
            self.page.wait_for_timeout(500)

    # === 表单校验 ===

    def get_validation_errors(self) -> list[str]:
        """获取表单校验错误信息"""
        dialog = self.page.locator("[role='dialog']")
        errors = dialog.locator(
            "[role='alert'], p.text-red-500, p.text-red-600, "
            "span.text-red-500, [class*='form-error'], "
            "[class*='invalid'], [class*='error']"
        )
        return [e.inner_text().strip() for e in errors.all() if e.inner_text().strip()]

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
            self.page.wait_for_timeout(5000)

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
        confirm = self.page.get_by_role("button", name="确认").or_(
            self.page.get_by_role("button", name="确定")
        ).or_(
            self.page.locator("[role='dialog']").get_by_role("button", name="删除")
        )
        if confirm.count() > 0:
            confirm.first.click()
            self.page.wait_for_timeout(2000)

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
