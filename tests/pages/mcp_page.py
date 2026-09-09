# tests/pages/mcp_page.py
"""MCP 插件市场页 Page Object — 基于 2026-09 新版两栏「MCP 插件市场」真实 DOM 编写

新版页面结构（已用 playwright MCP 在参照环境 100.105.9.16:38879 实测）：
- 顶栏：h1「MCP 插件市场」 + 按钮「添加插件」
- 筛选区：搜索框(ph=搜索插件、连接方式或用途) + 分段按钮 全部N/本组织N/公开N
- 左栏 catalog：navigation aria-label=插件目录，每项 = button，内含 strong{服务器名} + 副行(url/描述) + 徽标
- 右栏详情（选中某项后）：
  - header：h2{名} + 徽标 + 右侧按钮（owner=编辑 / 非owner=查看）
  - article dl：类型/状态/Tools(N 个工具)/详情
  - Tools 卡片：会话内点「检测」后原地渲染已发现工具列表；未发现则提示「暂无已发现的工具…」
  - 页脚操作条（owner 私有）：[检测][启用|禁用][设为公开|设为私有][删除]
    - owner 公开后：仍保留全部管理按钮，仅「设为公开」变「设为私有」
    - 非 owner（同组织他成员/公开分享）：页脚仅 [检测]，header 仅 [查看]，无管理按钮
- 行为要点（实测）：新建弹窗/编辑弹窗/删除确认弹窗文案均已确认。
"""
import re
import time
from playwright.sync_api import Page


