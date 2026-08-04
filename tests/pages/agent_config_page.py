# tests/pages/agent_config_page.py
"""智能体配置 Page Object — 基于真实 DOM 结构编写"""
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
        # 使用 /ctrl/agent/home（与 chat 测试一致），侧边栏更可靠
        self.page.goto(self.create_url)
        self.page.wait_for_load_state("networkidle")

    def goto_create(self):
        """导航到新建智能体页面（直接 URL 导航，不依赖侧边栏按钮）"""
        if "/ctrl/agent/home" in self.page.url:
            # 已在创建页面，先导航离开再回来确保 SPA 状态重置
            self.page.goto(self.agents_url)
            self.page.wait_for_load_state("networkidle")
        # 直接 URL 导航到创建页面（比侧边栏按钮更可靠，尤其在删除 agent 后的 chat 页面）
        self.page.goto(self.create_url)
        self.page.wait_for_load_state("networkidle")
        # 等待 textarea 和模版卡片出现（SPA 动态渲染）
        try:
            self.page.locator("textarea").first.wait_for(
                state="visible", timeout=10000
            )
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
                self.page.reload(wait_until="networkidle")
                self.page.wait_for_timeout(1000)
                card = self.page.locator("button.agent-sidebar-agent-card").filter(has_text=name)
        return card

    def click_agent(self, name: str, retries: int = 2):
        """在侧边栏查找并点击 agent，找不到时自动刷新重试（参考 chat 测试实现）"""
        card = self.wait_for_agent_card(name, retries)
        if card.count() > 0:
            # force=True 避免被 hover 操作按钮遮挡
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

        # 填写描述并点击一键创建
        desc = system_prompt if system_prompt else "创建一个通用助手，能够回答各种问题"
        self.fill_create_description(desc)
        quick_btn = self.get_quick_create_button()
        quick_btn.scroll_into_view_if_needed()
        quick_btn.click()

        # 等待 AI 生成表单出现
        create_btn = self.page.get_by_role("button", name="创建 Agent")
        create_btn.wait_for(state="visible", timeout=90000)
        self.page.wait_for_timeout(1000)

        # 替换名称
        name_input = self.page.locator("input[data-slot='input']").first
        name_input.wait_for(state="visible", timeout=15000)
        name_input.fill(name)
        self.page.wait_for_timeout(300)

        # 替换 System Prompt（包括清空）
        sp_ta = self.page.locator("textarea").first
        sp_ta.fill(system_prompt)  # fill("") 会清空 textarea
        self.page.wait_for_timeout(300)

        # 清除平台预选的技能
        if clear_skills:
            self._clear_skill_tags()

        # 点击创建
        create_btn.scroll_into_view_if_needed()
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
                    btns.first.click()
                    self.page.wait_for_timeout(200)

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
        if ta.count() > 0:
            ta.first.fill(text)
            ta.first.press("Enter")
            self.page.wait_for_load_state("networkidle")

    def get_last_message(self) -> str:
        """获取最后一条 AI 回复"""
        messages = self.page.locator("div[role='log'] > div")
        if messages.count() == 0:
            messages = self.page.locator("div.agent-chat-area > div")
        if messages.count() > 0:
            return messages.last.text_content().strip()
        return ""

    # ==================== 右侧面板（技能/文件/配置） ====================

    def open_agent_config_modal(self, agent_name: str):
        """打开 Agent 配置 modal 并等待内容加载完成。
        返回 (modal, agent_wrapper) 元组。"""
        card = self.wait_for_agent_card(agent_name)
        if card.count() == 0:
            return None, None
        agent_wrapper = card.first.locator(
            "xpath=ancestor::div[contains(@class,'agent-sidebar-agent')]"
        )
        agent_wrapper.hover()
        config_btn = agent_wrapper.locator('button[title="智能体配置"]')
        config_btn.click()
        modal = self.page.locator("div.absolute.inset-0.z-50")
        modal.wait_for(state="visible", timeout=10000)
        # 等待 modal 内容加载（API 请求完成）
        try:
            self.page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        self.page.wait_for_timeout(1000)
        return modal, agent_wrapper

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
                         model_id: str = "", _max_retries: int = 3) -> dict:
        """通过 API 创建智能体（含 environment）
        1. POST /web/config/agents 创建 Agent 配置
        2. POST /web/environments 创建运行环境
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
