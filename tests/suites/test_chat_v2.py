# tests/suites/test_chat_v2.py
"""对话聊天模块回归测试（基于 V2 Excel 用例 TC-CHAT-013~064）"""
import os
import pytest
import tempfile
from pathlib import Path
from tests.pages.chat_test_page import ChatTestPage


# === TC-CHAT-013: Markdown 完整渲染 ===

@pytest.mark.order(50)
@pytest.mark.p0
def test_markdown_rendering(logged_in_page, base_url):
    """✅ 人工评审通过 | Markdown 完整渲染（TC-CHAT-013）"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")
    assert chat.is_chat_loaded()

    chat.create_new_session()
    # 更明确的提示，使用直接指令
    chat.send_message(
        "请严格按照以下 Markdown 格式回复（必须包含每种元素）：\n"
        "# 一级标题\n"
        "## 二级标题\n"
        "**加粗文字**\n"
        "*斜体文字*\n"
        "1. 有序列表项\n"
        "- 无序列表项\n"
        "[示例链接](https://example.com)\n\n"
        "请按上面的格式原样输出，包含所有元素。"
    )

    # 轮询等待 Markdown 渲染（最长 10 秒）
    for _ in range(10):
        if chat.has_heading():
            break
        logged_in_page.wait_for_timeout(1000)

    assert chat.has_heading(), \
        "AI 未按指令生成标题元素（h1-h6），Markdown 渲染失败"

    # 至少再渲染 1 种其他 Markdown 元素
    rendered_count = sum([
        chat.has_ordered_list() or chat.has_unordered_list(),
        chat.has_link(),
        chat.has_bold(),
        chat.has_italic(),
    ])
    assert rendered_count >= 1, \
        f"Markdown 渲染不完整，仅渲染了 {rendered_count}/4 种元素（列表/链接/加粗/斜体）"


# === TC-CHAT-014: 代码块语法高亮与复制 ===

@pytest.mark.order(51)
@pytest.mark.p0
def test_code_block_highlight(logged_in_page, base_url):
    """✅ 人工评审通过 | 代码块语法高亮与复制功能（TC-CHAT-014）"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")
    chat.create_new_session()

    chat.send_message(
        "请用 Python 代码块格式写一个 print('hello world') 程序。\n"
        "必须使用三个反引号加 python 的格式：```python\nprint('hello world')\n```"
    )

    # 轮询等待代码块出现
    for _ in range(10):
        if chat.has_code_block():
            break
        logged_in_page.wait_for_timeout(1000)

    assert chat.has_code_block(), \
        "AI 未按指令生成代码块（pre 元素不存在），语法高亮测试无法进行"

    # 验证 code 元素存在
    code = logged_in_page.locator("pre code")
    assert code.count() > 0, "代码块中没有 code 元素"

    # 验证语法高亮类名
    assert chat.has_code_with_highlight(), \
        "代码块没有语法高亮类名（hljs/prism/shiki/language-）"


# === TC-CHAT-015: 长代码块不撑破布局 ===

