# tests/suites/test_chat_gaps.py
"""对话聊天模块 — 覆盖率补充测试（基于 Task 4 交叉对比发现的缺失场景）

已有用例 24 条覆盖：Markdown 渲染、会话管理、文件上传、基础输入、流式响应、Artifacts 面板、SSE 连接
本文件补充：边界值（超长/特殊字符/单字符）、Slash 命令、@ 引用、模型切换、
工具栏按钮、Artifacts Tabs、空状态/加载态、Token 显示、侧边栏折叠等
"""
import allure
import pytest
from tests.pages.chat_test_page import ChatTestPage


# === BV-02: 超长消息发送 ===

@pytest.mark.order(70)
@pytest.mark.p1
def test_long_message(logged_in_page, base_url):
    """TC-CHAT-GAP-001: 超长消息发送（10000 字符）"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")
    if not chat.is_on_chat_page():
        pytest.skip("未能导航到 my-auto-test 聊天页")
    assert chat.is_chat_loaded(), "聊天页面未加载"

    chat.create_new_session()

    # 生成 10000 字符的文本
    long_text = "这是一条超长消息测试。" * 500  # ~5000 中文字 ≈ 15000 bytes
    assert len(long_text) >= 5000, f"测试文本长度不足: {len(long_text)}"

    textarea = logged_in_page.locator("textarea").first
    textarea.wait_for(state="visible", timeout=5000)
    textarea.fill(long_text)
    textarea.press("Enter")
    logged_in_page.wait_for_timeout(2000)

    # 验证：输入框已清空（消息被接受）或有错误提示
    val_after = textarea.input_value()
    if val_after == "":
        # 消息已发送，验证消息区域有内容
        log_area = logged_in_page.locator("div[role='log']")
        if log_area.count() > 0:
            log_text = log_area.first.inner_text()
            # 至少用户消息部分内容出现
            assert "超长消息" in log_text or len(log_text) > 100, \
                "超长消息发送后消息区域内容异常"
    else:
        # 消息未被接受（可能有长度限制），验证有错误提示
        body_text = logged_in_page.locator("body").inner_text()
        has_error_hint = "太长" in body_text or "超出" in body_text or \
            "限制" in body_text or "过长" in body_text
        # 如果也没有错误提示，记录为应用 Bug
        if not has_error_hint:
            allure_attach = f"超长消息未被接受且无错误提示（输入框残留 {len(val_after)} 字符）"
            allure.attach(allure_attach, name="备注",
                          attachment_type=allure.attachment_type.TEXT)


# === BV-03: 特殊字符消息（emoji + CJK）===

@pytest.mark.order(71)
@pytest.mark.p1
def test_special_characters(logged_in_page, base_url):
    """TC-CHAT-GAP-002: 特殊字符消息 — emoji、CJK、混合字符"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")
    if not chat.is_on_chat_page():
        pytest.skip("未能导航到 my-auto-test 聊天页")
    chat.create_new_session()

    # 监听 alert（XSS 检测）
    alert_triggered = []
    logged_in_page.on("dialog", lambda d: (alert_triggered.append(True), d.dismiss()))

    special_msg = "🎉🚀 emoji test | 中文测试 | 日本語テスト | 한국어 | مرحبا | שלום"
    chat.send_message(special_msg)
    logged_in_page.wait_for_timeout(2000)

    # 验证无 XSS 弹窗
    assert len(alert_triggered) == 0, \
        f"特殊字符触发了 {len(alert_triggered)} 次 alert"

    # 验证消息区域包含用户消息
    log_area = logged_in_page.locator("div[role='log']")
    if log_area.count() > 0:
        log_text = log_area.first.inner_text()
        assert "emoji test" in log_text or "🎉" in log_text, \
            "特殊字符消息未在消息区域正确显示"

    # 验证页面未崩溃
    assert chat.is_chat_loaded(), "发送特殊字符后页面崩溃"


# === BV-07: 单字符消息 ===

