# tests/pages/sidebar_pages.py
"""侧边栏新页面 Page Objects（智能体编排、记忆、知识库、定时任务、组织、API Key）"""
import re
from playwright.sync_api import Page


_RE_RUN_LOG_BTN = re.compile(r"^运行日志：")
_RE_PAGINATION = re.compile(r"共 \d+ 条")
_RE_EDIT_URL = re.compile(r"/workflow/([^/]+)/edit")
_RE_PUBLISH_LOG_HEADING = re.compile(r"^发布日志")
_RE_RUN_LOG_HEADING = re.compile(r"^运行日志")
_RE_AUTOSAVED = re.compile(r"已自动保存")


class WorkflowPage:
    """智能体编排页 /ctrl/agent/workflow

    新版架构（2026-10 起）：
      * 列表页：卡片含「打开画布：{name}」「运行日志：{name}」「更多操作：{name}」，
        卡片菜单提供 发布日志 / 调用接口 / 重命名 / 删除。
      * 编辑器：`/ctrl/agent/workflow/{upstreamWorkflowId}/edit`，画布是
        `iframe[title='工作流画布']` 微前端（发布按钮在 iframe 内，控制台不再发布）。
      * 运行日志：页面级 dialog（不是 `?tab=runs` 页面），内含「工作流」下拉 + 执行记录列表。
    """

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/workflow"

    # 页面就绪标识：新版副标题（仅工作流页面有，不依赖懒加载）
    _READY_SELECTOR = "text=管理与编排工作流"
    # 画布微前端 iframe
    CANVAS_IFRAME = "iframe[title='工作流画布']"

    # ── 列表页 ──

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

    def is_space_blocked(self) -> bool:
        """工作流空间不可用状态（blocked）。

        新版工作流依赖「组织工作流空间」，未初始化时列表/新建/画布全部禁用，
        并提示「尚未初始化工作流空间」；点击初始化会 POST /web/workflow-v2/org-app，
        当平台工作流账号不可用时返回 503（PLATFORM_SESSION_UNAVAILABLE），
        页面提示「平台工作流账号当前不可用」。两种提示都代表功能不可用。
        """
        try:
            body = self.page.locator("body").inner_text()
        except Exception:
            return False
        return ("尚未初始化工作流空间" in body) or \
            ("平台工作流账号" in body and "不可用" in body)

    def get_workflow_count(self) -> int:
        """列表页工作流卡片数（每张卡片恰好有一个「运行日志：{name}」按钮）"""
        return self.page.get_by_role("button", name=_RE_RUN_LOG_BTN).count()

    def has_create_button(self) -> bool:
        btn = self.page.get_by_role("button", name="新建工作流")
        try:
            btn.first.wait_for(state="visible", timeout=10000)
            return btn.first.is_enabled()
        except Exception:
            return False

    def has_workflow(self, name: str) -> bool:
        """列表中是否存在指定名称的工作流（名称精确匹配，避免子串误判）"""
        btn = self.page.get_by_role("button", name=f"打开画布：{name}", exact=True)
        try:
            btn.first.wait_for(state="visible", timeout=5000)
            return True
        except Exception:
            return False

    def refresh_list(self):
        """点击「刷新列表」，等待列表重绘"""
        btn = self.page.get_by_role("button", name="刷新列表")
        btn.wait_for(state="visible", timeout=8000)
        btn.click()
        self.page.wait_for_timeout(1500)

    def get_pagination_text(self) -> str:
        """列表底部分页文本，形如「共 2 条」；不存在时返回空串"""
        el = self.page.get_by_text(_RE_PAGINATION).first
        try:
            el.wait_for(state="visible", timeout=5000)
            return el.inner_text().strip()
        except Exception:
            return ""

    # ── 创建工作流（UI 全流程） ──

    def create_workflow(self, name: str, description: str = "") -> str:
        """通过 UI 创建工作流：新建 → 填表 → 创建并打开
        返回 **上游 workflow ID**（编辑器路由 `$id` 用的就是它，从跳转后的 URL 提取）

        真实 DOM: 列表页 button "新建工作流" →
          dialog[role='dialog']: input#workflow-create-name / textarea#workflow-create-desc
          → button "创建并打开" → 跳转 /ctrl/agent/workflow/{upstreamId}/edit
        """
        btn = self.page.get_by_role("button", name="新建工作流")
        btn.wait_for(state="visible", timeout=8000)
        btn.click()

        dialog = self.page.get_by_role("dialog")
        dialog.wait_for(state="visible", timeout=8000)
        name_input = dialog.locator("#workflow-create-name")
        name_input.wait_for(state="visible", timeout=8000)
        name_input.fill(name)
        if description:
            dialog.locator("#workflow-create-desc").fill(description)

        create_btn = dialog.get_by_role("button", name="创建并打开")
        create_btn.wait_for(state="visible", timeout=8000)
        create_btn.click()

        try:
            self.page.wait_for_url(_RE_EDIT_URL, timeout=20000)
        except Exception:
            pass
        self.page.wait_for_timeout(1000)
        m = _RE_EDIT_URL.search(self.page.url)
        return m.group(1) if m else ""

    # ── 卡片操作 ──

    def open_canvas_by_id(self, upstream_id: str):
        """按上游 workflow ID 直连编辑器并等待画布就绪"""
        try:
            self.page.goto(
                f"{self.base_url}/ctrl/agent/workflow/{upstream_id}/edit",
                wait_until="domcontentloaded",
            )
        except Exception:
            pass
        self.wait_canvas_ready()

    def open_canvas(self, name: str):
        """点击卡片「打开画布」进入编辑器"""
        btn = self.page.get_by_role("button", name=f"打开画布：{name}")
        btn.first.wait_for(state="visible", timeout=8000)
        btn.first.click()
        try:
            self.page.wait_for_url(_RE_EDIT_URL, timeout=20000)
        except Exception:
            pass
        self.wait_canvas_ready()

    def open_run_logs(self, name: str):
        """点击卡片「运行日志：{name}」打开运行日志弹窗"""
        btn = self.page.get_by_role("button", name=f"运行日志：{name}")
        btn.wait_for(state="visible", timeout=8000)
        btn.click()
        self.page.wait_for_timeout(1500)

    def open_all_run_logs(self):
        """点击表头「全部运行日志」打开运行日志弹窗"""
        btn = self.page.get_by_role("button", name="全部运行日志")
        btn.wait_for(state="visible", timeout=8000)
        btn.click()
        self.page.wait_for_timeout(1500)

    def run_log_dialog(self):
        """运行日志弹窗（页级 dialog）

        「全部运行日志」标题为「运行日志」；卡片「运行日志：{name}」标题为
        「运行日志 · {name}」，因此用前缀匹配。
        """
        return self.page.locator("[role=dialog]").filter(
            has=self.page.get_by_role("heading", name=_RE_RUN_LOG_HEADING)
        )

    def _open_card_menu(self, name: str):
        btn = self.page.get_by_role("button", name=f"更多操作：{name}")
        btn.wait_for(state="visible", timeout=8000)
        btn.click()
        self.page.get_by_role("menu").wait_for(state="visible", timeout=8000)
        self.page.wait_for_timeout(300)

    def _click_menu_item(self, item: str):
        mi = self.page.get_by_role("menuitem", name=item, exact=True)
        mi.wait_for(state="visible", timeout=8000)
        mi.click()
        self.page.wait_for_timeout(1500)

    def open_publish_log(self, name: str):
        """卡片菜单 → 发布日志（打开「发布日志」弹窗）"""
        self._open_card_menu(name)
        self._click_menu_item("发布日志")

    def publish_log_dialog(self):
        return self.page.locator("[role=dialog]").filter(
            has=self.page.get_by_role("heading", name=_RE_PUBLISH_LOG_HEADING)
        )

    def open_api_info(self, name: str):
        """卡片菜单 → 调用接口（打开「调用接口」弹窗）"""
        self._open_card_menu(name)
        self._click_menu_item("调用接口")

    def rename(self, name: str, new_name: str):
        """卡片菜单 → 重命名 → 改名称 → 保存（仅对自建工作流使用）

        真实 DOM: dialog[role=dialog] 标题「重命名工作流」，
          input#workflow-rename-name（预填原名），按钮 取消 / 保存 / Close。
        """
        self._open_card_menu(name)
        self._click_menu_item("重命名")
        dialog = self.page.get_by_role("dialog")
        dialog.wait_for(state="visible", timeout=8000)
        name_box = dialog.locator("#workflow-rename-name")
        name_box.wait_for(state="visible", timeout=8000)
        name_box.fill(new_name)
        dialog.get_by_role("button", name="保存", exact=True).click()
        self.page.wait_for_timeout(2000)

    def delete_workflow(self, name: str):
        """删除工作流：更多操作 → 删除 → 校验弹窗内容 → 确认

        仅用于删除**测试自建**的工作流；弹窗前会校验弹窗文本包含目标名称，
        并断言确认按钮唯一，避免误删。
        """
        self._open_card_menu(name)
        self._click_menu_item("删除")
        dialog = self.page.locator("[role=alertdialog], [role=dialog]").last
        dialog.wait_for(state="visible", timeout=8000)

        text = dialog.inner_text()
        assert name in text, \
            f"删除确认弹窗未包含目标名称 '{name}'，可能误删其他对象！弹窗: {text[:120]}"
        assert "删除智能体" not in text, "弹窗是关于删除智能体的，不是删除工作流！"

        confirm = dialog.get_by_role("button", name="删除", exact=True)
        assert confirm.count() == 1, \
            f"删除确认按钮匹配了 {confirm.count()} 个元素，预期唯一"
        confirm.click()
        self.page.wait_for_timeout(2000)

    # ── 编辑器（iframe 画布） ──

    def canvas_frame(self):
        """画布微前端 iframe 的 FrameLocator"""
        return self.page.frame_locator(self.CANVAS_IFRAME)

    def wait_canvas_ready(self):
        """等待画布 iframe 握手完成并渲染出画布根节点"""
        try:
            self.page.locator("text=画布已就绪").first.wait_for(state="visible", timeout=20000)
        except Exception:
            pass
        try:
            self.canvas_frame().locator("[data-testid='sdk.workflow.canvas']").first.wait_for(
                state="visible", timeout=20000
            )
        except Exception:
            self.page.wait_for_timeout(1500)

    def is_canvas_ready(self) -> bool:
        return (
            self.page.locator(self.CANVAS_IFRAME).count() > 0
            and self.page.locator("[data-testid='sdk.workflow.canvas']").count() >= 0
            and self.canvas_frame().locator("[data-testid='sdk.workflow.canvas']").count() > 0
        )

    def has_publish_button(self) -> bool:
        """画布内「发布」按钮是否可见（发布入口在 iframe 内）"""
        btn = self.canvas_frame().get_by_test_id("workflow-base-publish-button")
        try:
            btn.first.wait_for(state="visible", timeout=15000)
            return True
        except Exception:
            return False

    def has_add_node_button(self) -> bool:
        """画布工具栏「添加节点」按钮是否存在"""
        btn = self.canvas_frame().get_by_test_id("workflow.detail.toolbar.add-node")
        try:
            btn.first.wait_for(state="visible", timeout=10000)
            return True
        except Exception:
            return False

    def node_type_card_count(self) -> int:
        """左侧节点面板中的节点类型卡片数量"""
        return self.canvas_frame().locator(
            "[data-testid^='workflow.detail.node-panel.card.']"
        ).count()

    def click_canvas_node(self, index: int = 0):
        """点击画布中的第 index 个节点（触发右侧节点配置表单）"""
        nodes = self.canvas_frame().locator("[data-testid='sdk.workflow.canvas.node']")
        nodes.nth(index).wait_for(state="visible", timeout=10000)
        nodes.nth(index).click()
        self.page.wait_for_timeout(1200)

    def node_config_form(self):
        """节点配置表单（点击节点后出现），testid 形如 playground.node.{id}.node-side-sheet-form"""
        return self.canvas_frame().locator("[data-testid$='.node-side-sheet-form']")

    def title_edit_button(self):
        """画布头部的工作流标题编辑（铅笔）按钮"""
        return self.canvas_frame().get_by_test_id("workflow.detail.title.edit")

    def autosave_tag(self):
        """自动保存状态标签，形如「已自动保存 10:19:02」"""
        return self.canvas_frame().get_by_text(_RE_AUTOSAVED)

    def run_button(self):
        """画布内「试运行」按钮"""
        return self.canvas_frame().get_by_role("button", name="试运行", exact=True)

    def click_run(self):
        """点击「试运行」，打开试运行输入面板"""
        self.run_button().first.click()
        self.page.wait_for_timeout(2000)


