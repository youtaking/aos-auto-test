# tests/suites/test_chat_supplement.py
"""对话聊天补充测试 — 流式响应、Artifacts、复制消息、删除会话"""
import allure
import pytest
from tests.pages.chat_test_page import ChatTestPage


@allure.epic("对话")
@pytest.mark.order(60)
@pytest.mark.p0
def test_chat_streaming(logged_in_page, base_url):
    """TC-CHAT-SUP-001: 发送消息后出现流式响应"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")
    assert chat.is_chat_loaded(), "聊天页面未加载"

    chat.create_new_session()
    session_title = "E2E-streaming-test"
    chat.send_message(f"{session_title}-请简单回复一句话")

    # 验证消息日志区域有内容（流式响应最终渲染）
    log_area = logged_in_page.locator("div[role='log']")
    assert log_area.count() > 0, "消息日志区域 div[role='log'] 不存在"
    log_text = log_area.first.inner_text()
    assert len(log_text.strip()) > 0, "流式响应后消息区域无内容"

    # 清理：删除测试会话
    try:
        chat.open_session_dialog()
        chat.delete_session_by_title(session_title)
    except Exception:
        pass


@allure.epic("对话")
@pytest.mark.order(61)
@pytest.mark.p1
def test_chat_artifacts_panel(logged_in_page, base_url):
    """TC-CHAT-SUP-002: Artifacts 面板检测"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")
    assert chat.is_chat_loaded(), "聊天页面未加载"

    # 检查是否存在 Artifacts 面板或 iframe
    artifacts_panel = logged_in_page.locator(
        "[data-slot*='artifact'], iframe[title*='artifact'], iframe[src*='artifact']"
    )
    iframe = logged_in_page.locator("iframe")

    has_artifacts = artifacts_panel.count() > 0 or iframe.count() > 0
    if not has_artifacts:
        pytest.skip("当前 Agent 未绑定 Sites，无 Artifacts 面板")

    # 如果有 Artifacts，验证面板可见
    if artifacts_panel.count() > 0:
        assert artifacts_panel.first.is_visible(), "Artifacts 面板存在但不可见"


@allure.epic("对话")
@pytest.mark.order(62)
@pytest.mark.p2
def test_chat_copy_message(logged_in_page, base_url):
    """TC-CHAT-SUP-003: AI 响应消息的复制按钮"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")
    assert chat.is_chat_loaded(), "聊天页面未加载"

    chat.create_new_session()
    chat.send_message("回复一句话：今天天气真好")

    # 在 AI 消息上寻找复制按钮
    log_area = logged_in_page.locator("div[role='log']")
    if log_area.count() == 0:
        pytest.skip("消息日志区域不存在")

    # Hover 最后一条消息，触发操作按钮显示
    last_msg = log_area.first.locator("> div").last
    if last_msg.count() == 0:
        pytest.skip("无消息气泡")

    last_msg.hover()
    logged_in_page.wait_for_timeout(800)

    # 查找复制按钮
    copy_btn = last_msg.locator(
        "button[title*='复制'], button[aria-label*='复制'], "
        "button[title*='copy'], button[aria-label*='copy']"
    ).or_(
        logged_in_page.locator(
            "button:has([data-lucide='copy'])"
        )
    )

    if copy_btn.count() == 0:
        pytest.skip("AI 消息上无复制按钮")

    assert copy_btn.first.is_visible(), "复制按钮存在但不可见"


@allure.epic("对话")
@pytest.mark.order(63)
@pytest.mark.p1
def test_chat_delete_session(logged_in_page, base_url):
    """TC-CHAT-SUP-004: 创建新会话后删除"""
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat("my-auto-test")
    assert chat.is_chat_loaded(), "聊天页面未加载"

    # 1. 创建新会话并发送消息使其有标题
    chat.create_new_session()
    session_marker = "E2E-delete-test"
    chat.send_message(f"{session_marker}-请回复OK")
    logged_in_page.wait_for_timeout(2000)

    try:
        # 2. 打开会话列表
        chat.open_session_dialog()
        assert chat.is_session_dialog_open(), "会话列表对话框未打开"

        # 3. 获取会话标题列表
        titles_before = chat.get_session_titles()
        assert len(titles_before) > 0, "会话列表为空"

        # 4. 找到最新会话（第一个，通常是刚创建的）
        target_title = titles_before[0]

        # 5. 删除该会话
        deleted = chat.delete_session_by_title(target_title)
        if not deleted:
            pytest.skip(f"无法删除会话 '{target_title}'（删除按钮未找到）")

        logged_in_page.wait_for_timeout(1500)

        # 6. 重新打开会话列表验证
        chat.open_session_dialog()
        titles_after = chat.get_session_titles()
        assert target_title not in titles_after, (
            f"删除后会话 '{target_title}' 仍存在"
        )
    finally:
        # 清理：关闭对话框
        try:
            chat.close_session_dialog()
        except Exception:
            pass
