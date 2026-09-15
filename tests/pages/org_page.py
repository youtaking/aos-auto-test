# tests/pages/org_page.py
"""组织管理页面 Page Object — 新版「左侧目录 + 右侧详情」双栏布局（基于真实 DOM）。

页面结构（2026-09-08 对 100.105.9.16:38879 实测）：
- main header：h1=组织管理 + button=创建组织
- 左列 aside.org-directory[aria-label=我的组织]
    - div.org-directory-heading（「我的组织 N」）
    - div.org-directory-list：每项 button.org-directory-row
        - span.org-directory-copy > strong(显示名) + small(slug)
        - span.org-directory-role（拥有者/成员/管理员）
- 右列 header.org-detail-header
    - div.org-detail-identity：div.org-detail-mark(首字母) + h2(显示名) + div.org-detail-meta(slug + 复制ID)
    - button=编辑（点击后变为 div.org-name-editor：input + 保存 + 取消）
- 右列 body div.org-detail
    - div.org-engine-strip：默认执行节点 select
    - section.org-section(团队访问)：h3=成员 (N)，button=添加成员，div.org-list>div.org-list-row
        - 成员行 div.org-list-main：strong(姓名)+span.org-role-badge(.is-member/.is-owner) + email
        - div.org-list-actions：select(管理员/成员) + button[aria-label=确认移除成员]
    - section.org-section(运行资源)：h3=机器 (N)，buttons=刷新/新增机器
    - section.org-danger-zone：危险区域 + button=删除组织
"""
import re
import time

from playwright.sync_api import Page


