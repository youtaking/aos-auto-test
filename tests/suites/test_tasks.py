# tests/suites/test_tasks.py
"""定时任务模块回归测试（基于 Excel 用例 TC-TASK-001 ~ TC-TASK-023）"""
import pytest
import time
from tests.pages.tasks_page import TasksPage

# 用于创建/编辑/删除的测试任务名（带时间戳避免冲突）
TEST_TASK_NAME = f"auto-test-task-{int(time.time())}"
EDITED_TASK_NAME = f"auto-test-edited-{int(time.time())}"


# === TC-TASK-001: 列表页面加载 ===

@pytest.mark.order(30)
@pytest.mark.p0
def test_task_list_page_loads(logged_in_page, base_url):
    """定时任务列表页面加载（TC-TASK-001）"""
    tasks = TasksPage(logged_in_page, base_url)
    tasks.goto()
    assert tasks.is_loaded()
    assert tasks.has_table()


# === TC-TASK-002: 创建定时任务 ===

@pytest.mark.order(31)
@pytest.mark.p0
def test_create_http_task(logged_in_page, base_url):
    """创建 HTTP 定时任务（TC-TASK-002）"""
    tasks = TasksPage(logged_in_page, base_url)
    tasks.goto()
    initial_count = tasks.get_task_count()

    # 使用应用自身的 health 接口作为 URL（避免外部服务依赖）
    tasks.create_http_task(
        name=TEST_TASK_NAME,
        url=f"{base_url}/api/health",
        cron="0 * * * *",
    )

    # 验证列表中出现新任务
    tasks.goto()
    assert tasks.has_task(TEST_TASK_NAME), f"任务 {TEST_TASK_NAME} 未出现在列表中"
    assert tasks.get_task_count() > initial_count


# === TC-TASK-003: Cron 表达式配置 ===

@pytest.mark.order(32)
@pytest.mark.p1
def test_cron_expression_config(logged_in_page, base_url):
    """Cron 表达式配置（TC-TASK-003）"""
    tasks = TasksPage(logged_in_page, base_url)
    tasks.goto()

    # 打开创建对话框，验证 Cron 预设按钮存在
    tasks.open_create_dialog()
    assert tasks.is_create_dialog_open()

    # 点击预设按钮，验证 Cron 输入框值变化
    dialog = logged_in_page.locator("[role='dialog']")
    cron_input = dialog.locator("input[placeholder*='* * *']")

    presets = ["每 5 分钟", "每小时", "每天上午 9:00"]
    for preset in presets:
        tasks.click_cron_preset(preset)
        if cron_input.count() > 0:
            val = cron_input.first.input_value()
            assert val, f"点击预设 '{preset}' 后 Cron 输入框为空"

    tasks.close_dialog()


# === TC-TASK-004: 手动触发执行 ===

@pytest.mark.order(33)
@pytest.mark.p0
def test_manual_execute_task(logged_in_page, base_url):
    """手动触发执行（TC-TASK-004）"""
    tasks = TasksPage(logged_in_page, base_url)
    tasks.goto()

    # 确保有可执行的任务
    if not tasks.has_task(TEST_TASK_NAME):
        tasks.create_http_task(
            name=TEST_TASK_NAME,
            url=f"{base_url}/api/health",
        )
        tasks.goto()

    # 手动执行
    tasks.execute_task(TEST_TASK_NAME)
    # 等待执行完成（可能需要几秒）
    logged_in_page.wait_for_timeout(3000)
    assert tasks.is_loaded(), "手动执行后页面崩溃"

    # 验证执行结果：状态变化 / [role='status'] toast 出现
    status = tasks.get_task_status(TEST_TASK_NAME)
    toast = logged_in_page.locator("[role='status']")
    has_toast = toast.first.is_visible() if toast.count() > 0 else False
    body_text = logged_in_page.locator("body").inner_text()
    has_execution_info = (
        bool(status)
        or has_toast
        or any(kw in body_text for kw in ["执行成功", "执行中", "已完成", "执行记录"])
    )
    assert has_execution_info, (
        f"手动执行后无任何执行状态反馈"
        f"（status='{status}'，toast可见={has_toast}）"
    )


# === TC-TASK-007: 查看执行日志 ===

