# tests/pages/org_page.py
"""组织管理页面 Page Object — 新版「主从双栏 workspace」UI（基于真实 DOM 实测）。

页面结构（2026-10-14 对 staging commit 1b80cdfa 实测）：
- 根容器 section.org-workspace（= agent-master-detail-workspace）
- 左列 aside.org-directory[aria-label=我的组织]
    - div.org-directory-list：每项 button.org-directory-row
        - span(图标) + span(副本) > strong(显示名) + small(slug) + span(角色，如「拥有者」)
- 右列 header（section.org-workspace header，唯一）
    - div(标记) + h2(显示名) + div(slug + button[aria-label=复制 ID])
    - button=编辑（点击后 header 内出现 input + button=保存/取消）
- 右列主体 div.org-detail
    - div.org-engine-strip：默认执行节点 select（仅拥有者）
    - section(团队访问)：h3=成员 (N)，button=添加成员，行 div[role=listitem]
        - 行内 strong(姓名) + span(角色) + span(email)
        - 行操作 select(管理员/成员) + button[aria-label=确认移除成员]
    - section(运行资源)：h3=机器 (N)，button=刷新 / 新增机器，行 div[role=listitem]
    - section(危险区域)：strong=危险区域 + button=删除组织（仅拥有者）
- 弹窗均为 [role=dialog]（创建组织/添加成员）；确认弹窗 [role=alertdialog]
"""
import re
import time

from playwright.sync_api import Page

