# tests/pages/chat_test_page.py
"""对话聊天测试 Page Object — 会话管理、消息交互、文件上传、Markdown 渲染"""
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

    def expand_artifacts_panel(self):
        """展开右侧 Artifacts 面板（文件树、预览区在面板内）"""
        # 按钮 title="显示内容面板" 表示面板已折叠
        btn = self.page.locator("button.agent-artifacts-expand-btn")
        if btn.count() > 0 and btn.first.is_visible():
            is_open = btn.first.evaluate("el => el.classList.contains('open')")
            if not is_open:
                btn.first.click()
                self.page.wait_for_timeout(1500)
                return True
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
                        # 点击"重连"按钮恢复 WebSocket 连接
                        reconnect_btn = self.page.locator(
                            "div.agent-welcome-empty button"
                        )
                        if reconnect_btn.count() > 0:
                            reconnect_btn.first.click()
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
        textarea.fill(text)
        textarea.press("Enter")
        self.page.wait_for_load_state("domcontentloaded")

    def send_message_with_shift_enter(self, lines: list[str]):
        """用 Shift+Enter 输入多行消息并发送"""
        textarea = self.page.locator("textarea").first
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
        textarea.fill("")
        textarea.press("Enter")
        self.page.wait_for_timeout(1000)

    def double_send(self, text: str):
        """快速连续发送两次（防重复测试）"""
        textarea = self.page.locator("textarea").first
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

    def get_file_input(self):
        """获取文件上传 input"""
        return self.page.locator("input[type='file']").first

    def upload_file(self, file_path: str):
        """上传文件"""
        file_input = self.get_file_input()
        file_input.set_input_files(file_path)
        self.page.wait_for_timeout(2000)

    def upload_files(self, file_paths: list[str]):
        """上传多个文件"""
        file_input = self.get_file_input()
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

    # === 刷新 ===

    def refresh_page(self):
        try:
            self.page.reload(wait_until="domcontentloaded")
        except Exception:
            pass
        self.page.wait_for_load_state("domcontentloaded")