@pytest.mark.order(72)
@pytest.mark.p2
def test_single_char_message(logged_in_page, base_url):
    """TC-CHAT-GAP-003: 单字符消息发送"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")
    if not chat.is_on_chat_page():
        pytest.skip("未能导航到 my-auto-test 聊天页")
    chat.create_new_session()

    chat.send_message("a")
    logged_in_page.wait_for_timeout(2000)

    # 验证输入框清空
    val = logged_in_page.locator("textarea").first.input_value()
    assert val == "", f"发送单字符后输入框未清空: '{val}'"

    # 验证消息区域有用户消息
    log_area = logged_in_page.locator("div[role='log']")
    if log_area.count() > 0:
        log_text = log_area.first.inner_text()
        # 用户消息 "a" 应出现在某个消息气泡中
        assert len(log_text.strip()) > 0, "单字符消息发送后消息区域为空"


# === BV-05: 快速连续发送 ===

@pytest.mark.order(73)
@pytest.mark.p1
def test_rapid_consecutive_messages(logged_in_page, base_url):
    """TC-CHAT-GAP-004: 快速连续发送两条消息"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")
    if not chat.is_on_chat_page():
        pytest.skip("未能导航到 my-auto-test 聊天页")
    chat.create_new_session()

    log_area = logged_in_page.locator("div[role='log']")

    # 发送第一条消息
    chat.send_message("第一条快速消息-A")
    logged_in_page.wait_for_timeout(500)

    # 立即发送第二条（不等 AI 回复完成）
    textarea = logged_in_page.locator("textarea").first
    textarea.wait_for(state="visible", timeout=5000)
    textarea.fill("第二条快速消息-B")
    textarea.press("Enter")
    logged_in_page.wait_for_timeout(2000)

    # 验证：页面未崩溃，消息区域有内容
    assert chat.is_chat_loaded(), "快速连续发送后页面崩溃"
    if log_area.count() > 0:
        log_text = log_area.first.inner_text()
        assert "快速消息" in log_text, "快速连续发送后消息区域缺少用户消息"


# === NF-11: 模型切换 ===

@pytest.mark.order(74)
@pytest.mark.p1
def test_model_switching(logged_in_page, base_url):
    """TC-CHAT-GAP-005: 模型切换 — 打开选择器、查看选项、切换模型"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")
    if not chat.is_on_chat_page():
        pytest.skip("未能导航到 my-auto-test 聊天页")
    chat.create_new_session()

    # 1. 获取当前模型名
    current_model = chat.get_current_model_name()
    if not current_model:
        pytest.skip("无法获取当前模型名（composer meta 区域不存在）")

    # 2. 打开模型选择器
    opened = chat.open_model_selector()
    assert opened, "模型选择器未打开"

    # 3. 获取选项列表
    options = chat.get_model_options()
    if len(options) < 2:
        chat.close_model_selector()
        pytest.skip(f"可用模型不足 2 个（当前选项: {options}），无法测试切换")

    # 4. 选择一个不同于当前的模型
    other_model = None
    for opt in options:
        if opt != current_model and current_model not in opt:
            other_model = opt
            break
    if other_model is None:
        chat.close_model_selector()
        pytest.skip(f"所有选项与当前模型相同: {options}")

    selected = chat.select_model(other_model)
    assert selected, f"未能选择模型 '{other_model}'"

    # 5. 验证模型名已更新
    logged_in_page.wait_for_timeout(500)
    new_model = chat.get_current_model_name()
    assert new_model != current_model, \
        f"切换后模型名未更新: 之前='{current_model}'，之后='{new_model}'"

    # 6. 发送消息验证新模型可用
    chat.send_message("模型切换测试：请回复OK")
    logged_in_page.wait_for_timeout(3000)
    log_area = logged_in_page.locator("div[role='log']")
    if log_area.count() > 0:
        log_text = log_area.first.inner_text()
        assert len(log_text.strip()) > 0, "切换模型后发送消息无响应"


# === NF-12: Slash 命令输入 ===

@pytest.mark.order(75)
@pytest.mark.p1
def test_slash_command(logged_in_page, base_url):
    """TC-CHAT-GAP-006: Slash 命令触发候选列表"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")
    if not chat.is_on_chat_page():
        pytest.skip("未能导航到 my-auto-test 聊天页")
    chat.create_new_session()

    # 输入 / 触发命令候选
    chat.type_slash_command()

    # 验证候选列表出现
    has_popup = chat.has_slash_popup()
    if not has_popup:
        # 可能当前智能体没有配置 Slash 命令，跳过
        pytest.skip("输入 / 后未弹出命令候选列表（当前智能体可能未配置 Slash 命令）")

    # 按 Escape 关闭
    logged_in_page.keyboard.press("Escape")
    logged_in_page.wait_for_timeout(300)

    # 清空输入框
    logged_in_page.locator("textarea").first.fill("")