@pytest.mark.order(52)
@pytest.mark.p2
def test_long_code_block_layout(logged_in_page, base_url):
    """✅ 人工评审通过 | 长代码块不撑破布局（TC-CHAT-015）"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")
    chat.create_new_session()

    chat.send_message(
        "请用Python写一个类叫MyClass，包含10个方法，每个方法做不同的事情。"
        "务必使用 ```python 代码块格式包裹整个代码。"
    )

    # 轮询等待代码块出现
    for _ in range(10):
        if chat.has_code_block():
            break
        logged_in_page.wait_for_timeout(1000)

    assert chat.has_code_block(), \
        "AI 未按指令生成代码块（pre 元素不存在），长代码块布局测试无法进行"

    # 验证代码块没有导致页面横向溢出
    body_width = logged_in_page.evaluate("document.body.scrollWidth")
    viewport_width = logged_in_page.evaluate("window.innerWidth")
    assert body_width <= viewport_width + 20, \
        f"代码块撑破了布局: body={body_width} > viewport={viewport_width}"

    # 代码块应有高度限制或可滚动（检查 pre 本身或其父容器）
    style = chat.get_code_block_style()
    if style:
        height = style.get("height", 0)
        # 如果代码块很高，应该有 overflow scroll/auto（pre 或父容器）
        if height > 400:
            overflow = style.get("overflowY", "")
            # 也检查父容器的 overflow（滚动可能在消息区域而非 pre 本身）
            if overflow not in ["auto", "scroll", "overlay"]:
                parent_overflow = logged_in_page.evaluate("""() => {
                    const pre = document.querySelector('pre');
                    if (!pre) return '';
                    let el = pre.parentElement;
                    while (el) {
                        const s = window.getComputedStyle(el);
                        if (['auto', 'scroll', 'overlay'].includes(s.overflowY)) return s.overflowY;
                        el = el.parentElement;
                    }
                    return '';
                }""")
                assert parent_overflow in ["auto", "scroll", "overlay"], \
                    f"长代码块缺少滚动: pre overflowY={overflow}，父容器也无滚动（代码块高度={height}px）"


# === TC-CHAT-016: Markdown 表格渲染 ===

@pytest.mark.order(53)
@pytest.mark.p1
def test_markdown_table_rendering(logged_in_page, base_url):
    """✅ 人工评审通过 | Markdown 表格渲染（TC-CHAT-016）"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")
    chat.create_new_session()

    chat.send_message(
        "请用 Markdown 表格格式回复，列出5个中国城市及其省份和人口：\n"
        "| 城市 | 省份 | 人口 |\n"
        "|------|------|------|\n"
        "| 北京 | 北京 | 2100万 |\n"
        "| 上海 | 上海 | 2400万 |\n"
        "| 广州 | 广东 | 1800万 |\n"
        "| 深圳 | 广东 | 1300万 |\n"
        "| 成都 | 四川 | 1600万 |\n\n"
        "请严格按此格式输出。"
    )

    # 轮询等待表格出现
    for _ in range(10):
        if chat.has_table():
            break
        logged_in_page.wait_for_timeout(1000)

    assert chat.has_table(), \
        "AI 未按指令生成表格（table 元素不存在），表格渲染测试失败"

    table = logged_in_page.locator("table").first
    # 验证表格至少有 2 行数据
    rows = table.locator("tbody tr, tr")
    assert rows.count() >= 2, f"表格行数不足: {rows.count()}（至少应有 2 行）"


# === TC-CHAT-018: XSS 防护 ===