class McpServerPage:
    """MCP 插件市场页 /ctrl/agent/mcp"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/mcp"

    # ═══════════ 导航/加载 ═══════════

    def goto(self):
        """直达 MCP 插件市场页并等待加载完成"""
        self.page.goto(self.url, wait_until="domcontentloaded")
        try:
            self.page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass
        if not self._wait_loaded(timeout=5000):
            # 兜底：重载一次（SPA 初始化偶发）
            for _ in range(2):
                try:
                    self.page.reload(wait_until="domcontentloaded")
                except Exception:
                    pass
                if self._wait_loaded(timeout=5000):
                    break

    def _wait_loaded(self, timeout: int = 8000) -> bool:
        try:
            self.page.get_by_role("heading", name="MCP 插件市场").wait_for(
                state="visible", timeout=timeout
            )
            return True
        except Exception:
            return False

    def is_loaded(self) -> bool:
        return "/ctrl/agent/mcp" in self.page.url and self._wait_loaded(timeout=3000)

    # ═══════════ 搜索/范围 ═══════════

    def search(self, keyword: str):
        """按名称/描述/类型过滤插件"""
        inp = self.page.get_by_placeholder("搜索插件、连接方式或用途")
        inp.first.wait_for(state="visible", timeout=5000)
        inp.first.fill(keyword)
        self.page.wait_for_timeout(500)

    def clear_search(self):
        try:
            inp = self.page.get_by_placeholder("搜索插件、连接方式或用途")
            inp.first.fill("")
            self.page.wait_for_timeout(400)
        except Exception:
            pass

    # ═══════════ 目录（catalog） ═══════════

    def _catalog(self):
        return self.page.get_by_role("navigation", name="插件目录")

    def get_server_count(self) -> int:
        """目录项总数（当前筛选范围下可见项）"""
        return self._catalog().locator("button").count()

    def get_server_names(self) -> list[str]:
        """所有目录项的显示名（strong 文本，可能带 ORG 前缀）"""
        items = self._catalog().locator("button")
        names = []
        for i in range(items.count()):
            strongs = items.nth(i).locator("strong")
            if strongs.count() > 0:
                txt = strongs.first.inner_text().strip()
                if txt and txt not in names:
                    names.append(txt)
        return names

    def has_server(self, name: str, timeout: float = 15000) -> bool:
        """目录里是否有（显示名或原名称）包含 name 的服务器"""
        try:
            self._catalog_item(name).first.wait_for(state="visible", timeout=timeout)
            return True
        except Exception:
            return False

    def _catalog_item(self, name: str):
        """目录项 button（可访问名/子文本含 name）"""
        return self._catalog().locator("button").filter(has_text=name)

    # ═══════════ 选择服务器（详情上下文） ═══════════

    def select_server(self, name: str):
        """点击目录项，让右侧详情指向该服务器；返回详情 h2 文本"""
        item = self._catalog_item(name).first
        item.wait_for(state="visible", timeout=8000)
        item.click()
        try:
            self.page.locator("main article").first.wait_for(state="visible", timeout=6000)
        except Exception:
            pass
        return self._detail_title()

    def _detail_title(self) -> str:
        """详情区当前选中服务器的标题文本"""
        try:
            return self.page.locator("main").get_by_role("heading", level=2).first.inner_text().strip()
        except Exception:
            return ""

    def _ensure_selected(self, name: str):
        """确保右侧详情正显示 name（防误操作其他服务器）"""
        cur = self._detail_title()
        if name not in cur:
            cur = self.select_server(name)
        assert name in cur, f"详情区当前显示 '{cur}'，与目标 '{name}' 不一致"

    # ═══════════ 新建 ═══════════

    def open_create_dialog(self):
        self.page.get_by_role("button", name="添加插件").first.wait_for(state="visible", timeout=5000)
        self.page.get_by_role("button", name="添加插件").first.click()
        self.page.wait_for_timeout(600)

    def is_create_dialog_open(self) -> bool:
        dlg = self.page.get_by_role("dialog")
        if dlg.count() == 0:
            return False
        try:
            dlg.filter(has=self.page.get_by_role("heading", name="新建 MCP 服务器")).first.wait_for(
                state="visible", timeout=2000
            )
            return True
        except Exception:
            return False

    def select_type(self, server_type: str):
        """在新建弹窗切换类型：Stdio/Local→Local（命令行启动）；SSE/Remote/Streamable HTTP→Remote（URL 连接）"""
        type_map = {
            "Stdio": "Local（命令行启动）",
            "Local": "Local（命令行启动）",
            "SSE": "Remote（URL 连接）",
            "Remote": "Remote（URL 连接）",
            "Streamable HTTP": "Remote（URL 连接）",
        }
        option_text = type_map.get(server_type, server_type)
        dlg = self.page.get_by_role("dialog").filter(
            has=self.page.get_by_role("heading", name="新建 MCP 服务器")
        )
        trigger = dlg.get_by_role("combobox").first
        trigger.wait_for(state="visible", timeout=5000)
        trigger.click()
        try:
            option = self.page.get_by_role("option", name=option_text, exact=True)
            option.first.wait_for(state="visible", timeout=5000)
            option.first.click()
        except Exception:
            pass
        self.page.wait_for_timeout(500)

    def fill_create_form(self, name: str, command: str = "", url: str = ""):
        """填写新建弹窗（仅填当前模式相关字段）"""
        dlg = self.page.get_by_role("dialog").filter(
            has=self.page.get_by_role("heading", name="新建 MCP 服务器")
        )
        name_input = dlg.get_by_placeholder("my-mcp-server")
        name_input.first.wait_for(state="visible", timeout=5000)
        name_input.first.fill(name)
        if url:
            url_input = dlg.get_by_placeholder("https://example.com/mcp")
            if url_input.count() > 0:
                url_input.first.fill(url)
        if command:
            cmd_input = dlg.get_by_placeholder("npx @modelcontextprotocol/server-filesystem")
            if cmd_input.count() > 0:
                cmd_input.first.fill(command)

    def add_header(self, header_name: str, header_value: str):
        """新建/编辑弹窗：新增一行请求头并填写（填最后一行，避免覆盖已有）"""
        dlg = self.page.get_by_role("dialog").first
        add_btn = dlg.get_by_role("button", name="+ 添加")
        if add_btn.count() > 0:
            add_btn.first.click()
            self.page.wait_for_timeout(300)
        names = dlg.get_by_placeholder("Header 名称")
        values = dlg.get_by_placeholder("Header 值")
        n = names.count()
        assert n > 0 and values.count() == n, "未找到请求头 名称/值 输入行"
        names.nth(n - 1).fill(header_name)
        values.nth(n - 1).fill(header_value)

    def save(self):
        dlg = self.page.get_by_role("dialog").first
        btn = dlg.get_by_role("button", name="保存", exact=True)
        btn.wait_for(state="visible", timeout=5000)
        btn.click()
        try:
            self.page.get_by_role("dialog").first.wait_for(state="hidden", timeout=8000)
        except Exception:
            pass
        self.page.wait_for_timeout(600)

    def close_dialog(self):
        """取消/关闭当前弹窗"""
        dlg = self.page.get_by_role("dialog")
        if dlg.count() == 0:
            return
        cancel = dlg.first.get_by_role("button", name="取消", exact=True)
        if cancel.count() > 0:
            cancel.first.click()
        else:
            self.page.keyboard.press("Escape")
        try:
            self.page.get_by_role("dialog").first.wait_for(state="hidden", timeout=5000)
        except Exception:
            pass

    # ═══════════ 表单校验反馈（toast + 弹窗内联） ═══════════

    def read_toast_texts(self) -> list[str]:
        """读取右上角通知区的全部 toast 文本"""
        return self.page.evaluate("""() => {
            const out = [];
            for (const li of document.querySelectorAll('li')) {
                if (!li.querySelector('button')) continue;
                const t = (li.textContent || '').replace('Close toast', '').trim();
                if (t) out.push(t);
            }
            return out;
        }""")

    def get_validation_errors(self) -> list[str]:
        """toast + 弹窗内联报错文本"""
        errors = []
        dlg = self.page.get_by_role("dialog")
        if dlg.count() > 0:
            inline = dlg.first.locator(
                "[role=alert], p.text-red-500, p.text-red-600, [data-slot='form-message']"
            )
            for e in inline.all():
                txt = e.inner_text().strip()
                if txt:
                    errors.append(txt)
        errors.extend(self.read_toast_texts())
        return errors

    # ═══════════ 详情只读/状态读取 ═══════════

    def _detail_article_text(self) -> str:
        try:
            return self.page.locator("main article").first.inner_text()
        except Exception:
            return ""

    def get_status(self, name: str) -> str:
        """返回状态：已启用 / 已停用"""
        self._ensure_selected(name)
        m = re.search(r"状态\s*(已启用|已停用)", self._detail_article_text())
        return m.group(1) if m else ""

    def get_tools_meta(self, name: str) -> str:
        """dl 里的 Tools 行，如 '4 个工具'"""
        self._ensure_selected(name)
        m = re.search(r"Tools\s*(\d+)\s*个工具", self._detail_article_text())
        return f"{m.group(1)} 个工具" if m else ""

    def is_managed(self, name: str) -> bool:
        """owner：header 有「编辑」按钮；非 owner 只读：header 是「查看」"""
        self._ensure_selected(name)
        main = self.page.locator("main")
        return main.get_by_role("button", name="编辑", exact=True).count() > 0

    def _find_readonly_server(self) -> str | None:
        """扫描目录，返回第一个「非 owner 只读」服务器名（header 为「查看」）"""
        for name in self.get_server_names():
            try:
                self.select_server(name)
                main = self.page.locator("main")
                if main.get_by_role("button", name="查看", exact=True).count() > 0:
                    return name
            except Exception:
                continue
        return None

    # ═══════════ 启用/禁用 ═══════════

    def is_server_enabled(self, name: str) -> bool:
        """有页脚「禁用」按钮=已启用；只有「启用」=已停用"""
        self._ensure_selected(name)
        main = self.page.locator("main")
        return main.get_by_role("button", name="禁用", exact=True).count() > 0

    def toggle_enabled(self, name: str):
        """切换启用/停用（点击页脚 禁用/启用）"""
        self._ensure_selected(name)
        main = self.page.locator("main")
        btn = main.get_by_role("button", name="禁用", exact=True).or_(
            main.get_by_role("button", name="启用", exact=True)
        )
        btn.first.wait_for(state="visible", timeout=5000)
        btn.first.click()
        self.page.wait_for_timeout(800)

    # ═══════════ 公开/私有 ═══════════

    def is_public(self, name: str) -> bool:
        """公开：页脚为「设为私有」"""
        self._ensure_selected(name)
        main = self.page.locator("main")
        return main.get_by_role("button", name="设为私有", exact=True).count() > 0

    def toggle_public(self, name: str):
        """切换 设为公开 ↔ 设为私有"""
        self._ensure_selected(name)
        main = self.page.locator("main")
        btn = main.get_by_role("button", name="设为公开", exact=True).or_(
            main.get_by_role("button", name="设为私有", exact=True)
        )
        btn.first.wait_for(state="visible", timeout=5000)
        btn.first.click()
        self.page.wait_for_timeout(800)

    # ═══════════ 检测（发现工具） ═══════════

    def click_inspect(self, name: str):
        """选中后点页脚「检测」（页脚是 main 内最后一个 检测）"""
        self._ensure_selected(name)
        main = self.page.locator("main")
        insp = main.get_by_role("button", name="检测", exact=True)
        n = insp.count()
        assert n > 0, "未找到「检测」按钮"
        insp.nth(n - 1).wait_for(state="visible", timeout=5000)
        insp.nth(n - 1).click()

    def wait_inspect_result(self, name: str, timeout: float = 15000):
        """等待检测出结果：出现 toast 或 Tools 卡片不再显示空态。

        返回 (toasts, tools_card_empty, article_text)
        """
        deadline = time.time() + timeout / 1000
        last_toasts, last_empty = [], True
        while time.time() < deadline:
            toasts = self.read_toast_texts()
            article = self._detail_article_text()
            empty = "暂无已发现的工具" in article
            last_toasts, last_empty = toasts, empty
            if toasts:
                return toasts, empty, article
            if not empty:
                return toasts, empty, article
            self.page.wait_for_timeout(500)
        return last_toasts, last_empty, self._detail_article_text()

    # ═══════════ 编辑 ═══════════

    def click_edit(self, name: str):
        self._ensure_selected(name)
        self.page.locator("main").get_by_role("button", name="编辑", exact=True).first.click()
        self.page.wait_for_timeout(600)

    def is_edit_dialog_open(self) -> bool:
        try:
            self.page.get_by_role("dialog").filter(
                has=self.page.get_by_role("heading", name="编辑 MCP 服务器")
            ).first.wait_for(state="visible", timeout=2000)
            return True
        except Exception:
            return False

    def _edit_dialog(self):
        return self.page.get_by_role("dialog").filter(
            has=self.page.get_by_role("heading", name="编辑 MCP 服务器")
        )

    def is_name_field_locked(self) -> bool:
        """编辑弹窗中名称输入框应 disabled + 有「名称创建后不可修改」提示"""
        dlg = self._edit_dialog()
        name_input = dlg.get_by_placeholder("my-mcp-server")
        if name_input.count() == 0:
            return False
        disabled = name_input.first.get_attribute("disabled") is not None
        hint = dlg.get_by_text("名称创建后不可修改").count() > 0
        return disabled and hint

    def edit_field_values(self) -> dict:
        """编辑弹窗当前字段值：url / timeout / headers(名称列表)"""
        dlg = self._edit_dialog()
        out = {"url": "", "timeout": "", "headers": []}
        url_input = dlg.get_by_placeholder("https://example.com/mcp")
        if url_input.count() > 0:
            out["url"] = url_input.first.input_value()
        spin = dlg.get_by_role("spinbutton")
        if spin.count() > 0:
            out["timeout"] = spin.first.input_value()
        names = dlg.get_by_placeholder("Header 名称")
        values = dlg.get_by_placeholder("Header 值")
        for i in range(names.count()):
            out["headers"].append({"name": names.nth(i).input_value(), "value": values.nth(i).input_value()})
        return out

    def set_edit_field(self, url: str = "", timeout: str = "", header: tuple[str, str] | None = None):
        """在编辑弹窗修改字段：url / timeout(毫秒) / 新增一条 header"""
        dlg = self._edit_dialog()
        if url:
            url_input = dlg.get_by_placeholder("https://example.com/mcp")
            if url_input.count() > 0:
                url_input.first.fill(url)
        if timeout:
            spin = dlg.get_by_role("spinbutton")
            if spin.count() > 0:
                spin.first.fill(timeout)
        if header:
            self.add_header(header[0], header[1])

    # ═══════════ 删除 ═══════════

    def delete_server(self, name: str):
        """删除当前选中的服务器（页脚删除→确认弹窗校验对象→确认）

        删除前必须确认：① 详情区标题是目标；② 确认弹窗文案包含目标名。
        """
        self._ensure_selected(name)
        main = self.page.locator("main")
        del_btn = main.get_by_role("button", name="删除", exact=True)
        del_btn.wait_for(state="visible", timeout=5000)
        del_btn.first.click()
        self.page.wait_for_timeout(500)

        ad = self.page.get_by_role("alertdialog")
        ad.first.wait_for(state="visible", timeout=5000)
        text = ad.first.inner_text()
        assert "确认删除" in text, f"确认弹窗标题异常: {text[:80]}"
        assert name in text, (
            f"确认弹窗内容不包含目标 '{name}'，可能误删其他服务器！弹窗: {text[:120]}"
        )
        confirm = ad.first.get_by_role("button", name="确认", exact=True)
        confirm.wait_for(state="visible", timeout=5000)
        confirm.click()
        try:
            self.page.get_by_role("alertdialog").first.wait_for(state="hidden", timeout=5000)
        except Exception:
            pass
        self.page.wait_for_timeout(800)

    # ═══════════ API 拦截辅助 ═══════════

    def setup_api_interceptor(self, url_pattern: str) -> list:
        """设置 API 响应拦截器"""
        responses = []

        def on_response(r):
            if url_pattern in r.url and ".js" not in r.url and ".css" not in r.url:
                data = {"url": r.url, "method": r.request.method, "status": r.status}
                try:
                    data["body"] = r.json()
                except Exception:
                    data["body"] = None
                responses.append(data)

        self.page.on("response", on_response)
        return responses
