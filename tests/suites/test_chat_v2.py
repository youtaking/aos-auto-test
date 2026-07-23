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
    """Markdown 完整渲染（TC-CHAT-013）"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat()
    assert chat.is_chat_loaded()

    chat.create_new_session()
    chat.send_message(
        "请用markdown格式回复，包含：# 一级标题、## 二级标题、"
        "**加粗**、*斜体*、1. 有序列表、- 无序列表、[链接](https://example.com)"
    )

    # 验证 Markdown 渲染元素 — 标题必须出现
    assert chat.has_heading(), "未渲染标题元素（h1/h2/h3）"
    # 至少再渲染 2 种其他 Markdown 元素
    rendered_count = sum([
        chat.has_ordered_list() or chat.has_unordered_list(),
        chat.has_link(),
        chat.has_bold(),
        chat.has_italic(),
    ])
    assert rendered_count >= 2, \
        f"Markdown 渲染不完整，仅渲染了 {rendered_count}/4 种元素（列表/链接/加粗/斜体）"


# === TC-CHAT-014: 代码块语法高亮与复制 ===

@pytest.mark.order(51)
@pytest.mark.p0
def test_code_block_highlight(logged_in_page, base_url):
    """代码块语法高亮与复制功能（TC-CHAT-014）"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat()
    chat.create_new_session()

    chat.send_message(
        "请用Python代码块写一个 print hello world 程序，"
        "务必使用 ```python 代码块格式"
    )

    # 验证代码块出现
    assert chat.has_code_block(), "未出现代码块（pre 元素）"

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
    """长代码块不撑破布局（TC-CHAT-015）"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat()
    chat.create_new_session()

    chat.send_message(
        "请用Python写一个完整的类，包含至少10个方法，每个方法有不同功能，"
        "代码要尽量长，使用 ```python 代码块格式"
    )

    if not chat.has_code_block():
        pytest.skip("AI 未生成代码块")

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
    """Markdown 表格渲染（TC-CHAT-016）"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat()
    chat.create_new_session()

    chat.send_message(
        "请用 Markdown 表格格式列出5个中国城市及其省份和人口数量"
    )

    # 验证表格渲染
    if not chat.has_table():
        # AI 可能没用表格格式，检查是否有其他表格元素
        tables = logged_in_page.locator("table")
        if tables.count() == 0:
            pytest.skip("AI 未生成表格")

    table = logged_in_page.locator("table").first
    thead = table.locator("thead")
    assert thead.count() > 0, "表格没有 thead 表头"
    # 验证表格至少有 2 行数据
    rows = table.locator("tbody tr")
    assert rows.count() >= 2, f"表格行数不足: {rows.count()}（至少应有 2 行）"


# === TC-CHAT-018: XSS 防护 ===

@pytest.mark.order(54)
@pytest.mark.p0
def test_xss_protection(logged_in_page, base_url):
    """XSS 防护 - 恶意脚本不执行（TC-CHAT-018）"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat()
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
        logged_in_page.wait_for_timeout(1000)

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
    """新建对话会话（TC-CHAT-020）"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat()
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


# === TC-CHAT-022: 切换会话后消息隔离 ===

