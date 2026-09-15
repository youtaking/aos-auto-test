# tests/pages/admin_page.py
"""Admin 管理面板 Page Object — 基于真实 DOM"""
import re
import time

from playwright.sync_api import Page


class AdminPage:
    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/admin"

    def goto(self):
        try:
            self.page.goto(self.url, wait_until="domcontentloaded")
        except Exception:
            pass
        self.page.wait_for_load_state("domcontentloaded")

    # ── Master Key Gate ──

    def is_master_key_gate_visible(self) -> bool:
        """是否显示 Master Key 认证门"""
        heading = self.page.locator("text=需要 Master Key")
        try:
            heading.first.wait_for(state="visible", timeout=5000)
            return True
        except Exception:
            return False

    def get_master_key_input(self):
        return self.page.get_by_role("textbox", name="系统 master key")

    def is_enter_button_disabled(self) -> bool:
        btn = self.page.get_by_role("button", name="进入面板")
        return btn.count() > 0 and btn.first.is_disabled()

    def enter_master_key(self, key: str):
        self.get_master_key_input().fill(key)

    def click_enter(self):
        self.page.get_by_role("button", name="进入面板").click()

    def authenticate(self, key: str):
        """输入 Master Key 并点击进入"""
        self.enter_master_key(key)
        self.click_enter()
        # 等待认证完成（Master Key gate 消失）
        try:
            self.page.wait_for_selector(
                "text=需要 Master Key", state="detached", timeout=8000
            )
        except Exception:
            pass

    # ── Observer 观察中心 ──

    def is_observer_loaded(self) -> bool:
        heading = self.page.locator("h1:has-text('Observer 观察中心')")
        try:
            heading.first.wait_for(state="visible", timeout=8000)
            return True
        except Exception:
            return False

    def get_content_area(self):
        """返回 Admin 当前页面的内容区定位器

        实测 2026-09-15：`/ctrl/admin` 布局层为 `main.ml-56.flex-1`（routes/admin.tsx:59），
        而 AdminObserverPage.tsx:106 会在其中再嵌一个 `<main class="mx-auto max-w-7xl ...">`。
        因此直接 `locator("main")` 在观察中心页会命中 2 个元素（strict mode 冲突）。
        统一取「最内层 main」作为页面内容区；只有布局层 main 的页面（人员管理/系统日志等）取其本身。
        """
        mains = self.page.locator("main")
        count = mains.count()
        if count == 0:
            return mains
        return mains.nth(count - 1)

    def wait_observer_stats_ready(self, timeout_ms: int = 15000) -> bool:
        """等待观察中心 4 张统计卡的标签全部渲染

        实测 2026-09-15：卡片数值由接口异步返回（`最后更新` 为本地时钟先行渲染），
        标题可见不代表卡片已就绪，直接读取会静默漏卡。
        """
        labels = ["观察总数", "活跃 machine", "一致性问题", "最后更新"]
        deadline = time.time() + timeout_ms / 1000
        while time.time() < deadline:
            if all(self.page.locator(f"p:text-is('{lb}')").count() > 0 for lb in labels):
                return True
            self.page.wait_for_timeout(200)
        return False

    def get_observer_stats(self) -> dict:
        """获取观察中心统计卡片数据（等待卡片就绪后解析 label→value）"""
        labels = ["观察总数", "活跃 machine", "一致性问题", "最后更新"]
        stats = {}
        deadline = time.time() + 15
        while True:
            stats = {}
            for label in labels:
                el = self.page.locator(f"p:text-is('{label}')")
                if el.count() > 0:
                    # 值在紧邻的下一个 p 中（AdminObserverPage 卡片结构：<p>label</p><p>value</p>）
                    parent = el.first.locator("xpath=..")
                    values = parent.locator("p")
                    if values.count() >= 2:
                        stats[label] = values.nth(1).inner_text().strip()
            if len(stats) == len(labels) or time.time() > deadline:
                return stats
            self.page.wait_for_timeout(200)

    def get_observer_checked_count(self) -> int:
        """解析「已核对: N」汇总行中的 N（用于交叉校验观察总数）"""
        el = self.page.get_by_text(re.compile(r"已核对[:：]\s*\d+"))
        if el.count() == 0:
            return -1
        m = re.search(r"(\d+)", el.first.inner_text())
        return int(m.group(1)) if m else -1

    def get_observer_tabs(self) -> list:
        """获取观察中心 Tab 列表"""
        tabs = self.page.locator("[role=tab]")
        return [tabs.nth(i).inner_text().strip() for i in range(tabs.count())]

    def has_refresh_button(self) -> bool:
        btn = self.page.get_by_role("button", name="刷新")
        return btn.count() > 0 and btn.first.is_visible()

    def has_exit_button(self) -> bool:
        btn = self.page.get_by_role("button", name="退出")
        return btn.count() > 0 and btn.first.is_visible()

    # ── 侧边栏导航 ──

    def get_nav_links(self) -> list:
        """获取侧边栏所有导航链接（nav 内 + complementary 内的链接）"""
        links = self.page.locator("[role=complementary] a, nav a")
        return [links.nth(i).inner_text().strip() for i in range(links.count())]

    def click_nav_link(self, name: str):
        self.page.locator("nav").get_by_role("link", name=name).click()
        self.page.wait_for_load_state("domcontentloaded")

    # ── 人员管理 ──

    def is_people_page_loaded(self) -> bool:
        heading = self.page.locator("h1:has-text('人员管理')")
        try:
            heading.first.wait_for(state="visible", timeout=8000)
            return True
        except Exception:
            return False

    def wait_people_tree(self, timeout_ms: int = 20000) -> str:
        """等待人员树渲染完成，返回内容区文本

        实测 2026-09-15：标题先渲染，随后页面显示「加载中…」，
        人员归属树（含「N 位用户」与邮箱）由接口异步返回，约 1s 后出现。
        未就绪即读取会得到只有表头的文本，导致误判。
        """
        area = self.get_content_area()
        deadline = time.time() + timeout_ms / 1000
        text = ""
        while time.time() < deadline:
            text = area.inner_text()
            if re.search(r"\d+\s*位用户", text):
                return text
            self.page.wait_for_timeout(200)
        return text

    def has_people_buttons(self) -> list:
        """获取人员管理页的功能按钮"""
        main = self.page.locator("main")
        if main.count() == 0:
            return []
        buttons = main.get_by_role("button")
        return [buttons.nth(i).inner_text().strip()
                for i in range(min(buttons.count(), 10))]

    # ── 系统日志 ──

    def is_logs_page_loaded(self) -> bool:
        heading = self.page.locator("h1:has-text('系统日志')")
        try:
            heading.first.wait_for(state="visible", timeout=8000)
            return True
        except Exception:
            return False

    def get_log_files(self) -> list:
        """获取日志文件列表（文件按钮为异步加载，先等待首个 .log 按钮出现）"""
        main = self.page.locator("main")
        if main.count() == 0:
            return []
        try:
            main.locator("button", has_text=".log").first.wait_for(
                state="visible", timeout=8000
            )
        except Exception:
            pass
        buttons = main.get_by_role("button")
        files = []
        for i in range(buttons.count()):
            text = buttons.nth(i).inner_text().strip()
            if text.endswith(".log") or "ERROR" in text:
                # 去掉 "ERROR" 后缀
                name = text.replace("ERROR", "").strip()
                if name:
                    files.append(name)
        return files

    def get_log_search_input(self):
        return self.page.locator("input[placeholder*='关键字']")

    def has_log_search_input(self) -> bool:
        inp = self.get_log_search_input()
        return inp.count() > 0 and inp.first.is_visible()

    # ── 沙盒管理 ──

    def is_sandbox_page_loaded(self) -> bool:
        """沙盒管理页是否加载（h1 标题可见）"""
        heading = self.page.locator("h1:has-text('沙盒管理')")
        try:
            heading.first.wait_for(state="visible", timeout=8000)
            return True
        except Exception:
            return False

    def get_sandbox_tabs(self) -> list:
        """沙盒管理页双 Tab 按钮文本（沙盒管理 / Cluster 管理）"""
        buttons = self.page.locator("main").get_by_role("button")
        tabs = []
        for i in range(buttons.count()):
            text = buttons.nth(i).inner_text().strip()
            if text in ("沙盒管理", "Cluster 管理"):
                tabs.append(text)
        return tabs

    def click_sandbox_tab(self, name: str):
        """切换到指定沙盒 Tab"""
        self.page.locator("main").get_by_role("button", name=name).click()

    def has_sandbox_create_pool_button(self) -> bool:
        btn = self.page.locator("main").get_by_role("button", name="新建资源池")
        try:
            btn.first.wait_for(state="visible", timeout=5000)
            return True
        except Exception:
            return False

    def get_sandbox_pool_cards(self):
        """资源池 `<details>` 卡片（限定在 main 内容区）"""
        return self.page.locator("main details")

    def get_sandbox_pool_summaries(self) -> list:
        """每个资源池摘要文本（含名称、provider、实例数）"""
        cards = self.get_sandbox_pool_cards()
        out = []
        for i in range(cards.count()):
            summary = cards.nth(i).locator("summary")
            if summary.count() > 0:
                out.append(summary.inner_text().strip())
        return out

    def get_sandbox_pool_card_buttons(self) -> list:
        """第一个资源池卡片的操作按钮文本"""
        cards = self.get_sandbox_pool_cards()
        if cards.count() == 0:
            return []
        summary = cards.first.locator("summary")
        buttons = summary.get_by_role("button")
        return [buttons.nth(i).inner_text().strip() for i in range(buttons.count())]

    def has_sandbox_status_dot(self) -> bool:
        """实例行状态圆点（title=状态：...，点击查看 Provider Payload）"""
        return self.page.locator("button[title*='状态']").count() > 0

    def open_sandbox_create_pool_dialog(self):
        self.page.locator("main").get_by_role("button", name="新建资源池").click()

    def open_sandbox_first_pool_detail(self):
        """打开第一个资源池的详情弹窗"""
        cards = self.get_sandbox_pool_cards()
        assert cards.count() > 0, "无资源池卡片可打开详情"
        cards.first.locator("summary").get_by_role("button", name="详情").click()

    def is_sandbox_dialog_open(self) -> bool:
        """沙盒弹窗是否已打开（Radix data-state=open）"""
        dlg = self.page.locator("[role=dialog][data-state=open]")
        try:
            dlg.first.wait_for(state="visible", timeout=5000)
            return True
        except Exception:
            return False

    def get_sandbox_dialog_title(self) -> str:
        """当前沙盒弹窗标题（h2）"""
        dlg = self.page.locator("[role=dialog][data-state=open]")
        h2 = dlg.first.locator("h2")
        return h2.inner_text().strip() if h2.count() > 0 else ""

    def get_sandbox_dialog_labels(self) -> list:
        """当前沙盒弹窗的字段 label"""
        dlg = self.page.locator("[role=dialog][data-state=open]")
        labels = dlg.first.locator("label")
        return [labels.nth(i).inner_text().strip() for i in range(labels.count())]

    def get_sandbox_dialog_readonly_count(self) -> int:
        """当前沙盒弹窗中只读/禁用的输入框数量"""
        dlg = self.page.locator("[role=dialog][data-state=open]")
        return dlg.first.locator("input[readonly], input:disabled, textarea[readonly]").count()

    def close_sandbox_dialog(self):
        """Escape 关闭弹窗并等待其关闭（安全操作，不提交）"""
        self.page.keyboard.press("Escape")
        try:
            self.page.wait_for_selector(
                "[role=dialog][data-state=open]", state="detached", timeout=5000
            )
        except Exception:
            pass

    def is_sandbox_cluster_loaded(self) -> bool:
        """Cluster 面板加载（Cluster Pool 卡片标题 或 错误重试卡片）"""
        main = self.page.locator("main")
        if main.count() == 0:
            return False
        if main.locator("div.font-semibold:has-text('Cluster Pool')").count() > 0:
            return True
        return main.get_by_role("button", name="重试").count() > 0

    def get_sandbox_cluster_status(self) -> str:
        """Cluster 面板状态：loaded / retry / unknown

        新版 DOM：Cluster Pool 为卡片标题 div.font-semibold（非 h3），
        Cluster 数据为异步加载，内部轮询最多 ~8s。
        """
        main = self.page.locator("main")
        if main.count() == 0:
            return "unknown"
        for _ in range(16):
            if main.locator(
                "div.font-semibold:has-text('Cluster Pool')"
            ).count() > 0:
                return "loaded"
            if main.get_by_role("button", name="重试").count() > 0:
                return "retry"
            self.page.wait_for_timeout(500)
        return "unknown"