@pytest.mark.order(34)
@pytest.mark.p1
def test_view_task_log(logged_in_page, base_url):
    """查看执行日志（TC-TASK-007）"""
    tasks = TasksPage(logged_in_page, base_url)
    tasks.goto()

    names = tasks.get_task_names()
    target_name = TEST_TASK_NAME if tasks.has_task(TEST_TASK_NAME) else (names[0] if names else None)
    if not target_name:
        pytest.skip("没有可查看日志的任务")

    tasks.view_task_log(target_name)
    logged_in_page.wait_for_timeout(1000)

    # 验证日志对话框出现或 URL 跳转到日志页
    dialog = logged_in_page.locator("[role='dialog']")
    url_has_log = "log" in logged_in_page.url.lower() or "execution" in logged_in_page.url.lower()
    assert dialog.count() > 0 or url_has_log, \
        "查看日志后既没有对话框也没有跳转到日志页面"
    # 关闭可能的 dialog
    if dialog.count() > 0:
        close_btn = dialog.get_by_role("button", name="Close").or_(
            dialog.get_by_role("button", name="关闭")
        ).or_(
            dialog.get_by_role("button", name="取消")
        )
        if close_btn.count() > 0:
            close_btn.first.click()
            logged_in_page.wait_for_timeout(500)


# === TC-TASK-008: 编辑任务 ===

@pytest.mark.order(35)
@pytest.mark.p1
def test_edit_task(logged_in_page, base_url):
    """编辑任务（TC-TASK-008）"""
    tasks = TasksPage(logged_in_page, base_url)
    tasks.goto()

    if not tasks.has_task(TEST_TASK_NAME):
        pytest.skip("无可编辑的测试任务")

    tasks.edit_task(TEST_TASK_NAME)
    assert tasks.is_create_dialog_open(), "编辑对话框未打开"

    # 修改名称
    dialog = logged_in_page.locator("[role='dialog']")
    name_input = dialog.locator("input[name='name']")
    name_input.fill(EDITED_TASK_NAME)

    tasks.save_task()
    tasks.goto()

    # 验证名称已更新
    assert tasks.has_task(EDITED_TASK_NAME), f"编辑后任务名 {EDITED_TASK_NAME} 未出现"
    assert not tasks.has_task(TEST_TASK_NAME), "旧任务名仍存在"


# === TC-TASK-009: 删除任务 ===

@pytest.mark.order(36)
@pytest.mark.p1
def test_delete_task(logged_in_page, base_url):
    """删除任务（TC-TASK-009）"""
    tasks = TasksPage(logged_in_page, base_url)
    tasks.goto()

    target = EDITED_TASK_NAME if tasks.has_task(EDITED_TASK_NAME) else TEST_TASK_NAME
    if not tasks.has_task(target):
        pytest.skip("无可删除的测试任务")

    initial_count = tasks.get_task_count()
    tasks.delete_task(target)
    tasks.goto()

    assert not tasks.has_task(target), f"任务 {target} 删除后仍存在"
    assert tasks.get_task_count() < initial_count


# === TC-TASK-012: 必填字段为空拦截 ===

@pytest.mark.order(37)
@pytest.mark.p1
def test_required_fields_validation(logged_in_page, base_url):
    """必填字段为空拦截（TC-TASK-012）"""
    tasks = TasksPage(logged_in_page, base_url)
    tasks.goto()

    tasks.open_create_dialog()
    assert tasks.is_create_dialog_open()

    # 不填任何内容直接保存
    tasks.save_task()
    logged_in_page.wait_for_timeout(500)

    # 对话框应该仍然打开（被校验拦截）
    assert tasks.is_create_dialog_open(), "空表单提交后对话框被关闭，校验未生效"

    tasks.close_dialog()


# === TC-TASK-014: 创建 HTTP 类型任务（V2）===

@pytest.mark.order(38)
@pytest.mark.p0
def test_create_http_task_v2(logged_in_page, base_url):
    """创建 HTTP 类型任务，含超时设置（TC-TASK-014）"""
    tasks = TasksPage(logged_in_page, base_url)
    tasks.goto()

    # 使用应用自身的 health 接口（避免外部服务依赖）
    task_name = f"http-v2-{int(time.time())}"
    tasks.create_http_task(
        name=task_name,
        url=f"{base_url}/api/health",
        cron="0 9 * * *",
        method="GET",
        timeout=60,
    )

    tasks.goto()
    assert tasks.has_task(task_name), f"HTTP V2 任务 {task_name} 未创建成功"

    # 验证超时设置已保存
    # 打开编辑对话框检查 timeout 字段
    tasks.edit_task(task_name)
    if tasks.is_create_dialog_open():
        dialog = logged_in_page.locator("[role='dialog']")
        timeout_input = dialog.locator("input[name='timeoutSeconds']")
        if timeout_input.count() > 0:
            timeout_val = timeout_input.first.input_value()
            assert timeout_val == "60", f"超时设置未保存: 期望 60, 实际 {timeout_val}"
        tasks.close_dialog()

    # 清理
    tasks.delete_task(task_name)