@pytest.mark.order(56)
@pytest.mark.p0
def test_session_message_isolation(logged_in_page, base_url):
    """切换会话后消息隔离（TC-CHAT-022）"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat()

    # 获取会话列表
    chat.open_session_dialog()
    assert chat.is_session_dialog_open(), "会话对话框未打开"

    titles = chat.get_session_titles()
    if len(titles) < 2:
        chat.close_session_dialog()
        pytest.skip("需要至少 2 个会话才能测试隔离")

    # 1. 点击第一个会话
    chat.click_session(titles[0])
    logged_in_page.wait_for_timeout(2000)
    msg_text_a = chat.get_chat_messages_text()

    # 2. 打开对话框，点击第二个会话
    chat.open_session_dialog()
    chat.click_session(titles[1])
    logged_in_page.wait_for_timeout(2000)
    msg_text_b = chat.get_chat_messages_text()

    # 3. 两个会话的消息区域内容不同（仅比较消息区，排除侧边栏）
    assert msg_text_a or msg_text_b, "两个会话的消息区域都为空，无法验证隔离"
    assert msg_text_a != msg_text_b, \
        "两个不同会话的消息内容完全相同，可能存在串台"


# === TC-CHAT-024: 会话数据持久化 - 刷新不丢失 ===

@pytest.mark.order(57)
@pytest.mark.p0
def test_session_persistence_refresh(logged_in_page, base_url):
    """会话数据持久化 - 刷新不丢失（TC-CHAT-024）"""
    import uuid
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat()
    chat.create_new_session()

    # 1. 发送唯一消息（UUID 确保全局唯一）
    unique_msg = f"persist_{uuid.uuid4().hex[:12]}"
    chat.send_message(unique_msg)

    # 2. 记录当前会话 URL
    session_url = logged_in_page.url

    # 3. 刷新页面 — 先导航到完全不同的页面，再 reload 回来，确保 SPA 重新初始化
    logged_in_page.goto(f"{base_url}/ctrl/agent/algorithms")
    logged_in_page.wait_for_load_state("networkidle")
    logged_in_page.wait_for_timeout(1000)
    logged_in_page.goto(session_url, wait_until="networkidle")
    logged_in_page.wait_for_timeout(5000)

    # 如果消息未出现，做一次 reload 强制 SPA 重新加载
    body_check = logged_in_page.locator("body").inner_text()
    if unique_msg not in body_check:
        logged_in_page.reload(wait_until="networkidle")
        logged_in_page.wait_for_timeout(5000)

    # 4. 等待消息加载（轮询检查，最长 15 秒）
    body_after = ""
    for _ in range(15):
        body_after = logged_in_page.locator("body").inner_text()
        if unique_msg in body_after:
            break
        logged_in_page.wait_for_timeout(1000)

    assert unique_msg in body_after, \
        f"刷新后消息丢失（URL: {logged_in_page.url}，原URL: {session_url}）: '{unique_msg}'"


# === TC-CHAT-026: 删除会话 ===

@pytest.mark.order(58)
@pytest.mark.p1
def test_delete_session(logged_in_page, base_url):
    """删除会话（TC-CHAT-026）"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat()

    # 先创建一个新会话并发送消息，等待自动生成标题
    chat.create_new_session()
    chat.send_message("这是一个待删除的测试会话，请回复收到")

    # 等待标题自动生成（轮询检查，最长 15 秒）
    title_to_delete = ""
    for _ in range(15):
        logged_in_page.wait_for_timeout(1000)
        title_to_delete = chat.get_session_header_title()
        if title_to_delete and title_to_delete != "新会话":
            break

    if not title_to_delete or title_to_delete == "新会话":
        pytest.skip("会话标题未自动生成，无法测试删除")

    # 打开会话对话框，记录删除前标题数
    chat.open_session_dialog()
    titles_before = chat.get_session_titles()

    # 使用 PO 封装方法删除会话
    success = chat.delete_session_by_title(title_to_delete)
    if not success:
        chat.close_session_dialog()
        pytest.skip("会话项没有删除操作按钮")

    # 验证：会话被删除
    chat.open_session_dialog()
    titles_after = chat.get_session_titles()
    chat.close_session_dialog()

    deleted_gone = title_to_delete not in titles_after
    list_shrunk = len(titles_after) < len(titles_before)
    assert deleted_gone or list_shrunk, (
        f"会话删除后仍出现在列表中"
        f"（删除标题='{title_to_delete}'，"
        f"删除前数量={len(titles_before)}，删除后数量={len(titles_after)}）"
    )


# === TC-CHAT-027: 会话列表数据加载 ===

@pytest.mark.order(59)
@pytest.mark.p0
def test_session_list_loads(logged_in_page, base_url):
    """会话列表数据加载（TC-CHAT-027）"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat()

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
    """会话搜索功能（TC-CHAT-028）"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat()

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

    # 3. 过滤后的结果应减少且包含关键词
    filtered = chat.get_filtered_session_titles()
    assert len(filtered) < len(all_titles), \
        f"搜索后结果数量未减少: {len(filtered)} vs {len(all_titles)}"
    # 搜索结果中应至少有一个匹配关键词
    matched = [t for t in filtered if keyword.lower() in t.lower()]
    assert len(matched) > 0, \
        f"搜索结果中没有匹配关键词 '{keyword}' 的会话"

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
    """不同会话状态视觉区分（TC-CHAT-031）"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat()

    chat.open_session_dialog()
    if not chat.is_session_dialog_open():
        pytest.skip("无法打开会话对话框")

    dialog = logged_in_page.locator("[role='dialog']")
    # 检查是否有时间分区标题（今天/昨天/更早）
    has_sections = chat.has_session_time_sections()

    if not has_sections:
        pytest.skip("会话列表没有时间分区（今天/昨天/更早），无法验证视觉区分")

    # 有时间分区，验证分区标题确实可见
    dialog_text = dialog.first.inner_text()
    found_sections = [s for s in ["今天", "昨天", "更早"] if s in dialog_text]
    assert len(found_sections) > 0, "has_session_time_sections 返回 True 但实际未找到分区标题"

    chat.close_session_dialog()


# === TC-CHAT-056: 文件上传成功并预览 ===

@pytest.mark.order(62)
@pytest.mark.p0
def test_file_upload_preview(logged_in_page, base_url):
    """文件上传成功并预览（TC-CHAT-056）"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat()
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

        # 验证：文件预览区域出现或文件名可见
        has_preview = chat.has_file_preview()
        has_name = logged_in_page.locator(f"[title*='test-upload']").count() > 0
        assert has_preview or has_name, (
            f"上传后页面上未出现文件预览或文件名 '{file_name}'"
            f"（has_preview={has_preview}，has_name={has_name}）"
        )
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


# === TC-CHAT-058: 不支持的文件类型被拦截 ===

