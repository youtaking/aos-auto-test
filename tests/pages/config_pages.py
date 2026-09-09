# tests/pages/config_pages.py
"""配置管理页面 Page Objects（模型、技能、MCP、Agent Sites）"""
import re
import time

from playwright.sync_api import Page


class ModelsPage:
    """服务商与模型管理页"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/models"

    # 页面就绪标识：搜索输入框
    _READY_SELECTOR = "input[placeholder*='搜索服务商']"

    def goto(self):
        for _attempt in range(2):
            try:
                self.page.goto(self.url, wait_until="domcontentloaded")
            except Exception:
                pass  # SPA 路由可能中断初始导航（net::ERR_ABORTED）
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
            nav_btn = self.page.locator("button.agent-sidebar-nav-item").filter(has_text="模型库")
            if nav_btn.count() > 0:
                nav_btn.first.click()
                try:
                    self.page.locator(self._READY_SELECTOR).first.wait_for(state="attached", timeout=15000)
                except Exception:
                    pass

    def is_loaded(self) -> bool:
        return "/ctrl/agent/models" in self.page.url and \
            self.page.locator(self._READY_SELECTOR).count() > 0

    def has_model_list(self) -> bool:
        """是否有模型列表内容"""
        return self.page.locator("table tbody tr, div.grid > div").count() > 0

    def search(self, keyword: str):
        inp = self.page.locator("input[placeholder*='搜索服务商']")
        if inp.count() > 0:
            inp.first.fill(keyword)
            self.page.wait_for_timeout(500)

    def clear_search(self):
        inp = self.page.locator("input[placeholder*='搜索服务商']")
        if inp.count() > 0:
            inp.first.fill("")
            self.page.wait_for_timeout(500)

    def get_provider_count(self) -> int:
        """获取服务商卡片数量"""
        cards = self.page.locator(
            "div.agent-panel-content div.rounded-lg.border"
        )
        return cards.count()


class SkillsPage:
    """技能库页 /ctrl/agent/skills — 基于 2026-09 新版两栏「技能库」真实 DOM 编写

    新版页面结构（已在参照环境 100.105.9.16:38879 用 playwright MCP 实测）：
    - 顶栏：h1「技能库」 + 右侧按钮 [导入][添加 Skill]
    - 筛选区：搜索框(ph=搜索 Skill) + 分段按钮 全部N/本组织N/公开N（aria-pressed 标记当前作用域）
    - 左栏 catalog：navigation aria-label=技能目录，每项 = button{ <strong>技能名 + 描述 + 所属组织徽标 [+公开徽标] }
    - 右栏详情（点击某项后）：
      - header：h2{技能名} + 所属组织徽标 + 右侧按钮（owner=编辑 / 非owner=查看）
      - article：Skill 徽标 + 描述(空则「暂无用途说明」) + 技能指令(SKILL.md 渲染内容) + 公开/未公开 徽标
      - 页脚操作条（owner）：[下载][设为公开|设为私有][删除]
      - 非 owner（同组织他成员/公开分享）：header=查看，页脚仅 [下载]
    - 新建弹窗「新建技能」：名称(input ph=my-skill) / 描述(textarea ph=可选，简要描述技能用途) / 内容(textarea ph=输入 Markdown 内容...)
    - 编辑弹窗「编辑技能」：名称 disabled（无「不可修改」提示文案）；描述/内容可编辑
    - 上传弹窗「上传技能」（由 [导入] 打开）：form 内 input[webkitdirectory] + 提示「点击选择包含技能的文件夹，每个子目录将被识别为一个 skill」+ [取消][开始上传]
    - 行为要点（实测）：
      - 空名称提交 → toast「名称不能为空」，弹窗保持打开
      - 空内容提交 → toast「内容不能为空」，弹窗保持打开
      - 新建成功 → toast「技能已创建」，弹窗关闭
      - 编辑保存/删除成功 → 静默（无 toast），需断言弹窗关闭+状态变化
      - 设为公开/私有 → 直接切换（无确认弹窗），页脚按钮 设为公开↔设为私有，article 徽标 未公开↔公开
      - 删除 → alertdialog「确认删除 / 此操作不可逆。确定要删除技能 "{name}" 吗？」+ [取消][确认]
      - 下载 → 触发下载，文件名 {技能名}.zip
      - 搜索/分段筛选实时作用于左栏 catalog 数量
      - 上传同名冲突：开始上传 → 后端 409 SKILL_CONFLICT → toast「检测到同名技能，请选择忽略或覆盖策略」
        + 弹窗内联冲突卡片（跳过冲突项/覆盖已有技能）。跳过→弹窗关闭+toast「已导入 N 个技能，跳过 M 个冲突技能」；
        覆盖已有技能→alertdialog「确认覆盖冲突技能」需 [确认覆盖]，成功后 toast「已导入 N 个技能」
    """

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/skills"

    # ═══════════ 导航/加载 ═══════════

    def goto(self):
        """直达技能库页并等待列表加载完成（整页刷新可复位 作用域/搜索 到默认）"""
        for _ in range(2):
            try:
                self.page.goto(self.url, wait_until="domcontentloaded")
            except Exception:
                pass
            try:
                self.page.wait_for_load_state("networkidle", timeout=6000)
            except Exception:
                pass
            if self._wait_loaded(timeout=8000):
                return
        assert self._wait_loaded(timeout=8000), "技能库页面加载超时"

    def reload(self) -> bool:
        """强制整页刷新并等待列表就绪（API 预置新技能后必须刷新才能看到）"""
        for _ in range(2):
            try:
                self.page.reload(wait_until="domcontentloaded")
            except Exception:
                pass
            try:
                self.page.wait_for_load_state("networkidle", timeout=6000)
            except Exception:
                pass
            if self._wait_loaded(timeout=8000):
                return True
            self.page.wait_for_timeout(500)
        return self._wait_loaded(timeout=8000)

    def _wait_loaded(self, timeout: int = 8000) -> bool:
        try:
            self._catalog().first.wait_for(state="visible", timeout=timeout)
            return True
        except Exception:
            return False

    def is_loaded(self) -> bool:
        return "/ctrl/agent/skills" in self.page.url and self._wait_loaded(timeout=3000)

    # ═══════════ 目录（catalog） ═══════════

    def _catalog(self):
        return self.page.get_by_role("navigation", name="技能目录")

    def _main(self):
        return self.page.locator("main")

    def get_skill_count(self) -> int:
        """左栏目录项总数（当前作用域/搜索过滤下可见项）"""
        try:
            return self._catalog().locator("button").count()
        except Exception:
            return 0

    def get_skill_names(self) -> list[str]:
        """所有目录项的技能名（strong 文本，去重，保持顺序）"""
        items = self._catalog().locator("button")
        names = []
        for i in range(items.count()):
            strongs = items.nth(i).locator("strong")
            if strongs.count() > 0:
                txt = strongs.first.inner_text().strip()
                if txt and txt not in names:
                    names.append(txt)
        return names

    def has_skill(self, name: str, timeout: float = 15000) -> bool:
        """目录里是否有技能名/描述含 name 的项"""
        try:
            self._catalog_item(name).first.wait_for(state="visible", timeout=timeout)
            return True
        except Exception:
            return False

    def _catalog_item(self, name: str):
        return self._catalog().locator("button").filter(has_text=name)

    def select_skill(self, name: str) -> str:
        """点击目录项，让右侧详情指向该技能；返回详情 h2 文本"""
        item = self._catalog_item(name).first
        item.wait_for(state="visible", timeout=8000)
        item.click()
        try:
            self._main().locator("article").first.wait_for(state="visible", timeout=6000)
        except Exception:
            pass
        return self._detail_title()

    def _ensure_selected(self, name: str):
        cur = self._detail_title()
        if name not in cur:
            cur = self.select_skill(name)
        assert name in cur, f"详情区当前显示 '{cur}'，与目标 '{name}' 不一致"

    def _detail_title(self) -> str:
        try:
            return self._main().get_by_role("heading", level=2).first.inner_text().strip()
        except Exception:
            return ""

    # ═══════════ 搜索 / 作用域筛选 ═══════════

    def search(self, keyword: str):
        inp = self.page.get_by_placeholder("搜索 Skill")
        inp.first.wait_for(state="visible", timeout=5000)
        inp.first.fill(keyword)
        self.page.wait_for_timeout(500)

    def clear_search(self):
        try:
            inp = self.page.get_by_placeholder("搜索 Skill")
            inp.first.fill("")
            self.page.wait_for_timeout(400)
        except Exception:
            pass

    def click_scope(self, label: str):
        """点击分段作用域按钮：全部 / 本组织 / 公开（按钮文案含数量后缀，用前缀匹配）"""
        btn = self._main().get_by_role("button", name=re.compile(f"^{label}\\d+$"))
        btn.first.wait_for(state="visible", timeout=5000)
        btn.first.click()
        self.page.wait_for_timeout(600)

    # ═══════════ 详情只读/状态读取 ═══════════

    def article_text(self, name: str) -> str:
        """读取详情正文并轮询等待含技能名（详情内容为异步拉取，重载下可能滞后）。

        调用方均断言正文含技能名；正文已渲染则首次读取即返回，未渲染时最多等 12s。
        """
        self._ensure_selected(name)
        deadline = time.time() + 12
        last = ""
        try:
            art = self._main().locator("article").first
            while time.time() < deadline:
                last = art.inner_text(timeout=2000)
                if name in last:
                    return last
                self.page.wait_for_timeout(400)
        except Exception:
            pass
        return last

    def is_owner(self, name: str) -> bool:
        """owner：详情 header 有「编辑」按钮；非 owner 只读：header 是「查看」"""
        self._ensure_selected(name)
        return self._main().get_by_role("button", name="编辑", exact=True).count() > 0

    def is_public(self, name: str) -> bool:
        """公开：页脚按钮为「设为私有」；未公开：「设为公开」"""
        self._ensure_selected(name)
        return self._main().get_by_role("button", name="设为私有", exact=True).count() > 0

    # ═══════════ toast ═══════════

    def read_toast_texts(self) -> list[str]:
        """右上角通知区全部 toast 文本"""
        return self.page.evaluate("""() => {
            const out = [];
            for (const li of document.querySelectorAll('li')) {
                if (!li.querySelector('button')) continue;
                const t = (li.textContent || '').replace('Close toast', '').trim();
                if (t) out.push(t);
            }
            return out;
        }""")

    def get_last_toast_text(self, timeout: float = 5000) -> str:
        """轮询等待并返回「最新」toast 文本（toast 自动消失，需在出现窗口内捕获）。

        实测通知区新 toast 插入在列表最前（index 0），旧 toast 在尾部待自动消失；
        故取 toasts[0]。若取 [-1]，同名冲突→覆盖导入叠加新旧 toast 时读到的是旧文案。
        """
        deadline = time.time() + timeout / 1000
        last = ""
        while time.time() < deadline:
            toasts = self.read_toast_texts()
            if toasts:
                last = toasts[0]
                return last
            self.page.wait_for_timeout(200)
        return last

    # ═══════════ 新建技能 ═══════════

    def open_create_dialog(self):
        self._main().get_by_role("button", name="添加 Skill", exact=True).first.click()
        self.page.wait_for_timeout(600)

    def is_create_dialog_open(self) -> bool:
        return self._dialog_with_heading("新建技能", timeout=3000)

    def _create_dialog(self):
        return self.page.get_by_role("dialog").filter(
            has=self.page.get_by_role("heading", name="新建技能")
        )

    def fill_create_form(self, name: str, description: str = "", content: str = ""):
        dlg = self._create_dialog()
        name_input = dlg.get_by_placeholder("my-skill")
        name_input.first.wait_for(state="visible", timeout=5000)
        name_input.first.fill(name)
        if description:
            desc = dlg.get_by_placeholder("可选，简要描述技能用途")
            if desc.count() > 0:
                desc.first.fill(description)
        if content:
            cont = dlg.get_by_placeholder("输入 Markdown 内容...")
            if cont.count() > 0:
                cont.first.fill(content)

    def create_skill(self, name: str, description: str = "", content: str = ""):
        """打开新建弹窗→填表→保存→弹窗关闭。返回 (toast, dialog_still_open)"""
        self.open_create_dialog()
        self.fill_create_form(name, description=description, content=content)
        self.save_dialog()
        return self.get_last_toast_text(), self.is_create_dialog_open()

    def save_dialog(self):
        dlg = self.page.get_by_role("dialog").first
        btn = dlg.get_by_role("button", name="保存", exact=True)
        btn.wait_for(state="visible", timeout=5000)
        btn.click()
        # 成功创建时弹窗自动关闭；校验/重名失败时弹窗保持打开且错误以 toast 提示。
        # 等待关闭上限 2.5s：校验失败场景若等 8s，会耗尽 toast 显示窗口导致读不到错误文案。
        try:
            dlg.wait_for(state="hidden", timeout=2500)
        except Exception:
            pass
        self.page.wait_for_timeout(250)

    def cancel_dialog(self):
        dlg = self.page.get_by_role("dialog").first
        cancel = dlg.get_by_role("button", name="取消", exact=True)
        if cancel.count() > 0:
            cancel.first.click()
        else:
            self.page.keyboard.press("Escape")
        try:
            dlg.wait_for(state="hidden", timeout=5000)
        except Exception:
            pass
        self.page.wait_for_timeout(500)

    def _dialog_with_heading(self, heading: str, timeout: int = 5000) -> bool:
        try:
            self.page.get_by_role("dialog").filter(
                has=self.page.get_by_role("heading", name=heading)
            ).first.wait_for(state="visible", timeout=timeout)
            return True
        except Exception:
            return False

    def is_dialog_open(self) -> bool:
        return self.page.get_by_role("dialog").count() > 0

    # ═══════════ 编辑技能 ═══════════

    def open_edit(self, name: str):
        self._ensure_selected(name)
        btn = self._main().get_by_role("button", name="编辑", exact=True)
        btn.first.wait_for(state="visible", timeout=5000)
        btn.first.click()
        self.page.wait_for_timeout(600)

    def is_edit_dialog_open(self) -> bool:
        return self._dialog_with_heading("编辑技能", timeout=3000)

    def _edit_dialog(self):
        return self.page.get_by_role("dialog").filter(
            has=self.page.get_by_role("heading", name="编辑技能")
        )

    def is_name_disabled(self) -> bool:
        dlg = self._edit_dialog()
        name_input = dlg.get_by_placeholder("my-skill")
        if name_input.count() == 0:
            return False
        return name_input.first.is_disabled()

    def edit_field_values(self) -> dict:
        dlg = self._edit_dialog()
        out = {"name": "", "description": "", "content": ""}
        name_input = dlg.get_by_placeholder("my-skill")
        if name_input.count() > 0:
            out["name"] = name_input.first.input_value()
        desc = dlg.get_by_placeholder("可选，简要描述技能用途")
        if desc.count() > 0:
            out["description"] = desc.first.input_value()
        cont = dlg.get_by_placeholder("输入 Markdown 内容...")
        if cont.count() > 0:
            out["content"] = cont.first.input_value()
        return out

    def set_edit_field(self, description: str | None = None, content: str | None = None):
        dlg = self._edit_dialog()
        if description is not None:
            desc = dlg.get_by_placeholder("可选，简要描述技能用途")
            if desc.count() > 0:
                desc.first.fill(description)
        if content is not None:
            cont = dlg.get_by_placeholder("输入 Markdown 内容...")
            if cont.count() > 0:
                cont.first.fill(content)

    # ═══════════ 公开/私有 ═══════════

    def toggle_public(self, name: str):
        """切换 设为公开 ↔ 设为私有（无确认弹窗，toast 为按钮文案）"""
        self._ensure_selected(name)
        main = self._main()
        btn = main.get_by_role("button", name="设为公开", exact=True).or_(
            main.get_by_role("button", name="设为私有", exact=True)
        )
        btn.first.wait_for(state="visible", timeout=5000)
        btn.first.click()
        self.page.wait_for_timeout(800)

    # ═══════════ 下载 ═══════════

    def download_skill(self, name: str):
        """点击页脚「下载」并返回 download 对象（owner 与非 owner 页脚都有下载）"""
        self._ensure_selected(name)
        main = self._main()
        with self.page.expect_download(timeout=15000) as dl:
            main.get_by_role("button", name="下载", exact=True).first.click()
        return dl.value

    # ═══════════ 删除 ═══════════

    def delete_skill(self, name: str):
        """删除当前选中技能（页脚删除→确认弹窗校验技能名→确认）。

        删除前必须确认：① 详情区标题是目标；② 确认弹窗文案包含目标名。
        """
        self._ensure_selected(name)
        main = self._main()
        del_btn = main.get_by_role("button", name="删除", exact=True)
        del_btn.first.wait_for(state="visible", timeout=5000)
        del_btn.first.click()
        self.page.wait_for_timeout(500)

        ad = self.page.get_by_role("alertdialog")
        ad.first.wait_for(state="visible", timeout=5000)
        text = ad.first.inner_text()
        assert "确认删除" in text, f"确认弹窗标题异常: {text[:80]}"
        assert name in text, (
            f"确认弹窗内容不包含目标 '{name}'，可能误删其他技能！弹窗: {text[:120]}"
        )
        confirm = ad.first.get_by_role("button", name="确认", exact=True)
        confirm.wait_for(state="visible", timeout=5000)
        confirm.click()
        try:
            ad.first.wait_for(state="hidden", timeout=5000)
        except Exception:
            pass
        self.page.wait_for_timeout(800)

    # ═══════════ 导入（上传技能文件夹） ═══════════

    def open_import_dialog(self):
        self._main().get_by_role("button", name="导入", exact=True).first.click()
        self.page.wait_for_timeout(600)

    def is_import_dialog_open(self) -> bool:
        return self._dialog_with_heading("上传技能", timeout=3000)

    def select_import_folder(self, folder_path: str):
        """在上传弹窗中通过 webkitdirectory 文件输入选择含多个技能子目录的文件夹"""
        dlg = self.page.get_by_role("dialog").filter(
            has=self.page.get_by_role("heading", name="上传技能")
        )
        folder_input = dlg.locator("input[webkitdirectory]")
        folder_input.first.wait_for(state="attached", timeout=5000)
        folder_input.first.set_input_files(folder_path)
        self.page.wait_for_timeout(800)

    def _upload_dialog(self):
        return self.page.get_by_role("dialog").filter(
            has=self.page.get_by_role("heading", name="上传技能")
        )

    def click_import_start(self):
        """点击开始上传。同名冲突时弹窗不关闭，转去 resolve_upload_conflict()"""
        dlg = self._upload_dialog()
        btn = dlg.get_by_role("button", name="开始上传", exact=True)
        btn.wait_for(state="visible", timeout=5000)
        btn.click()
        self.page.wait_for_timeout(1500)

    def has_upload_conflict(self, name: str, timeout: float = 8000) -> bool:
        """开始上传后是否出现同名冲突卡片（检测到同名技能冲突 + 冲突项 name）"""
        try:
            dlg = self._upload_dialog()
            dlg.filter(has_text="检测到同名技能冲突").wait_for(
                state="visible", timeout=timeout
            )
            dlg.get_by_text(name, exact=True).first.wait_for(state="visible", timeout=3000)
            return True
        except Exception:
            return False

    def resolve_upload_conflict(self, name: str, strategy: str):
        """处理上传同名冲突：strategy=skip 跳过该冲突项；overwrite 覆盖已有技能。

        实测（参照环境）：
        - skip → 立即以 ignore 策略重新上传，弹窗关闭，toast「已导入 N 个技能，跳过 M 个冲突技能」
        - overwrite → 弹出 alertdialog「确认覆盖冲突技能」，需再点 [确认覆盖] 才重新上传，
          弹窗关闭，toast「已导入 N 个技能」
        """
        dlg = self._upload_dialog()
        if strategy == "skip":
            btn = dlg.get_by_role("button", name="跳过冲突项", exact=True)
        elif strategy == "overwrite":
            btn = dlg.get_by_role("button", name="覆盖已有技能", exact=True)
        else:
            raise ValueError(f"未知冲突策略: {strategy}")
        btn.first.wait_for(state="visible", timeout=5000)
        btn.first.click()
        if strategy == "overwrite":
            ad = self.page.get_by_role("alertdialog")
            ad.first.wait_for(state="visible", timeout=5000)
            text = ad.first.inner_text()
            assert "确认覆盖冲突技能" in text, f"覆盖确认弹窗标题异常: {text[:80]}"
            assert name in text, (
                f"覆盖确认弹窗未包含目标 '{name}'，可能覆盖其他技能！弹窗: {text[:120]}"
            )
            confirm = ad.first.get_by_role("button", name="确认覆盖", exact=True)
            confirm.first.wait_for(state="visible", timeout=5000)
            confirm.first.click()
        # skip / overwrite 都会重新上传，成功后弹窗自动关闭
        try:
            dlg.first.wait_for(state="hidden", timeout=8000)
        except Exception:
            pass
        self.page.wait_for_timeout(250)


class McpPage:
    """MCP 服务器管理页"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/mcp"

    # 页面就绪标识：搜索输入框
    _READY_SELECTOR = "input[placeholder*='搜索 MCP'], input[placeholder*='搜索MCP']"

    def goto(self):
        for _attempt in range(2):
            try:
                self.page.goto(self.url, wait_until="domcontentloaded")
            except Exception:
                pass  # SPA 路由可能中断初始导航（net::ERR_ABORTED）
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
            nav_btn = self.page.locator("button.agent-sidebar-nav-item").filter(has_text="MCP")
            if nav_btn.count() > 0:
                nav_btn.first.click()
                try:
                    self.page.locator(self._READY_SELECTOR).first.wait_for(state="attached", timeout=15000)
                except Exception:
                    pass

    def is_loaded(self) -> bool:
        return "/ctrl/agent/mcp" in self.page.url and \
            self.page.locator(self._READY_SELECTOR).count() > 0

    def search(self, keyword: str):
        inp = self.page.locator("input[placeholder*='搜索 MCP'], input[placeholder*='搜索MCP']")
        if inp.count() > 0:
            inp.first.fill(keyword)
            self.page.wait_for_timeout(500)

    def clear_search(self):
        inp = self.page.locator("input[placeholder*='搜索 MCP'], input[placeholder*='搜索MCP']")
        if inp.count() > 0:
            inp.first.fill("")
            self.page.wait_for_timeout(500)

    def get_server_count(self) -> int:
        """获取 MCP 服务器列表数量"""
        items = self.page.locator(
            "div.agent-panel-content div.rounded-lg.border, "
            "table tbody tr"
        )
        return items.count()