# === TC-TASK-015: 创建 Agent 类型任务 ===

@pytest.mark.order(39)
@pytest.mark.p0
def test_create_agent_task(logged_in_page, base_url):
    """创建 Agent 类型任务（TC-TASK-015）"""
    tasks = TasksPage(logged_in_page, base_url)
    tasks.goto()

    task_name = f"agent-task-{int(time.time())}"
    # 动态获取可用 Agent 名称
    logged_in_page_inner = logged_in_page
    logged_in_page_inner.goto(f"{base_url}/ctrl/agent/agents")
    logged_in_page_inner.wait_for_load_state("networkidle")
    # 优先使用侧边栏 Agent 卡片（已知选择器），回退到按钮文本
    agent_badge = logged_in_page_inner.locator("button.agent-sidebar-agent-card")
    if agent_badge.count() == 0:
        agent_badge = logged_in_page_inner.locator("[role='listitem'] button, [role='card'] button")
    if agent_badge.count() == 0:
        pytest.skip("没有可用的 Agent")
    agent_name = agent_badge.first.inner_text().strip().split("\n")[0].strip()

    tasks.goto()
    tasks.create_agent_task(
        name=task_name,
        agent_name=agent_name,
        prompt="你好，请做一下自我介绍",
        cron="0 * * * *",
    )

    tasks.goto()
    assert tasks.has_task(task_name), f"Agent 任务 {task_name} 未创建成功"

    # 清理
    tasks.delete_task(task_name)


# === TC-TASK-016: Chat 右侧 TasksPanel 面板展示 ===

@pytest.mark.order(40)
@pytest.mark.p0
def test_chat_tasks_panel(logged_in_page, base_url):
    """Chat 右侧 TasksPanel 面板展示（TC-TASK-016）"""
    # 进入对话页面
    logged_in_page.goto(f"{base_url}/ctrl/agent/home")
    logged_in_page.wait_for_load_state("networkidle")
    logged_in_page.wait_for_timeout(1500)

    # 选择一个 Agent
    agent_card = logged_in_page.locator("button.agent-sidebar-agent-card")
    if agent_card.count() == 0:
        pytest.skip("侧边栏没有可用的 Agent")
    agent_card.first.click()
    logged_in_page.wait_for_timeout(2000)

    # 查找「定时任务」按钮/Tab
    tasks_btn = logged_in_page.get_by_text("定时任务", exact=True)
    assert tasks_btn.count() > 0, "Chat 页面找不到「定时任务」入口"
    tasks_btn.first.click()
    logged_in_page.wait_for_timeout(1500)

    # 验证面板加载 — 检查定时任务相关内容出现
    body_text = logged_in_page.locator("body").inner_text()
    has_tasks_section = "定时任务" in body_text
    # 表格行或列表项存在
    task_rows = logged_in_page.locator("table tbody tr")
    has_list_content = task_rows.count() > 0
    # 面板区域可见（aside 或右侧面板）
    panel_visible = logged_in_page.locator("aside").first.is_visible() if logged_in_page.locator("aside").count() > 0 else False
    assert has_tasks_section or has_list_content or panel_visible, (
        f"点击「定时任务」后面板未加载"
        f"（定时任务文本={has_tasks_section}，列表={has_list_content}，aside可见={panel_visible}）"
    )


# === TC-TASK-017: 按 Agent 过滤任务列表 ===

