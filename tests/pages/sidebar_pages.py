# tests/pages/sidebar_pages.py
"""侧边栏新页面 Page Objects（智能体编排、记忆、知识库、定时任务、组织、API Key）"""
from playwright.sync_api import Page


class WorkflowPage:
    """智能体编排页 /ctrl/agent/workflow"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/workflow"

    # 页面就绪标识：副标题（仅工作流页面有，不依赖懒加载）
    _READY_SELECTOR = "text=管理工作流与运行历史"

    def goto(self):
        for _attempt in range(2):
            try:
                self.page.goto(self.url, wait_until="domcontentloaded")
            except Exception:
                pass  # SPA 路由可能中断初始导航
            self.page.wait_for_load_state("domcontentloaded")
            try:
                self.page.locator(self._READY_SELECTOR).first.wait_for(state="attached", timeout=15000)
            except Exception:
                pass
            if self.is_loaded():
                break
            try:
                self.page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
            self.page.wait_for_timeout(500)
        # 降级：侧边栏 SPA 导航
        if not self.is_loaded():
            nav_btn = self.page.locator("button.agent-sidebar-nav-item").filter(has_text="智能体编排")
            if nav_btn.count() > 0:
                nav_btn.first.click()
                try:
                    self.page.locator(self._READY_SELECTOR).first.wait_for(state="attached", timeout=15000)
                except Exception:
                    pass

    def is_loaded(self) -> bool:
        if "/ctrl/agent/workflow" not in self.page.url:
            return False
        return self.page.locator(self._READY_SELECTOR).count() > 0

    def search(self, keyword: str):
        """搜索工作流"""
        inp = self.page.locator("input[placeholder*='搜索工作流']")
        if inp.count() > 0:
            inp.first.fill(keyword)
            self.page.wait_for_timeout(500)

    def clear_search(self):
        inp = self.page.locator("input[placeholder*='搜索工作流']")
        if inp.count() > 0:
            inp.first.fill("")
            self.page.wait_for_timeout(500)

    def get_workflow_count(self) -> int:
        """获取工作流卡片数量"""
        # 工作流卡片可能在不同容器内
        cards = self.page.locator(
            "div.agent-panel-content div.rounded-lg.border, "
            "div.group.rounded-lg.border"
        )
        return cards.count()

    def has_create_button(self) -> bool:
        btn = self.page.get_by_role("button", name="新建工作流")
        try:
            btn.first.wait_for(state="visible", timeout=10000)
            return btn.first.is_enabled()
        except Exception:
            return False

    # ── 创建工作流（UI 全流程） ──

    def create_workflow(self, name: str, description: str = "") -> str:
        """通过 UI 创建工作流：点击新建 → 填表 → 创建并编辑
        返回工作流 ID（从跳转后的 URL 中提取）
        真实 DOM: dialog[role='dialog'] > heading "新建工作流"
          textbox "名称 *" (placeholder='my-workflow')
          textbox "描述" (placeholder='工作流描述（可选）')
          button "创建并编辑"
        """
        btn = self.page.get_by_role("button", name="新建工作流")
        btn.wait_for(state="visible", timeout=5000)
        btn.click()

        dialog = self.page.get_by_role("dialog")
        dialog.wait_for(state="visible", timeout=5000)

        # 填写名称
        name_input = dialog.get_by_role("textbox", name="名称 *")
        name_input.wait_for(state="visible", timeout=5000)
        name_input.fill(name)

        # 填写描述（可选）
        if description:
            desc_input = dialog.get_by_role("textbox", name="描述")
            desc_input.fill(description)

        # 点击"创建并编辑"
        create_btn = dialog.get_by_role("button", name="创建并编辑")
        create_btn.wait_for(state="visible", timeout=5000)
        create_btn.click()

        # 等待跳转到编辑器页面
        self.page.wait_for_timeout(2000)
        # 从 URL 中提取工作流 ID: /ctrl/agent/workflow/{id}/edit
        url = self.page.url
        if "/workflow/" in url and "/edit" in url:
            parts = url.split("/workflow/")[1].split("/")
            return parts[0]
        return ""

    # ── 发布工作流（UI） ──

    def publish_workflow(self):
        """在编辑器中发布新版本
        真实 DOM: button "发布新版本" → alertdialog "发布新版本" → button "确认"
        """
        publish_btn = self.page.get_by_role("button", name="发布新版本")
        publish_btn.wait_for(state="visible", timeout=8000)
        publish_btn.click()

        # 等待确认弹窗
        dialog = self.page.get_by_role("alertdialog")
        dialog.wait_for(state="visible", timeout=5000)

        # 点击确认
        confirm_btn = dialog.get_by_role("button", name="确认")
        confirm_btn.wait_for(state="visible", timeout=5000)
        confirm_btn.click()
        self.page.wait_for_timeout(2000)

    # ── 列表操作 ──

    def click_version_history(self, workflow_name: str):
        """在列表中点击指定工作流的"版本历史"按钮
        真实 DOM: 每个工作流卡片有 button "编辑" / button "版本历史" / button(删除)
        """
        # 找到包含指定名称的工作流卡片
        card = self.page.locator("div.group").filter(has_text=workflow_name).first
        if card.count() == 0:
            # 降级：在所有卡片中搜索
            cards = self.page.locator("div[class*='rounded-lg'][class*='border']")
            for i in range(cards.count()):
                if workflow_name in (cards.nth(i).inner_text() or ""):
                    card = cards.nth(i)
                    break
        card.wait_for(state="visible", timeout=5000)
        version_btn = card.get_by_role("button", name="版本历史")
        version_btn.wait_for(state="visible", timeout=5000)
        version_btn.click()
        self.page.wait_for_timeout(2000)

    def delete_workflow(self, workflow_name: str):
        """在列表中删除指定工作流
        真实 DOM: 卡片中第三个 button（无 name，destructive 样式）→
                  alertdialog "删除" → button "确认"
        """
        card = self.page.locator("div.group").filter(has_text=workflow_name).first
        if card.count() == 0:
            cards = self.page.locator("div[class*='rounded-lg'][class*='border']")
            for i in range(cards.count()):
                if workflow_name in (cards.nth(i).inner_text() or ""):
                    card = cards.nth(i)
                    break
        card.wait_for(state="visible", timeout=5000)
        # 卡片中有3个按钮：编辑、版本历史、删除（无名按钮，destructive 样式）
        buttons = card.get_by_role("button")
        # 删除按钮是最后一个（无名）
        delete_btn = buttons.last
        delete_btn.wait_for(state="visible", timeout=5000)
        delete_btn.click()

        # 确认删除弹窗
        dialog = self.page.get_by_role("alertdialog")
        dialog.wait_for(state="visible", timeout=5000)
        confirm_btn = dialog.get_by_role("button", name="确认")
        confirm_btn.wait_for(state="visible", timeout=5000)
        confirm_btn.click()
        self.page.wait_for_timeout(1500)

    def has_workflow(self, workflow_name: str) -> bool:
        """列表中是否存在指定名称的工作流"""
        return (
            self.page.locator("div.group")
            .filter(has_text=workflow_name)
            .count()
            > 0
        )

    # ── 版本历史页面操作 ──

    def is_version_page_loaded(self, workflow_name: str) -> bool:
        """版本历史页面是否加载完成"""
        return (
            "/versions" in self.page.url
            and self.page.get_by_role("heading", name=workflow_name).count() > 0
        )

    def get_version_summary(self) -> dict:
        """获取版本摘要信息
        真实 DOM: "latest: v1" + "发布版本数: 1"
        """
        result = {"latest": "", "count": ""}
        latest_text = self.page.locator("text=latest:").first
        if latest_text.count() > 0:
            result["latest"] = latest_text.inner_text().strip()
        count_text = self.page.locator("text=发布版本数:").first
        if count_text.count() > 0:
            result["count"] = count_text.inner_text().strip()
        return result

    def has_version_card(self, version: str) -> bool:
        """是否有指定版本的卡片
        真实 DOM: 版本卡片内有 "v1" 文本
        """
        import re
        return (
            self.page.get_by_text(re.compile(rf'^{version}$'))
            .count()
            > 0
        )

    def has_latest_badge(self) -> bool:
        """是否有 'latest' 标记"""
        return self.page.get_by_text("latest").count() > 0

    def expand_version_card(self, version: str):
        """点击版本卡片展开 YAML 详情
        真实 DOM: 版本卡片的父容器 (cursor-pointer) 点击展开 <pre> YAML
        """
        import re
        version_label = self.page.get_by_text(re.compile(rf'^{version}$'))
        version_label.wait_for(state="visible", timeout=5000)
        # 点击父容器（版本卡片的 header 行）
        version_label.locator("xpath=..").click()
        self.page.wait_for_timeout(1000)

    def is_yaml_expanded(self) -> bool:
        """YAML 详情面板是否展开"""
        return self.page.locator("pre").count() > 0

    def restore_to_draft(self, version: str):
        """点击指定版本的"恢复到草稿"并确认
        真实 DOM: button "恢复到草稿" → alertdialog "恢复到草稿" → button "确认"
        """
        # 找到包含指定版本的卡片中的恢复按钮
        import re
        version_label = self.page.get_by_text(re.compile(rf'^{version}$'))
        version_label.wait_for(state="visible", timeout=5000)
        # 版本卡片的父容器中找到"恢复到草稿"按钮
        card_container = version_label.locator("xpath=ancestor::div[contains(@class, 'cursor-pointer') or contains(@class, 'group')]")
        restore_btn = card_container.get_by_role("button", name="恢复到草稿")
        if restore_btn.count() == 0:
            # 降级：直接使用页面上的恢复按钮
            restore_btn = self.page.get_by_role("button", name="恢复到草稿")
        restore_btn.first.wait_for(state="visible", timeout=5000)
        restore_btn.first.click()

        # 确认弹窗
        dialog = self.page.get_by_role("alertdialog")
        dialog.wait_for(state="visible", timeout=5000)
        confirm_btn = dialog.get_by_role("button", name="确认")
        confirm_btn.wait_for(state="visible", timeout=5000)
        confirm_btn.click()
        self.page.wait_for_timeout(1500)

    # ── 编辑器导航 ──

    def go_back_to_list(self):
        """从编辑器或版本页面回到工作流列表"""
        breadcrumb = self.page.get_by_role("link", name="工作流")
        if breadcrumb.count() > 0:
            breadcrumb.first.click()
            self.page.wait_for_timeout(1500)
        else:
            self.goto()


class MemoryPage:
    """记忆页 /ctrl/agent/memories"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/memories"

    # 页面就绪标识：Tab 或"未开启"提示（记忆服务未配置时显示"记忆能力未开启..."）
    _READY_SELECTORS = "[role='tab'], :text('未开启'), :text('记忆能力'), :text('Hindsight')"

    def goto(self):
        for _attempt in range(2):
            try:
                self.page.goto(self.url, wait_until="domcontentloaded")
            except Exception:
                pass
            self.page.wait_for_load_state("domcontentloaded")
            try:
                self.page.locator(self._READY_SELECTORS).first.wait_for(state="attached", timeout=15000)
            except Exception:
                pass
            if self.is_loaded():
                break
            try:
                self.page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
            self.page.wait_for_timeout(500)
        # 降级：侧边栏 SPA 导航
        if not self.is_loaded():
            nav_btn = self.page.locator("button.agent-sidebar-nav-item").filter(has_text="记忆")
            if nav_btn.count() > 0:
                nav_btn.first.click()
                try:
                    self.page.locator(self._READY_SELECTORS).first.wait_for(state="attached", timeout=15000)
                except Exception:
                    pass

    def is_loaded(self) -> bool:
        return "/ctrl/agent/memor" in self.page.url and \
            self.page.locator(self._READY_SELECTORS).count() > 0

    def get_tab_names(self) -> list[str]:
        """获取分类 Tab 名称列表"""
        tabs = self.page.locator("[role='tab']")
        return [t.strip() for t in tabs.all_text_contents() if t.strip()]

    def click_tab(self, name: str):
        """点击某个分类 Tab"""
        tab = self.page.locator("[role='tab']").filter(has_text=name).first
        tab.wait_for(state="visible", timeout=5000)
        tab.click()
        self.page.wait_for_timeout(500)

    def is_tab_active(self, name: str) -> bool:
        """某个 Tab 是否处于激活状态"""
        tab = self.page.locator("[role='tab']").filter(has_text=name)
        if tab.count() == 0:
            return False
        cls = tab.first.get_attribute("class") or ""
        aria = tab.first.get_attribute("aria-selected") or ""
        return "active" in cls.lower() or aria == "true" or "selected" in cls.lower()

    def has_view_buttons(self) -> bool:
        """是否有视图切换按钮（星座图/图谱/表格/时间线）"""
        btns = self.page.get_by_role("button", name="星座图").or_(
            self.page.get_by_role("button", name="图谱")
        )
        try:
            btns.first.wait_for(state="visible", timeout=15000)
            return True
        except Exception:
            return False