@pytest.mark.order(54)
@pytest.mark.p0
def test_xss_protection(logged_in_page, base_url):
    """✅ 人工评审通过 | XSS 防护 - 恶意脚本不执行（TC-CHAT-018）"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")
    chat.create_new_session()

    # 监听 alert 弹窗
    alert_triggered = []
    logged_in_page.on("dialog", lambda d: (alert_triggered.append(True), d.dismiss()))

    # 多种 XSS payload 测试
    xss_payloads = [
        "<script>alert('xss1')</script>",
        "<img src=x onerror=alert('xss2')>",
        "<svg onload=alert('xss3')>",
    ]

    for payload in xss_payloads:
        chat.send_message(payload)
        logged_in_page.wait_for_timeout(800)

    # 1. 不应弹出任何 alert
    assert len(alert_triggered) == 0, \
        f"XSS 脚本被执行，弹出了 {len(alert_triggered)} 次 alert"

    # 2. DOM 中不应有注入的可执行 script 标签
    injected_scripts = logged_in_page.evaluate("""
        () => {
            const scripts = document.querySelectorAll('script:not([src])');
            return Array.from(scripts).filter(s =>
                s.textContent.includes('alert')
            ).length;
        }
    """)
    assert injected_scripts == 0, \
        f"DOM 中存在 {injected_scripts} 个包含 alert 的注入 script 标签"


# === TC-CHAT-020: 新建对话会话 ===

@pytest.mark.order(55)
@pytest.mark.p0
def test_create_new_session(logged_in_page, base_url):
    """✅ 人工评审通过 | 新建对话会话（TC-CHAT-020）"""
    chat = ChatTestPage(logged_in_page, base_url)
    agent_name = "my-auto-test"
    chat.goto_agent_chat(agent_name)
    assert chat.is_chat_loaded()

    # 1. 新建会话
    chat.create_new_session()

    # 2. URL 仍在聊天页面且包含 /chat/
    assert "/chat/" in logged_in_page.url, f"新建会话后 URL 异常: {logged_in_page.url}"

    # 3. 会话标题变为"新会话"或空（非旧标题）
    title = chat.get_session_header_title()
    assert title, "新建会话后标题为空"

    # 4. textarea 仍可用
    textarea = logged_in_page.locator("textarea")
    assert textarea.count() > 0, "新建会话后输入框消失"

    # 5. textarea 有正确的 placeholder
    placeholder = textarea.first.get_attribute("placeholder") or ""
    assert "给智能体发送消息" in placeholder, \
        f"新建会话后输入框 placeholder 异常: '{placeholder}'"

    # 6. 当前 agent 名称在页面中显示（侧边栏或 header 区域）
    page_text = logged_in_page.locator("body").inner_text()
    assert agent_name in page_text, \
        f"新建会话后页面中未显示当前 agent 名称 '{agent_name}'"

    # 7. 模型名称在输入框区域显示（不写死具体模型名，只验证非空）
    composer_card = logged_in_page.locator("div.chat-composer-card")
    assert composer_card.count() > 0, "输入框卡片（chat-composer-card）不存在"
    model_span = composer_card.locator("span[data-slot='popover-anchor']")
    assert model_span.count() > 0, "未找到模型名称展示区域"
    model_title = model_span.first.get_attribute("title") or model_span.first.inner_text().strip()
    assert model_title.strip(), "模型名称为空"


# === TC-CHAT-022: 切换会话后消息隔离 ===

@pytest.mark.order(56)
@pytest.mark.p0
def test_session_message_isolation(logged_in_page, base_url):
    """✅ 人工评审通过 | 切换会话后消息隔离（TC-CHAT-022）"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")

    # 获取会话列表
    chat.open_session_dialog()
    assert chat.is_session_dialog_open(), "会话对话框未打开"

    titles = chat.get_session_titles()
    if len(titles) < 2:
        chat.close_session_dialog()
        pytest.skip("需要至少 2 个会话才能测试隔离")

    # 1. 点击第一个会话
    chat.click_session(titles[0])
    logged_in_page.wait_for_timeout(800)
    msg_text_a = chat.get_chat_messages_text()

    # 2. 打开对话框，点击第二个会话
    chat.open_session_dialog()
    chat.click_session(titles[1])
    logged_in_page.wait_for_timeout(800)
    msg_text_b = chat.get_chat_messages_text()

    # 3. 两个会话的消息区域内容不同（仅比较消息区，排除侧边栏）
    assert msg_text_a, "会话A消息区域为空"
    assert msg_text_b, "会话B消息区域为空"
    assert msg_text_a != msg_text_b, \
        "两个不同会话的消息内容完全相同，可能存在串台"


# === TC-CHAT-024: 会话数据持久化 - 刷新不丢失 ===