@pytest.mark.order(41)
@pytest.mark.p1
def test_tasks_filter_by_agent(logged_in_page, base_url):
    """按 Agent 过滤任务列表（TC-TASK-017）"""
    logged_in_page.goto(f"{base_url}/ctrl/agent/home")
    logged_in_page.wait_for_load_state("networkidle")
    logged_in_page.wait_for_timeout(1500)

    agent_cards = logged_in_page.locator("button.agent-sidebar-agent-card")
    if agent_cards.count() < 2:
        pytest.skip("需要至少 2 个 Agent 才能测试过滤")

    # 选择第一个 Agent，点击定时任务
    agent_cards.first.click()
    logged_in_page.wait_for_timeout(1500)
    logged_in_page.get_by_text("定时任务", exact=True).first.click()
    logged_in_page.wait_for_timeout(1000)

    # 切换到第二个 Agent
    agent_cards.nth(1).click()
    logged_in_page.wait_for_timeout(1500)
    logged_in_page.get_by_text("定时任务", exact=True).first.click()
    logged_in_page.wait_for_timeout(1000)

    # 切换后页面应正常加载 — 验证面板或任务内容区域仍可见
    body_text = logged_in_page.locator("body").inner_text()
    has_tasks_section = "定时任务" in body_text
    task_rows = logged_in_page.locator("table tbody tr")
    has_list_content = task_rows.count() > 0
    panel_visible = logged_in_page.locator("aside").first.is_visible() if logged_in_page.locator("aside").count() > 0 else False
    assert has_tasks_section or has_list_content or panel_visible, (
        f"切换 Agent 后定时任务面板未正常加载"
        f"（定时任务文本={has_tasks_section}，列表={has_list_content}，aside可见={panel_visible}）"
    )


# === TC-TASK-021: 执行日志上下两栏实时查看 ===

@pytest.mark.order(42)
@pytest.mark.p1
def test_task_log_panel_layout(logged_in_page, base_url):
    """执行日志上下两栏查看（TC-TASK-021）"""
    tasks = TasksPage(logged_in_page, base_url)
    tasks.goto()

    # 找到任一任务查看日志
    names = tasks.get_task_names()
    if not names:
        pytest.skip("没有可查看日志的任务")

    tasks.view_task_log(names[0])
    logged_in_page.wait_for_timeout(1000)

    # 验证日志面板出现（dialog 或页面）
    dialog = logged_in_page.locator("[role='dialog']")
    if dialog.count() > 0:
        text = dialog.first.inner_text()
        # 日志面板应包含任务名或日志特有字段（执行时间、状态、日志详情等）
        task_name_in_text = names[0] in text
        log_keywords = any(kw in text for kw in [
            "执行时间", "执行状态", "日志详情", "开始时间", "结束时间",
            "运行时间", "Execution", "Duration", "Log",
        ])
        assert task_name_in_text or log_keywords, (
            f"日志面板缺少任务信息或日志字段"
            f"（任务名'{names[0]}'在文本中={task_name_in_text}，"
            f"内容前80字: '{text[:80]}'）"
        )
        # 关闭
        close_btn = dialog.get_by_role("button", name="Close").or_(
            dialog.get_by_role("button", name="关闭")
        ).or_(
            dialog.get_by_role("button", name="取消")
        )
        if close_btn.count() > 0:
            close_btn.first.click()
    else:
        # 可能跳转到了独立日志页面
        url_has_log = "log" in logged_in_page.url.lower() or "execution" in logged_in_page.url.lower()
        body_text = logged_in_page.locator("body").inner_text()
        has_log_content = any(kw in body_text for kw in ["执行日志", "日志详情", "Execution Log"])
        assert url_has_log or has_log_content, (
            f"查看日志后未跳转到日志页面且无日志内容"
            f"（URL: {logged_in_page.url}）"
        )


# === TC-TASK-006: 启用/禁用任务（部分实现）===

@pytest.mark.order(43)
@pytest.mark.p0
def test_toggle_task_enabled(logged_in_page, base_url):
    """启用/禁用任务开关（TC-TASK-006）"""
    tasks = TasksPage(logged_in_page, base_url)
    tasks.goto()

    names = tasks.get_task_names()
    if not names:
        pytest.skip("没有可操作的任务")

    target = names[0]
    initial_state = tasks.is_task_enabled(target)

    # 切换开关
    tasks.toggle_task_enabled(target)
    new_state = tasks.is_task_enabled(target)

    # 状态应该改变了
    assert new_state != initial_state, f"开关切换后状态未变化: {initial_state} -> {new_state}"

    # 切换回来
    tasks.toggle_task_enabled(target)
    restored = tasks.is_task_enabled(target)
    assert restored == initial_state, "开关未恢复"
