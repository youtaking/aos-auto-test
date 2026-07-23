# tests/pages/tasks_page.py
"""定时任务页面 Page Object（基于真实页面结构）"""
from playwright.sync_api import Page, expect


class TasksPage:
    """定时任务管理页 /ctrl/agent/tasks"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/tasks"

    def goto(self):
        self.page.goto(self.url)
        self.page.wait_for_load_state("networkidle")

    def is_loaded(self) -> bool:
        return self.page.locator("h1").filter(has_text="定时任务").count() > 0

    # === 列表 ===

    def get_task_count(self) -> int:
        return self.page.locator("table tbody tr").count()

    def has_table(self) -> bool:
        return self.page.locator("table").count() > 0

    def get_task_names(self) -> list[str]:
        """获取所有任务名称"""
        names = []
        for row in self.page.locator("table tbody tr").all():
            name_btn = row.locator("td").nth(1).locator("button")
            if name_btn.count() > 0:
                names.append(name_btn.inner_text().strip())
        return names

    def has_task(self, name: str) -> bool:
        return name in self.get_task_names()

    def search(self, keyword: str):
        inp = self.page.locator("input[placeholder*='搜索任务']")
        if inp.count() > 0:
            inp.first.fill(keyword)
            self.page.wait_for_timeout(500)

    def clear_search(self):
        inp = self.page.locator("input[placeholder*='搜索任务']")
        if inp.count() > 0:
            inp.first.fill("")
            self.page.wait_for_timeout(500)

    # === 创建任务 ===

    def open_create_dialog(self):
        self.page.get_by_role("button", name="新建任务").first.click()
        self.page.wait_for_timeout(1000)

    def is_create_dialog_open(self) -> bool:
        return self.page.locator("[role='dialog']").count() > 0

    def close_dialog(self):
        cancel = self.page.locator("[role='dialog']").get_by_role("button", name="取消")
        if cancel.count() > 0:
            cancel.first.click()
            self.page.wait_for_timeout(500)
        else:
            close_btn = self.page.locator("[role='dialog']").get_by_role("button", name="Close")
            if close_btn.count() > 0:
                close_btn.first.click()
                self.page.wait_for_timeout(500)

    def select_type(self, task_type: str):
        """选择任务类型：'HTTP 请求' 或 'Agent 调用'"""
        dialog = self.page.locator("[role='dialog']")
        tab = dialog.locator("[role='tab']").filter(has_text=task_type)
        if tab.count() > 0:
            tab.first.click()
            self.page.wait_for_timeout(500)

    def fill_task_form(self, name: str, cron: str = "", task_type: str = "HTTP 请求",
                       url: str = "", method: str = "POST",
                       agent_name: str = "", prompt: str = "",
                       timeout: int = None):
        """填写任务表单"""
        dialog = self.page.locator("[role='dialog']")

        # 选择类型
        self.select_type(task_type)

        # 任务名称
        name_input = dialog.locator("input[name='name']")
        name_input.fill(name)

        # Cron 表达式
        if cron:
            cron_input = dialog.locator("input[placeholder*='* * *']")
            if cron_input.count() > 0:
                cron_input.first.fill(cron)

        # 超时时间
        if timeout is not None:
            timeout_input = dialog.locator("input[name='timeoutSeconds']")
            timeout_input.fill(str(timeout))

        if task_type == "HTTP 请求":
            # URL
            if url:
                url_input = dialog.locator("input[name='url']")
                url_input.fill(url)
            # HTTP Method (combobox -> listbox -> option)
            if method != "POST":
                method_combo = dialog.locator("[role='combobox']")
                if method_combo.count() > 0:
                    method_combo.first.click()
                    self.page.wait_for_timeout(300)
                    option = self.page.locator("[role='option']").filter(has_text=method)
                    if option.count() > 0:
                        option.first.click()
                    self.page.wait_for_timeout(300)
        elif task_type == "Agent 调用":
            # 选择 Agent (combobox -> listbox -> option)
            if agent_name:
                agent_combo = dialog.locator("[role='combobox']")
                if agent_combo.count() > 0:
                    agent_combo.first.click()
                    self.page.wait_for_timeout(500)
                    option = self.page.locator("[role='option']").filter(has_text=agent_name)
                    if option.count() > 0:
                        option.first.click()
                    self.page.wait_for_timeout(300)
            # Prompt
            if prompt:
                prompt_input = dialog.locator("input[name='prompt'], textarea[name='prompt']")
                if prompt_input.count() > 0:
                    prompt_input.first.fill(prompt)

    def save_task(self):
        """点击保存"""
        dialog = self.page.locator("[role='dialog']")
        save_btn = dialog.get_by_role("button", name="保存")
        save_btn.first.click()
        self.page.wait_for_timeout(1500)

    def create_http_task(self, name: str, url: str, cron: str = "0 * * * *",
                         method: str = "POST", timeout: int = None):
        """快捷创建 HTTP 任务"""
        self.open_create_dialog()
        self.fill_task_form(name=name, task_type="HTTP 请求", url=url,
                           cron=cron, method=method, timeout=timeout)
        self.save_task()

    def create_agent_task(self, name: str, agent_name: str, prompt: str,
                          cron: str = "0 * * * *", timeout: int = None):
        """快捷创建 Agent 任务"""
        self.open_create_dialog()
        self.fill_task_form(name=name, task_type="Agent 调用",
                           agent_name=agent_name, prompt=prompt,
                           cron=cron, timeout=timeout)
        self.save_task()

    # === 表单校验 ===

    def submit_empty_form(self):
        """直接点击保存（不填任何内容）"""
        self.open_create_dialog()
        self.save_task()

    def get_validation_errors(self) -> list[str]:
        """获取表单校验错误信息"""
        dialog = self.page.locator("[role='dialog']")
        errors = dialog.locator("[class*='error'], [class*='invalid'], [class*='danger'], p[class*='red']")
        return [e.inner_text().strip() for e in errors.all() if e.inner_text().strip()]

    # === 行操作 ===

    def _get_row_by_name(self, name: str):
        """根据任务名找到对应行"""
        rows = self.page.locator("table tbody tr")
        for row in rows.all():
            name_btn = row.locator("td").nth(1).locator("button")
            if name_btn.count() > 0 and name_btn.inner_text().strip() == name:
                return row
        return None

    def execute_task(self, name: str):
        """手动执行某个任务"""
        row = self._get_row_by_name(name)
        if row:
            exec_btn = row.locator("td").last.locator("button[title='执行']")
            if exec_btn.count() > 0:
                exec_btn.first.click()
                self.page.wait_for_timeout(2000)

    def open_task_menu(self, name: str):
        """打开某个任务的三点菜单"""
        row = self._get_row_by_name(name)
        if row:
            # btn[1] is the three-dot menu
            menu_btn = row.locator("td").last.locator("button").nth(1)
            menu_btn.click()
            self.page.wait_for_timeout(500)

    def edit_task(self, name: str):
        """点击编辑"""
        self.open_task_menu(name)
        self.page.get_by_role("menuitem", name="编辑").click()
        self.page.wait_for_timeout(1000)

    def view_task_log(self, name: str):
        """点击查看日志"""
        self.open_task_menu(name)
        self.page.get_by_role("menuitem", name="日志").click()
        self.page.wait_for_timeout(1000)

    def delete_task(self, name: str):
        """删除某个任务"""
        self.open_task_menu(name)
        self.page.get_by_role("menuitem", name="删除").click()
        self.page.wait_for_timeout(500)
        # 确认删除
        confirm = self.page.get_by_role("button", name="确认").or_(
            self.page.get_by_role("button", name="确定")
        ).or_(
            self.page.get_by_role("button", name="删除")
        )
        # 可能在 dialog 中
        dialog_confirm = self.page.locator("[role='dialog']").get_by_role("button", name="确认").or_(
            self.page.locator("[role='dialog']").get_by_role("button", name="确定")
        ).or_(
            self.page.locator("[role='dialog']").get_by_role("button", name="删除")
        )
        if dialog_confirm.count() > 0:
            dialog_confirm.first.click()
        elif confirm.count() > 0:
            confirm.first.click()
        self.page.wait_for_timeout(1500)

    def toggle_task_enabled(self, name: str):
        """切换任务的启用/禁用开关"""
        row = self._get_row_by_name(name)
        if row:
            switch = row.locator("[role='switch']")
            if switch.count() > 0:
                switch.first.click()
                self.page.wait_for_timeout(500)

    def is_task_enabled(self, name: str) -> bool:
        """任务是否启用"""
        row = self._get_row_by_name(name)
        if row:
            switch = row.locator("[role='switch']")
            if switch.count() > 0:
                data_state = switch.first.get_attribute("data-state") or ""
                return data_state == "checked"
        return False

    # === Cron 预设 ===

    def click_cron_preset(self, preset: str):
        """点击 Cron 预设按钮"""
        dialog = self.page.locator("[role='dialog']")
        btn = dialog.get_by_role("button", name=preset)
        if btn.count() > 0:
            btn.first.click()
            self.page.wait_for_timeout(300)

    # === 执行状态 ===

    def get_task_status(self, name: str) -> str:
        """获取任务上次执行状态"""
        row = self._get_row_by_name(name)
        if row:
            # 上次执行列（第6列，index=5）
            status_td = row.locator("td").nth(5)
            text = status_td.inner_text().strip()
            return text
        return ""