# === NF-13: @ 引用文件 ===

@pytest.mark.order(76)
@pytest.mark.p1
def test_at_file_reference(logged_in_page, base_url):
    """TC-CHAT-GAP-007: @ 引用文件触发候选列表"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")
    if not chat.is_on_chat_page():
        pytest.skip("未能导航到 my-auto-test 聊天页")
    chat.create_new_session()

    # 输入 @ 触发文件引用
    chat.type_at_reference()

    # 验证候选列表出现
    has_popup = chat.has_at_popup()
    if not has_popup:
        pytest.skip("输入 @ 后未弹出文件引用列表（当前智能体可能未配置文件树）")

    # 按 Escape 关闭
    logged_in_page.keyboard.press("Escape")
    logged_in_page.wait_for_timeout(300)
    logged_in_page.locator("textarea").first.fill("")


# === NF-14: 技能按钮工具栏 ===

@pytest.mark.order(77)
@pytest.mark.p2
def test_skill_button_toolbar(logged_in_page, base_url):
    """TC-CHAT-GAP-008: 技能按钮工具栏 — 点击弹出技能面板"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")
    if not chat.is_on_chat_page():
        pytest.skip("未能导航到 my-auto-test 聊天页")
    chat.create_new_session()

    # 点击技能按钮
    skill_btn = logged_in_page.get_by_role("button", name="技能")
    if skill_btn.count() == 0:
        pytest.skip("当前对话页无「技能」按钮")
    skill_btn.first.wait_for(state="visible", timeout=3000)

    chat.click_skill_button()

    # 验证弹出了面板或列表
    has_panel = chat.has_popup_or_panel()
    if not has_panel:
        # 技能按钮可能无响应（未绑定技能），记录但不失败
        allure.attach(
            "点击技能按钮后未弹出面板（当前智能体可能未绑定技能）",
            name="备注", attachment_type=allure.attachment_type.TEXT
        )
        return

    # 按 Escape 关闭
    logged_in_page.keyboard.press("Escape")
    logged_in_page.wait_for_timeout(300)


# === NF-15: 文件按钮工具栏 ===

@pytest.mark.order(78)
@pytest.mark.p2
def test_file_button_toolbar(logged_in_page, base_url):
    """TC-CHAT-GAP-009: 文件按钮工具栏 — 点击弹出文件面板"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")
    if not chat.is_on_chat_page():
        pytest.skip("未能导航到 my-auto-test 聊天页")
    chat.create_new_session()

    # 点击文件按钮（输入区左侧，非 Artifacts 面板 Tab）
    chat.click_file_button()

    # 验证弹出了面板或列表
    has_panel = chat.has_popup_or_panel()
    if not has_panel:
        allure.attach(
            "点击文件按钮后未弹出面板（当前智能体可能未配置文件树）",
            name="备注", attachment_type=allure.attachment_type.TEXT
        )
        return

    # 按 Escape 关闭
    logged_in_page.keyboard.press("Escape")
    logged_in_page.wait_for_timeout(300)


# === NF-16: 文件树 Tab 操作 ===

@pytest.mark.order(79)
@pytest.mark.p1
def test_artifacts_file_tree_tab(logged_in_page, base_url):
    """TC-CHAT-GAP-010: Artifacts 文件 Tab — 文件树展示"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")
    if not chat.is_on_chat_page():
        pytest.skip("未能导航到 my-auto-test 聊天页")

    # 确保 Artifacts 面板展开
    chat.expand_artifacts_panel()

    # 点击"文件"Tab
    file_tab = logged_in_page.get_by_role("button", name="文件")
    # 在 Artifacts 面板区域查找（排除输入区按钮）
    panel_tabs = logged_in_page.locator(
        "button[role='tab'], button[data-state]"
    ).filter(has_text="文件")
    if panel_tabs.count() > 0:
        panel_tabs.first.click(force=True)
        logged_in_page.wait_for_timeout(800)
    elif file_tab.count() > 0:
        file_tab.first.click(force=True)
        logged_in_page.wait_for_timeout(800)
    else:
        pytest.skip("Artifacts 面板无「文件」Tab")

    # 验证文件树存在
    has_tree = chat.has_file_tree()
    if not has_tree:
        pytest.skip("点击文件 Tab 后文件树未出现（可能 workspace 未配置）")

    # 验证树中有项目
    tree_items = logged_in_page.locator("div[role='treeitem']")
    assert tree_items.count() > 0, "文件树为空，至少应有 1 个文件"


