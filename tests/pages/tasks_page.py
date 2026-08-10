# tests/pages/tasks_page.py
"""定时任务页面 Page Object — 基于真实 DOM（CRUD 表格 + 创建/编辑弹窗）"""
from playwright.sync_api import Page


class TasksPage:
    """定时任务页 /ctrl/agent/tasks"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/tasks"

    def goto(self):
        self.page.goto(self.url)
        self.page.wait_for_load_state("networkidle")
        # 等待工作台 Tab 渲染完成（而非仅等 networkidle）
        try:
            self.page.locator("div.agent-panel-content button").filter(
                has_text="定时任务"
            ).first.wait_for(state="visible", timeout=5000)
        except Exception:
            pass

    def is_loaded(self) -> bool:
        """页面加载完成：URL 正确 + 面板内容可见"""
        return "/ctrl/agent/tasks" in self.page.url and \
            self.page.locator("div.agent-panel-content").count() > 0

    # === 工作台 Tab ===

    def has_workspace_tabs(self) -> bool:
        """是否有工作台 Tab 导航（文件/站点/定时任务/发布视图）"""
        content = self.page.locator("div.agent-panel-content")
        btns = content.locator("button").filter(has_text="定时任务")
        return btns.count() > 0

    def click_workspace_tab(self, name: str):
        """点击工作台 Tab"""
        btn = self.page.locator("div.agent-panel-content button").filter(
            has_text=name, has_not_text="新建"
        )
        if btn.count() > 0:
            btn.first.click()
            self.page.wait_for_timeout(1500)

    # === 筛选 Tab ===

    def get_filter_tabs(self) -> list[str]:
        """获取筛选 Tab 名称列表"""
        tabs = self.page.locator('[role="tab"]')
        return [tabs.nth(i).inner_text().strip() for i in range(tabs.count())]

    def click_filter_tab(self, name: str):
        """点击筛选 Tab（全部/HTTP/Agent）"""
        tab = self.page.locator('[role="tab"]').filter(has_text=name)
        if tab.count() > 0:
            tab.first.click()
            self.page.wait_for_timeout(1000)

    # === 表格 ===

    def get_task_count(self) -> int:
        """获取表格中的任务行数"""
        return self.page.locator("table tbody tr").count()

    def get_task_names(self) -> list[str]:
        """获取所有任务名称"""
        names = []
        rows = self.page.locator("table tbody tr")
        for row in rows.all():
            # 第一个 button 是任务名称
            name_btn = row.locator("button").first
            if name_btn.count() > 0:
                txt = name_btn.inner_text().strip()
                if txt:
                    names.append(txt)
        return names

    def has_task(self, name: str) -> bool:
        """列表中是否包含指定任务"""
        names = self.get_task_names()
        return any(name in n for n in names)

    def get_task_types(self) -> list[str]:
        """获取每行的任务类型（HTTP/Agent）"""
        types = []
        rows = self.page.locator("table tbody tr")
        for row in rows.all():
            text = row.inner_text()
            if "HTTP" in text:
                types.append("HTTP")
            elif "Agent" in text:
                types.append("Agent")
            else:
                types.append("unknown")
        return types

    # === 搜索 ===

    def search(self, keyword: str):
        """搜索任务"""
        inp = self.page.locator("div.agent-panel-content input[placeholder*='搜索']")
        if inp.count() == 0:
            # 备选：使用第一个 input
            inp = self.page.locator("table").locator("input")
        if inp.count() > 0:
            inp.first.fill("")
            inp.first.press_sequentially(keyword, delay=100)
            self.page.wait_for_timeout(500)

    def clear_search(self):
        inp = self.page.locator("div.agent-panel-content input[placeholder*='搜索']")
        if inp.count() == 0:
            inp = self.page.locator("table").locator("input")
        if inp.count() > 0:
            inp.first.fill("")
            self.page.wait_for_timeout(500)

    # === 创建任务 ===

    def click_create(self):
        """点击'新建任务'按钮"""
        btn = self.page.locator("button").filter(has_text="新建任务")
        if btn.count() > 0:
            btn.first.click()
            self.page.wait_for_timeout(1500)

    def is_dialog_open(self) -> bool:
        """创建/编辑弹窗是否打开"""
        d = self.page.locator('[role="dialog"]')
        return d.count() > 0 and d.first.is_visible()

    def get_dialog_title(self) -> str:
        """获取弹窗标题"""
        d = self.page.locator('[role="dialog"]')
        if d.count() > 0:
            return d.first.inner_text().split("\n")[0].strip()
        return ""

    def fill_task_name(self, name: str):
        """填写任务名称"""
        d = self.page.locator('[role="dialog"]')
        inp = d.locator('input[placeholder="输入任务名称"]')
        if inp.count() > 0:
            inp.first.fill(name)

    def fill_cron(self, cron: str):
        """填写 Cron 表达式"""
        d = self.page.locator('[role="dialog"]')
        inp = d.locator('input[placeholder="0 * * * *"]')
        if inp.count() > 0:
            inp.first.fill(cron)

    def click_cron_preset(self, preset_name: str):
        """点击 Cron 快捷预设按钮"""
        d = self.page.locator('[role="dialog"]')
        btn = d.locator("button").filter(has_text=preset_name)
        if btn.count() > 0:
            btn.first.click()
            self.page.wait_for_timeout(500)

    def switch_to_http(self):
        """切换到 HTTP 请求类型"""
        d = self.page.locator('[role="dialog"]')
        btn = d.locator("button").filter(has_text="HTTP 请求")
        if btn.count() > 0:
            btn.first.click()
            self.page.wait_for_timeout(500)

    def switch_to_agent(self):
        """切换到 Agent 调用类型"""
        d = self.page.locator('[role="dialog"]')
        btn = d.locator("button").filter(has_text="Agent 调用")
        if btn.count() > 0:
            btn.first.click()
            self.page.wait_for_timeout(500)

    def fill_http_url(self, url: str):
        """填写 HTTP URL"""
        d = self.page.locator('[role="dialog"]')
        inp = d.locator('input[placeholder*="example.com"]')
        if inp.count() > 0:
            inp.first.fill(url)

    def select_http_method(self, method: str):
        """选择 HTTP 方法"""
        d = self.page.locator('[role="dialog"]')
        sel = d.locator("select")
        if sel.count() > 0:
            sel.first.select_option(label=method)

    def fill_agent_prompt(self, prompt: str):
        """填写 Agent Prompt"""
        d = self.page.locator('[role="dialog"]')
        ta = d.locator('textarea[placeholder*="Agent"]')
        if ta.count() > 0:
            ta.first.fill(prompt)

    def select_agent(self, agent_name: str):
        """选择 Agent（combobox）"""
        d = self.page.locator('[role="dialog"]')
        combo = d.locator('[role="combobox"]')
        if combo.count() > 0:
            combo.first.click()
            self.page.wait_for_timeout(500)
            option = self.page.locator('[role="option"]').filter(has_text=agent_name)
            if option.count() > 0:
                option.first.click()
                self.page.wait_for_timeout(500)

    def save_dialog(self):
        """点击弹窗中的'保存'按钮"""
        d = self.page.locator('[role="dialog"]')
        btn = d.locator("button").filter(has_text="保存")
        if btn.count() > 0:
            btn.first.click()
            self.page.wait_for_timeout(1000)

    def cancel_dialog(self):
        """取消弹窗"""
        d = self.page.locator('[role="dialog"]')
        btn = d.locator("button").filter(has_text="取消")
        if btn.count() > 0:
            btn.first.click()
            self.page.wait_for_timeout(500)

    def close_dialog(self):
        """关闭弹窗（Close 按钮或 Escape）"""
        d = self.page.locator('[role="dialog"]')
        if d.count() > 0:
            close_btn = d.locator("button").filter(has_text="Close")
            if close_btn.count() > 0:
                close_btn.first.click()
            else:
                self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(500)

    # === 行内操作 ===

    def click_task_name(self, name: str):
        """点击任务名称（打开编辑弹窗）"""
        rows = self.page.locator("table tbody tr")
        for i in range(rows.count()):
            row = rows.nth(i)
            name_btn = row.locator("button").first
            if name_btn.count() > 0 and name in name_btn.inner_text():
                name_btn.click()
                self.page.wait_for_timeout(1500)
                return

    def click_execute(self, name: str):
        """点击手动执行按钮"""
        rows = self.page.locator("table tbody tr")
        for i in range(rows.count()):
            row = rows.nth(i)
            name_btn = row.locator("button").first
            if name_btn.count() > 0 and name in name_btn.inner_text():
                exec_btn = row.locator('button[title="执行"]')
                if exec_btn.count() > 0:
                    exec_btn.first.click()
                    self.page.wait_for_timeout(1000)
                    return

    def open_row_menu(self, name: str):
        """点击三点菜单（打开编辑/日志/删除菜单）"""
        rows = self.page.locator("table tbody tr")
        for i in range(rows.count()):
            row = rows.nth(i)
            name_btn = row.locator("button").first
            if name_btn.count() > 0 and name in name_btn.inner_text():
                row.hover()
                self.page.wait_for_timeout(500)
                ellipsis = row.locator("button").filter(
                    has=self.page.locator("svg.lucide-ellipsis")
                )
                if ellipsis.count() > 0:
                    ellipsis.first.click()
                    self.page.wait_for_timeout(1000)
                    return

    def click_menu_item(self, item_name: str):
        """点击菜单项（编辑/日志/删除）"""
        menu = self.page.locator('[role="menu"]')
        if menu.count() > 0:
            item = menu.locator('[role="menuitem"]').filter(has_text=item_name)
            if item.count() > 0:
                item.first.click()
                self.page.wait_for_timeout(1500)

    def get_row_switch_state(self, name: str) -> str:
        """获取行内开关状态"""
        rows = self.page.locator("table tbody tr")
        for i in range(rows.count()):
            row = rows.nth(i)
            name_btn = row.locator("button").first
            if name_btn.count() > 0 and name in name_btn.inner_text():
                sw = row.locator('[role="switch"]')
                if sw.count() > 0:
                    return sw.first.get_attribute("aria-checked") or \
                        sw.first.get_attribute("data-state") or "unknown"
        return "not_found"

    def toggle_switch(self, name: str):
        """切换行内开关"""
        rows = self.page.locator("table tbody tr")
        for i in range(rows.count()):
            row = rows.nth(i)
            name_btn = row.locator("button").first
            if name_btn.count() > 0 and name in name_btn.inner_text():
                sw = row.locator('[role="switch"]')
                if sw.count() > 0:
                    sw.first.click()
                    self.page.wait_for_timeout(1000)
                    return

    # === 面板内容 ===

    def get_panel_text(self) -> str:
        """获取面板内容区文本"""
        content = self.page.locator("div.agent-panel-content")
        if content.count() > 0:
            return content.inner_text()
        return ""