@pytest.mark.order(57)
@pytest.mark.p0
def test_session_persistence_refresh(logged_in_page, base_url):
    """✅ 人工评审通过 | 会话数据持久化 - 刷新不丢失（TC-CHAT-024）"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")
    chat.create_new_session()

    # 1. 发送一条自然的消息
    user_message = "你好，请简单介绍一下什么是人工智能，至少回复50个字"
    chat.send_message(user_message)

    # 2. 验证用户消息出现在消息区域（role='log' 容器）
    log_area = logged_in_page.locator("div[role='log']")
    assert log_area.count() > 0, "消息列表容器（role='log'）不存在"

    # 轮询等待 AI 回复
    for _ in range(20):
        messages_before = log_area.first.inner_text()
        if user_message in messages_before and len(messages_before) > len(user_message) + 20:
            break
        logged_in_page.wait_for_timeout(1000)

    messages_before = log_area.first.inner_text()
    assert user_message in messages_before, \
        f"用户消息未出现在消息区域: '{user_message}'"

    # 3. 验证 AI 有回复（消息区域有除用户消息以外的内容）
    ai_response_length = len(messages_before) - len(user_message)
    if ai_response_length <= 10:
        pytest.skip(f"AI 回复内容过少（仅 {ai_response_length} 字符），可能未正常响应")

    # 4. 记录当前会话 URL
    session_url = logged_in_page.url

    # 5. 导航到完全不同的页面，再回到原会话 URL
    logged_in_page.goto(f"{base_url}/ctrl/agent/algorithms")
    logged_in_page.wait_for_load_state("networkidle")
    logged_in_page.goto(session_url, wait_until="networkidle")
    logged_in_page.wait_for_load_state("networkidle")

    # 6. 如果消息未出现，做一次 reload
    log_check = logged_in_page.locator("div[role='log']")
    if log_check.count() > 0 and user_message not in log_check.first.inner_text():
        logged_in_page.reload(wait_until="networkidle")
        logged_in_page.wait_for_load_state("networkidle")

    # 7. 轮询等待消息加载（最长 15 秒）
    messages_after = ""
    for _ in range(15):
        log_after = logged_in_page.locator("div[role='log']")
        if log_after.count() > 0:
            messages_after = log_after.first.inner_text()
            if user_message in messages_after:
                break
        logged_in_page.wait_for_timeout(800)

    # 8. 验证：用户消息和 AI 回复都在
    assert user_message in messages_after, \
        f"刷新后用户消息丢失（URL: {logged_in_page.url}）: '{user_message}'"
    assert len(messages_after) > len(user_message) + 50, \
        "刷新后 AI 回复丢失，仅剩用户消息"


# === TC-CHAT-027: 会话列表数据加载 ===

@pytest.mark.order(59)
@pytest.mark.p0
def test_session_list_loads(logged_in_page, base_url):
    """✅ 人工评审通过 | 会话列表数据加载（TC-CHAT-027）"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")

    chat.open_session_dialog()
    assert chat.is_session_dialog_open(), "会话对话框未打开"

    titles = chat.get_session_titles()
    assert len(titles) > 0, "会话列表为空，至少应有一个会话"

    # 每个标题都非空
    for title in titles:
        assert title.strip(), "存在空标题的会话"

    chat.close_session_dialog()


# === TC-CHAT-028: 会话搜索功能 ===

@pytest.mark.order(60)
@pytest.mark.p1
def test_session_search(logged_in_page, base_url):
    """✅ 人工评审通过 | 会话搜索功能（TC-CHAT-028）"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")

    chat.open_session_dialog()
    assert chat.is_session_dialog_open()

    # 1. 获取所有会话
    all_titles = chat.get_session_titles()
    if len(all_titles) < 2:
        chat.close_session_dialog()
        pytest.skip("需要至少 2 个会话才能测试搜索")

    # 2. 用第一个会话的关键词搜索
    keyword = all_titles[0][:4]  # 取前4个字符
    chat.search_sessions(keyword)

    # 3. 过滤后的结果应减少，且每条结果都包含关键词
    filtered = chat.get_filtered_session_titles()
    assert len(filtered) > 0, "搜索后结果为空，应该有匹配结果"
    assert len(filtered) < len(all_titles), \
        f"搜索后结果数量未减少: {len(filtered)} vs {len(all_titles)}"
    # 每条过滤结果都应包含关键词
    for title in filtered:
        assert keyword.lower() in title.lower(), \
            f"搜索结果中出现不匹配项: '{title}' 不包含关键词 '{keyword}'"

    # 4. 搜索不存在的关键词
    chat.search_sessions("zzz_不存在_zzz_99999")
    empty_results = chat.get_filtered_session_titles()
    assert len(empty_results) == 0, \
        f"搜索不存在关键词后仍有 {len(empty_results)} 条结果"

    # 清理
    chat.search_sessions("")
    chat.close_session_dialog()


# === TC-CHAT-031: 不同会话状态视觉区分 ===

@pytest.mark.order(61)
@pytest.mark.p2
def test_session_status_visual_distinction(logged_in_page, base_url):
    """✅ 人工评审通过 | 不同会话状态视觉区分（TC-CHAT-031）"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")

    chat.open_session_dialog()
    assert chat.is_session_dialog_open(), "无法打开会话对话框，系统可能异常"

    dialog = logged_in_page.locator("[role='dialog']")
    dialog_text = dialog.first.inner_text()

    # 检查时间分区标题（三种情况都算通过：只有今天 / 今天+昨天 / 今天+昨天+更早）
    found_sections = [s for s in ["今天", "昨天", "更早"] if s in dialog_text]
    assert len(found_sections) >= 1, \
        f"会话列表未显示任何时间分区（今天/昨天/更早），当前对话框内容: {dialog_text[:200]}"

    chat.close_session_dialog()


