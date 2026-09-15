# tests/pages/apikey_page.py
"""API 密钥管理页面 Page Object — 基于真实 DOM 结构编写"""
from playwright.sync_api import Page


class ApiKeyPage:
    """API 密钥管理页 /ctrl/agent/apikeys"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/apikeys"

    # ==================== 导航 ====================

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
                nav_btn.first.wait_for(state="visible", timeout=5000)
                nav_btn.first.click()
                try:
                    self.page.locator(self._READY_SELECTOR).first.wait_for(state="attached", timeout=15000)
                except Exception:
                    pass

    def goto_via_sidebar(self):
        btn = self.page.locator("button.agent-sidebar-nav-item").filter(has_text="API Key")
        btn.first.wait_for(state="visible", timeout=5000)
        btn.first.click()
        try:
            self.page.locator(self._READY_SELECTOR).first.wait_for(state="attached", timeout=15000)
        except Exception:
            pass
        self.page.wait_for_load_state("domcontentloaded")

    def is_loaded(self) -> bool:
        return "/ctrl/agent/apikeys" in self.page.url and self.page.locator(self._READY_SELECTOR).count() > 0

    def _body(self):
        """获取 API Key 主内容区"""
        return self.page.locator("div.agent-panel-body")

    def search(self, keyword: str):
        body = self._body()
        inp = body.locator("input[placeholder*='搜索密钥']")
        if inp.count() > 0:
            inp.first.wait_for(state="visible", timeout=5000)
            inp.first.fill(keyword)
            self.page.wait_for_timeout(500)

    def clear_search(self):
        body = self._body()
        inp = body.locator("input[placeholder*='搜索密钥']")
        if inp.count() > 0:
            inp.first.wait_for(state="visible", timeout=5000)
            inp.first.fill("")
            self.page.wait_for_timeout(500)

    def has_search_input(self) -> bool:
        body = self._body()
        return body.locator("input[placeholder*='搜索密钥']").count() > 0

    # ==================== 密钥列表 ====================

    def get_key_count(self) -> int:
        """密钥数量（通过吊销按钮数量）"""
        body = self._body()
        return body.get_by_role("button", name="吊销").count()

    def get_key_items(self):
        """获取密钥行元素（真实 DOM：table > tbody > tr，每行一个密钥）"""
        body = self._body()
        return body.locator("tr").filter(has=body.get_by_role("button", name="吊销"))

    def find_key_row(self, name: str):
        """返回名称匹配 name 的唯一密钥行 locator；未找到返回 None。

        只定位到 <tr> 这一层：Playwright 的 has_text 会同时命中外层容器 div，
        若在外层容器里取"第一个"按钮，就会点到第一行（即他人/共享密钥）的吊销按钮。
        匹配到多行时直接失败——宁可报错也不赌哪一行才是目标。
        """
        if not name:
            return None
        rows = self._body().locator("tr").filter(has_text=name)
        assert rows.count() <= 1, (
            f"匹配名称 {name!r} 的密钥行应唯一，实际 {rows.count()} 行——"
            f"匹配不唯一时拒绝操作，避免误伤其他密钥"
        )
        if rows.count() == 0:
            return None
        rows.first.wait_for(state="visible", timeout=5000)
        return rows.first

    def has_key(self, name: str) -> bool:
        body = self._body()
        return name in body.inner_text()

    def get_key_prefixes(self) -> list[str]:
        """获取所有密钥前缀（如 rcs_...）"""
        body = self._body()
        text = body.inner_text()
        import re
        return re.findall(r"[a-z]{3,5}_\.{3}", text)

    def get_body_text(self) -> str:
        body = self._body()
        return body.inner_text()

    # ==================== 创建密钥 ====================

    def click_create_key(self):
        body = self._body()
        body.get_by_role("button", name="创建密钥").wait_for(state="visible", timeout=5000)
        body.get_by_role("button", name="创建密钥").click()
        self.page.wait_for_timeout(1000)

    def has_create_button(self) -> bool:
        body = self._body()
        return body.get_by_role("button", name="创建密钥").count() > 0

    # ==================== 弹窗操作 ====================

    def is_dialog_open(self) -> bool:
        dialog = self.page.locator("[role=dialog]")
        return dialog.count() > 0 and dialog.first.is_visible()

    def get_dialog_title(self) -> str:
        dialog = self.page.locator("[role=dialog]")
        h2 = dialog.locator("h2")
        if h2.count() > 0:
            return h2.first.text_content().strip()
        return ""

    def get_dialog_text(self) -> str:
        dialog = self.page.locator("[role=dialog]")
        if dialog.count() > 0:
            return dialog.first.inner_text().strip()
        return ""

    def fill_key_name(self, name: str):
        dialog = self.page.locator("[role=dialog]")
        inp = dialog.locator("input[data-slot='input']").or_(dialog.locator("input[type=text]"))
        if inp.count() > 0:
            inp.first.wait_for(state="visible", timeout=5000)
            inp.first.fill(name)

    def submit_dialog(self):
        dialog = self.page.locator("[role=dialog]")
        submit_btn = dialog.get_by_role("button", name="创建").or_(
            dialog.get_by_role("button", name="保存")
        )
        submit_btn.first.wait_for(state="visible", timeout=5000)
        submit_btn.first.click()
        self.page.wait_for_timeout(1000)

    def cancel_dialog(self):
        dialog = self.page.locator("[role=dialog]")
        dialog.get_by_role("button", name="取消").wait_for(state="visible", timeout=5000)
        dialog.get_by_role("button", name="取消").click()
        self.page.wait_for_timeout(500)

    def close_dialog(self):
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(500)

    def get_form_validation_text(self) -> str:
        dialog = self.page.locator("[role=dialog]")
        errors = dialog.locator("[data-slot='form-message'], [role='alert']")
        if errors.count() == 0:
            errors = dialog.locator("p.text-red-500, p.text-destructive")
        if errors.count() > 0:
            return errors.first.text_content().strip()
        return ""

    # ==================== 密钥展示（创建后） ====================

    def get_shown_key(self) -> str:
        """获取弹窗中展示的完整密钥"""
        dialog = self.page.locator("[role=dialog]")
        if dialog.count() == 0:
            return ""
        text = dialog.first.inner_text()
        # 密钥通常以 rcs_ 开头
        import re
        match = re.search(r"rcs_[a-zA-Z0-9]+", text)
        return match.group(0) if match else ""

    def has_copy_button(self) -> bool:
        dialog = self.page.locator("[role=dialog]")
        if dialog.count() == 0:
            return False
        # 复制按钮
        return (
            dialog.get_by_role("button", name="复制").count() > 0
            or dialog.locator("button[aria-label*='copy' i], button[aria-label*='复制']").count() > 0
        )

    def click_copy(self):
        dialog = self.page.locator("[role=dialog]")
        copy_btn = dialog.get_by_role("button", name="复制").or_(
            dialog.locator("button[aria-label*='copy' i], button[aria-label*='复制']")
        )
        copy_btn.first.wait_for(state="visible", timeout=5000)
        copy_btn.first.click()
        self.page.wait_for_timeout(500)

    def has_security_warning(self) -> bool:
        """创建流程中是否有安全警告"""
        dialog = self.page.locator("[role=dialog]")
        if dialog.count() == 0:
            return False
        text = dialog.first.inner_text()
        return any(kw in text for kw in [
            "仅显示一次", "仅一次", "妥善保管", "妥善保存", "不要", "安全",
            "警告", "注意", "重要", "无法再次查看", "无法再次",
        ])

    # ==================== 吊销/删除 ====================

    # 共享凭据保护名单：这些密钥供 CI / OpenAPI 用例 / 其他模块使用，任何用例都不得吊销
    PROTECTED_KEY_NAMES = ("openapi-key",)

    def click_revoke(self, name: str):
        """点击指定密钥行的『吊销』按钮。

        安全约束（本页操作的是共享账号，误删会直接打断流水线）：
        1. 必须显式传入 name —— 不再支持"点击第一个吊销按钮"这种无差别吊销；
        2. 只在该名称对应的 <tr> 行内点击，绝不跨行；
        3. 命中 PROTECTED_KEY_NAMES 时不点击，直接失败。
        """
        if not name:
            raise ValueError(
                "click_revoke(name) 必须指定密钥名称：禁止对共享环境做无差别吊销"
            )
        row = self.find_key_row(name)
        if row is None:
            return False
        # 精确名称匹配：行内必须存在"整格文本 == name"的单元格。
        # 仅用 has_text 子串匹配时，name="abc" 会同时命中名为 "abc-2" 的密钥。
        cells = [
            (row.locator("td").nth(i).inner_text() or "").strip()
            for i in range(row.locator("td").count())
        ]
        if name not in cells:
            raise AssertionError(
                f"目标行的名称单元格中没有与 {name!r} 精确相等的值，实际单元格={cells!r}"
                f"——拒绝吊销，避免子串误匹配到其他密钥"
            )
        row_text = (row.inner_text() or "").strip()
        for protected in self.PROTECTED_KEY_NAMES:
            if protected in row_text:
                raise AssertionError(
                    f"拒绝吊销受保护密钥 {protected!r}（共享凭据，删除会导致 OpenAPI 用例全部失效）"
                )
        revoke_btn = row.get_by_role("button", name="吊销")
        if revoke_btn.count() == 0:
            return False
        revoke_btn.first.wait_for(state="visible", timeout=5000)
        revoke_btn.first.click()
        self.page.wait_for_timeout(500)
        return True

    # ==================== 确认弹窗 ====================

    def is_alert_dialog_open(self) -> bool:
        dialog = self.page.locator("[role=alertdialog]")
        return dialog.count() > 0 and dialog.first.is_visible()

    def get_alert_dialog_text(self) -> str:
        dialog = self.page.locator("[role=alertdialog]")
        if dialog.count() > 0:
            return dialog.first.inner_text().strip()
        return ""

    def confirm_alert(self):
        dialog = self.page.locator("[role=alertdialog]")
        confirm_btn = dialog.get_by_role("button", name="确认").or_(
            dialog.get_by_role("button", name="吊销")
        )
        confirm_btn.first.wait_for(state="visible", timeout=5000)
        confirm_btn.first.click()
        self.page.wait_for_timeout(1000)

    def cancel_alert(self):
        dialog = self.page.locator("[role=alertdialog]")
        dialog.get_by_role("button", name="取消").wait_for(state="visible", timeout=5000)
        dialog.get_by_role("button", name="取消").click()
        self.page.wait_for_timeout(500)

    # ==================== 加载状态 ====================

    def has_skeleton_or_spinner(self) -> bool:
        body = self._body()
        loading = body.locator(
            "[role='progressbar'], [data-slot='skeleton'], "
            "div.animate-pulse, [data-slot='spinner']"
        )
        return loading.count() > 0

    # ==================== API 拦截 ====================

    def intercept_api(self, url_pattern: str):
        # 移除之前的监听器，避免累积

        if hasattr(self, '_last_listener') and self._last_listener:

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