class KnowledgeBasePage:
    """知识库页 /ctrl/agent/knowledge-bases"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/knowledge-bases"

    # 页面就绪标识：搜索输入框
    _READY_SELECTOR = "input[placeholder*='搜索知识库']"

    def goto(self):
        for _attempt in range(2):
            try:
                self.page.goto(self.url, wait_until="domcontentloaded")
            except Exception:
                pass
            self.page.wait_for_load_state("domcontentloaded")
            try:
                self.page.locator(self._READY_SELECTOR).first.wait_for(state="attached", timeout=15000)
            except Exception:
                pass
            if self.is_loaded():
                break
            try:
                self.page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
            self.page.wait_for_timeout(500)
        # 降级：侧边栏 SPA 导航
        if not self.is_loaded():
            nav_btn = self.page.locator("button.agent-sidebar-nav-item").filter(has_text="知识库")
            if nav_btn.count() > 0:
                nav_btn.first.click()
                try:
                    self.page.locator(self._READY_SELECTOR).first.wait_for(state="attached", timeout=15000)
                except Exception:
                    pass

    def is_loaded(self) -> bool:
        return "/ctrl/agent/knowledge" in self.page.url and \
            self.page.locator(self._READY_SELECTOR).count() > 0

    def search(self, keyword: str):
        inp = self.page.locator("input[placeholder*='搜索知识库']")
        if inp.count() > 0:
            inp.first.fill(keyword)
            self.page.wait_for_timeout(500)

    def clear_search(self):
        inp = self.page.locator("input[placeholder*='搜索知识库']")
        if inp.count() > 0:
            inp.first.fill("")
            self.page.wait_for_timeout(500)

    def get_kb_count(self) -> int:
        """获取知识库卡片数量"""
        cards = self.page.locator(
            "div.agent-panel-content div.rounded-lg.border"
        )
        return cards.count()

    def has_create_button(self) -> bool:
        btn = self.page.get_by_role("button", name="新建知识库")
        return btn.count() > 0 and btn.first.is_visible() and btn.first.is_enabled()


class TasksPage:
    """定时任务页 /ctrl/agent/tasks"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/tasks"

    # 页面就绪标识：搜索输入框或定时任务按钮
    _READY_SELECTOR = "input[placeholder*='搜索任务'], button:has-text('定时任务')"

    def goto(self):
        for _attempt in range(2):
            try:
                self.page.goto(self.url, wait_until="domcontentloaded")
            except Exception:
                pass  # SPA 路由可能中断初始导航
            self.page.wait_for_load_state("domcontentloaded")
            try:
                self.page.locator(self._READY_SELECTOR).first.wait_for(state="attached", timeout=15000)
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
        return "/ctrl/agent/tasks" in self.page.url and \
            self.page.locator(self._READY_SELECTOR).count() > 0

    def get_tab_names(self) -> list[str]:
        tabs = self.page.locator("[role='tab']")
        return [t.strip() for t in tabs.all_text_contents() if t.strip()]

    def click_tab(self, name: str):
        tab = self.page.locator("[role='tab']").filter(has_text=name).first
        tab.wait_for(state="visible", timeout=5000)
        tab.click()
        self.page.wait_for_timeout(500)

    def get_task_count(self) -> int:
        """表格中的任务行数"""
        rows = self.page.locator("table tbody tr")
        return rows.count()

    def has_table(self) -> bool:
        return self.page.locator("table").count() > 0

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

    def click_create(self):
        """点击「新建任务」按钮"""
        btn = self.page.get_by_role("button", name="新建任务")
        if btn.count() == 0:
            # 尝试其他可能的按钮文本
            btn = self.page.locator("button").filter(has_text="新建")
        if btn.count() > 0:
            btn.first.click()
            self.page.wait_for_timeout(1000)

    def is_dialog_open(self) -> bool:
        """检查新建/编辑任务弹窗是否打开"""
        dialog = self.page.locator("[role='dialog']")
        return dialog.count() > 0 and dialog.first.is_visible()