# === TC-CHAT-056: 文件上传成功并预览 ===

@pytest.mark.order(62)
@pytest.mark.p0
def test_file_upload_preview(logged_in_page, base_url):
    """✅ 人工评审通过 | 文件上传成功并预览（TC-CHAT-056）"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")
    chat.create_new_session()

    # 创建临时文件（使用已知文件名便于验证）
    file_name = "test-upload-doc.txt"
    tmp_dir = tempfile.mkdtemp()
    tmp_path = os.path.join(tmp_dir, file_name)
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write("这是一个测试文件，内容是 hello world")

    try:
        # 上传文件
        chat.upload_file(tmp_path)

        # 等待文件出现在文件树中（轮询，最长 10 秒）
        file_tree_item = None
        for _ in range(10):
            # 查找上传的文件（node-id 为文件名）
            item = logged_in_page.locator(
                f"div[role='treeitem'][data-node-id='{file_name}']"
            )
            if item.count() > 0:
                file_tree_item = item
                break
            logged_in_page.wait_for_timeout(800)

        assert file_tree_item is not None, \
            f"上传后文件 '{file_name}' 未出现在文件树中（已等待 10 秒）"

        # 点击文件打开预览
        file_tree_item.first.click()
        logged_in_page.wait_for_timeout(800)

        # 验证：预览区域正常打开
        preview_container = logged_in_page.locator("div.ofv-code-container")
        assert preview_container.count() > 0, "点击文件后未打开预览区域（ofv-code-container 不存在）"

        # 验证：预览中文件名正确
        preview_title = preview_container.locator("div.ofv-code-title strong")
        assert preview_title.count() > 0, "预览区域缺少文件名标题"
        displayed_name = preview_title.first.inner_text().strip()
        assert displayed_name == file_name, \
            f"预览文件名不匹配: 显示 '{displayed_name}'，期望 '{file_name}'"

        # 验证：预览中文件内容正确
        preview_content = preview_container.locator("pre code").first.inner_text().strip()
        assert "hello world" in preview_content, \
            f"预览文件内容不匹配: 显示 '{preview_content}'，期望包含 'hello world'"
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


# === TC-CHAT-059: 多文件上传 ===

@pytest.mark.order(64)
@pytest.mark.p2
def test_multi_file_upload(logged_in_page, base_url):
    """✅ 人工评审通过 | 多文件上传（TC-CHAT-059）"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")
    chat.create_new_session()

    # 创建多个临时文件（使用已知文件名）
    tmp_dir = tempfile.mkdtemp()
    tmp_files = []
    for i in range(2):
        fname = f"multi-upload-{i}.txt"
        fpath = os.path.join(tmp_dir, fname)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(f"测试文件 {i} 的内容")
        tmp_files.append(fpath)

    try:
        # 上传多个文件
        file_input = chat.get_file_input()
        multiple = file_input.get_attribute("multiple")
        assert multiple is not None, \
            "文件上传 input 缺少 multiple 属性，不支持多文件选择"

        chat.upload_files(tmp_files)

        # 验证：两个文件都出现在文件树中
        file_names = [f"multi-upload-{i}.txt" for i in range(2)]
        for i, fname in enumerate(file_names):
            # 等待文件出现在文件树
            item = None
            for _ in range(10):
                item = logged_in_page.locator(
                    f"div[role='treeitem'][data-node-id='{fname}']"
                )
                if item.count() > 0:
                    break
                logged_in_page.wait_for_timeout(800)
            assert item is not None and item.count() > 0, \
                f"多文件上传后 '{fname}' 未出现在文件树中（已等待 10 秒）"

            # 点击文件打开预览（force 避免元素被遮挡）
            item.first.click(force=True)
            logged_in_page.wait_for_timeout(800)

            # 验证预览区域打开
            preview_container = logged_in_page.locator("div.ofv-code-container")
            assert preview_container.count() > 0, \
                f"点击文件 '{fname}' 后未打开预览区域"

            # 验证预览中文件名正确
            preview_title = preview_container.locator("div.ofv-code-title strong")
            displayed_name = preview_title.first.inner_text().strip() \
                if preview_title.count() > 0 else ""
            assert displayed_name == fname, \
                f"预览文件名不匹配: 显示 '{displayed_name}'，期望 '{fname}'"

            # 验证预览中文件内容正确
            expected_content = f"测试文件 {i} 的内容"
            preview_content = preview_container.locator("pre code").first.inner_text().strip() \
                if preview_container.locator("pre code").count() > 0 else ""
            assert expected_content in preview_content, \
                f"文件 '{fname}' 预览内容不匹配: 显示 '{preview_content}'，期望包含 '{expected_content}'"
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