class OrgPage:
    """组织管理页 /ctrl/agent/organizations"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/organizations"

    # ==================== 导航 ====================

    def goto(self, timeout: int = 15000):
        """直接导航到组织管理页，等待目录 + 详情两栏渲染完成。"""
        try:
            self.page.goto(self.url, wait_until="domcontentloaded")
        except Exception:
            pass
        try:
            self.page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass
        try:
            self.page.locator("aside.org-directory").first.wait_for(state="visible", timeout=timeout)
        except Exception:
            pass
        self.page.wait_for_timeout(600)

    def is_loaded(self) -> bool:
        """页面是否已加载（目录栏 + 标题存在）。"""
        return self.page.locator("aside.org-directory").count() > 0

    def wait_loaded(self, timeout: int = 10000):
        self.page.locator("aside.org-directory").first.wait_for(state="visible", timeout=timeout)

    # ==================== 组织目录（左列） ====================

    def directory_rows(self):
        """左列目录行 button.org-directory-row"""
        return self.page.locator("aside.org-directory button.org-directory-row")

    def _row_by_name(self, name: str):
        """按显示名精确定位目录行（行内 strong 文本 == name）。"""
        strong = self.page.locator("strong").filter(has_text=re.compile(rf"^{re.escape(name)}$"))
        return self.directory_rows().filter(has=strong)

    def get_org_names(self) -> list[str]:
        """获取组织显示名列表。"""
        names = []
        for i in range(self.directory_rows().count()):
            strong = self.directory_rows().nth(i).locator("strong").first
            txt = strong.inner_text().strip()
            if txt:
                names.append(txt)
        return names

    def get_org_count(self) -> int:
        """组织数量（目录行数）。"""
        return self.directory_rows().count()

    def has_org(self, name: str) -> bool:
        """目录中是否存在指定显示名组织。"""
        try:
            for i in range(self.directory_rows().count()):
                strong = self.directory_rows().nth(i).locator("strong").first
                if strong.inner_text().strip() == name:
                    return True
        except Exception:
            return False
        return False

    def click_org(self, name: str):
        """点击左列某组织，等待右列详情切换到该组织。"""
        row = self._row_by_name(name)
        if row.count() == 0:
            row = self.directory_rows().filter(has_text=name)
        row.first.wait_for(state="visible", timeout=8000)
        row.first.click()
        self._wait_org_active(name)

    def _wait_org_active(self, name: str, timeout: float = 8000):
        """等待右侧详情 identity 标题变为 name。"""
        deadline = time.time() + timeout / 1000
        while time.time() < deadline:
            try:
                h2 = self.page.locator("header.org-detail-header div.org-detail-identity h2").first
                if h2.is_visible() and h2.inner_text().strip() == name:
                    return
            except Exception:
                pass
            self.page.wait_for_timeout(200)
        self.page.wait_for_timeout(500)

    def active_org_name(self) -> str:
        """当前选中组织的显示名。"""
        try:
            h2 = self.page.locator("header.org-detail-header div.org-detail-identity h2").first
            if h2.is_visible():
                return h2.inner_text().strip()
        except Exception:
            pass
        return ""

    # ==================== 右列详情文本 ====================

    def get_detail_text(self) -> str:
        """右列详情整体文本（identity 头部 + org-detail body）。"""
        parts = []
        hdr = self.page.locator("header.org-detail-header")
        if hdr.count():
            parts.append(hdr.first.inner_text())
        body = self.page.locator("div.org-detail")
        if body.count():
            parts.append(body.first.inner_text())
        return "\n".join(parts)

    def detail_body(self):
        """右列 body div.org-detail"""
        return self.page.locator("div.org-detail")

    # ==================== 创建组织 ====================

    def create_org_button(self):
        """页面顶栏「创建组织」按钮（限定 main header）。"""
        return self.page.locator("main header button, main button").filter(has_text="创建组织").first

    def has_create_button(self) -> bool:
        return self.page.locator("button").filter(has_text="创建组织").count() > 0

    def click_create_org(self):
        btn = self.page.locator("button").filter(has_text="创建组织").first
        btn.wait_for(state="visible", timeout=8000)
        btn.click()
        self._wait_dialog()

    # ==================== 弹窗通用 ====================

    def is_dialog_open(self) -> bool:
        d = self.page.locator("[role=dialog]")
        return d.count() > 0 and d.first.is_visible()

    def dialog(self):
        return self.page.locator("[role=dialog]").first

    def get_dialog_title(self) -> str:
        d = self.page.locator("[role=dialog]")
        h = d.locator("h2")
        if h.count() > 0:
            return h.first.text_content().strip()
        return ""

    def _wait_dialog(self, timeout: float = 5000):
        deadline = time.time() + timeout / 1000
        while time.time() < deadline:
            if self.is_dialog_open():
                return
            self.page.wait_for_timeout(150)
        raise AssertionError("弹窗未打开")

    def cancel_dialog(self):
        d = self.page.locator("[role=dialog]")
        btn = d.get_by_role("button", name="取消")
        if btn.count() > 0:
            btn.first.click()
        else:
            self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(600)

    def close_dialog(self):
        d = self.page.locator("[role=dialog]")
        close_btn = d.locator("button").filter(has_text="Close")
        if close_btn.count() > 0:
            close_btn.first.click()
        else:
            self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(600)

    # ==================== 创建组织弹窗字段 ====================

    def create_name_input(self):
        return self.page.locator("[role=dialog] input[placeholder='组织名称']").first

    def create_slug_input(self):
        return self.page.locator("[role=dialog] input[placeholder='url-identifier']").first

    def fill_create_name(self, value: str):
        inp = self.create_name_input()
        inp.wait_for(state="visible", timeout=5000)
        inp.fill(value)

    def fill_create_slug(self, value: str):
        inp = self.create_slug_input()
        inp.wait_for(state="visible", timeout=5000)
        inp.fill(value)

    def create_submit_enabled(self) -> bool:
        btn = self.page.locator("[role=dialog] button").filter(has_text="创建").first
        try:
            return not btn.is_disabled()
        except Exception:
            return False

    def click_create_submit(self):
        btn = self.page.locator("[role=dialog] button").filter(has_text="创建").first
        btn.wait_for(state="visible", timeout=5000)
        try:
            btn.click()
        except Exception:
            btn.click(force=True)
        self.page.wait_for_timeout(1200)

    # ==================== 编辑组织（header 内联编辑） ====================

    def has_edit_button(self) -> bool:
        return self.page.locator("header.org-detail-header button").filter(has_text="编辑").count() > 0

    def click_edit(self):
        btn = self.page.locator("header.org-detail-header button").filter(has_text="编辑").first
        btn.wait_for(state="visible", timeout=8000)
        btn.click()
        self.page.wait_for_timeout(800)

    def is_editing(self) -> bool:
        return self.page.locator("header.org-detail-header div.org-name-editor").count() > 0

    def edit_name_input(self):
        return self.page.locator("header.org-detail-header div.org-name-editor input").first

    def save_edit(self):
        btn = self.page.locator("header.org-detail-header div.org-name-editor button").filter(has_text="保存").first
        btn.wait_for(state="visible", timeout=5000)
        btn.click()
        self.page.wait_for_timeout(1200)

    def cancel_edit(self):
        btn = self.page.locator("header.org-detail-header div.org-name-editor button").filter(has_text="取消").first
        if btn.count() > 0:
            btn.click()
            self.page.wait_for_timeout(800)

    # ==================== 成员区（右列详情） ====================

    def _member_section(self):
        """包含 h3「成员 (N)」的 org-section。"""
        return self.page.locator(
            "div.org-detail section.org-section"
        ).filter(has_text=re.compile(r"成员\s*\(")).first

    def member_rows(self):
        """成员区所有 org-list-row。"""
        sec = self._member_section()
        return sec.locator("div.org-list-row")

    def get_member_count(self) -> int:
        """成员数量（从 h3「成员 (N)」解析）。"""
        try:
            h3 = self._member_section().locator("h3").filter(has_text=re.compile(r"成员\s*\(")).first
            m = re.search(r"(\d+)", h3.inner_text())
            if m:
                return int(m.group(1))
        except Exception:
            pass
        return 0

    def has_member(self, name: str) -> bool:
        try:
            for i in range(self.member_rows().count()):
                strong = self.member_rows().nth(i).locator("div.org-list-main strong").first
                if strong.inner_text().strip() == name:
                    return True
        except Exception:
            return False
        return False

    def member_row(self, name: str):
        """按姓名定位成员行（div.org-list-main strong == name）。"""
        return self.member_rows().filter(has_text=name)

    def has_add_member_button(self) -> bool:
        sec = self._member_section()
        return sec.get_by_role("button", name="添加成员").count() > 0

    def click_add_member(self):
        sec = self._member_section()
        btn = sec.get_by_role("button", name="添加成员").first
        btn.wait_for(state="visible", timeout=8000)
        btn.click()
        self._wait_dialog()

    # ==================== 添加成员弹窗 ====================

    def add_member_search_input(self):
        d = self.page.locator("[role=dialog]")
        inp = d.locator("input[placeholder*='搜索']").first
        inp.wait_for(state="visible", timeout=5000)
        return inp

    def add_candidates(self):
        """真实 DOM：候选为包含 strong 姓名的 button，不是 select option。"""
        return self.page.get_by_role("dialog").get_by_role("button").filter(
            has=self.page.locator("strong")
        )

    def search_add_candidate(self, keyword: str, enter: bool = True, wait: float = 5000):
        """搜索后等待候选；enter 参数保留兼容，使用点击完成选择。"""
        inp = self.add_member_search_input()
        inp.fill(keyword)
        candidates = self.add_candidates().filter(has_text=re.compile(re.escape(keyword), re.I))
        candidates.first.wait_for(state="visible", timeout=wait)
        if enter:
            candidates.first.click()

    def select_add_role(self, role: str = "成员"):
        sel = self.page.locator("[role=dialog] select").first
        sel.wait_for(state="visible", timeout=5000)
        try:
            sel.select_option(label=role)
        except Exception:
            sel.select_option(value=role)
        self.page.wait_for_timeout(300)

    def add_submit_enabled(self) -> bool:
        btn = self.page.locator("[role=dialog] button").filter(has_text="添加").first
        try:
            return not btn.is_disabled()
        except Exception:
            return False

    def click_add_submit(self):
        btn = self.page.locator("[role=dialog] button").filter(has_text="添加").first
        btn.wait_for(state="visible", timeout=5000)
        btn.click()
        self.page.wait_for_timeout(1200)

    def add_member(self, keyword: str, role: str = "成员"):
        """完整添加成员：搜索→Enter→选角色→点添加。返回是否成功执行。"""
        self.search_add_candidate(keyword, enter=True)
        # 确保已选中（Enter 后添加按钮应可用）
        if not self.add_submit_enabled():
            self.page.wait_for_timeout(800)
        self.select_add_role(role)
        if not self.add_submit_enabled():
            return False
        self.click_add_submit()
        return True

    # ==================== 移除成员 ====================

    def click_remove_member(self, name: str):
        """点击成员行的「确认移除成员」按钮（打开确认弹窗）。"""
        row = self.member_row(name).first
        row.wait_for(state="visible", timeout=8000)
        rm_btn = row.locator("button[aria-label='确认移除成员']").first
        rm_btn.wait_for(state="visible", timeout=5000)
        rm_btn.click()
        self.page.wait_for_timeout(900)

    def is_alert_dialog_open(self) -> bool:
        d = self.page.locator("[role=alertdialog]")
        return d.count() > 0 and d.first.is_visible()

    def get_alert_dialog_text(self) -> str:
        d = self.page.locator("[role=alertdialog]")
        if d.count() > 0:
            return d.first.inner_text().strip()
        return ""

    def click_alert_button(self, name: str):
        btn = self.page.locator("[role=alertdialog] button").filter(has_text=name).first
        btn.wait_for(state="visible", timeout=5000)
        btn.click()
        self.page.wait_for_timeout(1200)

    def cancel_alert(self):
        btn = self.page.locator("[role=alertdialog] button").filter(has_text="取消").first
        if btn.count() > 0:
            btn.click()
        else:
            self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(600)

    # ==================== 危险区域 / 删除组织 ====================

    def danger_zone(self):
        return self.page.locator("div.org-detail section.org-danger-zone").first

    def has_danger_zone(self) -> bool:
        return self.page.locator("section.org-danger-zone").count() > 0

    def get_danger_text(self) -> str:
        try:
            return self.danger_zone().inner_text().strip()
        except Exception:
            return ""

    def has_delete_org_button(self) -> bool:
        return self.page.locator("section.org-danger-zone button").filter(has_text="删除组织").count() > 0

    def click_delete_org(self):
        btn = self.page.locator("section.org-danger-zone button").filter(has_text="删除组织").first
        btn.wait_for(state="visible", timeout=8000)
        btn.click()
        self.page.wait_for_timeout(1000)

    def confirm_delete_org(self):
        """在删除组织确认弹窗中点击「确认删除」。调用前应先读弹窗文本确认对象。"""
        self.click_alert_button("确认删除")

    # ==================== 默认执行节点 / 机器区 ====================

    def engine_strip(self):
        return self.page.locator("div.org-detail div.org-engine-strip").first

    def default_node_select(self):
        return self.page.locator("div.org-engine-strip select").first

    def has_engine_strip(self) -> bool:
        return self.page.locator("div.org-engine-strip").count() > 0

    def machine_section(self):
        return self.page.locator(
            "div.org-detail section.org-section"
        ).filter(has_text=re.compile(r"机器\s*\(")).first

    def has_machine_region(self) -> bool:
        return self.page.locator("div.org-detail h3").filter(has_text=re.compile(r"机器\s*\(")).count() > 0

    def get_machine_section_title(self) -> str:
        """机器区域标题原文（如「机器 (1)」）"""
        h3 = self.page.locator("div.org-detail h3").filter(has_text=re.compile(r"机器\s*\(")).first
        try:
            h3.wait_for(state="visible", timeout=5000)
            return h3.inner_text().strip()
        except Exception:
            return ""

    def get_machine_rows_count(self) -> int:
        """机器区域内实际渲染的机器行数（.org-list-row，限定在机器 section 内）"""
        return self.machine_section().locator(".org-list-row").count()

    def get_machine_count(self) -> int:
        try:
            h3 = self.page.locator("div.org-detail h3").filter(has_text=re.compile(r"机器\s*\(")).first
            m = re.search(r"(\d+)", h3.inner_text())
            if m:
                return int(m.group(1))
        except Exception:
            pass
        return 0

    def has_machine_buttons(self) -> bool:
        sec = self.machine_section()
        btns = sec.locator("button").filter(has_text="新增机器").or_(
            sec.locator("button").filter(has_text="刷新")
        )
        return btns.count() > 0

    # ==================== Toast ====================

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

    # ==================== API 拦截 ====================

    def intercept_api(self, url_pattern: str):
        """设置 API 响应拦截，返回收集列表（列表实时追加）。"""
        if getattr(self, '_last_listener', None):
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
                        "url": resp.url, "status": resp.status,
                        "method": resp.request.method, "body": body,
                    })
                except Exception:
                    pass

        self._last_listener = on_response
        self.page.on("response", on_response)
        return collected