# 主从 workspace 根容器（新版 UI）
_WS = "section.org-workspace"


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
        """页面是否已加载（目录栏存在）。"""
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
        rows = self.directory_rows()
        for i in range(rows.count()):
            strong = rows.nth(i).locator("strong").first
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
            rows = self.directory_rows()
            for i in range(rows.count()):
                strong = rows.nth(i).locator("strong").first
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
        """等待右侧详情 header 标题 h2 变为 name。"""
        deadline = time.time() + timeout / 1000
        while time.time() < deadline:
            try:
                h2 = self.page.locator(f"{_WS} header h2").first
                if h2.is_visible() and h2.inner_text().strip() == name:
                    return
            except Exception:
                pass
            self.page.wait_for_timeout(200)
        self.page.wait_for_timeout(500)

    def active_org_name(self) -> str:
        """当前选中组织的显示名（详情 header h2）。"""
        try:
            h2 = self.page.locator(f"{_WS} header h2").first
            if h2.is_visible():
                return h2.inner_text().strip()
        except Exception:
            pass
        return ""

    # ==================== 右列详情文本 ====================

    def get_detail_text(self) -> str:
        """右列详情整体文本（详情 header 含组织名 + org-detail body）。

        注意：workspace 内有 2 个 header —— 左列目录 header（class 含
        `agent-catalog-index-header`，文本「我的组织 / N」，无 h2）与右列详情 header
        （含 h2 组织名 + 编辑按钮；编辑态下 h2 被 input 替换）。用
        `header:not(.agent-catalog-index-header)` 精确取详情 header，两种模式下均有效。
        """
        parts = []
        hdr = self.page.locator(f"{_WS} header:not(.agent-catalog-index-header)")
        if hdr.count():
            parts.append(hdr.first.inner_text())
        body = self.page.locator(f"{_WS} .org-detail")
        if body.count():
            parts.append(body.first.inner_text())
        return "\n".join(parts)

    def detail_body(self):
        """右列 body .org-detail"""
        return self.page.locator(f"{_WS} .org-detail")

    def _detail_header(self):
        """右列详情 header（workspace 内非目录 header 的那个 header；编辑态仍在）"""
        return self.page.locator(f"{_WS} header:not(.agent-catalog-index-header)").first

    # ==================== 创建组织 ====================

    def create_org_button(self):
        """页面顶栏「创建组织」按钮。"""
        return self.page.get_by_role("button", name="创建组织").first

    def has_create_button(self) -> bool:
        return self.page.get_by_role("button", name="创建组织").count() > 0

    def click_create_org(self):
        btn = self.page.get_by_role("button", name="创建组织").first
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
        btn = d.get_by_role("button", name="取消")
        if btn.count() > 0:
            btn.first.click()
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
        btn = self.page.locator("[role=dialog]").get_by_role("button", name="创建", exact=True).first
        try:
            return not btn.is_disabled()
        except Exception:
            return False

    def click_create_submit(self):
        btn = self.page.locator("[role=dialog]").get_by_role("button", name="创建", exact=True).first
        btn.wait_for(state="visible", timeout=5000)
        try:
            btn.click()
        except Exception:
            btn.click(force=True)
        self.page.wait_for_timeout(1200)

    # ==================== 编辑组织（header 内联编辑） ====================

    def has_edit_button(self) -> bool:
        return self._detail_header().get_by_role("button", name="编辑").count() > 0

    def click_edit(self):
        btn = self._detail_header().get_by_role("button", name="编辑").first
        btn.wait_for(state="visible", timeout=8000)
        btn.click()
        self.page.wait_for_timeout(800)

    def is_editing(self) -> bool:
        return self._detail_header().locator("input").count() > 0

    def edit_name_input(self):
        return self._detail_header().locator("input").first

    def save_edit(self):
        btn = self._detail_header().get_by_role("button", name="保存").first
        btn.wait_for(state="visible", timeout=5000)
        btn.click()
        self.page.wait_for_timeout(1200)

    def cancel_edit(self):
        btn = self._detail_header().get_by_role("button", name="取消")
        if btn.count() > 0:
            btn.first.click()
            self.page.wait_for_timeout(800)

    # ==================== 成员区（右列详情） ====================

    def _member_section(self):
        """包含 h3「成员 (N)」的 section（限定在 workspace 内层 section）。"""
        return self.page.locator(f"{_WS} section").filter(
            has_text=re.compile(r"成员\s*\(")
        ).first

    def member_rows(self):
        """成员区所有行 div[role=listitem]。"""
        return self._member_section().locator("[role=listitem]")

    def get_member_count(self) -> int:
        """成员数量（从 h3「成员 (N)」解析）。"""
        try:
            h3 = self._member_section().locator("h3").filter(
                has_text=re.compile(r"成员\s*\(")).first
            m = re.search(r"(\d+)", h3.inner_text())
            if m:
                return int(m.group(1))
        except Exception:
            pass
        return 0

    def _row_name(self, row) -> str:
        try:
            return row.locator("strong").first.inner_text().strip()
        except Exception:
            return ""

    def has_member(self, name: str) -> bool:
        try:
            rows = self.member_rows()
            for i in range(rows.count()):
                if self._row_name(rows.nth(i)) == name:
                    return True
        except Exception:
            return False
        return False

    def member_row(self, name: str):
        """按姓名定位成员行（行内 strong == name）。"""
        rows = self.member_rows()
        out = rows.filter(has=self.page.locator("strong").filter(
            has_text=re.compile(rf"^{re.escape(name)}$")))
        return out if out.count() > 0 else rows.filter(has_text=name)

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
        inp = d.locator("input#org-member-search")
        if inp.count() == 0:
            inp = d.locator("input[placeholder*='搜索']")
        inp = inp.first
        inp.wait_for(state="visible", timeout=5000)
        return inp

    def add_candidates(self):
        """候选用户：弹窗内含 <strong> 的用户按钮（排除已选/已在组织内的禁用项）。"""
        return self.page.locator(
            "[role=dialog] button:has(strong):not([disabled])"
        )

    def search_add_candidate(self, keyword: str, enter: bool = True, wait: float = 5000):
        """搜索并点击首个匹配候选（enter 参数保留兼容，实际用点击完成选择）。"""
        inp = self.add_member_search_input()
        inp.fill(keyword)
        candidates = self.add_candidates().filter(
            has_text=re.compile(re.escape(keyword), re.I))
        candidates.first.wait_for(state="visible", timeout=wait)
        if enter:
            candidates.first.click()
            self.page.wait_for_timeout(600)

    def select_add_role(self, role: str = "成员"):
        sel = self.page.locator("[role=dialog] select").first
        sel.wait_for(state="visible", timeout=5000)
        try:
            sel.select_option(label=role)
        except Exception:
            sel.select_option(value=role)
        self.page.wait_for_timeout(300)

    def add_submit_enabled(self) -> bool:
        btn = self.page.locator("[role=dialog]").get_by_role("button", name="添加", exact=True).first
        try:
            return not btn.is_disabled()
        except Exception:
            return False

    def click_add_submit(self):
        btn = self.page.locator("[role=dialog]").get_by_role("button", name="添加", exact=True).first
        btn.wait_for(state="visible", timeout=5000)
        btn.click()
        self.page.wait_for_timeout(1200)

    def add_member(self, keyword: str, role: str = "成员"):
        """完整添加成员：搜索→点击候选→选角色→点添加。返回是否成功执行。"""
        self.search_add_candidate(keyword, enter=True)
        # 确保已选中（点击候选后添加按钮应可用）
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
        btn = self.page.locator("[role=alertdialog]").get_by_role("button", name=name, exact=True).first
        btn.wait_for(state="visible", timeout=5000)
        btn.click()
        self.page.wait_for_timeout(1200)

    def cancel_alert(self):
        btn = self.page.locator("[role=alertdialog]").get_by_role("button", name="取消")
        if btn.count() > 0:
            btn.first.click()
        else:
            self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(600)

    # ==================== 危险区域 / 删除组织 ====================

    def danger_zone(self):
        """含「危险区域」文本的 section（取最近的 section 祖先）。"""
        return self.page.get_by_text("危险区域", exact=True).locator("xpath=ancestor::section[1]")

    def has_danger_zone(self) -> bool:
        return self.danger_zone().count() > 0

    def get_danger_text(self) -> str:
        try:
            return self.danger_zone().first.inner_text().strip()
        except Exception:
            return ""

    def has_delete_org_button(self) -> bool:
        return self.danger_zone().get_by_role("button", name="删除组织").count() > 0

    def click_delete_org(self):
        btn = self.danger_zone().get_by_role("button", name="删除组织").first
        btn.wait_for(state="visible", timeout=8000)
        btn.click()
        self.page.wait_for_timeout(1000)

    def confirm_delete_org(self):
        """在删除组织确认弹窗中点击「确认删除」。调用前应先读弹窗文本确认对象。"""
        self.click_alert_button("确认删除")

    # ==================== 默认执行节点 / 机器区 ====================

    def engine_strip(self):
        return self.page.locator(f"{_WS} .org-engine-strip").first

    def default_node_select(self):
        return self.page.locator(f"{_WS} .org-engine-strip select").first

    def has_engine_strip(self) -> bool:
        return self.page.locator(f"{_WS} .org-engine-strip").count() > 0

    def machine_section(self):
        return self.page.locator(f"{_WS} section").filter(
            has_text=re.compile(r"机器\s*\(")).first

    def has_machine_region(self) -> bool:
        return self.page.locator(f"{_WS} h3").filter(
            has_text=re.compile(r"机器\s*\(")).count() > 0

    def get_machine_section_title(self) -> str:
        """机器区域标题原文（如「机器 (1)」）"""
        h3 = self.page.locator(f"{_WS} h3").filter(
            has_text=re.compile(r"机器\s*\(")).first
        try:
            h3.wait_for(state="visible", timeout=5000)
            return h3.inner_text().strip()
        except Exception:
            return ""

    def get_machine_rows_count(self) -> int:
        """机器区域内实际渲染的机器行数（[role=listitem]，限定在机器 section 内）"""
        return self.machine_section().locator("[role=listitem]").count()

    def get_machine_count(self) -> int:
        try:
            h3 = self.page.locator(f"{_WS} h3").filter(
                has_text=re.compile(r"机器\s*\(")).first
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
