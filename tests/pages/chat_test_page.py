# tests/pages/chat_test_page.py
"""对话聊天测试 Page Object — 会话管理、消息交互、文件上传、Markdown 渲染"""
from playwright.sync_api import Page


class ChatTestPage:
    """聊天页面综合测试对象"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url

    # === 导航 ===

    def goto_agent_chat(self, agent_name: str = "通用助手"):
        """进入指定 Agent 的对话页"""
        self.page.goto(f"{self.base_url}/ctrl/agent/home")
        self.page.wait_for_load_state("networkidle")
        card = self.page.locator("button.agent-sidebar-agent-card").filter(has_text=agent_name)
        if card.count() > 0:
            card.first.scroll_into_view_if_needed()
            self.page.wait_for_timeout(300)
            card.first.click()
            self.page.wait_for_timeout(2000)

    def is_chat_loaded(self) -> bool:
        """聊天界面是否加载完成（URL 不变，通过 textarea 判断）"""
        return self.page.locator("textarea").count() > 0

    # === 会话管理 ===

    def create_new_session(self):
        """点击 + 新会话"""
        btn = self.page.locator("button").filter(has_text="新会话")
        if btn.count() > 0:
            btn.first.click()
            self.page.wait_for_timeout(1500)

    def get_session_header_title(self) -> str:
        """获取当前会话标题"""
        header = self.page.locator(".chat-header-card")
        if header.count() > 0:
            return header.first.inner_text().strip()
        return ""

    def open_session_dialog(self):
        """点击会话头部打开会话列表对话框（Radix Popover）"""
        trigger = self.page.locator(".chat-header-card button[data-slot='popover-trigger']")
        if trigger.count() > 0:
            trigger.first.click()
            self.page.wait_for_timeout(1500)
        else:
            # 回退：点击整个 header card
            header = self.page.locator(".chat-header-card")
            if header.count() > 0:
                header.first.click()
                self.page.wait_for_timeout(1500)

    def is_session_dialog_open(self) -> bool:
        return self.page.locator("[role='dialog']").count() > 0

    def close_session_dialog(self):
        dialog = self.page.locator("[role='dialog']")
        if dialog.count() > 0:
            close_btn = dialog.get_by_role("button", name="Close").or_(
                dialog.get_by_role("button", name="关闭")
            )
            if close_btn.count() > 0:
                close_btn.first.click()
                self.page.wait_for_timeout(500)
            else:
                self.page.keyboard.press("Escape")
                self.page.wait_for_timeout(300)

    def get_session_titles(self) -> list[str]:
        """获取会话列表中的所有标题（排除工具栏和操作按钮）"""
        dialog = self.page.locator("[role='dialog']")
        if dialog.count() == 0:
            self.open_session_dialog()
            dialog = self.page.locator("[role='dialog']")
        # 排除工具栏按钮和 hover 操作按钮（重命名/删除）
        exclude = {"刷新会话列表", "新会话", "钉住会话面板", "Close",
                   "重命名", "删除", "关闭", "搜索会话"}
        titles = []
        btns = dialog.locator("button[title]")
        for i in range(btns.count()):
            title = btns.nth(i).get_attribute("title") or ""
            if title and title not in exclude and btns.nth(i).is_visible():
                titles.append(title)
        return titles

    def get_session_titles_via_client(self) -> list[str]:
        """通过 React client 对象获取会话标题列表（WebSocket JSON-RPC）"""
        result = self.page.evaluate("""() => {
            const header = document.querySelector('.chat-header-card');
            if (!header) return [];
            const fiberKey = Object.keys(header).find(k => k.startsWith('__reactFiber'));
            if (!fiberKey) return [];
            let fiber = header[fiberKey];
            let client = null;
            for (let i = 0; i < 30 && fiber; i++) {
                const props = fiber.memoizedProps || {};
                if (props.client && typeof props.client.listSessions === 'function') {
                    client = props.client;
                    break;
                }
                fiber = fiber.return;
            }
            if (!client) return [];
            return client.listSessions().then(resp => {
                const sessions = Array.isArray(resp?.sessions) ? resp.sessions : [];
                return sessions.map(s => s.title || '').filter(t => t.length > 0);
            }).catch(() => []);
        }""")
        return result if isinstance(result, list) else []

    def search_sessions(self, keyword: str):
        """搜索会话"""
        dialog = self.page.locator("[role='dialog']")
        inp = dialog.locator("input[placeholder*='搜索']")
        if inp.count() > 0:
            inp.first.fill(keyword)
            self.page.wait_for_timeout(500)

    def get_filtered_session_titles(self) -> list[str]:
        """获取搜索过滤后的会话标题"""
        dialog = self.page.locator("[role='dialog']")
        exclude = {"刷新会话列表", "新会话", "钉住会话面板", "Close",
                   "重命名", "删除", "关闭", "搜索会话"}
        titles = []
        btns = dialog.locator("button[title]")
        for i in range(btns.count()):
            btn = btns.nth(i)
            if btn.is_visible():
                title = btn.get_attribute("title") or ""
                if title and title not in exclude:
                    titles.append(title)
        return titles

    def click_session(self, title: str):
        """点击某个会话（仅匹配可见的会话按钮）"""
        dialog = self.page.locator("[role='dialog']")
        # 避免 CSS 选择器中直接使用标题文本（可能包含 XSS 等特殊字符）
        # 改用 filter(has_text) 匹配
        btns = dialog.locator("button[title]").filter(has_text=title)
        if btns.count() > 0:
            btns.first.click()
            self.page.wait_for_timeout(2000)

    def has_session_time_sections(self) -> bool:
        """会话列表是否有时间分区（今天/昨天/更早）"""
        dialog = self.page.locator("[role='dialog']")
        if dialog.count() == 0:
            return False
        text = dialog.first.inner_text()
        return any(section in text for section in ["今天", "昨天", "更早", "本周", "上周"])

    # === 消息发送 ===

    def send_message(self, text: str):
        """发送文本消息"""
        textarea = self.page.locator("textarea").first
        textarea.fill(text)
        textarea.press("Enter")
        self.page.wait_for_load_state("networkidle")

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
        self.page.wait_for_load_state("networkidle")

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
        """在流式响应期间点击发送/停止按钮"""
        textarea_parent = self.page.locator("textarea").locator("xpath=../../..")
        btns = textarea_parent.locator("button")
        if btns.count() >= 3:
            btns.nth(2).click()
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
        self.page.wait_for_load_state("networkidle")

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
        self.page.reload()
        self.page.wait_for_load_state("networkidle")

    # === 删除会话 ===

    def delete_session_by_title(self, title: str) -> bool:
        """通过标题删除会话，返回是否成功。
        会话删除使用 WebSocket JSON-RPC (session/delete)。
        先创建新会话使目标会话变为非活跃状态，再通过 client.deleteSession 删除。"""
        # 先创建新会话，使目标会话变为非活跃
        self.create_new_session()
        self.page.wait_for_timeout(1000)

        # 通过 React fiber 找到 client 对象并删除会话
        result = self.page.evaluate("""(targetTitle) => {
            // 1. 从 chat-header-card 找到 client
            const header = document.querySelector('.chat-header-card');
            if (!header) return {error: 'no chat-header-card'};

            const fiberKey = Object.keys(header).find(k => k.startsWith('__reactFiber'));
            if (!fiberKey) return {error: 'no fiber key'};

            let fiber = header[fiberKey];
            let client = null;
            for (let i = 0; i < 30 && fiber; i++) {
                const props = fiber.memoizedProps || {};
                if (props.client && typeof props.client.deleteSession === 'function') {
                    client = props.client;
                    break;
                }
                fiber = fiber.return;
            }
            if (!client) return {error: 'client not found'};

            // 2. 获取会话列表
            return client.listSessions().then(resp => {
                const sessions = Array.isArray(resp?.sessions) ? resp.sessions : [];
                // 3. 按标题匹配
                let match = sessions.find(s => s.title && s.title.includes(targetTitle));
                if (!match) {
                    match = sessions.find(s => s.title && targetTitle.substring(0, 6) && s.title.includes(targetTitle.substring(0, 6)));
                }
                if (!match) return {error: 'session not found', titles: sessions.map(s => s.title), target: targetTitle};

                // 4. 调用 deleteSession
                return client.deleteSession({sessionId: match.sessionId}).then(deleteResult => {
                    return {success: true, sessionId: match.sessionId, title: match.title, deleteResult: JSON.stringify(deleteResult).substring(0, 200)};
                }).catch(err => {
                    return {error: 'delete failed: ' + err.message, sessionId: match.sessionId};
                });
            }).catch(err => {
                return {error: 'listSessions failed: ' + err.message};
            });
        }""", title)

        if isinstance(result, dict) and result.get("success"):
            delete_result = result.get("deleteResult", "")
            # Check if the JSON-RPC response contains an error
            if "error" in delete_result and "Method not found" in delete_result:
                print(f"\n[delete_session_by_title] Server does not support session/delete: {delete_result}")
                return False
            if '"error"' in delete_result:
                print(f"\n[delete_session_by_title] Server error: {delete_result}")
                return False
            self.page.wait_for_timeout(1500)
            return True
        # Debug: print failure reason
        if result:
            print(f"\n[delete_session_by_title] result: {result}")
        return False