class SitesPage:
    """Agent Sites 管理页"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/ctrl/agent/sites"

    # 页面就绪标识：搜索输入框
    _READY_SELECTOR = "input[placeholder*='搜索 app'], input[placeholder*='搜索app']"

    def goto(self):
        for _attempt in range(2):
            try:
                self.page.goto(self.url, wait_until="domcontentloaded")
            except Exception:
                pass  # SPA 路由可能中断初始导航（net::ERR_ABORTED）
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
            nav_btn = self.page.locator("button.agent-sidebar-nav-item").filter(has_text="AOS应用部署")
            if nav_btn.count() > 0:
                nav_btn.first.click()
                try:
                    self.page.locator(self._READY_SELECTOR).first.wait_for(state="attached", timeout=15000)
                except Exception:
                    pass

    def is_loaded(self) -> bool:
        return "/ctrl/agent/sites" in self.page.url and \
            self.page.locator(self._READY_SELECTOR).count() > 0

    def get_filter_tabs(self) -> list[str]:
        """获取筛选 Tab 列表"""
        tabs = self.page.locator("[role='tab']").all_text_contents()
        return [t.strip() for t in tabs if t.strip()]

    def click_filter_tab(self, tab_name: str):
        """点击筛选 Tab"""
        tab = self.page.get_by_text(tab_name, exact=True)
        tab.wait_for(state="visible", timeout=5000)
        tab.click()
        self.page.wait_for_timeout(500)

    def search(self, keyword: str):
        inp = self.page.locator("input[placeholder*='搜索 app'], input[placeholder*='搜索app']")
        if inp.count() > 0:
            inp.first.fill(keyword)
            self.page.wait_for_timeout(500)

    def clear_search(self):
        inp = self.page.locator("input[placeholder*='搜索 app'], input[placeholder*='搜索app']")
        if inp.count() > 0:
            inp.first.fill("")
            self.page.wait_for_timeout(500)

    def get_app_count(self) -> int:
        """获取 App 数量（表格行数）"""
        rows = self.page.locator("table tbody tr")
        return rows.count()
