# tests/suites/test_chat_sidebar.py
"""Chat 侧边栏 — P1 缺失测试（Meta Agent 开关、重启按钮、共享智能体只读）

DOM 选择器均通过 Playwright MCP 在有头模式下对测试环境实测验证：
- 侧边栏容器: aside.agent-sidebar
- Meta Agent 开关: [role="switch"]（aria-checked 属性跟踪状态）
- 智能体操作按钮: button[title="..."]（展开实例/重启智能体/智能体配置/删除智能体/查看智能体详情）
- 共享智能体卡片: 包含 "共享" 文字标签
"""
import allure
import pytest


# === SIDEBAR-01: Meta Agent 开关切换 ===

@pytest.mark.order(200)
@pytest.mark.p1
def test_meta_agent_toggle(logged_in_page, base_url):
    """TC-SIDEBAR-001: Meta Agent 开关切换 — 点击后 aria-checked 状态变化并可恢复"""
    page = logged_in_page

    # 导航到首页确保侧边栏加载
    try:
        page.goto(f"{base_url}/ctrl/agent/home", wait_until="domcontentloaded")
    except Exception:
        pass
    page.wait_for_load_state("domcontentloaded")

    # 等待侧边栏加载
    sidebar = page.locator("aside.agent-sidebar")
    sidebar.wait_for(state="visible", timeout=10000)

    # 等待 agent 列表渲染完成
    for _ in range(10):
        if sidebar.locator("button.agent-sidebar-agent-card").count() > 0:
            break
        page.wait_for_timeout(1000)

    # 定位 Meta Agent 开关
    meta_switch = sidebar.locator('[role="switch"]')
    if meta_switch.count() == 0:
        pytest.skip("侧边栏中未找到 Meta Agent 开关")

    meta_switch.first.wait_for(state="visible", timeout=5000)

    # 记录当前状态
    state_before = meta_switch.first.get_attribute("aria-checked")
    assert state_before in ("true", "false"), (
        f"Meta Agent 开关 aria-checked 值异常: '{state_before}'"
    )

    # 点击切换
    meta_switch.first.click()
    page.wait_for_timeout(500)

    # 验证状态变化
    state_after = meta_switch.first.get_attribute("aria-checked")
    expected_after = "false" if state_before == "true" else "true"
    assert state_after == expected_after, (
        f"点击 Meta Agent 开关后状态未变化: "
        f"期望 '{expected_after}', 实际 '{state_after}'"
    )

    # 再次点击恢复原状
    meta_switch.first.click()
    page.wait_for_timeout(500)

    state_restored = meta_switch.first.get_attribute("aria-checked")
    assert state_restored == state_before, (
        f"再次点击 Meta Agent 开关后未恢复原状: "
        f"期望 '{state_before}', 实际 '{state_restored}'"
    )


# === SIDEBAR-02: 重启智能体按钮 ===

@pytest.mark.order(201)
@pytest.mark.p1
def test_restart_agent_button(logged_in_page, base_url):
    """TC-SIDEBAR-002: 重启智能体按钮 — 点击后弹出实例选择确认弹窗"""
    page = logged_in_page

    # 导航到首页确保侧边栏加载
    try:
        page.goto(f"{base_url}/ctrl/agent/home", wait_until="domcontentloaded")
    except Exception:
        pass
    page.wait_for_load_state("domcontentloaded")

    sidebar = page.locator("aside.agent-sidebar")
    sidebar.wait_for(state="visible", timeout=10000)

    # 等待 agent 列表渲染
    for _ in range(10):
        if sidebar.locator("button.agent-sidebar-agent-card").count() > 0:
            break
        page.wait_for_timeout(1000)

    # 找到第一个非共享智能体的重启按钮
    # 非共享智能体：不包含 "共享" 文字的卡片
    all_cards = sidebar.locator("button.agent-sidebar-agent-card")
    non_shared_restart_btn = None

    for i in range(all_cards.count()):
        card = all_cards.nth(i)
        card_text = card.inner_text()
        if "共享" in card_text:
            continue
        # 找到非共享智能体，在其父容器中查找重启按钮
        parent = card.locator("xpath=..")
        restart_btn = parent.locator("button[title='重启智能体']")
        if restart_btn.count() > 0:
            non_shared_restart_btn = restart_btn.first
            break

    if non_shared_restart_btn is None:
        pytest.skip("未找到非共享智能体的重启按钮")

    # 验证按钮可见且可点击
    assert non_shared_restart_btn.is_visible(), "重启智能体按钮不可见"
    assert non_shared_restart_btn.is_enabled(), "重启智能体按钮不可点击"

    # 点击重启按钮
    non_shared_restart_btn.click()
    page.wait_for_timeout(800)

    # 验证出现确认弹窗（alertdialog）
    confirm_dialog = page.locator("[role='alertdialog']")
    dialog_visible = False
    for _ in range(5):
        if confirm_dialog.count() > 0 and confirm_dialog.first.is_visible():
            dialog_visible = True
            break
        page.wait_for_timeout(500)

    assert dialog_visible, (
        "点击重启智能体按钮后未弹出确认弹窗（alertdialog）"
    )

    # 验证弹窗标题包含"重启"
    dialog_text = confirm_dialog.first.inner_text()
    assert "重启" in dialog_text, (
        f"重启确认弹窗内容异常，未包含'重启'关键字: '{dialog_text[:200]}'"
    )

    # 点击"稍后"按钮取消重启（不要真的重启）
    cancel_btn = confirm_dialog.first.locator("button").filter(has_text="稍后")
    if cancel_btn.count() > 0:
        cancel_btn.first.click()
        page.wait_for_timeout(500)
    else:
        # fallback: 按 Escape 关闭弹窗
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)

    # 验证弹窗已关闭
    dialog_gone = (
        confirm_dialog.count() == 0
        or not confirm_dialog.first.is_visible()
    )
    assert dialog_gone, "取消后重启确认弹窗未关闭"