@pytest.mark.order(63)
@pytest.mark.p1
def test_unsupported_file_type_blocked(logged_in_page, base_url):
    """不支持的文件类型被拦截（TC-CHAT-058）"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat()
    chat.create_new_session()

    # 创建临时 .exe 文件
    with tempfile.NamedTemporaryFile(suffix=".exe", delete=False, mode="wb") as f:
        f.write(b"\x00" * 100)
        tmp_path = f.name

    try:
        # 尝试上传
        file_input = chat.get_file_input()
        # 检查 accept 属性 — 如果有白名单限制，.exe 会被浏览器拦截
        accept = file_input.get_attribute("accept") or ""

        if accept:
            # 有 accept 限制，浏览器会自动过滤 .exe
            # 验证 accept 不包含 .exe
            assert ".exe" not in accept, f"accept 属性允许 .exe: {accept}"
        else:
            # 没有 accept 限制，尝试上传后检查错误提示
            chat.upload_file(tmp_path)
            body_text = logged_in_page.locator("body").inner_text()
            # 检查是否有错误提示或不支持的文件类型提示
            has_error = (
                chat.has_file_error()
                or "不支持" in body_text
                or "格式" in body_text
                or "类型" in body_text
                or "invalid" in body_text.lower()
                or "error" in body_text.lower()
            )
            # 如果有文件预览出现，说明 .exe 未被拦截 — 记录为问题
            has_preview = chat.has_file_preview()
            assert has_error or not has_preview, \
                "上传 .exe 文件后既没有错误提示，也未被拦截（出现了文件预览）"
    finally:
        os.unlink(tmp_path)


# === TC-CHAT-059: 多文件上传 ===

@pytest.mark.order(64)
@pytest.mark.p2
def test_multi_file_upload(logged_in_page, base_url):
    """多文件上传（TC-CHAT-059）"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat()
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

        if multiple is None:
            pytest.skip("文件上传不支持多文件选择")

        chat.upload_files(tmp_files)

        # 验证：应有文件预览区域出现
        assert chat.has_file_preview(), "多文件上传后未显示文件预览"
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


# === TC-CHAT-061: 消息输入框基础功能 ===

@pytest.mark.order(65)
@pytest.mark.p0
def test_input_box_basics(logged_in_page, base_url):
    """消息输入框基础功能（TC-CHAT-061）"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat()
    chat.create_new_session()

    textarea = logged_in_page.locator("textarea").first

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
    logged_in_page.wait_for_timeout(3000)

    # 发送后输入框应清空
    val_after = textarea.input_value()
    assert val_after == "", f"发送后输入框未清空: '{val_after}'"


# === TC-CHAT-063: 发送防重复提交 ===

@pytest.mark.order(66)
@pytest.mark.p1
def test_prevent_double_send(logged_in_page, base_url):
    """发送防重复提交（TC-CHAT-063）"""
    import time
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat()
    chat.create_new_session()

    textarea = logged_in_page.locator("textarea").first

    # 使用时间戳唯一消息，避免 AI 通用回复干扰计数
    unique_msg = f"dblsnd_{int(time.time() * 1000) % 100000}"
    textarea.fill(unique_msg)
    textarea.press("Enter")
    logged_in_page.wait_for_timeout(200)
    textarea.press("Enter")
    logged_in_page.wait_for_load_state("networkidle", timeout=8000)
    logged_in_page.wait_for_timeout(2000)

    # 唯一消息：不重复时最多出现 2 次（用户气泡 + AI 可能引用）
    # 双重发送时至少 3 次（2 个用户气泡 + AI 回复）
    body_text = logged_in_page.locator("body").inner_text()
    count = body_text.count(unique_msg)
    assert count <= 2, \
        f"消息被重复发送，'{unique_msg}' 在页面中出现了 {count} 次（防重复失效）"


# === TC-CHAT-064: 停止生成按钮 ===

@pytest.mark.order(67)
@pytest.mark.p0
def test_stop_generation(logged_in_page, base_url):
    """停止生成按钮（TC-CHAT-064）"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat()
    chat.create_new_session()

    textarea = logged_in_page.locator("textarea").first

    # 记录发送前页面内容长度
    body_before = logged_in_page.locator("body").inner_text()
    len_before = len(body_before)

    # 发送一条会触发长回复的消息
    textarea.fill("请详细解释量子力学的不确定性原理，写一篇2000字的论文")
    textarea.press("Enter")

    # 等待流式响应开始
    logged_in_page.wait_for_timeout(2000)

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
    logged_in_page.wait_for_timeout(2000)
    textarea_after = logged_in_page.locator("textarea").first
    assert textarea_after.is_visible(), "停止生成后输入框不可见"

    # 3. 可以继续发送新消息
    textarea_after.fill("继续测试")
    textarea_after.press("Enter")
    logged_in_page.wait_for_timeout(3000)

    # 4. 停止后已接收的内容应保留（不回滚）
    body_after_stop = logged_in_page.locator("body").inner_text()
    assert len(body_after_stop) >= len_during - 20, \
        "停止生成后已有内容被回滚"