class OrganizationPage:
    """组织管理页 /ctrl/agent/organizations"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/organizations"

    # 页面就绪标识：h2 标题
    _READY_SELECTOR = "h2"

    def goto(self):
        for _attempt in range(2):
            try:
                self.page.goto(self.url, wait_until="domcontentloaded")
            except Exception:
                pass
            self.page.wait_for_load_state("domcontentloaded")
            try:
                self.page.locator(self._READY_SELECTOR).first.wait_for(state="attached", timeout=15000)
            except Exception:
                pass
            if self.is_loaded():
                break
            try:
                self.page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
            self.page.wait_for_timeout(500)
        # 降级：侧边栏 SPA 导航
        if not self.is_loaded():
            nav_btn = self.page.locator("button.agent-sidebar-nav-item").filter(has_text="组织")
            if nav_btn.count() > 0:
                nav_btn.first.click()
                try:
                    self.page.locator(self._READY_SELECTOR).first.wait_for(state="attached", timeout=15000)
                except Exception:
                    pass

    def is_loaded(self) -> bool:
        return "/ctrl/agent/organization" in self.page.url and \
            self.page.locator(self._READY_SELECTOR).count() > 0

    def get_org_name(self) -> str:
        """获取当前组织名称"""
        h2 = self.page.locator("h2")
        if h2.count() > 0:
            return h2.first.inner_text().strip()
        return ""

    def has_member_section(self) -> bool:
        """是否有成员区域"""
        return self.page.locator("h3").filter(has_text="成员").count() > 0

    def get_member_count_text(self) -> str:
        """获取成员数文本，如 '成员 (42)'"""
        h3 = self.page.locator("h3").filter(has_text="成员")
        if h3.count() > 0:
            return h3.first.inner_text().strip()
        return ""


class ApiKeyPage:
    """API 密钥页 /ctrl/agent/apikeys"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/apikeys"

    # 页面就绪标识：搜索输入框
    _READY_SELECTOR = "input[placeholder*='搜索密钥']"

    def goto(self):
        for _attempt in range(2):
            try:
                self.page.goto(self.url, wait_until="domcontentloaded")
            except Exception:
                pass
            self.page.wait_for_load_state("domcontentloaded")
            try:
                self.page.locator(self._READY_SELECTOR).first.wait_for(state="attached", timeout=15000)
            except Exception:
                pass
            if self.is_loaded():
                break
            try:
                self.page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
            self.page.wait_for_timeout(500)
        # 降级：侧边栏 SPA 导航
        if not self.is_loaded():
            nav_btn = self.page.locator("button.agent-sidebar-nav-item").filter(has_text="API Key")
            if nav_btn.count() > 0:
                nav_btn.first.click()
                try:
                    self.page.locator(self._READY_SELECTOR).first.wait_for(state="attached", timeout=15000)
                except Exception:
                    pass

    def is_loaded(self) -> bool:
        return "/ctrl/agent/apikeys" in self.page.url and \
            self.page.locator(self._READY_SELECTOR).count() > 0

    def search(self, keyword: str):
        inp = self.page.locator("input[placeholder*='搜索密钥']")
        if inp.count() > 0:
            inp.first.fill(keyword)
            inp.first.press("Enter")
            self.page.wait_for_timeout(1500)

    def clear_search(self):
        inp = self.page.locator("input[placeholder*='搜索密钥']")
        if inp.count() > 0:
            inp.first.fill("")
            inp.first.press("Enter")
            self.page.wait_for_timeout(1500)

    def get_key_count(self) -> int:
        """获取密钥列表项数量（grid 卡片布局）"""
        return self.page.locator("div.grid.gap-3 > div").count()

    def has_create_button(self) -> bool:
        btn = self.page.get_by_role("button", name="创建密钥")
        return btn.count() > 0 and btn.first.is_visible() and btn.first.is_enabled()


