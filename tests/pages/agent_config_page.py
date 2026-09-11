# tests/pages/agent_config_page.py
"""智能体配置 Page Object — 基于真实 DOM 结构编写"""
import re
from playwright.sync_api import Page


class AgentConfigPage:
    """智能体管理 /ctrl/agent/agents + 新建智能体页面"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.agents_url = f"{base_url}/ctrl/agent/agents"
        self.create_url = f"{base_url}/ctrl/agent/home"

    # ==================== 导航 ====================

    def goto_agents(self):
        # 若残留重启提示/配置弹窗，先关闭，否则会遮挡 sidebar 导航点击
        self._dismiss_any_dialog()
        # SPA 导航优先（sidebar 测试已验证可靠），避免全页面刷新后 router 初始化问题
        nav_btn = self.page.locator("button.agent-sidebar-nav-item").filter(has_text="智能体管理")
        if nav_btn.count() > 0:
            nav_btn.first.wait_for(state="visible", timeout=5000)
            nav_btn.first.click()
            try:
                self.page.locator("div.agent-panel-content").first.wait_for(state="attached", timeout=8000)
            except Exception:
                pass
            if "/ctrl/agent/agents" in self.page.url and self.page.locator("div.agent-panel-content").count() > 0:
                return
        # 降级：全页面刷新（SPA 导航失败时）
        for _attempt in range(2):
            try:
                self.page.goto(self.agents_url, wait_until="domcontentloaded")
            except Exception:
                pass
            self.page.wait_for_load_state("domcontentloaded")
            try:
                self.page.locator("div.agent-panel-content").first.wait_for(state="attached", timeout=8000)
            except Exception:
                pass
            if "/ctrl/agent/agents" in self.page.url and self.page.locator("div.agent-panel-content").count() > 0:
                break
            try:
                self.page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
            self.page.wait_for_timeout(500)

    def goto_create(self):
        """导航到新建智能体页面（直接 URL 导航，不依赖侧边栏按钮）"""
        if "/ctrl/agent/home" in self.page.url:
            # 已在创建页面，先导航离开再回来确保 SPA 状态重置
            try:
                self.page.goto(self.agents_url, wait_until="domcontentloaded")
            except Exception:
                pass
            self.page.wait_for_load_state("domcontentloaded")
        # 直接 URL 导航到创建页面（比侧边栏按钮更可靠，尤其在删除 agent 后的 chat 页面）
        try:
            self.page.goto(self.create_url, wait_until="domcontentloaded")
        except Exception:
            pass
        self.page.wait_for_load_state("domcontentloaded")
        try:
            self.page.locator("div.agent-panel-content").first.wait_for(state="attached", timeout=8000)
        except Exception:
            pass
        # 等待 textarea 和模版卡片出现（SPA 动态渲染）
        try:
            self.page.locator("textarea").first.wait_for(
                state="visible", timeout=10000
            )
        except Exception:
            pass
        # 降级：侧边栏 SPA 导航
        if self.page.locator("textarea").count() == 0:
            nav_btn = self.page.locator("button.agent-sidebar-nav-item").filter(has_text="新建智能体")
            if nav_btn.count() > 0:
                nav_btn.first.wait_for(state="visible", timeout=5000)
                nav_btn.first.click()
                try:
                    self.page.locator("textarea").first.wait_for(state="visible", timeout=10000)
                except Exception:
                    pass
        try:
            self.page.locator("button.agent-home-template-pill").first.wait_for(
                state="visible", timeout=5000
            )
        except Exception:
            pass

    def is_agents_page(self) -> bool:
        return "/ctrl/agent/agents" in self.page.url

    def is_create_page(self) -> bool:
        return "/ctrl/agent/home" in self.page.url or self._has_create_ui()

    def _has_create_ui(self) -> bool:
        """检查是否有创建界面（textarea + 模版卡片）"""
        ta = self.page.locator("textarea[placeholder*='描述']")
        return ta.count() > 0

    # ==================== 智能体列表 ====================

    def get_agent_count(self) -> int:
        return self.page.locator("button.agent-sidebar-agent-card").count()

    def get_agent_names(self) -> list[str]:
        cards = self.page.locator("button.agent-sidebar-agent-card")
        names = []
        for i in range(cards.count()):
            # 从名称 div 直接提取，避免拼接组织标识
            name_el = cards.nth(i).locator("div.text-\\[13px\\].font-semibold").first
            if name_el.count() > 0:
                name = name_el.text_content().strip()
            else:
                # fallback: 去掉 ORG_001 和已知后缀
                text = cards.nth(i).text_content().strip()
                name = text.replace("ORG_001_new", "").replace("ORG_001", "").replace("公开", "").replace("共享", "").strip()
            if name:
                names.append(name)
        return names

    def has_agent(self, name: str) -> bool:
        names = self.get_agent_names()
        return any(name in n for n in names)

    def _scroll_sidebar_to_load(self):
        """滚动侧边栏到底部触发懒加载，再滚回顶部"""
        container = self.page.locator("div.agent-sidebar-tree")
        if container.count() > 0:
            container.first.evaluate("el => el.scrollTop = el.scrollHeight")
            self.page.wait_for_timeout(800)
            container.first.evaluate("el => el.scrollTop = 0")
            self.page.wait_for_timeout(300)

    def wait_for_agent_card(self, name: str, retries: int = 2):
        """等待 agent 卡片出现在侧边栏，滚动触发懒加载，找不到时自动刷新重试。
        返回 card locator（count > 0 表示找到），供后续操作使用。
        """
        card = self.page.locator("button.agent-sidebar-agent-card").filter(has_text=name)
        for attempt in range(retries + 1):
            # 先滚动侧边栏触发懒加载
            self._scroll_sidebar_to_load()
            if card.count() > 0:
                card.first.scroll_into_view_if_needed()
                self.page.wait_for_timeout(300)
                return card
            # 逐段向下滚动，查找未渲染的卡片
            container = self.page.locator("div.agent-sidebar-tree")
            if container.count() > 0:
                scroll_height = container.first.evaluate("el => el.scrollHeight")
                step = 200
                pos = 0
                while pos < scroll_height:
                    pos += step
                    container.first.evaluate(f"el => el.scrollTop = {pos}")
                    self.page.wait_for_timeout(200)
                    if card.count() > 0:
                        card.first.scroll_into_view_if_needed()
                        self.page.wait_for_timeout(300)
                        return card
            if attempt < retries:
                self.page.wait_for_timeout(2000)
                self.page.reload(wait_until="domcontentloaded")
                self.page.wait_for_timeout(1000)
                card = self.page.locator("button.agent-sidebar-agent-card").filter(has_text=name)
        return card

    def click_agent(self, name: str, retries: int = 2):
        """在侧边栏查找并点击 agent，找不到时自动刷新重试（参考 chat 测试实现）"""
        card = self.wait_for_agent_card(name, retries)
        if card.count() > 0:
            # force=True 避免被 hover 操作按钮遮挡
            card.first.wait_for(state="visible", timeout=5000)
            card.first.click(force=True)
            # 等待 SPA 路由跳转完成
            try:
                self.page.wait_for_url(
                    lambda url: "/ctrl/agent/chat/" in url, timeout=10000
                )
            except Exception:
                pass
            self.page.wait_for_timeout(1000)
            return True
        return False

    def click_agent_in_main(self, name: str):
        """在主内容区点击智能体卡片"""
        badge = self.page.locator(f"div.agent-badge[data-badge-name='{name}']")
        if badge.count() > 0:
            badge.first.wait_for(state="visible", timeout=5000)
            badge.first.click()
            self.page.wait_for_timeout(1000)
            return True
        return False

    # ==================== 新建智能体页面 ====================

    def get_create_textarea(self):
        return self.page.locator("textarea[placeholder*='描述']")

    def fill_create_description(self, desc: str):
        ta = self.get_create_textarea()
        if ta.count() > 0:
            ta.first.wait_for(state="visible", timeout=5000)
            ta.first.fill(desc)
            self.page.wait_for_timeout(500)

    def has_meta_agent(self) -> bool:
        """是否有 MetaAgent（自然语言创建）入口"""
        return self.get_create_textarea().count() > 0

    def get_template_cards(self):
        """获取快捷模版卡片"""
        return self.page.locator("button.agent-home-template-pill")

    def get_template_names(self) -> list[str]:
        """获取模版名称列表"""
        cards = self.get_template_cards()
        names = []
        for i in range(cards.count()):
            text = cards.nth(i).inner_text().strip()
            # 第一行是名称，后面是描述
            name = text.split("\n")[0].strip()
            if name:
                names.append(name)
        return names

    def get_template_details(self) -> list[dict]:
        """获取模版名称和描述"""
        cards = self.get_template_cards()
        details = []
        for i in range(cards.count()):
            text = cards.nth(i).inner_text().strip()
            lines = text.split("\n", 1)
            name = lines[0].strip()
            desc = lines[1].strip() if len(lines) > 1 else ""
            details.append({"name": name, "desc": desc})
        return details

    def click_template(self, name: str) -> bool:
        """点击模版卡片"""
        pills = self.page.locator("button.agent-home-template-pill")
        for i in range(pills.count()):
            if pills.nth(i).inner_text().startswith(name):
                pills.nth(i).wait_for(state="visible", timeout=5000)
                pills.nth(i).click()
                self.page.wait_for_timeout(1000)
                return True
        return False

    def has_quick_create_button(self) -> bool:
        """是否有"一键创建"按钮"""
        return self.page.get_by_role("button", name="一键创建").count() > 0

    def get_quick_create_button(self):
        """获取"一键创建"按钮"""
        return self.page.get_by_role("button", name="一键创建")

    def create_agent_ui(self, name: str, system_prompt: str = "",
                        clear_skills: bool = False) -> dict:
        """通过 UI 创建智能体（描述 → AI 生成 → 替换名称/SP → 创建）
        返回 {"status": 200, "agent_name": 实际使用的名称} 或错误信息

        Args:
            name: Agent 名称
            system_prompt: 系统提示词（空字符串则留空）
            clear_skills: 若为 True，创建前移除所有平台预选的技能
        """
        self.goto_create()

        # 等待 textarea 加载
        cards = self.page.locator("button.agent-home-template-pill")
        cards.first.wait_for(state="visible", timeout=10000)

        # 填写描述并点击一键创建（AI 生成表单；生成偶发 422 解析失败，重试最多 2 次）
        desc = system_prompt if system_prompt else "创建一个通用助手，能够回答各种问题"
        create_btn = self.page.get_by_role("button", name="创建 Agent")
        _created = False
        for _attempt in range(2):
            self.fill_create_description(desc)
            quick_btn = self.get_quick_create_button()
            if quick_btn.count() == 0:
                # 页面可能停在生成失败态，回到创建页重来
                self.goto_create()
                self.fill_create_description(desc)
                quick_btn = self.get_quick_create_button()
            quick_btn.scroll_into_view_if_needed()
            quick_btn.wait_for(state="visible", timeout=5000)
            quick_btn.click()
            try:
                create_btn.wait_for(state="visible", timeout=60000)
                _created = True
                break
            except Exception:
                # AI 生成 422/超时，等 2s 后重试触发
                self.page.wait_for_timeout(2000)
        if not _created:
            raise TimeoutError("一键创建后 AI 未生成「创建 Agent」按钮（重试 2 次仍失败）")
        self.page.wait_for_timeout(1000)

        # 替换名称
        name_input = self.page.locator("input[data-slot='input']").first
        name_input.wait_for(state="visible", timeout=15000)
        name_input.fill(name)
        self.page.wait_for_timeout(300)

        # 替换 System Prompt（包括清空）
        sp_ta = self.page.locator("textarea").first
        sp_ta.wait_for(state="visible", timeout=5000)
        sp_ta.fill(system_prompt)  # fill("") 会清空 textarea
        self.page.wait_for_timeout(300)

        # 清除平台预选的技能
        if clear_skills:
            self._clear_skill_tags()

        # 注意：一键创建流程没有模型选择器，模型由系统自动从模型库取第一个
        # 如果模型库有遗留假模型，可能选到无效模型 → 创建后需通过配置界面修改

        # 点击创建
        create_btn.scroll_into_view_if_needed()
        create_btn.wait_for(state="visible", timeout=5000)
        create_btn.click()

        # 等待跳转
        try:
            self.page.wait_for_url(
                lambda url: "/ctrl/agent/chat/" in url, timeout=15000
            )
        except Exception:
            pass

        is_chat = "/ctrl/agent/chat/" in self.page.url
        # 等待聊天输入框就绪（环境启动完成）
        if is_chat:
            ta = self.page.locator("textarea[placeholder*='发送']")
            try:
                ta.first.wait_for(state="visible", timeout=15000)
                self.page.wait_for_timeout(1000)
            except Exception:
                pass

        return {"status": 200 if is_chat else 500, "agent_name": name}

    def _clear_skill_tags(self):
        """移除创建表单中平台预选的技能标签（点 X 按钮）"""
        skill_x_btns = self.page.locator(
            "div.flex.max-w-full.items-start.gap-2 "
            "button:has(svg.lucide-x)"
        )
        count = skill_x_btns.count()
        if count > 0:
            print(f"  [clear_skill_tags] 移除 {count} 个预选技能")
            for _ in range(count):
                btns = self.page.locator(
                    "div.flex.max-w-full.items-start.gap-2 "
                    "button:has(svg.lucide-x)"
                )
                if btns.count() > 0:
                    btns.first.wait_for(state="visible", timeout=5000)
                    btns.first.click()
                    self.page.wait_for_timeout(200)

    def _select_model(self, provider: str, model_name: str):
        """在创建/编辑表单中选择模型（Radix Select 下拉）

        Args:
            provider: provider 名称（如 "deepseek-test"）
            model_name: 模型名称（如 "deepseek-v4-flash"）
        """
        target_label = f"{provider}/{model_name}"
        # 找到模型 Select 触发器（Label "模型" 旁边的 SelectTrigger）
        model_label = self.page.locator("label", has_text="模型")
        if model_label.count() == 0:
            print(f"  [select_model] 未找到模型 Label，跳过")
            return
        # SelectTrigger 是 label 的兄弟元素
        select_trigger = model_label.locator("..").locator("button[role='combobox']")
        if select_trigger.count() == 0:
            # 回退：直接找包含当前模型文本的 button
            select_trigger = model_label.locator("..").locator("button").first
        select_trigger.scroll_into_view_if_needed()
        select_trigger.wait_for(state="visible", timeout=5000)
        select_trigger.click()
        self.page.wait_for_timeout(500)
        # 在下拉面板中选择目标模型
        option = self.page.locator("[role='option']").filter(has_text=target_label)
        if option.count() > 0:
            option.first.wait_for(state="visible", timeout=5000)
            option.first.click()
            self.page.wait_for_timeout(300)
            print(f"  [select_model] 已选择模型: {target_label}")
        else:
            # 找不到目标模型，关闭下拉
            self.page.keyboard.press("Escape")
            print(f"  [select_model] 警告：未找到模型 '{target_label}'，保持当前选择")

    # ==================== 对话页面 ====================

    def is_on_chat_page(self) -> bool:
        return "/ctrl/agent/chat/" in self.page.url

    def get_chat_page_text(self) -> str:
        content = self.page.locator("div.agent-panel-content").first
        if content.count() > 0:
            return content.inner_text()
        return self.page.locator("div.agent-chat-area").inner_text()

    def send_message(self, text: str):
        ta = self.page.locator("textarea[placeholder*='发送']")
        if ta.count() == 0:
            # fallback: 任意 textarea
            ta = self.page.locator("textarea")
        ta.first.wait_for(state="visible", timeout=15000)
        ta.first.fill(text)
        ta.first.press("Enter")
        self.page.wait_for_load_state("domcontentloaded")

    def get_last_message(self) -> str:
        """获取最后一条 AI 回复"""
        messages = self.page.locator("div[role='log'] > div")
        if messages.count() == 0:
            messages = self.page.locator("div.agent-chat-area > div")
        if messages.count() > 0:
            try:
                return messages.last.text_content(timeout=5000).strip()
            except Exception:
                return ""
        return ""

    # ==================== 右侧面板（技能/文件/配置） ====================

    # ==================== 新版 6-tab Agent 配置 Modal ====================

    def _edit_agent_dialog(self):
        """新版「编辑Agent」配置对话框 locator（h2=编辑Agent 的 role=dialog）"""
        return self.page.locator("[role='dialog']").filter(
            has=self.page.locator("h2", has_text="编辑Agent")
        ).first

    def _dismiss_any_dialog(self):
        """若页面上残留 dialog/alertdialog，先按 Escape 关掉，避免叠层干扰。"""
        for _ in range(3):
            any_dlg = self.page.locator("[role='alertdialog'], [role='dialog']")
            try:
                if any_dlg.count() > 0 and any_dlg.first.is_visible():
                    self.page.keyboard.press("Escape")
                    self.page.wait_for_timeout(400)
                else:
                    break
            except Exception:
                break

    def open_agent_config_modal(self, agent_name: str):
        """打开新版 Agent 配置 modal（6-tab 配置地图）。
        返回 (modal_locator, agent_wrapper)；重试后仍失败返回 (None, agent_wrapper)。

        打开后校验 modal 确实绑定到目标 Agent（禁用的「名称」输入框值 == agent_name）。
        长时间全量跑时，侧边栏可能残留上个用例的选中态，点「智能体配置」会把 modal 绑定到
        残留/已删除的 Agent，保存时 PUT 到错误 name → 404/NOT_FOUND。校验失败即关闭重试。
        """
        for _attempt in range(3):
            modal, wrapper = self._open_config_modal_once(agent_name)
            if modal is not None and self._modal_bound_to(modal, agent_name):
                return modal, wrapper
            # 打开失败或绑定到错误 Agent：清理叠层后重试
            try:
                if modal is not None:
                    self._dismiss_modal_if_open(modal)
                else:
                    self._dismiss_any_dialog()
            except Exception:
                pass
            self.page.wait_for_timeout(800)
        return None, None

    def _open_config_modal_once(self, agent_name):
        """单次尝试：定位卡片 → 悬停 → 点「智能体配置」→ 等 modal 可见。"""
        self.goto_agents()
        card = self.wait_for_agent_card(agent_name)
        if card.count() == 0:
            return None, None
        # 若已有其它配置弹窗残留，先关闭，避免叠层
        self._dismiss_any_dialog()
        self.page.wait_for_timeout(300)
        agent_wrapper = card.first.locator(
            "xpath=ancestor::div[contains(@class,'agent-sidebar-agent')]"
        )
        agent_wrapper.hover()
        config_btn = agent_wrapper.locator('button[title="智能体配置"]')
        config_btn.wait_for(state="visible", timeout=5000)
        config_btn.click()
        modal = self._edit_agent_dialog()
        try:
            modal.wait_for(state="visible", timeout=12000)
        except Exception:
            return None, agent_wrapper
        # 等 配置地图 tab 栏渲染完成（modal 内容 API 加载）
        try:
            self.page.locator("[role='dialog'] [role='tab']").filter(
                has_text="身份与指令"
            ).first.wait_for(state="visible", timeout=8000)
        except Exception:
            pass
        self.page.wait_for_timeout(600)
        return modal, agent_wrapper

    def _modal_bound_to(self, modal, agent_name) -> bool:
        """校验配置 modal 是否绑定到目标 Agent：读取禁用的「名称」输入框值。"""
        try:
            # 重新打开时会保留上次的配置 tab；名称仅在身份页可见。
            self.switch_config_tab(modal, "身份与指令")
            name_input = modal.locator("input[placeholder*='例如 my-agent']").first
            if name_input.count() > 0 and name_input.is_visible():
                return (name_input.input_value().strip() == agent_name)
        except Exception:
            pass
        return False

    def switch_config_tab(self, modal, label: str):
        """切换 6-tab 配置地图大 tab（身份与指令/模型/能力与工具/知识与记忆/运行环境/共享与访问）。
        label 为短标签，用 strong 精确匹配，避免命中能力页内层 sub-tab。"""
        tab = modal.locator("[role='tab']").filter(
            has=self.page.locator("strong", has_text=label)
        ).first
        tab.wait_for(state="visible", timeout=8000)
        if tab.get_attribute("aria-selected") != "true":
            tab.click()
            self.page.wait_for_timeout(600)

    def identity_field(self, modal, kind: str):
        """身份与指令 tab 中的输入框 locator。kind: 'description' | 'prompt'"""
        if kind == "description":
            return modal.locator("input[placeholder*='Agent 的简短描述']").first
        if kind == "prompt":
            return modal.locator("textarea[placeholder*='自定义 Agent 提示词']").first
        return None

    def _active_main_panel(self, modal, heading: str):
        """返回 main 区中带指定 h3 标题的外层 tabpanel locator"""
        return modal.locator("[role='tabpanel']").filter(
            has=self.page.locator("h3", has_text=heading)
        ).first

    def capability_panel(self, modal, kind: str):
        """进入 能力与工具 并切到内层 绑定技能/绑定MCP/绑定Sites，返回内层 tabpanel locator。
        kind: '技能' | 'MCP' | 'Sites'
        内层 tabpanel 的 accessible-name 形如「绑定技能 1」「绑定 MCP 0」，用 name 匹配最稳。"""
        self.switch_config_tab(modal, "能力与工具")
        outer = self._active_main_panel(modal, "能力与工具")
        pattern = re.compile(rf"绑定\s*{re.escape(kind)}")
        inner_tab = outer.get_by_role("tab", name=pattern)
        inner_tab.wait_for(state="visible", timeout=8000)
        inner_tab.click()
        self.page.wait_for_timeout(700)
        panel = modal.get_by_role("tabpanel", name=pattern)
        panel.wait_for(state="visible", timeout=5000)
        return panel

    def knowledge_group(self, modal):
        """进入 知识与记忆 tab，返回「绑定知识库」候选 group（含 已选 N 项 + chips + checkbox 行）。
        结构同能力面板，可复用 _cap_* 帮助方法。"""
        self.switch_config_tab(modal, "知识与记忆")
        outer = self._active_main_panel(modal, "知识与记忆")
        group = outer.locator("[role='group']").filter(
            has=self.page.locator("strong", has_text=re.compile(r"已选\s*\d+\s*项"))
        ).first
        group.wait_for(state="visible", timeout=8000)
        return group

    def _cap_bound_names(self, panel) -> set:
        """已绑定项集合（从「移除 xxx」chips 的 aria-label 提取）"""
        bound = set()
        chips = panel.locator("button[aria-label^='移除 ']")
        for i in range(chips.count()):
            lab = chips.nth(i).get_attribute("aria-label") or ""
            bound.add(lab.replace("移除 ", "").strip())
        return bound

    def _cap_selected_count(self, panel) -> int:
        """解析「已选 N 项」数量；解析失败退回 chips 数量"""
        s = panel.locator("strong", has_text=re.compile(r"已选\s*\d+\s*项")).first
        if s.count() > 0:
            m = re.search(r"已选\s*(\d+)\s*项", s.inner_text())
            if m:
                return int(m.group(1))
        return len(self._cap_bound_names(panel))

    def pick_unbound_candidate(self, panel):
        """候选 checkbox 中挑一个未绑定的名称；没有则返回 None"""
        bound = self._cap_bound_names(panel)
        for cb in panel.get_by_role("checkbox").all():
            nm = cb.get_attribute("aria-label") or ""
            nm = nm.strip()
            if nm and nm not in bound:
                return nm
        return None

    def bind_cap_item(self, panel, name: str):
        """通过 candidate checkbox 绑定一个 item（技能/MCP/Sites/知识库共用结构）"""
        cb = panel.get_by_role("checkbox", name=name).first
        cb.scroll_into_view_if_needed()
        cb.wait_for(state="visible", timeout=5000)
        cb.click(force=True)
        self.page.wait_for_timeout(600)

    def unbind_cap_item(self, panel, name: str):
        """点击「移除 name」chip 解除绑定"""
        chip = panel.get_by_role("button", name=re.compile(rf"^移除 {re.escape(name)}$"))
        chip.first.wait_for(state="visible", timeout=5000)
        chip.first.click()
        self.page.wait_for_timeout(600)

    def save_edit_modal(self, modal, restart: bool = True, timeout_s: int = 20):
        """点击保存并处理「配置已保存…是否立即重启」弹窗。
        restart=True → 点『重启选中』；否则点『稍后』。完成后确保 modal 关闭。
        """
        save_btn = modal.get_by_role("button", name="保存")
        save_btn.wait_for(state="visible", timeout=8000)
        save_btn.click()
        self.page.wait_for_timeout(1200)
        # 等待保存结果：alertdialog（'配置已保存'）或 modal 自动关闭
        import time as _t
        alert = self.page.locator("[role='alertdialog']")
        appeared = False
        _end = _t.time() + 8
        while _t.time() < _end:
            try:
                if alert.count() > 0 and alert.first.is_visible():
                    appeared = True
                    break
            except Exception:
                pass
            try:
                if not modal.is_visible():
                    break  # 已静默关闭（无实例场景）
            except Exception:
                pass
            self.page.wait_for_timeout(400)
        if appeared:
            txt = alert.first.inner_text()
            if restart and "重启" in txt:
                rb = alert.get_by_role("button", name="重启选中")
                if rb.count() == 0:
                    rb = alert.get_by_role("button", name=re.compile("重启"))
                rb.first.wait_for(state="visible", timeout=5000)
                rb.first.click()
                self.page.wait_for_timeout(2000)
            else:
                lb = alert.get_by_role("button", name="稍后")
                if lb.count() > 0:
                    lb.first.wait_for(state="visible", timeout=5000)
                    lb.first.click()
                    self.page.wait_for_timeout(800)
        self._dismiss_modal_if_open(modal)
        return True

    def _dismiss_modal_if_open(self, modal):
        """保存后若 modal 仍停留则关闭（避免叠层影响后续操作）"""
        try:
            modal.wait_for(state="hidden", timeout=10000)
            return
        except Exception:
            pass
        try:
            cancel = modal.get_by_role("button", name="取消")
            if cancel.count() > 0 and cancel.first.is_visible():
                cancel.first.click()
                modal.wait_for(state="hidden", timeout=5000)
                return
        except Exception:
            pass
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(500)

    def close_edit_modal(self, modal):
        """点「取消」关闭编辑 modal（丢弃草稿）。
        新版若有未保存修改，会先弹「放弃未保存修改？」alertdialog，需点「放弃修改」确认。"""
        try:
            cancel = modal.get_by_role("button", name="取消")
            cancel.wait_for(state="visible", timeout=5000)
            cancel.click()
        except Exception:
            self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(700)
        # 处理「放弃未保存修改？」确认弹窗
        confirm = self.page.locator("[role='alertdialog']")
        try:
            if confirm.count() > 0 and confirm.first.is_visible():
                txt = confirm.first.inner_text()
                if "放弃" in txt:
                    btn = confirm.get_by_role("button", name="放弃修改")
                    btn.first.wait_for(state="visible", timeout=4000)
                    btn.first.click()
        except Exception:
            pass
        try:
            modal.wait_for(state="hidden", timeout=6000)
        except Exception:
            pass

    def model_panel(self, modal):
        """切换到 模型 外层 tab，返回其 tabpanel locator"""
        self.switch_config_tab(modal, "模型")
        return self._active_main_panel(modal, "模型")

    def model_selected_name(self, panel) -> str:
        """模型页中当前勾选(aria-checked=true)的模型名；未配置模型时返回 ''"""
        radios = panel.locator("button[role='radio']")
        for i in range(radios.count()):
            checked = (radios.nth(i).get_attribute("aria-checked") or "").lower()
            s = radios.nth(i).locator("strong").first
            if checked == "true" and s.count() > 0:
                return s.inner_text().strip()
        return ""

    def _model_provider_nav(self, panel):
        """「资源来源」provider 过滤导航（nav aria-label=资源来源），找不到则回退第一个 nav"""
        try:
            nav = panel.get_by_role("navigation", name="资源来源")
            if nav.count() == 0:
                nav = panel.locator("nav").first
        except Exception:
            nav = panel.locator("nav").first
        return nav

    def model_provider_buttons(self, panel) -> list:
        """返回「资源来源」provider 过滤按钮文本列表（如 ['Qwen-Test 5', 'deepseek 2']）"""
        nav = self._model_provider_nav(panel)
        out = []
        for i in range(nav.get_by_role("button").count()):
            out.append(nav.get_by_role("button").nth(i).inner_text().strip())
        return out

    def model_select_provider(self, panel, provider: str) -> bool:
        """点击 provider 过滤按钮（如 deepseek / Qwen-Test），按名称前缀匹配，命中返回 True"""
        nav = self._model_provider_nav(panel)
        btns = nav.get_by_role("button")
        for i in range(btns.count()):
            txt = btns.nth(i).inner_text().strip()
            if txt.split()[0] == provider or txt.startswith(provider + " "):
                btns.nth(i).wait_for(state="visible", timeout=6000)
                btns.nth(i).click()
                self.page.wait_for_timeout(600)
                return True
        return False

    def model_select_provider_index(self, panel, index: int):
        """点击第 index 个 provider 过滤按钮（0-based）"""
        nav = self._model_provider_nav(panel)
        btn = nav.get_by_role("button").nth(index)
        btn.wait_for(state="visible", timeout=6000)
        btn.click()
        self.page.wait_for_timeout(700)

    def model_radio_names(self, panel) -> list:
        """返回当前 radiogroup 里可见模型的名称列表"""
        names = []
        radios = panel.locator("[role='radio']")
        for i in range(radios.count()):
            s = radios.nth(i).locator("strong").first
            if s.count() > 0:
                names.append(s.inner_text().strip())
        return names

    def model_select_radio(self, panel, model_name: str) -> bool:
        """点击 radiogroup 中 strong 文本 == model_name 的 radio，成功返回 True"""
        radios = panel.locator("[role='radio']")
        for i in range(radios.count()):
            strong = radios.nth(i).locator("strong").first
            if strong.count() > 0 and strong.inner_text().strip() == model_name:
                radios.nth(i).scroll_into_view_if_needed()
                radios.nth(i).wait_for(state="visible", timeout=5000)
                radios.nth(i).click()
                self.page.wait_for_timeout(500)
                return True
        return False

    def change_model_via_config(self, agent_name: str, target_model_label: str) -> bool:
        """通过新版 6-tab 配置 modal 修改模型并保存+重启。

        Args:
            agent_name: Agent 名称
            target_model_label: 'provider/model'（如 'deepseek/deepseek-v4-flash'）

        Returns:
            True 表示切换成功并回到聊天页；False 表示失败
        """
        modal, _ = self.open_agent_config_modal(agent_name)
        if modal is None:
            print(f"  [change_model] 无法打开配置 modal: {agent_name}")
            return False
        try:
            if "/" in target_model_label:
                provider, model_name = target_model_label.split("/", 1)
            else:
                provider, model_name = "", target_model_label
            panel = self.model_panel(modal)
            if provider and not self.model_select_provider(panel, provider):
                print(f"  [change_model] 未找到 provider 过滤按钮: {provider}")
                self.close_edit_modal(modal)
                return False
            if not self.model_select_radio(panel, model_name):
                print(f"  [change_model] 未找到模型 radio: {model_name} (provider={provider})")
                self.close_edit_modal(modal)
                return False
            self.save_edit_modal(modal, restart=True)
        except Exception as e:
            print(f"  [change_model] 配置保存异常: {e}")
            self._dismiss_modal_if_open(modal)
            return False
        # 回到该 Agent 对话页并轮询聊天输入框稳定就绪
        return self._enter_chat_and_wait_ready(agent_name)

    def _enter_chat_and_wait_ready(self, agent_name: str, timeout_ms: int = 45000) -> bool:
        """重启后进入 Agent 对话页，轮询聊天输入框稳定可见（最长 timeout_ms）"""
        card = self.page.locator("button.agent-sidebar-agent-card").filter(has_text=agent_name)
        if card.count() > 0:
            try:
                card.first.scroll_into_view_if_needed()
                card.first.wait_for(state="visible", timeout=5000)
                card.first.click(force=True)
            except Exception:
                pass
        import time as _t
        _end = _t.time() + timeout_ms / 1000
        while _t.time() < _end:
            ta = self.page.locator("textarea[placeholder*='发送']")
            if ta.count() > 0 and ta.first.is_visible():
                # 等 2s 再确认仍然可见（排除闪现）
                self.page.wait_for_timeout(2000)
                if ta.count() > 0 and ta.first.is_visible():
                    return True
            # 尝试手动重连（欢迎/重连卡片）
            try:
                reconnect_area = self.page.locator("div.agent-welcome-empty")
                if reconnect_area.count() > 0 and reconnect_area.first.is_visible():
                    rbtn = reconnect_area.locator("button").first
                    if rbtn.count() > 0 and rbtn.first.is_visible():
                        rbtn.first.click()
                        self.page.wait_for_timeout(2000)
                        continue
            except Exception:
                pass
            self.page.wait_for_timeout(2000)
        return True

    def wait_for_ai_reply(self, timeout_ms: int = 30000) -> str:
        """轮询等待 AI 回复完成（不再显示"思考中"），返回最终回复文本。"""
        import time
        start = time.time()
        last_reply = ""
        stable_count = 0
        while (time.time() - start) * 1000 < timeout_ms:
            reply = self.get_last_message()
            if reply and "思考中" not in reply and len(reply) > 5:
                if reply == last_reply:
                    stable_count += 1
                    if stable_count >= 2:
                        return reply
                else:
                    stable_count = 0
                last_reply = reply
            self.page.wait_for_timeout(1000)
        return last_reply or self.get_last_message()

    def wait_for_env_ready(self, env_id: str, timeout_ms: int = 15000) -> bool:
        """轮询等待 environment 就绪（GET 返回 200）。"""
        import time
        start = time.time()
        while (time.time() - start) * 1000 < timeout_ms:
            resp = self.page.request.get(f"{self.base_url}/web/environments/{env_id}")
            if resp.status == 200:
                return True
            self.page.wait_for_timeout(1000)
        return False

    def has_skill_section(self) -> bool:
        body = self.get_chat_page_text()
        return "技能" in body

    def has_file_section(self) -> bool:
        body = self.get_chat_page_text()
        return "文件" in body

    def get_model_display(self) -> str:
        """获取当前模型名称"""
        body = self.get_chat_page_text()
        # 模型名通常在底部状态栏
        lines = body.split("\n")
        for line in lines:
            line = line.strip()
            if "/" in line and not line.startswith("http"):
                # 可能是 "provider/model" 格式
                return line
        return ""

    # ==================== API ====================

    def create_agent_api(self, name: str, system_prompt: str = "",
                         model_id: str = "", _max_retries: int = 3,
                         with_env: bool = True) -> dict:
        """通过 API 创建智能体
        1. POST /web/config/agents 创建 Agent 配置
        2. with_env=True 时 POST /web/environments 创建运行环境
        遇到 500 或假成功（success=true 但无 id）时自动重试
        """
        import json
        import time
        data = {"prompt": system_prompt, "skillIds": []}
        if model_id:
            data["modelId"] = model_id
        body = {"name": name, "data": data}

        resp = None
        for attempt in range(_max_retries):
            resp = self.page.request.post(
                f"{self.base_url}/web/config/agents",
                data=json.dumps(body),
                headers={"Content-Type": "application/json"},
            )
            # 判断是否需要重试：500 错误或假成功（200 但无 agent id）
            need_retry = False
            if resp.status >= 500:
                need_retry = True
            elif resp.status == 200:
                try:
                    rj = resp.json()
                    agent_id = (rj.get("data") or {}).get("id", "") if isinstance(rj, dict) else ""
                    if not agent_id:
                        need_retry = True
                except Exception:
                    pass
            if not need_retry:
                break
            print(f"  [create_agent_api] '{name}': status={resp.status}, 需要重试 {attempt+1}/{_max_retries}")
            if attempt < _max_retries - 1:
                time.sleep(3 * (attempt + 1))

        result = {"status": resp.status}
        try:
            resp_data = resp.json()
            result["data"] = resp_data
            success = resp_data.get("success") if isinstance(resp_data, dict) else None
            agent_id_preview = (resp_data.get("data") or {}).get("id", "") if isinstance(resp_data, dict) else ""
            print(f"  [create_agent_api] '{name}': status={resp.status}, success={success}, id={agent_id_preview[:12]}")
        except Exception:
            result["text"] = resp.text()
            print(f"  [create_agent_api] '{name}': status={resp.status}, parse_error, text={resp.text()[:200]}")
            return result

        # 创建 environment（点击 Agent 进入对话需要）
        if resp.status == 200 and isinstance(resp_data, dict):
            agent_id = (resp_data.get("data") or {}).get("id", "")
            if agent_id:
                # 创建后立即 GET 验证 agent 是否真正存在
                verify = self.page.request.get(
                    f"{self.base_url}/web/config/agents",
                    params={"name": name},
                )
                v_data = verify.json() if verify.status == 200 else {}
                v_found = bool((v_data.get("data") or {}).get("id"))
                print(f"  [create_agent_api] verify GET: status={verify.status}, found={v_found}")

                if with_env:
                    env_body = json.dumps({
                        "name": f"env-{agent_id[:8]}",
                        "agentConfigId": agent_id,
                        "autoStart": True,
                    })
                    env_resp = self.page.request.post(
                        f"{self.base_url}/web/environments",
                        data=env_body,
                        headers={"Content-Type": "application/json"},
                    )
                    result["env_status"] = env_resp.status
                    try:
                        env_data = env_resp.json()
                        env_id = (env_data.get("data") or {}).get("id", "")
                        result["env_id"] = env_id
                    except Exception:
                        pass

        return result

    def get_agents_api(self) -> list:
        """获取智能体列表 API
        返回结构: {"data": {"agents": [...], "default_agent": ...}}
        """
        resp = self.page.request.get(f"{self.base_url}/web/config/agents")
        try:
            data = resp.json()
            if isinstance(data, dict):
                inner = data.get("data", data)
                if isinstance(inner, dict):
                    return inner.get("agents", [])
                return inner if isinstance(inner, list) else []
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def delete_agent_api(self, agent_id: str, retries: int = 2) -> int:
        """删除智能体（通过 id 或 name），500 时自动重试

        返回: status code (int)
        """
        import logging
        logger = logging.getLogger("cleanup")

        for attempt in range(retries + 1):
            resp = self.page.request.delete(
                f"{self.base_url}/web/config/agents?name={agent_id}"
            )
            status = resp.status

            if status in (200, 204, 404):
                return status

            # 500 或其他错误，记录详情
            try:
                body = resp.text()[:200]
            except Exception:
                body = ""

            if status == 500 and attempt < retries:
                logger.warning(f"删除 '{agent_id}' 返回 500 (尝试 {attempt + 1}/{retries + 1})，2秒后重试。body: {body}")
                self.page.wait_for_timeout(2000)
            else:
                logger.error(f"删除 '{agent_id}' 失败: status={status}, body: {body}")
                return status

        return status

    def update_agent_api(self, agent_id: str, updates: dict) -> dict:
        """更新智能体配置"""
        import json
        resp = self.page.request.put(
            f"{self.base_url}/web/agents/{agent_id}",
            data=json.dumps(updates),
            headers={"Content-Type": "application/json"},
        )
        result = {"status": resp.status}
        try:
            result["data"] = resp.json()
        except Exception:
            result["text"] = resp.text()
        return result

    # ==================== 通用 ====================

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
                    body = resp.json()
                except Exception:
                    body = None
                collected.append({
                    "url": resp.url,
                    "status": resp.status,
                    "method": resp.request.method,
                    "body": body,
                })

        self._last_listener = on_response
        self.page.on("response", on_response)
        return collected