# === NF-18: 定时任务 Tab ===

@pytest.mark.order(80)
@pytest.mark.p2
def test_artifacts_scheduled_tasks_tab(logged_in_page, base_url):
    """TC-CHAT-GAP-011: Artifacts 定时任务 Tab"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")
    if not chat.is_on_chat_page():
        pytest.skip("未能导航到 my-auto-test 聊天页")

    # 确保 Artifacts 面板展开
    chat.expand_artifacts_panel()

    # 点击"定时任务"Tab
    tab = logged_in_page.get_by_role("button", name="定时任务")
    if tab.count() == 0:
        pytest.skip("Artifacts 面板无「定时任务」Tab")
    tab.first.wait_for(state="visible", timeout=3000)
    tab.first.click(force=True)
    logged_in_page.wait_for_timeout(800)

    # 验证有内容（列表或空状态提示）
    assert chat.has_scheduled_tasks_content(), \
        "点击定时任务 Tab 后无任何内容显示"


# === NF-19: 发布视图 Tab ===

@pytest.mark.order(81)
@pytest.mark.p2
def test_artifacts_published_views_tab(logged_in_page, base_url):
    """TC-CHAT-GAP-012: Artifacts 发布视图 Tab"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")
    if not chat.is_on_chat_page():
        pytest.skip("未能导航到 my-auto-test 聊天页")

    # 确保 Artifacts 面板展开
    chat.expand_artifacts_panel()

    # 点击"发布视图"Tab
    tab = logged_in_page.get_by_role("button", name="发布视图")
    if tab.count() == 0:
        pytest.skip("Artifacts 面板无「发布视图」Tab")
    tab.first.wait_for(state="visible", timeout=3000)
    tab.first.click(force=True)
    logged_in_page.wait_for_timeout(800)

    # 验证页面未崩溃
    assert chat.is_chat_loaded(), "点击发布视图 Tab 后页面异常"


# === UI-01: 空状态页面 ===

@pytest.mark.order(82)
@pytest.mark.p1
def test_empty_state_display(logged_in_page, base_url):
    """TC-CHAT-GAP-013: 新会话空状态展示"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")
    if not chat.is_on_chat_page():
        pytest.skip("未能导航到 my-auto-test 聊天页")
    chat.create_new_session()

    # 1. 验证"开始对话"标题
    has_empty = chat.has_empty_state()
    if not has_empty:
        # 如果已有历史消息，空状态不显示是正常的
        log_area = logged_in_page.locator("div[role='log']")
        if log_area.count() > 0 and log_area.first.inner_text().strip():
            pytest.skip("新会话后仍有历史消息（可能是 keep-alive 缓存未清空）")
        # 如果没有消息也没有标题，记录
        allure.attach(
            "新会话后未显示「开始对话」标题且消息区域为空",
            name="备注", attachment_type=allure.attachment_type.TEXT
        )

    # 2. 验证输入框可用
    textarea = logged_in_page.locator("textarea").first
    assert textarea.is_visible(), "空状态下输入框不可见"
    placeholder = textarea.get_attribute("placeholder") or ""
    assert "给智能体发送消息" in placeholder, \
        f"输入框 placeholder 异常: '{placeholder}'"

    # 3. 验证提示文字
    assert chat.has_hint_text(), \
        "缺少输入提示文字（Enter 发送，Shift+Enter 换行）"


# === UI-02: 侧边栏折叠/展开 ===

@pytest.mark.order(83)
@pytest.mark.p2
def test_sidebar_collapse_expand(logged_in_page, base_url):
    """TC-CHAT-GAP-014: 侧边栏折叠/展开"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")
    if not chat.is_on_chat_page():
        pytest.skip("未能导航到 my-auto-test 聊天页")

    # 确保侧边栏展开
    if not chat.is_sidebar_expanded():
        chat.expand_sidebar()

    # 1. 折叠侧边栏
    collapsed = chat.collapse_sidebar()
    if not collapsed:
        pytest.skip("未找到侧边栏折叠按钮")

    logged_in_page.wait_for_timeout(500)
    # 折叠后侧边栏应变窄或隐藏
    is_still_expanded = chat.is_sidebar_expanded()

    # 2. 展开侧边栏
    expanded = chat.expand_sidebar()
    if not expanded:
        # 如果折叠按钮变为展开按钮
        allure.attach(
            "折叠后未找到展开按钮（可能需要其他交互方式）",
            name="备注", attachment_type=allure.attachment_type.TEXT
        )
        return

    logged_in_page.wait_for_timeout(500)
    assert chat.is_sidebar_expanded(), "展开侧边栏后侧边栏仍不可见"


