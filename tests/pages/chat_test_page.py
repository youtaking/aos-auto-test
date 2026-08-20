# tests/pages/chat_test_page.py
"""对话聊天测试 Page Object — 会话管理、消息交互、文件上传、Markdown 渲染"""
import re
from playwright.sync_api import Page


class ChatTestPage:
    """聊天页面综合测试对象"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url

    # === 导航 ===

    def _collapse_artifacts_if_open(self):
        """如果 Artifacts 面板是展开的，折叠它（避免 resizable panel 遮挡按钮）"""
        expand_btn = self.page.locator("button.agent-artifacts-expand-btn.open")
        if expand_btn.count() > 0:
            try:
                expand_btn.first.click()
                self.page.wait_for_timeout(500)
            except Exception:
                pass

    def _expand_sidebar_if_collapsed(self):
        """如果左侧侧边栏折叠了，点击展开按钮"""
        sidebar = self.page.locator("aside.agent-sidebar")
        if sidebar.count() == 0:
            return
        is_collapsed = sidebar.first.evaluate("el => el.classList.contains('collapsed')")
        if is_collapsed:
            toggle = self.page.locator("button.agent-sidebar-toggle")
            if toggle.count() > 0:
                toggle.first.click()
                self.page.wait_for_timeout(800)

    def expand_artifacts_panel(self):
        """展开右侧 Artifacts 面板（文件树、预览区在面板内）
        注意：页面可能有多个 agent-artifacts-expand-btn（内层+外层），
        外层按钮 title="显示内容面板" 表示折叠态，"隐藏内容面板"/"收起至弹窗" 表示已展开。
        """
        # 精确匹配外层折叠按钮：title="显示内容面板" = 面板已折叠
        collapsed_btn = self.page.locator(
            "button.agent-artifacts-expand-btn[title='显示内容面板']"
        )
        if collapsed_btn.count() > 0:
            collapsed_btn.first.click()
            self.page.wait_for_timeout(1500)
            return True
        # 没有 title="显示内容面板" 的按钮 → 面板已展开，无需操作
        return False

    def goto_agent_chat(self, agent_name: str = "通用助手"):
        """进入指定 Agent 的对话页（带重试）"""
        try:
            self.page.goto(f"{self.base_url}/ctrl/agent/home", wait_until="domcontentloaded")
        except Exception:
            pass  # SPA 路由可能中断初始导航
        self.page.wait_for_load_state("domcontentloaded")
        try:
            self.page.locator("div.agent-panel-content").first.wait_for(state="attached", timeout=8000)
        except Exception:
            pass
        # 确保左侧侧边栏展开（折叠状态存储在 localStorage，前面的测试可能折叠了）
        self._expand_sidebar_if_collapsed()
        # 等待侧边栏 Agent 列表加载（API 异步返回，全量回归时可能较慢）
        for _w in range(10):
            all_cards = self.page.locator("button.agent-sidebar-agent-card")
            if all_cards.count() > 0:
                break
            self.page.wait_for_timeout(1000)
        card = self.page.locator("button.agent-sidebar-agent-card").filter(has_text=agent_name)
        if card.count() == 0:
            return  # Agent 不在列表中（可能环境未配置）
        card.first.scroll_into_view_if_needed()
        self.page.wait_for_timeout(300)
        # 点击 agent 卡片，期望导航到 chat 页
        card.first.wait_for(state="visible", timeout=5000)
        card.first.click()
        # 等待 URL 变化（离开 home 页）+ textarea 出现
        for _attempt in range(3):
            try:
                # 先等 URL 变化（最长 8 秒，全量回归时 SPA 路由可能较慢）
                self.page.wait_for_url("**/chat/**", timeout=8000)
                # 再等 textarea 出现（WebSocket 连接需要时间，给 20 秒）
                self.page.locator("textarea").first.wait_for(
                    state="visible", timeout=20000
                )
                self._collapse_artifacts_if_open()
                return  # 成功
            except Exception:
                if _attempt < 2:
                    # 重试：重新查找并点击卡片
                    card = self.page.locator("button.agent-sidebar-agent-card").filter(has_text=agent_name)
                    if card.count() > 0:
                        try:
                            card.first.click()
                        except Exception:
                            pass
                    self.page.wait_for_timeout(1500)
                else:
                    # 第三次也失败：检查是否卡在 "Agent 未连接" 状态
                    connecting = self.page.locator(".agent-welcome-empty, [class*='connecting']")
                    if connecting.count() > 0:
                        # 第一层：点击"重连"按钮
                        reconnect_btn = self.page.locator(
                            "div.agent-welcome-empty button"
                        )
                        if reconnect_btn.count() > 0:
                            reconnect_btn.first.click()
                            self.page.wait_for_timeout(5000)
                            if self.page.locator("textarea").count() > 0:
                                self._collapse_artifacts_if_open()
                                return

                        # 间隔等待，让连接充分恢复
                        self.page.wait_for_timeout(3000)

                        # 第二层：再点击 agent 卡片重新连接
                        card2 = self.page.locator("button.agent-sidebar-agent-card").filter(has_text=agent_name)
                        if card2.count() > 0:
                            card2.first.click()
                            try:
                                self.page.locator("textarea").first.wait_for(
                                    state="visible", timeout=10000
                                )
                                self._collapse_artifacts_if_open()
                                return
                            except Exception:
                                pass

                        # 间隔等待
                        self.page.wait_for_timeout(3000)

                        # 第三层：跳回 home 再重新进入
                        try:
                            self.page.goto(
                                f"{self.base_url}/ctrl/agent/home",
                                wait_until="domcontentloaded"
                            )
                        except Exception:
                            pass
                        self.page.wait_for_load_state("domcontentloaded")
                        self.page.wait_for_timeout(3000)
                        for _w in range(5):
                            if self.page.locator("button.agent-sidebar-agent-card").count() > 0:
                                break
                            self.page.wait_for_timeout(1000)
                        card3 = self.page.locator("button.agent-sidebar-agent-card").filter(has_text=agent_name)
                        if card3.count() > 0:
                            card3.first.click()
                            try:
                                self.page.locator("textarea").first.wait_for(
                                    state="visible", timeout=20000
                                )
                                self._collapse_artifacts_if_open()
                                return
                            except Exception:
                                pass
        # 最终回退
        self.page.wait_for_timeout(2000)

    def is_on_chat_page(self) -> bool:
        """当前是否在聊天页面（URL 包含 /chat/ 且有 textarea）"""
        return "/chat/" in self.page.url and self.page.locator("textarea").count() > 0

    def is_chat_loaded(self) -> bool:
        """聊天界面是否加载完成（URL 不变，通过 textarea 判断）"""
        return self.page.locator("textarea").count() > 0

    # === 会话管理 ===（适配 SessionSidebar，替代旧 ChatHeader Popover）

    # --- 侧边栏定位辅助 ---

    def _get_sidebar(self):
        """获取 SessionSidebar 根元素"""
        return self.page.locator(
            "div.flex.min-h-0.flex-col.overflow-hidden.rounded-xl"
        ).first

    def _get_session_nav(self):
        """获取会话列表 nav 元素（SidebarSessionList 渲染的 <nav>）"""
        return self.page.locator("nav[aria-label]").filter(
            has=self.page.locator("span.truncate")
        )

    def _get_new_session_button(self):
        """获取"新会话"按钮（Plus 图标，title/aria-label='新会话'）"""
        return self.page.locator(
            "button[title='新会话'], button[aria-label='新会话']"
        )

    def create_new_session(self):
        """点击侧边栏 + 按钮新建会话"""
        new_btn = self._get_new_session_button()
        if new_btn.count() > 0 and new_btn.first.is_visible():
            new_btn.first.click()
            self.page.wait_for_timeout(1500)
        else:
            self.page.wait_for_timeout(1000)

    def get_session_header_title(self) -> str:
        """获取当前活跃会话标题（侧边栏中 bg-brand/8 高亮的会话）"""
        # 精确匹配：bg-brand/8 表示活跃会话（用属性子串选择器避免 CSS 转义问题）
        active = self.page.locator("div[class*='bg-brand/8'] span.truncate")
        if active.count() > 0:
            title = active.first.inner_text().strip()
            if title:
                return title
        # 回退：nav 中第一个会话按钮的 span 文本
        nav = self._get_session_nav()
        if nav.count() > 0:
            first_span = nav.locator("button span.truncate").first
            if first_span.count() > 0:
                return first_span.inner_text().strip()
        return ""

    def open_session_dialog(self):
        """等待侧边栏会话列表可见（新 UI 侧边栏常驻，无需点击打开）"""
        try:
            self.page.locator("nav[aria-label] button span.truncate").first.wait_for(
                state="visible", timeout=5000
            )
        except Exception:
            self.page.wait_for_timeout(1000)

    def is_session_dialog_open(self) -> bool:
        """侧边栏会话列表是否可见（新 UI 始终可见）"""
        return self.page.locator("nav[aria-label] button span.truncate").count() > 0

    def close_session_dialog(self):
        """关闭会话对话框（新 UI 侧边栏常驻，no-op）"""
        pass

    def get_session_titles(self) -> list[str]:
        """获取侧边栏会话列表中的所有标题（读取 DOM textContent，不受 CSS truncate 影响）"""
        nav = self._get_session_nav()
        if nav.count() == 0:
            self.open_session_dialog()
            nav = self._get_session_nav()
        titles = []
        spans = nav.locator("button span.truncate")
        for i in range(spans.count()):
            try:
                title = spans.nth(i).inner_text(timeout=2000).strip()
                if title:
                    titles.append(title)
            except Exception:
                pass  # 跳过不可见或已卸载的元素（ScrollArea 虚拟渲染）
        return titles

    def search_sessions(self, keyword: str):
        """在侧边栏搜索框中输入关键词过滤会话"""
        search_input = self.page.locator(
            "input[aria-label*='搜索'], input[placeholder*='搜索']"
        )
        if search_input.count() > 0:
            search_input.first.fill(keyword)
            self.page.wait_for_timeout(500)

    def get_filtered_session_titles(self) -> list[str]:
        """获取搜索过滤后的会话标题（与 get_session_titles 相同，过滤由前端完成）"""
        return self.get_session_titles()

    def click_session(self, title: str):
        """点击侧边栏中指定标题的会话（优先精确匹配，回退前缀匹配）"""
        nav = self._get_session_nav()
        # 精确匹配（DOM textContent 包含完整标题，即使视觉被 truncate 截断）
        btn = nav.locator("button").filter(has_text=title)
        if btn.count() == 0:
            # 回退：取标题前 6 字符做前缀匹配
            prefix = title[:6] if len(title) >= 6 else title
            btn = nav.locator("button").filter(has_text=prefix)
        if btn.count() > 0:
            btn.first.click()
            self.page.wait_for_timeout(2000)

    def has_session_time_sections(self) -> bool:
        """侧边栏会话列表是否有时间分区标签（今天/昨天/更早）"""
        nav = self._get_session_nav()
        if nav.count() == 0:
            return False
        # 时间分区标签：text-[10px] uppercase 样式的 span
        labels = nav.locator("span.uppercase")
        for i in range(labels.count()):
            text = labels.nth(i).inner_text().strip()
            if text in ("今天", "昨天", "更早", "TODAY", "YESTERDAY", "EARLIER"):
                return True
        # 回退：检查 nav 全文
        text = nav.first.inner_text()
        return any(s in text for s in ["今天", "昨天", "更早"])

    def get_session_titles_via_client(self) -> list[str]:
        """通过 React fiber 获取会话标题列表。
        从 SessionSidebar 的 sessions prop 或 chatState.sessions 获取。"""
        result = self.page.evaluate("""() => {
            const sidebar = document.querySelector('div.flex.min-h-0.flex-col.overflow-hidden.rounded-xl');
            const target = sidebar || document.querySelector('nav[aria-label]');
            if (!target) return [];
            const fiberKey = Object.keys(target).find(k => k.startsWith('__reactFiber'));
            if (!fiberKey) return [];
            let fiber = target[fiberKey];

            for (let i = 0; i < 40 && fiber; i++) {
                const props = fiber.memoizedProps || {};
                if (Array.isArray(props.sessions) && props.sessions.length > 0) {
                    return props.sessions
                        .map(s => (s.title || '').trim())
                        .filter(t => t.length > 0);
                }
                fiber = fiber.return;
            }
            return [];
        }""")
        return result if isinstance(result, list) else []

    def delete_session_by_title(self, title: str) -> bool:
        """通过标题删除会话。
        使用 WebSocket JSON-RPC (delete_session action)。
        先创建新会话使目标会话变为非活跃状态，再通过 onDeleteSession 回调删除。"""
        # 先创建新会话，使目标会话变为非活跃
        self.create_new_session()
        self.page.wait_for_timeout(1000)

        # 通过 React fiber 找到 onDeleteSession 回调和 sessions 数组
        result = self.page.evaluate("""(targetTitle) => {
            const sidebar = document.querySelector('div.flex.min-h-0.flex-col.overflow-hidden.rounded-xl');
            const target = sidebar || document.querySelector('nav[aria-label]');
            if (!target) return {error: 'no sidebar found'};

            const fiberKey = Object.keys(target).find(k => k.startsWith('__reactFiber'));
            if (!fiberKey) return {error: 'no fiber key'};

            let fiber = target[fiberKey];
            let onDeleteSession = null;
            let sessions = null;
            for (let i = 0; i < 40 && fiber; i++) {
                const props = fiber.memoizedProps || {};
                if (typeof props.onDeleteSession === 'function') {
                    onDeleteSession = props.onDeleteSession;
                }
                if (Array.isArray(props.sessions) && props.sessions.length > 0) {
                    sessions = props.sessions;
                }
                if (onDeleteSession && sessions) break;
                fiber = fiber.return;
            }

            if (!onDeleteSession) return {error: 'onDeleteSession callback not found'};
            if (!sessions || sessions.length === 0) return {error: 'sessions array not found or empty'};

            // 找到匹配的会话
            let match = sessions.find(s => s.title && s.title.includes(targetTitle));
            if (!match) {
                const prefix = targetTitle.substring(0, 8);
                match = sessions.find(s => s.title && s.title.includes(prefix));
            }
            if (!match) return {error: 'session not found', titles: sessions.map(s => s.title), target: targetTitle};

            // 调用删除回调
            try {
                onDeleteSession(match.sessionId);
                return {success: true, sessionId: match.sessionId, title: match.title};
            } catch (err) {
                return {error: 'delete callback failed: ' + err.message, sessionId: match.sessionId};
            }
        }""", title)

        if isinstance(result, dict) and result.get("success"):
            self.page.wait_for_timeout(1500)
            return True
        if result:
            print(f"\n[delete_session_by_title] result: {result}")
        return False

    # === 消息发送 ===

    def send_message(self, text: str):
        """发送文本消息"""
        textarea = self.page.locator("textarea").first
        textarea.wait_for(state="visible", timeout=10000)
        textarea.fill(text)
        textarea.press("Enter")
        self.page.wait_for_load_state("domcontentloaded")

    def send_message_with_shift_enter(self, lines: list[str]):
        """用 Shift+Enter 输入多行消息并发送"""
        textarea = self.page.locator("textarea").first
        textarea.wait_for(state="visible", timeout=10000)
        textarea.click()
        for i, line in enumerate(lines):
            textarea.press_sequentially(line, delay=20)
            if i < len(lines) - 1:
                textarea.press("Shift+Enter")
        self.page.wait_for_timeout(300)
        textarea.press("Enter")
        self.page.wait_for_load_state("domcontentloaded")

    def get_textarea_value(self) -> str:
        return self.page.locator("textarea").first.input_value()

    def is_send_button_disabled(self) -> bool:
        """发送按钮是否禁用"""
        textarea_parent = self.page.locator("textarea").locator("xpath=../../..")
        btns = textarea_parent.locator("button")
        # Btn 2 is the send button (svg, no text)
        if btns.count() >= 3:
            return btns.nth(2).is_disabled()
        return True

    def is_skill_button_disabled(self) -> bool:
        """技能按钮是否禁用（流式响应期间应禁用）"""
        textarea_parent = self.page.locator("textarea").locator("xpath=../../..")
        btns = textarea_parent.locator("button")
        if btns.count() >= 1:
            return btns.nth(0).is_disabled()
        return False

    def click_send_button_during_streaming(self):
        """在流式响应期间点击停止生成按钮"""
        # 优先用图标精确匹配停止按钮（Square 图标）
        stop_btn = self.page.locator("button:has(svg.lucide-square)")
        if stop_btn.count() > 0:
            stop_btn.first.click()
            self.page.wait_for_timeout(2000)
            return
        # fallback：从 textarea 向上找编辑区容器，取其中的按钮
        textarea_parent = self.page.locator("textarea").locator("xpath=../..")
        btns = textarea_parent.locator("button")
        if btns.count() > 0:
            btns.first.click()
            self.page.wait_for_timeout(2000)

    def try_send_empty(self):
        """尝试发送空消息"""
        textarea = self.page.locator("textarea").first
        textarea.wait_for(state="visible", timeout=10000)
        textarea.fill("")
        textarea.press("Enter")
        self.page.wait_for_timeout(1000)

    def double_send(self, text: str):
        """快速连续发送两次（防重复测试）"""
        textarea = self.page.locator("textarea").first
        textarea.wait_for(state="visible", timeout=10000)
        textarea.fill(text)
        textarea.press("Enter")
        self.page.wait_for_timeout(200)
        textarea.press("Enter")
        self.page.wait_for_load_state("domcontentloaded")

    # === 消息计数 ===

    def get_chat_messages_text(self) -> str:
        """获取聊天消息区域的所有文本（仅消息内容，不含侧边栏/导航）"""
        # role='log' 是消息列表容器，包含实际的聊天消息
        log_area = self.page.locator("div[role='log']")
        if log_area.count() > 0:
            return log_area.first.inner_text()
        # 回退：agent-chat-area 去掉 header
        chat_area = self.page.locator("div.agent-chat-area")
        if chat_area.count() > 0:
            return chat_area.first.inner_text()
        return ""

    def get_user_message_count(self) -> int:
        """获取用户消息气泡数量"""
        # User messages are typically in specific containers
        messages = self.page.locator("div[role='log'] > div")
        return messages.count()

    # === Markdown 渲染检查 ===

    def has_heading(self) -> bool:
        return self.page.locator("h1, h2, h3, h4").count() > 0

    def has_bold(self) -> bool:
        return self.page.locator("strong, b").count() > 0

    def has_italic(self) -> bool:
        return self.page.locator("em, i").count() > 0

    def has_ordered_list(self) -> bool:
        return self.page.locator("ol").count() > 0

    def has_unordered_list(self) -> bool:
        return self.page.locator("ul").count() > 0

    def has_link(self) -> bool:
        return self.page.locator("a[href]").count() > 0

    def has_code_block(self) -> bool:
        return self.page.locator("pre").count() > 0

    def has_code_with_highlight(self) -> bool:
        """代码块是否有语法高亮（检查 code 和父 pre 的 class）"""
        code = self.page.locator("pre code")
        if code.count() == 0:
            return False
        # 检查 code 元素自身的 class
        code_cls = code.first.get_attribute("class") or ""
        # 检查父 pre 元素的 class（shiki/highlight.js 常在 pre 上标注 language-）
        pre = self.page.locator("pre").first
        pre_cls = pre.get_attribute("class") or "" if pre.count() > 0 else ""
        combined = f"{code_cls} {pre_cls}"
        # hljs / prism / shiki / language- 等常见高亮库
        return any(lib in combined for lib in ["hljs", "prism", "shiki", "highlight", "language-"])

    def has_table(self) -> bool:
        return self.page.locator("table").count() > 0

    def get_code_block_style(self) -> dict:
        """获取代码块的 CSS 样式（max-height, overflow 等）"""
        pre = self.page.locator("pre").first
        if pre.count() == 0:
            return {}
        return pre.evaluate("""el => {
            const style = window.getComputedStyle(el);
            return {
                maxHeight: style.maxHeight,
                overflow: style.overflow,
                overflowY: style.overflowY,
                height: el.offsetHeight
            };
        }""")

    # === XSS 检查 ===

    def check_xss_safe(self, script_text: str) -> bool:
        """发送 XSS payload 后检查是否安全"""
        self.send_message(script_text)
        # 检查页面是否弹出了 alert dialog
        had_alert = False
        self.page.on("dialog", lambda d: setattr(d, '_handled', True) or d.dismiss())
        # 检查 script 文本是否作为纯文本显示
        body_text = self.page.locator("body").inner_text()
        return script_text in body_text or "&lt;script&gt;" in body_text

    # === 文件上传 ===

    def _get_upload_button(self):
        """获取文件树头部的"上传"按钮（lucide-upload 图标，无 title/aria-label）"""
        return self.page.locator("svg.lucide-upload").locator("xpath=ancestor::button")

    def _get_file_input(self):
        """获取隐藏的文件上传 input[type=file]（通过上传按钮所在的 panel 内查找）"""
        upload_btn = self._get_upload_button()
        if upload_btn.count() == 0:
            return None
        # 在上传按钮的最近共同祖先中查找隐藏 file input
        panel = upload_btn.first.locator("xpath=ancestor::div[@data-panel='true']")
        if panel.count() == 0:
            panel = upload_btn.first.locator("xpath=ancestor::div[contains(@class,'agent-panel')]")
        if panel.count() > 0:
            inp = panel.locator("input[type='file']")
            if inp.count() > 0:
                return inp.first
        # fallback: 全局查找隐藏 file input
        inp = self.page.locator("input[type='file'][style*='display: none'], input[type='file'][style*='display:none']")
        if inp.count() > 0:
            return inp.first
        return self.page.locator("input[type='file']").first

    def upload_file(self, file_path: str):
        """通过 UI 上传文件 — 直接操作隐藏 file input，避免点击被分隔条拦截
        自动展开右侧面板（如果未展开）"""
        upload_btn = self._get_upload_button()
        if upload_btn.count() == 0 or not upload_btn.first.is_visible():
            self.expand_artifacts_panel()
        upload_btn.wait_for(state="visible", timeout=5000)
        file_input = self._get_file_input()
        file_input.set_input_files(file_path)
        self.page.wait_for_timeout(2000)

    def upload_files(self, file_paths: list[str]):
        """通过 UI 上传多个文件 — 直接操作隐藏 file input"""
        upload_btn = self._get_upload_button()
        if upload_btn.count() == 0 or not upload_btn.first.is_visible():
            self.expand_artifacts_panel()
        upload_btn.wait_for(state="visible", timeout=5000)
        file_input = self._get_file_input()
        file_input.set_input_files(file_paths)
        self.page.wait_for_timeout(2000)

    def has_file_preview(self) -> bool:
        """是否有文件预览区域"""
        # 检查上传后的预览元素
        preview = self.page.locator("[data-slot='file-item'], [data-slot='attachment']")
        if preview.count() == 0:
            preview = self.page.locator("div[data-file-preview], img[alt*='preview']")
        return preview.count() > 0

    def has_file_error(self) -> bool:
        """是否有文件错误提示"""
        error = self.page.locator("[role='alert'], p.text-red-500, p.text-destructive")
        return error.count() > 0

    # === 文件树操作 ===

    def get_file_tree_item(self, file_name: str):
        """获取文件树中的指定文件项
        真实 DOM: role='treeitem'，accessible name 为文件名
        """
        return self.page.get_by_role("treeitem", name=file_name)

    def has_file_in_tree(self, file_name: str) -> bool:
        """检查文件是否在文件树中"""
        item = self.get_file_tree_item(file_name)
        return item.count() > 0

    def wait_for_file_in_tree(self, file_name: str, timeout_ms: int = 10000) -> bool:
        """等待文件出现在文件树中"""
        for _ in range(timeout_ms // 800):
            if self.has_file_in_tree(file_name):
                return True
            self.page.wait_for_timeout(800)
        return self.has_file_in_tree(file_name)

    def delete_file(self, file_name: str) -> bool:
        """删除文件树中的文件

        操作流程：hover 文件项 → 点击删除按钮 → 确认对话框 → 点击确认

        Returns:
            True 如果删除成功，False 如果文件不存在或删除失败
        """
        file_item = self.get_file_tree_item(file_name)
        if file_item.count() == 0:
            return False

        # hover 文件项以显示操作按钮
        file_item.first.scroll_into_view_if_needed()
        file_item.first.hover()
        self.page.wait_for_timeout(300)

        # 找到删除按钮（文件项内的第二个 button，有 hover:text-status-error 样式）
        # 使用 CSS 选择器精确定位：文件项内 actions 区域的最后一个按钮
        delete_btn = file_item.first.locator("button").last
        delete_btn.wait_for(state="visible", timeout=3000)
        delete_btn.click()

        # 等待确认对话框出现
        confirm_dialog = self.page.locator("div[role='alertdialog']")
        confirm_dialog.wait_for(state="visible", timeout=5000)

        # 点击确认删除按钮
        confirm_btn = confirm_dialog.locator("button").filter(has_text="删除").last
        confirm_btn.wait_for(state="visible", timeout=3000)
        confirm_btn.click()

        # 等待对话框关闭
        confirm_dialog.wait_for(state="hidden", timeout=5000)

        # 等待文件从树中消失
        for _ in range(10):
            if not self.has_file_in_tree(file_name):
                return True
            self.page.wait_for_timeout(500)

        return not self.has_file_in_tree(file_name)

    def get_all_files_in_tree(self) -> list[str]:
        """获取文件树中所有文件的名称列表
        真实 DOM: role='treeitem'，accessible name 为文件名
        """
        items = self.page.get_by_role("treeitem")
        count = items.count()
        names = []
        for i in range(count):
            name = items.nth(i).inner_text().strip()
            if name:
                names.append(name)
        return names

    # === 模型操作 ===

    def get_current_model_name(self) -> str:
        """获取当前选中模型名称（从 composer meta 区域的 span[title] 读取）"""
        composer_meta = self.page.locator("div.chat-composer-meta")
        if composer_meta.count() == 0:
            return ""
        model_span = composer_meta.locator("span[title]")
        if model_span.count() == 0:
            return ""
        return (model_span.first.get_attribute("title")
                or model_span.first.inner_text().strip())

    def open_model_selector(self) -> bool:
        """打开模型选择器下拉列表，返回是否成功"""
        composer_meta = self.page.locator("div.chat-composer-meta")
        if composer_meta.count() == 0:
            return False
        model_span = composer_meta.locator("span[title]").first
        if model_span.count() == 0:
            return False
        model_span.click()
        self.page.wait_for_timeout(800)
        return True

    def get_model_options(self) -> list[str]:
        """获取模型选择器下拉选项列表（需要先调用 open_model_selector）"""
        # 常见的下拉容器选择器
        options = self.page.locator(
            "div[role='listbox'] [role='option'], "
            "div[role='menu'] [role='menuitem'], "
            "div[data-radix-select-content] [role='option']"
        )
        result = []
        for i in range(options.count()):
            text = options.nth(i).inner_text(timeout=2000).strip()
            if text:
                result.append(text)
        return result

    def select_model(self, model_name: str) -> bool:
        """在已打开的模型选择器中选择指定模型"""
        option = self.page.locator(
            f"[role='option'], [role='menuitem']"
        ).filter(has_text=model_name)
        if option.count() > 0:
            option.first.click()
            self.page.wait_for_timeout(500)
            return True
        return False

    def close_model_selector(self):
        """关闭模型选择器（按 Escape）"""
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(300)

    # === Slash 命令 / @ 引用 ===

    def type_slash_command(self) -> bool:
        """在输入框输入 / 触发命令候选列表"""
        textarea = self.page.locator("textarea").first
        textarea.wait_for(state="visible", timeout=10000)
        textarea.click()
        textarea.fill("")
        textarea.press_sequentially("/", delay=50)
        self.page.wait_for_timeout(800)
        return True

    def has_slash_popup(self) -> bool:
        """是否有 Slash 命令候选列表弹出
        真实 DOM: div.rounded-xl 内包含 /commandName 按钮，无 role/data-slot 属性
        """
        # 检测方式：查找文本以 / 开头的按钮（命令候选项）
        slash_buttons = self.page.locator(
            "button:visible"
        ).filter(has_text=re.compile(r"^/[a-z]"))
        return slash_buttons.count() > 0

    def type_at_reference(self) -> bool:
        """在输入框输入 @ 触发文件引用候选列表"""
        textarea = self.page.locator("textarea").first
        textarea.wait_for(state="visible", timeout=10000)
        textarea.click()
        textarea.fill("")
        textarea.press_sequentially("@", delay=50)
        self.page.wait_for_timeout(800)
        return True

    def has_at_popup(self) -> bool:
        """是否有 @ 文件引用候选列表弹出
        真实 DOM: <dialog> 元素，标题为"选择文件"
        """
        dialog = self.page.get_by_role("dialog")
        if dialog.count() == 0:
            return False
        # 检查是否包含"选择文件"标题
        heading = dialog.get_by_role("heading", name="选择文件")
        return heading.count() > 0 and heading.first.is_visible()

    # === 工具栏按钮 ===

    def click_skill_button(self):
        """点击输入框左侧"技能"按钮"""
        btn = self.page.get_by_role("button", name="技能")
        if btn.count() > 0:
            btn.first.click(force=True)
            self.page.wait_for_timeout(800)

    def click_file_button(self):
        """点击输入框左侧"文件"按钮"""
        btn = self.page.get_by_role("button", name="文件")
        # 排除 Artifacts 面板中的"文件"Tab
        input_area = self.page.locator("textarea").locator("xpath=../../..")
        file_btns = input_area.locator("button").filter(has_text="文件")
        if file_btns.count() > 0:
            file_btns.first.click(force=True)
            self.page.wait_for_timeout(800)
        elif btn.count() > 0:
            btn.first.click(force=True)
            self.page.wait_for_timeout(800)

    def has_popup_or_panel(self) -> bool:
        """点击工具栏按钮后是否弹出了面板/列表"""
        popup = self.page.locator(
            "div[role='dialog'], div[role='listbox'], div[role='menu'], "
            "div[data-slot='popover'], div[class*='popover']"
        )
        if popup.count() > 0:
            return popup.first.is_visible()
        return False

    # === Artifacts 面板 Tabs ===

    def click_artifacts_tab(self, tab_name: str):
        """点击 Artifacts 面板中的 Tab（文件/站点/定时任务/发布视图）"""
        tab = self.page.get_by_role("button", name=tab_name)
        if tab.count() > 0:
            tab.first.click(force=True)
            self.page.wait_for_timeout(800)

    def is_artifacts_tab_active(self, tab_name: str) -> bool:
        """检查指定 Artifacts Tab 是否处于活跃状态"""
        tab = self.page.get_by_role("button", name=tab_name)
        if tab.count() == 0:
            return False
        # 检查 aria-selected 或 active 样式
        selected = tab.first.get_attribute("aria-selected")
        if selected == "true":
            return True
        # 回退：检查 data-state="active"
        state = tab.first.get_attribute("data-state")
        return state == "active"

    def has_file_tree(self) -> bool:
        """Artifacts 文件 Tab 中是否有文件树"""
        tree = self.page.locator("div[role='tree']")
        return tree.count() > 0 and tree.first.is_visible()

    def has_scheduled_tasks_content(self) -> bool:
        """定时任务 Tab 是否有内容（列表或空状态提示）"""
        # 检查是否有定时任务相关的文本
        body = self.page.locator("body").inner_text()
        return "定时任务" in body or "暂无" in body or "创建" in body

    # === 空状态 / 加载状态 ===

    def has_empty_state(self) -> bool:
        """新会话是否显示空状态（"开始对话"标题）"""
        heading = self.page.get_by_role("heading", name="开始对话")
        return heading.count() > 0 and heading.first.is_visible()

    def has_hint_text(self) -> bool:
        """是否有输入提示文字（Enter 发送，Shift+Enter 换行）"""
        body = self.page.locator("body").inner_text()
        return "Enter 发送" in body and "Shift+Enter" in body

    def has_loading_spinner(self) -> bool:
        """是否有加载中的 Spinner 或骨架屏"""
        spinner = self.page.locator(
            "[role='progressbar'], div.animate-spin, "
            "[data-slot='spinner'], div[class*='connecting']"
        )
        return spinner.count() > 0

    def has_reconnect_button(self) -> bool:
        """是否有手动重连按钮"""
        btn = self.page.locator(
            "div.agent-welcome-empty button, "
            "button:has-text('重新连接'), button:has-text('重连')"
        )
        return btn.count() > 0

    # === Token 用量 ===

    def get_token_usage_text(self) -> str:
        """获取消息区域中的 Token 用量文本"""
        log_area = self.page.locator("div[role='log']")
        if log_area.count() == 0:
            return ""
        # Token 用量通常在最后一条消息的底部
        text = log_area.first.inner_text()
        # 查找包含 "token" 或 "tokens" 的行
        for line in text.split("\n"):
            line_lower = line.lower().strip()
            if "token" in line_lower and any(c.isdigit() for c in line):
                return line.strip()
        return ""

    def has_token_display(self) -> bool:
        """消息区域是否显示 Token 用量信息"""
        token_text = self.get_token_usage_text()
        if token_text:
            return True
        # 回退：检查 DOM 中是否有 token 相关的元素
        token_el = self.page.locator(
            "[class*='token'], [data-slot*='token'], "
            "span:has-text('tokens'), span:has-text('Tokens')"
        )
        return token_el.count() > 0

    # === 侧边栏折叠/展开 ===

    def collapse_sidebar(self) -> bool:
        """折叠左侧侧边栏"""
        collapse_btn = self.page.locator(
            "button[title*='收起'], button[aria-label*='收起']"
        )
        if collapse_btn.count() > 0:
            collapse_btn.first.click()
            self.page.wait_for_timeout(800)
            return True
        return False

    def expand_sidebar(self) -> bool:
        """展开左侧侧边栏"""
        expand_btn = self.page.locator(
            "button[title*='展开'], button[aria-label*='展开'], "
            "button.agent-sidebar-toggle"
        )
        if expand_btn.count() > 0:
            expand_btn.first.click()
            self.page.wait_for_timeout(800)
            return True
        return False

    def is_sidebar_expanded(self) -> bool:
        """左侧侧边栏是否处于展开状态"""
        sidebar = self.page.locator("aside.agent-sidebar")
        if sidebar.count() == 0:
            return False
        return sidebar.first.is_visible()

    # === Action Error Banner ===

    def has_action_error_banner(self) -> bool:
        """是否有 Action Error 错误 Banner（排除 toast/notification 等非错误元素）"""
        banner = self.page.locator(
            "div[class*='error-banner'], div[class*='transient-error'], "
            "div[class*='action-error'], div[class*='chat-error']"
        )
        if banner.count() > 0:
            return banner.first.is_visible()
        return False

    # === 刷新 ===

    def refresh_page(self):
        try:
            self.page.reload(wait_until="domcontentloaded")
        except Exception:
            pass
        self.page.wait_for_load_state("domcontentloaded")
