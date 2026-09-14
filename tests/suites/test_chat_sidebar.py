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

# 多实例 Agent 点击「重启智能体」后弹出的选择弹窗（AgentSidebarTree.tsx）
_RESTART_DIALOG = "[data-slot='alert-dialog-content']"


def _restart_dialog_visible(page) -> bool:
    dialog = page.locator(_RESTART_DIALOG)
    return dialog.count() > 0 and dialog.first.is_visible()


def _dismiss_stray_dialog(page):
    """关闭上一轮循环残留的弹窗：其 overlay 会拦截后续点击"""
    if not _restart_dialog_visible(page):
        return
    page.keyboard.press("Escape")
    try:
        page.locator(_RESTART_DIALOG).first.wait_for(state="hidden", timeout=3000)
    except Exception:
        pass


def _confirm_restart_dialog(page) -> bool:
    """多实例选择弹窗默认全选运行中实例，点「重启选中」才会发出重启请求"""
    dialog = page.locator(_RESTART_DIALOG)
    try:
        dialog.first.wait_for(state="visible", timeout=2000)
    except Exception:
        return False

    title = (dialog.first.locator("h2, [role='heading']").first.text_content() or "").strip()
    if "重启" not in title:
        _dismiss_stray_dialog(page)
        pytest.fail(f"点击重启智能体后弹出非预期弹窗: {title!r}")

    confirm = dialog.first.get_by_role("button", name="重启选中", exact=True)
    assert confirm.count() == 1, f"'重启选中' 按钮匹配 {confirm.count()} 个，预期唯一"
    confirm.click()
    try:
        dialog.first.wait_for(state="hidden", timeout=5000)
    except Exception:
        pass
    return True


@pytest.mark.order(201)
@pytest.mark.p1
def test_restart_agent_button(logged_in_page, base_url):
    """TC-SIDEBAR-002: 重启智能体按钮 — 点击后触发实例重启请求

    实测 UI 行为（AgentSidebarTree.tsx handleRestartAgent）：
    - 1 个运行中实例：点击即 POST /instances/{id}/restart，无弹窗；
    - ≥2 个运行中实例：先弹「重启智能体实例」选择弹窗（默认全选），
      点「重启选中」后才发请求；
    - 无运行中实例：仅 toast 提示，不发请求。
    本用例拦截重启请求（route fulfill 假响应）仅断言点击确实发出请求，避免真重启共享实例。
    """
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

    all_cards = sidebar.locator("button.agent-sidebar-agent-card")
    if all_cards.count() == 0:
        pytest.skip("侧边栏无智能体卡片（重启按钮无可作用目标）")

    # 遍历非共享智能体卡片：点击其「重启智能体」按钮，断言发出重启请求。
    # 无运行中实例时点击 no-op，多实例时会先弹选择弹窗，故逐个尝试并处理弹窗，
    # 命中第一个真正发出请求的卡片即成功；全程拦截该请求避免真重启共享实例。
    fired = {"url": None}

    # 用 200 + success 兜底响应代替 abort，避免浏览器记录
    # "Failed to load resource: net::ERR_FAILED" 被 conftest 页面错误监控当作失败
    def _block(route):
        fired["url"] = route.request.url
        route.fulfill(
            status=200,
            content_type="application/json",
            body='{"success":true,"data":{}}',
        )

    page.route("**/web/instances/*/restart", _block)
    clicked_any = False
    try:
        for i in range(all_cards.count()):
            card = all_cards.nth(i)
            if "共享" in (card.inner_text() or ""):
                continue
            parent = card.locator("xpath=..")
            restart_btn = parent.locator("button[title='重启智能体']")
            if restart_btn.count() == 0:
                continue
            if not (restart_btn.first.is_visible() and restart_btn.first.is_enabled()):
                continue
            clicked_any = True
            # 残留弹窗的 overlay 会拦截点击，先关闭再点
            _dismiss_stray_dialog(page)
            restart_btn.first.click()

            # 轮询等待：单实例直启会立刻发请求，多实例需先确认选择弹窗
            dialog_handled = False
            for _ in range(12):
                if fired["url"]:
                    break
                if not dialog_handled and _restart_dialog_visible(page):
                    dialog_handled = _confirm_restart_dialog(page)
                page.wait_for_timeout(500)
            if fired["url"]:
                break
        if not clicked_any:
            pytest.skip("未找到非共享智能体的可用重启按钮")
        assert fired["url"], (
            "点击重启智能体按钮未触发重启请求——所选非共享智能体可能均无运行中实例"
        )
    finally:
        page.unroute("**/web/instances/*/restart", _block)


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