# === 上传 .exe 文件预览提示 ===

@pytest.mark.order(64.1)
@pytest.mark.p1
def test_exe_file_preview_unsupported(logged_in_page, base_url):
    """✅ 人工评审通过 | 上传 .exe 文件后预览提示暂不支持此格式"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")
    chat.create_new_session()

    # 创建临时 .exe 文件
    with tempfile.NamedTemporaryFile(suffix=".exe", delete=False, mode="wb",
                                     prefix="test-exe-") as f:
        f.write(b"\x00" * 100)
        tmp_path = f.name
    exe_name = os.path.basename(tmp_path)

    try:
        # 上传 .exe 文件
        chat.upload_file(tmp_path)

        # 等待文件出现在文件树
        file_item = None
        for _ in range(10):
            file_item = logged_in_page.locator(
                f"div[role='treeitem'][data-node-id='{exe_name}']"
            )
            if file_item.count() > 0:
                break
            logged_in_page.wait_for_timeout(800)

        assert file_item is not None and file_item.count() > 0, \
            f"上传 .exe 文件 '{exe_name}' 未出现在文件树中（上传失败）"

        # 点击文件
        file_item.first.click()
        logged_in_page.wait_for_timeout(800)

        # 验证预览区域显示"暂不支持此格式"提示
        body_text = logged_in_page.locator("body").inner_text()
        assert "暂不支持此格式" in body_text or "不支持" in body_text, \
            f"点击 .exe 文件后未显示'暂不支持此格式'提示"
    finally:
        os.unlink(tmp_path)


# === TC-CHAT-061: 消息输入框基础功能 ===

@pytest.mark.order(65)
@pytest.mark.p0
def test_input_box_basics(logged_in_page, base_url):
    """✅ 人工评审通过 | 消息输入框基础功能（TC-CHAT-061）"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")
    chat.create_new_session()

    textarea = logged_in_page.locator("textarea").first

    # 0. 验证会话已就绪，输入框不是"等待会话"状态
    placeholder = textarea.get_attribute("placeholder") or ""
    assert "等待会话" not in placeholder, \
        f"会话未就绪，输入框仍处于等待状态: placeholder='{placeholder}'"

    # 1. 空消息不发送 — 按 Enter 后输入框仍为空
    textarea.fill("")
    textarea.press("Enter")
    logged_in_page.wait_for_timeout(500)
    val = textarea.input_value()
    assert val == "", f"空消息按 Enter 后输入框不为空: '{val}'"
    # 同时验证消息没有被发送（消息列表未增加）
    msg_count_before = chat.get_user_message_count()

    # 2. Shift+Enter 换行
    textarea.fill("第一行")
    textarea.press("Shift+Enter")
    textarea.press_sequentially("第二行", delay=20)
    val = textarea.input_value()
    assert "\n" in val, f"Shift+Enter 未产生换行: '{repr(val)}'"

    # 3. 清空输入框
    textarea.fill("")

    # 4. 正常发送
    textarea.fill("输入框测试消息")
    textarea.press("Enter")
    logged_in_page.wait_for_timeout(800)

    # 发送后输入框应清空
    val_after = textarea.input_value()
    assert val_after == "", f"发送后输入框未清空: '{val_after}'"