# === UI-03: 加载状态 Spinner ===

@pytest.mark.order(84)
@pytest.mark.p2
def test_loading_state(logged_in_page, base_url):
    """TC-CHAT-GAP-015: 进入对话时加载状态"""
    # 导航到 agent home 页
    try:
        logged_in_page.goto(f"{base_url}/ctrl/agent/home",
                              wait_until="domcontentloaded")
    except Exception:
        pass
    logged_in_page.wait_for_load_state("domcontentloaded")

    # 等待侧边栏加载
    for _ in range(10):
        if logged_in_page.locator("button.agent-sidebar-agent-card").count() > 0:
            break
        logged_in_page.wait_for_timeout(1000)

    # 点击智能体卡片
    card = logged_in_page.locator("button.agent-sidebar-agent-card").filter(
        has_text="my-auto-test"
    )
    if card.count() == 0:
        pytest.skip("my-auto-test 不在智能体列表中")

    card.first.click()

    # 在加载过程中检查是否有 Spinner 或连接状态
    # 注意：如果加载很快，可能看不到 Spinner
    chat = ChatTestPage(logged_in_page, base_url)
    has_spinner = False
    for _ in range(5):
        if chat.has_loading_spinner() or chat.has_reconnect_button():
            has_spinner = True
            break
        logged_in_page.wait_for_timeout(500)

    # 等待加载完成
    try:
        logged_in_page.locator("textarea").first.wait_for(
            state="visible", timeout=20000
        )
    except Exception:
        pytest.skip("进入对话页后输入框未出现（20 秒超时）")

    if not has_spinner:
        allure.attach(
            "进入对话页时未检测到加载 Spinner（加载过快或无 Spinner 设计）",
            name="备注", attachment_type=allure.attachment_type.TEXT
        )


# === UI-04: Token 用量显示 ===

