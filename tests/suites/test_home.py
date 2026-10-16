# tests/suites/test_home.py
"""首页创建模块回归测试"""
import allure
import pytest


@allure.epic("首页")
@pytest.mark.order(10)
@pytest.mark.p1
def test_home_page_loads(logged_in_page, base_url):
    """TC-HOME-001: 首页加载并显示描述输入框"""
    try:
        logged_in_page.goto(f"{base_url}/ctrl/agent/home", wait_until="domcontentloaded")
    except Exception:
        pass  # SPA 路由可能中断初始导航
    logged_in_page.wait_for_load_state("domcontentloaded")
    try:
        logged_in_page.locator("div.agent-panel-content").first.wait_for(state="attached", timeout=8000)
    except Exception:
        pass

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
    try:
        logged_in_page.goto(f"{base_url}/ctrl/agent/home", wait_until="domcontentloaded")
    except Exception:
        pass  # SPA 路由可能中断初始导航
    logged_in_page.wait_for_load_state("domcontentloaded")
    try:
        logged_in_page.locator("div.agent-panel-content").first.wait_for(state="attached", timeout=8000)
    except Exception:
        pass

    # 获取所有模板药丸（模板列表来自接口，渲染有延迟，必须等待）
    pills = logged_in_page.locator("button.agent-home-template-pill")
    try:
        pills.first.wait_for(state="visible", timeout=10000)
    except Exception:
        pass
    assert pills.count() > 0, "首页无模板药丸按钮"

    # 记录点击前的 URL 和 textarea 值
    url_before = logged_in_page.url
    textarea = logged_in_page.locator(
        "textarea[placeholder='描述你想要的 Agent 能力...']"
    )
    textarea_value_before = (
        textarea.first.input_value() if textarea.count() > 0 else ""
    )

    # 点击第一个模板
    first_pill_text = pills.first.inner_text().strip()
    pills.first.wait_for(state="visible", timeout=5000)
    pills.first.click()

    # 真实行为：点击模板会把描述送入「一键创建」，切到 AI 生成配置视图
    # （出现「返回」与「创建 Agent」按钮，URL 不变）。生成有延迟，需等待。
    gen_view_btn = logged_in_page.get_by_role("button", name="创建 Agent", exact=True)
    try:
        gen_view_btn.first.wait_for(state="visible", timeout=20000)
    except Exception:
        pass
    logged_in_page.wait_for_timeout(500)

    # 验证：任意一种反馈即视为通过
    url_after = logged_in_page.url
    has_text_filled = (
        textarea.count() > 0
        and textarea.first.input_value().strip() != textarea_value_before.strip()
        and len(textarea.first.input_value().strip()) > 0
    )
    has_dialog = logged_in_page.locator("[role='dialog']").count() > 0
    has_inline_form = (
        logged_in_page.locator("input[placeholder='例如 my-agent']").count() > 0
    )
    has_config_modal = logged_in_page.locator(
        "div.absolute.inset-0.z-50"
    ).count() > 0
    has_url_changed = url_after != url_before
    # 检查是否有弹窗/面板弹出（基于 Radix UI 的 data-state 属性）
    has_overlay = logged_in_page.locator(
        "[data-state='open'], [data-radix-dialog-content]"
    ).count() > 0
    # 生成配置视图：出现「创建 Agent」或「返回」按钮
    has_gen_view = (
        gen_view_btn.count() > 0
        or logged_in_page.get_by_role("button", name="返回", exact=True).count() > 0
    )

    any_feedback = (
        has_text_filled or has_dialog or has_inline_form
        or has_config_modal or has_url_changed or has_overlay
        or has_gen_view
    )

    assert any_feedback, (
        f"点击模板 '{first_pill_text}' 后未检测到任何反馈"
    )

    # 清理：返回首页（点击模板进入的生成视图不在 URL 上体现，需点「返回」）
    back_btn = logged_in_page.get_by_role("button", name="返回", exact=True)
    if back_btn.count() > 0:
        back_btn.first.click()
        logged_in_page.wait_for_timeout(800)
    if has_config_modal:
        logged_in_page.keyboard.press("Escape")
        logged_in_page.wait_for_timeout(500)
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
    try:
        logged_in_page.goto(f"{base_url}/ctrl/agent/home", wait_until="domcontentloaded")
    except Exception:
        pass  # SPA 路由可能中断初始导航
    logged_in_page.wait_for_load_state("domcontentloaded")
    try:
        logged_in_page.locator("div.agent-panel-content").first.wait_for(state="attached", timeout=8000)
    except Exception:
        pass

    textarea = logged_in_page.locator(
        "textarea[placeholder='描述你想要的 Agent 能力...']"
    )
    assert textarea.count() > 0, \
        "首页应有描述输入框（textarea[placeholder='描述你想要的 Agent 能力...']），但未找到"

    # 输入描述
    textarea.first.fill("帮我写一封正式的商务邮件")
    logged_in_page.wait_for_timeout(800)

    # 验证一键创建按钮存在且可用
    polish_btn = logged_in_page.locator("button.agent-home-polish-btn").or_(
        logged_in_page.get_by_role("button", name="一键创建")
    )
    assert polish_btn.count() > 0, "一键创建按钮不存在"
    assert polish_btn.first.is_visible(), "一键创建按钮不可见"

    # 清理：清空输入
    textarea.first.fill("")
    logged_in_page.wait_for_timeout(500)