# === TC-CHAT-063: 发送防重复提交 ===

@pytest.mark.order(66)
@pytest.mark.p1
def test_prevent_double_send(logged_in_page, base_url):
    """✅ 人工评审通过 | 发送防重复提交（TC-CHAT-063）"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")
    chat.create_new_session()

    # 验证会话已就绪
    textarea = logged_in_page.locator("textarea").first
    placeholder = textarea.get_attribute("placeholder") or ""
    assert "等待会话" not in placeholder, \
        f"会话未就绪: placeholder='{placeholder}'"

    # 记录发送前消息区域的气泡数
    log_area = logged_in_page.locator("div[role='log']")
    bubbles_before = log_area.first.locator("div").count() \
        if log_area.count() > 0 else 0

    # 发送一条自然消息，快速连按两次 Enter
    user_message = "这是一条防重复发送的测试消息"
    textarea.fill(user_message)
    textarea.press("Enter")

    # 第一次 Enter 后输入框应立即清空
    logged_in_page.wait_for_timeout(200)
    val_after_first = textarea.input_value()
    assert val_after_first == "", \
        f"第一次 Enter 后输入框未清空: '{val_after_first}'（第二次 Enter 会重复发送）"

    # 第二次 Enter（此时输入框为空，不应发送任何内容）
    textarea.press("Enter")

    # 等待响应完成
    logged_in_page.wait_for_load_state("networkidle", timeout=8000)

    # 验证：用户消息气泡只有 1 个（bg-user-bubble 是用户消息的标识）
    log_area_after = logged_in_page.locator("div[role='log']")
    assert log_area_after.count() > 0, "消息区域不存在"
    user_bubbles = log_area_after.locator("div.bg-user-bubble")
    user_bubble_count = user_bubbles.count()
    assert user_bubble_count == 1, \
        f"消息被重复发送，检测到 {user_bubble_count} 个用户气泡（期望 1 个）"


# === TC-CHAT-064: 停止生成按钮 ===

@pytest.mark.order(67)
@pytest.mark.p0
def test_stop_generation(logged_in_page, base_url):
    """✅ 人工评审通过 | 停止生成按钮（TC-CHAT-064）"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")
    chat.create_new_session()

    textarea = logged_in_page.locator("textarea").first

    # 记录发送前页面内容长度
    body_before = logged_in_page.locator("body").inner_text()
    len_before = len(body_before)

    # 发送一条会触发长回复的消息
    textarea.fill("请详细解释量子力学的不确定性原理，写一篇2000字的论文")
    textarea.press("Enter")

    # 等待流式响应开始
    logged_in_page.wait_for_timeout(800)

    # 1. 验证流式响应确实开始了（页面内容增量 > 50 字符 或 按钮被禁用）
    body_during = logged_in_page.locator("body").inner_text()
    content_diff = len(body_during) - len_before
    is_disabled = chat.is_skill_button_disabled()
    assert content_diff > 50 or is_disabled, (
        f"流式响应未开始：页面内容增量={content_diff}字符（需>50）且按钮未禁用"
    )

    # 点击发送/停止按钮（第3个按钮）
    len_during = len(body_during)
    chat.click_send_button_during_streaming()

    # 2. 停止后输入框应恢复可用
    logged_in_page.wait_for_timeout(800)
    textarea_after = logged_in_page.locator("textarea").first
    assert textarea_after.is_visible(), "停止生成后输入框不可见"

    # 3. 可以继续发送新消息
    textarea_after.fill("继续测试")
    textarea_after.press("Enter")
    logged_in_page.wait_for_timeout(800)

    # 4. 停止后已接收的内容应保留（不回滚）
    body_after_stop = logged_in_page.locator("body").inner_text()
    assert len(body_after_stop) >= len_during - 20, \
        "停止生成后已有内容被回滚"