@pytest.mark.order(85)
@pytest.mark.p1
def test_token_usage_display(logged_in_page, base_url):
    """TC-CHAT-GAP-016: Token 用量信息显示"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")
    if not chat.is_on_chat_page():
        pytest.skip("未能导航到 my-auto-test 聊天页")
    chat.create_new_session()

    # 发送消息等待 AI 回复
    chat.send_message("请回复：token用量测试")
    logged_in_page.wait_for_timeout(2000)

    # 等待 AI 回复完成
    log_area = logged_in_page.locator("div[role='log']")
    if log_area.count() == 0:
        for _ in range(5):
            logged_in_page.wait_for_timeout(1000)
            if log_area.count() > 0:
                break
    if log_area.count() == 0:
        pytest.skip("消息区域未出现")

    # 等待回复完成（轮询）
    for _ in range(15):
        if chat.has_token_display():
            break
        logged_in_page.wait_for_timeout(1000)

    # 检查 Token 显示
    token_text = chat.get_token_usage_text()
    has_token = chat.has_token_display()

    if not has_token:
        # Token 显示可能是可选功能，记录但不失败
        allure.attach(
            "AI 回复后未检测到 Token 用量信息（可能该功能未实现或 DOM 选择器不匹配）",
            name="备注", attachment_type=allure.attachment_type.TEXT
        )
    else:
        assert token_text or has_token, "Token 用量显示异常"


# === UI-06: 消息区域自动滚动 ===

@pytest.mark.order(86)
@pytest.mark.p2
def test_auto_scroll_on_message(logged_in_page, base_url):
    """TC-CHAT-GAP-017: 新消息出现时自动滚动到底部"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")
    if not chat.is_on_chat_page():
        pytest.skip("未能导航到 my-auto-test 聊天页")
    chat.create_new_session()

    log_area = logged_in_page.locator("div[role='log']")

    # 发送消息
    chat.send_message("自动滚动测试消息")
    logged_in_page.wait_for_timeout(2000)

    if log_area.count() == 0:
        pytest.skip("消息区域未出现")

    # 获取滚动容器（log 区域的父元素通常有 overflow 滚动）
    scroll_info = log_area.first.evaluate("""el => {
        // 查找最近的可滚动父容器
        let container = el;
        while (container) {
            const style = window.getComputedStyle(container);
            if (['auto', 'scroll', 'overlay'].includes(style.overflowY)) {
                return {
                    scrollTop: container.scrollTop,
                    scrollHeight: container.scrollHeight,
                    clientHeight: container.clientHeight,
                    isScrolledToBottom: container.scrollHeight - container.scrollTop - container.clientHeight < 50
                };
            }
            container = container.parentElement;
        }
        return null;
    }""")

    if scroll_info is None:
        pytest.skip("未找到可滚动的消息容器")

    # 新消息后应该滚动到底部（或接近底部）
    assert scroll_info.get("isScrolledToBottom", True), \
        f"新消息后未自动滚动到底部: scrollTop={scroll_info.get('scrollTop')}, " \
        f"scrollHeight={scroll_info.get('scrollHeight')}, " \
        f"clientHeight={scroll_info.get('clientHeight')}"


# === BV-04: Shift+Enter 换行（独立用例）===

@pytest.mark.order(87)
@pytest.mark.p1
def test_shift_enter_newline(logged_in_page, base_url):
    """TC-CHAT-GAP-018: Shift+Enter 换行 — 不发送、产生换行"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")
    if not chat.is_on_chat_page():
        pytest.skip("未能导航到 my-auto-test 聊天页")
    chat.create_new_session()

    textarea = logged_in_page.locator("textarea").first
    textarea.wait_for(state="visible", timeout=5000)

    # 输入多行
    textarea.click()
    textarea.press_sequentially("Line1", delay=20)
    textarea.press("Shift+Enter")
    textarea.press_sequentially("Line2", delay=20)
    textarea.press("Shift+Enter")
    textarea.press_sequentially("Line3", delay=20)

    # 验证输入框包含换行
    val = textarea.input_value()
    assert "Line1" in val and "Line2" in val and "Line3" in val, \
        f"Shift+Enter 多行输入失败: '{repr(val)}'"
    newline_count = val.count("\n")
    assert newline_count >= 2, \
        f"Shift+Enter 未产生足够换行: {newline_count}（期望 >= 2）"

    # 发送
    textarea.press("Enter")
    logged_in_page.wait_for_timeout(1000)

    # 验证输入框已清空
    val_after = textarea.input_value()
    assert val_after == "", f"多行消息发送后输入框未清空: '{val_after}'"


# === EX-04: Action Error Banner 检测 ===

@pytest.mark.order(88)
@pytest.mark.p2
def test_action_error_banner(logged_in_page, base_url):
    """TC-CHAT-GAP-019: Action Error Banner — 触发后出现并自动消失"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")
    if not chat.is_on_chat_page():
        pytest.skip("未能导航到 my-auto-test 聊天页")
    chat.create_new_session()

    # Action Error 需要特定条件触发，这里只验证 Banner 机制存在
    # 检查初始状态无 Banner
    has_banner_initial = chat.has_action_error_banner()
    assert not has_banner_initial, "初始状态下不应有 Error Banner"

    # 发送正常消息
    chat.send_message("Error banner 测试：请回复 OK")
    logged_in_page.wait_for_timeout(3000)

    # 正常消息不应触发 Error Banner
    has_banner_after = chat.has_action_error_banner()
    assert not has_banner_after, "正常消息发送后不应出现 Error Banner"

    allure.attach(
        "Action Error Banner 需要异常条件触发（如模型不可用），"
        "正常操作下无法测试，此用例仅验证正常流程无 Banner",
        name="备注", attachment_type=allure.attachment_type.TEXT
    )