class SidebarNavigation:
    """侧边栏导航通用操作"""

    # 侧边栏菜单项 → 预期 URL 路径
    NAV_ITEMS = {
        "新建智能体": "/ctrl/agent/home",
        "智能体管理": "/ctrl/agent/agents",
        "智能体编排": "/ctrl/agent/workflow",
        "记忆": "/ctrl/agent/memor",
        "知识库": "/ctrl/agent/knowledge",
        "定时任务": "/ctrl/agent/tasks",
        "组织": "/ctrl/agent/organization",
        "API Key": "/ctrl/agent/apikeys",
        "模型库": "/ctrl/agent/models",
        "垂直模型库": "/ctrl/agent/vertical-models",
        "算法库": "/ctrl/agent/algorithms",
        "技能库": "/ctrl/agent/skills",
        "MCP": "/ctrl/agent/mcp",
        "Agent Sites": "/ctrl/agent/sites",
    }

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url

    def get_nav_items(self) -> list[str]:
        """获取所有侧边栏导航项名称"""
        items = self.page.locator("button.agent-sidebar-nav-item")
        return [t.strip() for t in items.all_text_contents() if t.strip()]

    def get_nav_count(self) -> int:
        return self.page.locator("button.agent-sidebar-nav-item").count()

    def click_nav(self, name: str):
        """点击侧边栏导航项"""
        btn = self.page.locator("button.agent-sidebar-nav-item").filter(
            has_text=name
        )
        if btn.count() > 0:
            btn.first.click()
            self.page.wait_for_load_state("domcontentloaded")

    def is_nav_active(self, name: str) -> bool:
        """某导航项是否处于激活状态"""
        btn = self.page.locator("button.agent-sidebar-nav-item").filter(
            has_text=name
        )
        if btn.count() == 0:
            return False
        cls = btn.first.get_attribute("class") or ""
        return "active" in cls.lower() or "selected" in cls.lower()

    def get_group_labels(self) -> list[str]:
        """获取侧边栏分组标签（如 '核心'、'配置'）"""
        groups = self.page.locator("aside.agent-sidebar span, aside.agent-sidebar h3, aside.agent-sidebar h4")
        return [t.strip() for t in groups.all_text_contents() if t.strip()]

    def has_nav_item(self, name: str) -> bool:
        return self.page.locator("button.agent-sidebar-nav-item").filter(
            has_text=name
        ).count() > 0

    def has_panel_content(self) -> bool:
        return self.page.locator("div.agent-panel-content").count() > 0
