# tests/suites/test_home.py
"""首页创建模块回归测试"""
import allure
import pytest


@allure.epic("首页")
@pytest.mark.order(10)
@pytest.mark.p1
def test_home_page_loads(logged_in_page, base_url):
    """TC-HOME-001: 首页加载并显示描述输入框"""
    logged_in_page.goto(f"{base_url}/ctrl/agent/home")
    logged_in_page.wait_for_load_state("networkidle")
    logged_in_page.wait_for_timeout(2000)

    textarea = logged_in_page.locator(
        "textarea[placeholder='描述你想要的 Agent 能力...']"
    )
    assert textarea.count() > 0, "首页未显示描述输入框"
    assert textarea.first.is_visible(), "描述输入框不可见"


@allure.epic("首页")
@pytest.mark.order(11)
@pytest.mark.p0
def test_home_quick_create_template(logged_in_page, base_url):
    """TC-HOME-002: 点击模板快捷填充描述"""
    logged_in_page.goto(f"{base_url}/ctrl/agent/home")
    logged_in_page.wait_for_load_state("networkidle")
    logged_in_page.wait_for_timeout(2000)

    # 获取所有模板药丸
    pills = logged_in_page.locator("button.agent-home-template-pill")
    assert pills.count() > 0, "首页无模板药丸按钮"

    # 点击第一个模板
    first_pill_text = pills.first.inner_text().strip()
    pills.first.click()
    logged_in_page.wait_for_timeout(1500)

    # 验证 textarea 被填充或弹出创建对话框
    textarea = logged_in_page.locator(
        "textarea[placeholder='描述你想要的 Agent 能力...']"
    )
    has_text_filled = (
        textarea.count() > 0 and len(textarea.first.input_value().strip()) > 0
    )
    has_dialog = logged_in_page.locator("[role='dialog']").count() > 0
    has_inline_form = (
        logged_in_page.locator("input[placeholder='例如 my-agent']").count() > 0
    )

    assert has_text_filled or has_dialog or has_inline_form, (
        f"点击模板 '{first_pill_text}' 后未填充描述、弹出对话框或显示创建表单"
    )

    # 清理：如果打开了对话框或表单，关闭/导航离开
    if has_dialog:
        close_btn = logged_in_page.locator("[role='dialog']").get_by_role(
            "button", name="取消"
        ).or_(
            logged_in_page.locator("[role='dialog']").get_by_role(
                "button", name="关闭"
            )
        )
        if close_btn.count() > 0:
            close_btn.first.click()
            logged_in_page.wait_for_timeout(500)
        else:
            logged_in_page.keyboard.press("Escape")
            logged_in_page.wait_for_timeout(500)


@allure.epic("首页")
@pytest.mark.order(12)
@pytest.mark.p1
def test_home_description_input(logged_in_page, base_url):
    """TC-HOME-003: 输入描述后一键创建按钮可用"""
    logged_in_page.goto(f"{base_url}/ctrl/agent/home")
    logged_in_page.wait_for_load_state("networkidle")
    logged_in_page.wait_for_timeout(2000)

    textarea = logged_in_page.locator(
        "textarea[placeholder='描述你想要的 Agent 能力...']"
    )
    if textarea.count() == 0:
        pytest.skip("首页无描述输入框")

    # 输入描述
    textarea.first.fill("帮我写一封正式的商务邮件")
    logged_in_page.wait_for_timeout(1000)

    # 验证一键创建按钮存在且可用
    polish_btn = logged_in_page.locator("button.agent-home-polish-btn").or_(
        logged_in_page.get_by_role("button", name="一键创建")
    )
    assert polish_btn.count() > 0, "一键创建按钮不存在"
    assert polish_btn.first.is_visible(), "一键创建按钮不可见"

    # 清理：清空输入
    textarea.first.fill("")
    logged_in_page.wait_for_timeout(500)