# === SIDEBAR-03: 共享智能体只读模式 ===

@pytest.mark.order(202)
@pytest.mark.p1
def test_shared_agent_readonly(logged_in_page, base_url):
    """TC-SIDEBAR-003: 共享智能体只读 — 操作按钮仅有展开实例和查看详情"""
    page = logged_in_page

    # 导航到首页确保侧边栏加载
    try:
        page.goto(f"{base_url}/ctrl/agent/home", wait_until="domcontentloaded")
    except Exception:
        pass
    page.wait_for_load_state("domcontentloaded")

    sidebar = page.locator("aside.agent-sidebar")
    sidebar.wait_for(state="visible", timeout=10000)

    # 等待 agent 列表渲染
    for _ in range(10):
        if sidebar.locator("button.agent-sidebar-agent-card").count() > 0:
            break
        page.wait_for_timeout(1000)

    # 找到所有共享智能体（卡片文本包含"共享"）
    all_cards = sidebar.locator("button.agent-sidebar-agent-card")
    shared_agents = []

    for i in range(all_cards.count()):
        card = all_cards.nth(i)
        card_text = card.inner_text()
        if "共享" in card_text:
            parent = card.locator("xpath=..")
            shared_agents.append(parent)

    if len(shared_agents) == 0:
        pytest.skip("侧边栏中未找到共享智能体")

    # 对每个共享智能体验证操作按钮
    for idx, agent_container in enumerate(shared_agents):
        agent_name_el = agent_container.locator("button.agent-sidebar-agent-card").first
        agent_name = agent_name_el.inner_text().replace("共享", "").strip()

        # 收集该智能体所有操作按钮的 title
        action_buttons = agent_container.locator("button[title]")
        button_titles = []
        for j in range(action_buttons.count()):
            title = action_buttons.nth(j).get_attribute("title")
            if title:
                button_titles.append(title)

        # 验证：应有"展开实例"和"查看智能体详情"
        assert "展开实例" in button_titles, (
            f"共享智能体 '{agent_name}' 缺少'展开实例'按钮，"
            f"实际按钮: {button_titles}"
        )
        assert "查看智能体详情" in button_titles, (
            f"共享智能体 '{agent_name}' 缺少'查看智能体详情'按钮，"
            f"实际按钮: {button_titles}"
        )

        # 验证：不应有"智能体配置"和"删除智能体"
        assert "智能体配置" not in button_titles, (
            f"共享智能体 '{agent_name}' 不应有'智能体配置'按钮（只读模式），"
            f"实际按钮: {button_titles}"
        )
        assert "删除智能体" not in button_titles, (
            f"共享智能体 '{agent_name}' 不应有'删除智能体'按钮（只读模式），"
            f"实际按钮: {button_titles}"
        )

    # 附加信息到 Allure 报告
    allure.attach(
        f"共验证 {len(shared_agents)} 个共享智能体的只读模式",
        name="测试摘要", attachment_type=allure.attachment_type.TEXT
    )