class MemoryPage:
    """记忆页 /ctrl/agent/memories"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/memories"

    # 页面就绪标识：记忆视角导航 / 记忆标题 / "未开启"提示
    _READY_SELECTORS = "nav[aria-label='记忆视角'], :text('未开启'), :text('记忆能力'), :text('Hindsight')"

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

    def _perspective_nav(self):
        """左侧「记忆视角」导航（nav[aria-label=记忆视角]，含 5 个视角按钮）"""
        return self.page.locator("nav[aria-label='记忆视角']").first

    def get_tab_names(self) -> list[str]:
        """获取「记忆视角」分类名称列表（世界事实/经验/观察/心理模型/实体）
        新版记忆页是独立页面，视角是左侧导航按钮而非 [role=tab]，
        旧实现读全局 [role=tab] 会误中工作区 Tab（文件/站点/定时任务/发布视图）。"""
        nav = self._perspective_nav()
        if nav.count() == 0:
            return []
        names = []
        for b in nav.locator("button").all():
            strong = b.locator("strong").first
            if strong.count() > 0:
                t = strong.inner_text().strip()
                if t:
                    names.append(t)
        return names

    def click_tab(self, name: str):
        """点击某个记忆视角"""
        nav = self._perspective_nav()
        if nav.count() == 0:
            return
        tab = nav.locator("button").filter(has_text=name).first
        tab.wait_for(state="visible", timeout=5000)
        tab.click()
        self.page.wait_for_timeout(600)

    def is_tab_active(self, name: str) -> bool:
        """某个记忆视角是否处于激活状态（aria-pressed=true）"""
        nav = self._perspective_nav()
        if nav.count() == 0:
            return False
        tab = nav.locator("button").filter(has_text=name)
        if tab.count() == 0:
            return False
        return (tab.first.get_attribute("aria-pressed") or "").lower() == "true"

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
    """知识库页 /ctrl/agent/knowledge-bases

    新版为「目录式」布局：左侧 aside.knowledge-directory 展示知识库目录项
    （div.knowledge-directory-item 内 button，strong=名称，small=N 个资源），
    右侧显示选中库详情；无库级搜索框。页面就绪标识 main.agent-knowledge-page。
    """

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/knowledge-bases"

    # 页面就绪标识：知识库目录页根容器（仅该路由存在）
    _READY_SELECTOR = "main.agent-knowledge-page"

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

    def _directory_items(self):
        return self.page.locator("aside.knowledge-directory .knowledge-directory-item")

    def has_search_input(self) -> bool:
        """新版目录式布局无库级搜索框（旧版遗留 input 会返回 True）"""
        main = self.page.locator(self._READY_SELECTOR).first
        if main.count() == 0:
            return False
        return main.locator("input").count() > 0

    def get_kb_count(self) -> int:
        """知识库目录项数量"""
        return self._directory_items().count()

    def get_kb_names(self) -> list[str]:
        """目录项名称列表（strong 元素内）"""
        names = []
        items = self._directory_items()
        for i in range(items.count()):
            strong = items.nth(i).locator("strong").first
            if strong.count() > 0:
                name = strong.inner_text().strip()
                if name:
                    names.append(name)
        return names

    def get_resource_counts(self) -> list[str]:
        """目录项资源数文本列表（small 元素内，如 '2 个资源'）"""
        counts = []
        items = self._directory_items()
        for i in range(items.count()):
            small = items.nth(i).locator("small").first
            if small.count() > 0:
                counts.append(small.inner_text().strip())
        return counts

    def has_create_button(self) -> bool:
        main = self.page.locator(self._READY_SELECTOR).first
        if main.count() == 0:
            return False
        btn = main.get_by_role("button", name="新建知识库")
        return btn.count() > 0 and btn.first.is_visible() and btn.first.is_enabled()


class TasksPage:
    """定时任务页 /ctrl/agent/tasks"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/tasks"

    # 等待任务内容渲染；侧边栏的「定时任务」按钮在骨架屏阶段已经存在。
    _READY_SELECTOR = "main [role='group'][aria-label='任务类型']"

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

    def _type_filter_group(self):
        """类型筛选按钮组（新版任务页顶部工具栏），全局 [role=tab] 会误中 artifacts 工作区 tab"""
        return self.page.locator("main div[role=group][aria-label='任务类型']").first

    def get_tab_names(self) -> list[str]:
        """获取类型筛选档名称（全部/HTTP/Agent）"""
        grp = self._type_filter_group()
        grp.wait_for(state="visible", timeout=15000)
        return [b.inner_text().strip() for b in grp.locator("button").all() if b.inner_text().strip()]

    def click_tab(self, name: str):
        grp = self._type_filter_group()
        if grp.count() == 0:
            return
        btn = grp.locator("button", has_text=name).first
        if btn.count() > 0:
            btn.wait_for(state="visible", timeout=5000)
            btn.click()
            self.page.wait_for_timeout(1000)

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

    # 侧边栏菜单项 → 预期 URL 路径（新版 UI 名称）
    NAV_ITEMS = {
        "新建智能体": "/ctrl/agent/home",
        "智能体管理": "/ctrl/agent/agents",
        "智能体编排": "/ctrl/agent/workflow",
        "企业垂直大模型": "/ctrl/agent/vertical-models",
        "模型库": "/ctrl/agent/models",
        "算法库": "/ctrl/agent/algorithms",
        "技能库": "/ctrl/agent/skills",
        "知识库": "/ctrl/agent/knowledge-bases",
        "插件市场": "/ctrl/agent/mcp",
        "定时任务": "/ctrl/agent/tasks",
        "记忆": "/ctrl/agent/memories",
        "应用部署": "/ctrl/agent/sites",
        "组织": "/ctrl/agent/organizations",
        "API Key": "/ctrl/agent/apikeys",
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
