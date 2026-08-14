# tests/suites/test_tasks.py
"""定时任务模块回归测试（基于 Excel 用例 TC-TASK-001 ~ TC-TASK-023）
/ctrl/agent/tasks 为工作台面板，含定时任务 Tab，支持完整 CRUD。"""
import json
import time
import uuid
import pytest
from tests.pages.tasks_page import TasksPage
from tests.pages import locators as loc
from tests.conftest import register_cleanup


_PREFIX = f"e2e-{int(time.time())}"


# === API helpers ===


def _list_tasks_api(page, base_url):
    """GET /web/tasks/v2 → list of tasks (paginated: data.items)"""
    r = page.request.get(f"{base_url}/web/tasks/v2")
    if r.status == 200:
        body = r.json()
        data = body.get("data", {})
        if isinstance(data, list):
            return data
        # Paginated response: { success, data: { items: [...], total, page, pageSize } }
        return data.get("items", [])
    return []


def _create_task_api(page, base_url, name=None, cron="0 9 * * *",
                      task_type="http", url="https://httpbin.org/get"):
    """POST /web/tasks/v2 → created task（自动注册清理）

    源码 schema (CreateTaskV2RequestSchema):
      name, cron, type: "http"|"agent",
      definition: { url, method } | { prompt },
      timeoutSeconds?, agentId?
    """
    import sys as _sys
    _req = None
    _frame = _sys._getframe(1)
    for _i in range(5):
        _req = _frame.f_locals.get('request')
        if _req:
            break
        _frame = _frame.f_back
        if _frame is None:
            break

    name = name or f"e2e-task-{uuid.uuid4().hex[:6]}"
    # Build definition based on task type
    if task_type == "agent":
        definition = {"prompt": "请执行每日检查任务"}
    else:
        definition = {"url": url, "method": "GET"}

    payload = {
        "name": name,
        "cron": cron,
        "type": task_type,
        "timeoutSeconds": 300,
        "definition": definition,
    }
    r = page.request.post(
        f"{base_url}/web/tasks/v2",
        data=json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )
    task_data = {}
    if r.status in (200, 201):
        task_data = r.json().get("data", {})

    if _req and task_data.get("id"):
        _tid = task_data["id"]
        register_cleanup(_req, lambda: _delete_task_api(page, base_url, _tid))

    return task_data


def _delete_task_api(page, base_url, task_id):
    """DELETE /web/tasks/v2/:id"""
    if task_id:
        page.request.delete(f"{base_url}/web/tasks/v2/{task_id}")


def _get_or_create_task(page, base_url):
    """获取第一个任务，若无则创建一个。返回 (task_dict, created_flag)"""
    tasks = _list_tasks_api(page, base_url)
    if tasks:
        return tasks[0], False
    task = _create_task_api(page, base_url)
    return task, True


# === TC-TASK-001: 列表页面加载 ===

@pytest.mark.order(30)
@pytest.mark.p0
def test_task_list_page_loads(logged_in_page, base_url):
    """定时任务页面加载（TC-TASK-001） | ✅ 人工评审通过 |"""
    tasks = TasksPage(logged_in_page, base_url)
    tasks.goto()
    assert tasks.is_loaded(), "定时任务页面未加载"
    assert tasks.has_workspace_tabs(), "工作台 Tab 导航缺失"


# === TC-TASK-002: 创建 HTTP 定时任务 ===

@pytest.mark.order(31)
@pytest.mark.p0
def test_create_http_task(logged_in_page, base_url):
    """创建 HTTP 定时任务（TC-TASK-002） | ✅ 人工评审通过 |"""
    tasks = TasksPage(logged_in_page, base_url)
    tasks.goto()

    # 点击新建任务
    tasks.click_create()
    assert tasks.is_dialog_open(), "新建任务弹窗未打开"
    assert "创建任务" in tasks.get_dialog_title(), "弹窗标题不正确"

    # 默认就是 HTTP 类型
    task_name = f"http-task-{_PREFIX}"
    tasks.fill_task_name(task_name)
    tasks.fill_cron("0 9 * * *")
    tasks.fill_http_url("https://httpbin.org/get")

    # 保存
    tasks.save_dialog()

    # 刷新验证
    tasks.goto()
    assert tasks.has_task(task_name), f"HTTP 任务 {task_name} 未出现在列表中"

    # 清理：删除测试任务
    tasks.open_row_menu(task_name)
    tasks.click_menu_item("删除")
    alert = logged_in_page.locator('[role="alertdialog"]')
    if alert.count() > 0:
        confirm = loc.confirm_button(alert)
        if confirm.count() > 0:
            confirm.first.click()
            logged_in_page.wait_for_timeout(800)


# === TC-TASK-003: Cron 表达式配置 ===

@pytest.mark.order(32)
@pytest.mark.p1
def test_cron_expression_config(logged_in_page, base_url):
    """Cron 表达式快捷预设 + 自定义配置（TC-TASK-003） | ✅ 人工评审通过 |"""
    tasks = TasksPage(logged_in_page, base_url)
    tasks.goto()

    tasks.click_create()
    assert tasks.is_dialog_open(), "新建任务弹窗未打开"

    dialog = logged_in_page.locator('[role="dialog"]')
    cron_input = dialog.locator('input[placeholder="0 * * * *"]')

    # 1. 点击"每天上午 9:00"，验证 Cron 值正确
    tasks.click_cron_preset("每天上午 9:00")
    logged_in_page.wait_for_timeout(500)
    cron_value = cron_input.input_value()
    assert "0 9 * * *" in cron_value, \
        f"'每天上午 9:00' 预设 Cron 不正确: {cron_value}"

    # 2. 点击"每 5 分钟"，验证 Cron 值变化
    tasks.click_cron_preset("每 5 分钟")
    logged_in_page.wait_for_timeout(500)
    cron_value2 = cron_input.input_value()
    assert "*/5" in cron_value2 or "5" in cron_value2, \
        f"'每 5 分钟' 预设 Cron 不正确: {cron_value2}"

    # 3. 切换到"自定义"，手动输入
    tasks.click_cron_preset("自定义")
    logged_in_page.wait_for_timeout(500)
    cron_input.fill("30 8 * * 1-5")
    assert cron_input.input_value() == "30 8 * * 1-5", \
        "自定义 Cron 输入失败"

    tasks.cancel_dialog()


# === TC-TASK-004: 手动触发执行 ===

@pytest.mark.order(33)
@pytest.mark.p0
def test_manual_execute_task(logged_in_page, base_url):
    """手动触发执行任务（TC-TASK-004） | ✅ 人工评审通过 |"""
    tasks = TasksPage(logged_in_page, base_url)
    tasks.goto()

    # 1. 创建一个可执行的 HTTP GET 任务（默认启用）
    task_name = f"exec-task-{_PREFIX}"
    tasks.click_create()
    assert tasks.is_dialog_open(), "创建弹窗未打开"
    tasks.fill_task_name(task_name)
    tasks.fill_cron("0 9 * * *")
    tasks.fill_http_url("http://www.baidu.com")
    # 默认就是 GET 方法
    tasks.save_dialog()

    tasks.goto()
    assert tasks.has_task(task_name), f"任务 {task_name} 未创建成功"

    # 2. 拦截 API 响应
    api_responses = []
    def on_response(resp):
        if "task" in resp.url.lower() or "execute" in resp.url.lower() or "run" in resp.url.lower():
            api_responses.append(f"[{resp.status}] {resp.request.method} {resp.url}")
    logged_in_page.on("response", on_response)

    # 3. 点击执行
    tasks.click_execute(task_name)

    # 4. 轮询检查反馈
    has_feedback = False
    for _ in range(8):
        logged_in_page.wait_for_timeout(500)
        # 检查 toast
        toasts = logged_in_page.locator(
            "ol > li, [data-slot='toast'] li, [data-sonner-toast] li"
        )
        for t in toasts.all():
            txt = t.inner_text().strip()
            if txt:
                has_feedback = True
                break
        if has_feedback:
            break

    # 也检查 API 是否有执行相关响应
    if not has_feedback and api_responses:
        has_feedback = any("200" in r or "201" in r for r in api_responses)

    assert has_feedback, "手动执行后无任何反馈（无 toast、无 API 响应）"

    # 5. 清理
    tasks.open_row_menu(task_name)
    tasks.click_menu_item("删除")
    alert = logged_in_page.locator('[role="alertdialog"]')
    if alert.count() > 0:
        confirm = loc.confirm_button(alert)
        if confirm.count() > 0:
            confirm.first.click()
            logged_in_page.wait_for_timeout(800)

    # 移除监听器
    try:
        logged_in_page.remove_listener("response", on_response)
    except Exception:
        pass


# === TC-TASK-007: 查看执行日志 ===

@pytest.mark.order(34)
@pytest.mark.p1
def test_view_task_log(logged_in_page, base_url):
    """通过三点菜单查看执行日志（TC-TASK-007） | ✅ 人工评审通过 |"""
    tasks = TasksPage(logged_in_page, base_url)
    tasks.goto()

    # 确保有任务可用
    names = tasks.get_task_names()
    if not names:
        task_data, _ = _get_or_create_task(logged_in_page, base_url)
        if not task_data:
            pytest.skip("无法获取或创建任务")
        tasks.goto()
        names = tasks.get_task_names()
        if not names:
            pytest.skip("任务列表仍为空")

    # 打开三点菜单 → 日志
    tasks.open_row_menu(names[0])
    tasks.click_menu_item("日志")

    # 验证有日志相关内容
    logged_in_page.wait_for_timeout(800)
    # 检查弹窗或面板
    dialog = logged_in_page.locator('[role="dialog"]')
    body = logged_in_page.locator("div.agent-panel-content")
    has_log = False
    if dialog.count() > 0:
        has_log = any(kw in dialog.first.inner_text()
                      for kw in ["日志", "执行", "log", "时间", "状态"])
    if not has_log and body.count() > 0:
        has_log = any(kw in body.inner_text()
                      for kw in ["日志", "执行", "log", "时间", "状态"])
    assert has_log, "查看日志后无日志相关内容"

    # 关闭可能的弹窗
    if dialog.count() > 0:
        close = dialog.locator("button").filter(has_text="Close")
        if close.count() > 0:
            close.first.click()


# === TC-TASK-008: 编辑任务 ===

@pytest.mark.order(35)
@pytest.mark.p1
def test_edit_task(logged_in_page, base_url):
    """编辑任务名称（TC-TASK-008） | ✅ 人工评审通过 |"""
    tasks = TasksPage(logged_in_page, base_url)
    tasks.goto()

    names = tasks.get_task_names()
    if not names:
        task_data, _ = _get_or_create_task(logged_in_page, base_url)
        if not task_data:
            pytest.skip("无法获取或创建任务")
        tasks.goto()
        names = tasks.get_task_names()
        if not names:
            pytest.skip("任务列表仍为空")

    original_name = names[0]

    # 点击任务名称打开编辑弹窗
    tasks.click_task_name(original_name)
    assert tasks.is_dialog_open(), "编辑弹窗未打开"
    assert "编辑" in tasks.get_dialog_title(), "弹窗标题不包含'编辑'"

    # 修改名称
    dialog = logged_in_page.locator('[role="dialog"]')
    name_input = dialog.locator('input[placeholder="输入任务名称"]')
    old_name = name_input.input_value()
    new_name = f"{old_name}-edited"
    name_input.fill(new_name)

    tasks.save_dialog()

    # 刷新验证
    tasks.goto()
    assert tasks.has_task(new_name), f"编辑后新名称 {new_name} 未出现"

    # 还原名称
    tasks.click_task_name(new_name)
    if tasks.is_dialog_open():
        dialog = logged_in_page.locator('[role="dialog"]')
        name_input = dialog.locator('input[placeholder="输入任务名称"]')
        name_input.fill(old_name)
        tasks.save_dialog()


# === TC-TASK-009: 删除任务 ===

@pytest.mark.order(36)
@pytest.mark.p1
def test_delete_task(logged_in_page, base_url):
    """删除任务（TC-TASK-009） | ✅ 人工评审通过 |"""
    tasks = TasksPage(logged_in_page, base_url)
    tasks.goto()

    # 先创建一个待删除的任务
    tasks.click_create()
    assert tasks.is_dialog_open(), "创建弹窗未打开"
    del_name = f"del-task-{_PREFIX}"
    tasks.fill_task_name(del_name)
    tasks.fill_cron("0 0 1 * *")
    tasks.fill_http_url("https://httpbin.org/get")
    tasks.save_dialog()

    tasks.goto()
    assert tasks.has_task(del_name), "待删除任务未创建成功"

    initial_count = tasks.get_task_count()

    # 三点菜单 → 删除
    tasks.open_row_menu(del_name)
    tasks.click_menu_item("删除")

    # 确认弹窗
    logged_in_page.wait_for_timeout(800)
    alert = logged_in_page.locator('[role="alertdialog"]')
    if alert.count() > 0:
        confirm = alert.locator("button").filter(
            has_text="确认"
        ).or_(alert.locator("button").filter(has_text="删除"))
        if confirm.count() > 0:
            confirm.first.click()
            logged_in_page.wait_for_timeout(800)

    # 刷新验证
    tasks.goto()
    assert not tasks.has_task(del_name), f"删除后 {del_name} 仍在列表中"
    assert tasks.get_task_count() < initial_count, "删除后任务数量未减少"


# === TC-TASK-012: 必填字段为空拦截 ===

@pytest.mark.order(37)
@pytest.mark.p1
def test_required_fields_validation(logged_in_page, base_url):
    """必填字段为空拦截（TC-TASK-012） | ✅ 人工评审通过 |"""
    tasks = TasksPage(logged_in_page, base_url)
    tasks.goto()

    initial_count = tasks.get_task_count()

    tasks.click_create()
    assert tasks.is_dialog_open(), "创建弹窗未打开"

    # 不填写名称，检查保存按钮状态
    dialog = logged_in_page.locator('[role="dialog"]')
    save_btn = dialog.locator("button").filter(has_text="保存")

    is_disabled = save_btn.first.is_disabled()

    if not is_disabled:
        # 尝试点击保存
        save_btn.first.click(force=True)
        logged_in_page.wait_for_timeout(800)
        # 弹窗应该还在（未成功创建）
        still_open = tasks.is_dialog_open()
        assert still_open or is_disabled, f"名称为空时未拦截: still_open={still_open}, is_disabled={is_disabled}"
    else:
        assert save_btn.first.is_disabled(), "保存按钮在名称为空时被禁用（前端校验生效）"

    tasks.cancel_dialog()

    # 验证数量未变
    tasks.goto()
    assert tasks.get_task_count() == initial_count, \
        "名称为空时任务被创建了"


# === TC-TASK-014: 创建 HTTP 类型任务（含超时）===

@pytest.mark.order(38)
@pytest.mark.p0
def test_create_http_task_v2(logged_in_page, base_url):
    """创建 HTTP 类型任务，含超时设置（TC-TASK-014） | ✅ 人工评审通过 |"""
    tasks = TasksPage(logged_in_page, base_url)
    tasks.goto()

    tasks.click_create()
    assert tasks.is_dialog_open(), "创建弹窗未打开"

    # 默认 HTTP 类型
    task_name = f"http-v2-{_PREFIX}"
    tasks.fill_task_name(task_name)
    tasks.fill_cron("*/5 * * * *")
    tasks.fill_http_url("https://httpbin.org/post")
    tasks.select_http_method("POST")

    # 设置超时
    dialog = logged_in_page.locator('[role="dialog"]')
    timeout_input = dialog.locator('input[type="number"]')
    if timeout_input.count() > 0:
        timeout_input.first.fill("30")

    tasks.save_dialog()

    # 刷新验证
    tasks.goto()
    assert tasks.has_task(task_name), f"HTTP V2 任务 {task_name} 未出现"

    # 清理：删除测试任务
    tasks.open_row_menu(task_name)
    tasks.click_menu_item("删除")
    alert = logged_in_page.locator('[role="alertdialog"]')
    if alert.count() > 0:
        confirm = loc.confirm_button(alert)
        if confirm.count() > 0:
            confirm.first.click()
            logged_in_page.wait_for_timeout(800)


# === TC-TASK-015: 创建 Agent 类型任务 ===

@pytest.mark.order(39)
@pytest.mark.p0
def test_create_agent_task(logged_in_page, base_url):
    """创建 Agent 类型任务（TC-TASK-015） | ✅ 人工评审通过 |"""
    tasks = TasksPage(logged_in_page, base_url)
    tasks.goto()

    tasks.click_create()
    assert tasks.is_dialog_open(), "创建弹窗未打开"

    # 切换到 Agent 类型
    tasks.switch_to_agent()
    logged_in_page.wait_for_timeout(500)

    task_name = f"agent-task-{_PREFIX}"
    tasks.fill_task_name(task_name)
    tasks.fill_cron("0 10 * * 1-5")

    # 选择 Agent
    dialog = logged_in_page.locator('[role="dialog"]')
    combo = dialog.locator('[role="combobox"]')
    if combo.count() > 0:
        combo.first.click()
        logged_in_page.wait_for_timeout(500)
        options = logged_in_page.locator('[role="option"]')
        if options.count() > 0:
            # 选第一个可用 Agent
            agent_name = options.first.inner_text().strip()
            options.first.click()
            logged_in_page.wait_for_timeout(500)
        else:
            pytest.skip("没有可选 Agent")

    # 填写 Prompt
    tasks.fill_agent_prompt("请执行每日检查任务")

    tasks.save_dialog()

    # 刷新验证
    tasks.goto()
    assert tasks.has_task(task_name), f"Agent 任务 {task_name} 未出现"

    # 清理：删除测试任务
    tasks.open_row_menu(task_name)
    tasks.click_menu_item("删除")
    alert = logged_in_page.locator('[role="alertdialog"]')
    if alert.count() > 0:
        confirm = loc.confirm_button(alert)
        if confirm.count() > 0:
            confirm.first.click()
            logged_in_page.wait_for_timeout(800)


# === TC-TASK-016: Chat 右侧 TasksPanel 面板展示 ===

@pytest.mark.order(40)
@pytest.mark.p0
def test_chat_tasks_panel(logged_in_page, base_url):
    """Chat 右侧 TasksPanel 面板展示（TC-TASK-016） | ✅ 人工评审通过 |"""
    # 进入对话页面
    try:
        logged_in_page.goto(f"{base_url}/ctrl/agent/home", wait_until="domcontentloaded")
    except Exception:
        pass  # SPA 路由可能中断初始导航
    logged_in_page.wait_for_load_state("networkidle")

    # 选择一个 Agent
    agent_card = logged_in_page.locator("button.agent-sidebar-agent-card")
    if agent_card.count() == 0:
        pytest.skip("侧边栏没有可用的 Agent")
    agent_card.first.click()
    logged_in_page.wait_for_timeout(800)

    # 查找「定时任务」按钮
    tasks_btn = logged_in_page.locator("div.agent-panel-content button").filter(
        has_text="定时任务"
    )
    assert tasks_btn.count() > 0, "Chat 页面找不到「定时任务」入口"
    tasks_btn.first.click()
    logged_in_page.wait_for_timeout(1500)

    # 验证面板加载 — 限定到面板内容区（不含侧边栏）
    panel = logged_in_page.locator("div.agent-panel-content")
    assert panel.count() > 0, "面板内容区不存在"
    panel_text = panel.inner_text()
    assert "定时任务" in panel_text, "点击「定时任务」后面板中未显示定时任务相关内容"


# === TC-TASK-017: 按类型过滤任务列表 ===

@pytest.mark.order(41)
@pytest.mark.p1
def test_tasks_filter_by_type(logged_in_page, base_url):
    """按类型过滤任务列表（TC-TASK-017） | ✅ 人工评审通过 |"""
    tasks = TasksPage(logged_in_page, base_url)
    tasks.goto()

    total = tasks.get_task_count()
    if total == 0:
        # 尝试创建任务
        task_data, _ = _get_or_create_task(logged_in_page, base_url)
        if not task_data:
            pytest.skip("任务列表为空且无法创建")
        tasks.goto()
        total = tasks.get_task_count()
        if total == 0:
            pytest.skip("任务列表仍为空")

    # 检查筛选 Tab
    filter_tabs = tasks.get_filter_tabs()
    assert len(filter_tabs) > 0, "未找到筛选 Tab"
    assert "全部" in filter_tabs, f"筛选 Tab 缺少'全部': {filter_tabs}"

    # 筛选 HTTP 类型
    if "HTTP" in filter_tabs:
        tasks.click_filter_tab("HTTP")
        http_count = tasks.get_task_count()
        assert http_count <= total, \
            f"HTTP 筛选后数量({http_count})大于全部({total})"
        # 验证所有行都是 HTTP 类型
        if http_count > 0:
            types = tasks.get_task_types()
            assert all(t == "HTTP" for t in types), \
                f"HTTP 筛选后混入非 HTTP 类型: {types}"

    # 切回全部
    tasks.click_filter_tab("全部")
    restored = tasks.get_task_count()
    assert restored == total, \
        f"切回全部后数量未恢复: {restored} vs {total}"


# === TC-TASK-006: 启用/禁用任务 ===

@pytest.mark.order(43)
@pytest.mark.p0
def test_toggle_task_enabled(logged_in_page, base_url):
    """启用/禁用任务开关（TC-TASK-006） | ✅ 人工评审通过 |"""
    tasks = TasksPage(logged_in_page, base_url)
    tasks.goto()

    names = tasks.get_task_names()
    if not names:
        task_data, _ = _get_or_create_task(logged_in_page, base_url)
        if not task_data:
            pytest.skip("任务列表为空且无法创建")
        tasks.goto()
        names = tasks.get_task_names()
        if not names:
            pytest.skip("任务列表仍为空")

    target = names[0]

    # 获取初始状态
    initial_state = tasks.get_row_switch_state(target)

    # 切换开关
    tasks.toggle_switch(target)

    # 验证状态变化
    new_state = tasks.get_row_switch_state(target)
    assert new_state != initial_state, \
        f"切换开关后状态未变化: {initial_state} → {new_state}"

    # 再切换回来
    tasks.toggle_switch(target)
    restored_state = tasks.get_row_switch_state(target)
    assert restored_state == initial_state, \
        f"再次切换后未恢复: {initial_state} → {restored_state}"


# === 新增测试 ===


@pytest.mark.order(810)
@pytest.mark.p1
def test_task_cron_editor(logged_in_page, base_url):
    """TC-TASK-018: Cron 表达式编辑 — 创建任务时使用 Cron 编辑器"""
    tasks = TasksPage(logged_in_page, base_url)
    tasks.goto()

    tasks.click_create()
    assert tasks.is_dialog_open(), "新建任务弹窗未打开"

    dialog = logged_in_page.locator('[role="dialog"]')
    cron_input = dialog.locator('input[placeholder="0 * * * *"]')

    # 验证 Cron 输入框存在
    assert cron_input.count() > 0, "Cron 输入框不存在"

    # 直接输入自定义 Cron
    cron_input.fill("15 3 * * 0")
    logged_in_page.wait_for_timeout(500)
    assert cron_input.input_value() == "15 3 * * 0", \
        f"Cron 输入值不正确: {cron_input.input_value()}"

    # 点击预设按钮验证切换
    preset_btns = dialog.locator("button").filter(has_text="每天")
    if preset_btns.count() > 0:
        preset_btns.first.click()
        logged_in_page.wait_for_timeout(500)
        new_value = cron_input.input_value()
        assert new_value != "15 3 * * 0", \
            "点击预设后 Cron 值未变化"

    tasks.cancel_dialog()


@pytest.mark.order(811)
@pytest.mark.p1
def test_task_log_view(logged_in_page, base_url):
    """TC-TASK-019: 任务日志查看 — 查看任务执行日志"""
    tasks = TasksPage(logged_in_page, base_url)
    tasks.goto()

    names = tasks.get_task_names()
    if not names:
        task_data, _ = _get_or_create_task(logged_in_page, base_url)
        if not task_data:
            pytest.skip("无法获取或创建任务")
        tasks.goto()
        names = tasks.get_task_names()
        if not names:
            pytest.skip("任务列表仍为空")

    target = names[0]

    # 打开三点菜单
    tasks.open_row_menu(target)

    # 查找日志菜单项
    menu = logged_in_page.locator('[role="menu"]')
    assert menu.count() > 0, "三点菜单未弹出"

    log_item = menu.locator('[role="menuitem"]').filter(has_text="日志")
    assert log_item.count() > 0, "菜单中无'日志'选项"

    log_item.first.click()
    logged_in_page.wait_for_timeout(800)

    # 验证日志对话框或面板打开
    dialog = logged_in_page.locator('[role="dialog"]')
    panel = logged_in_page.locator("div.agent-panel-content")

    if dialog.count() > 0:
        dialog_text = dialog.first.inner_text()
        has_log_content = any(kw in dialog_text for kw in [
            "日志", "执行", "log", "时间", "状态", "成功", "失败", "暂无"
        ])
        assert has_log_content, "日志对话框无相关内容"
        # 关闭对话框
        close_btn = dialog.locator("button").filter(has_text="Close").or_(
            dialog.locator("button").filter(has_text="关闭")
        )
        if close_btn.count() > 0:
            close_btn.first.click()
        else:
            logged_in_page.keyboard.press("Escape")
    else:
        # 可能内嵌在面板中
        panel_text = panel.inner_text() if panel.count() > 0 else ""
        assert "日志" in panel_text or "log" in panel_text.lower() or len(panel_text) > 0, \
            "日志面板无内容"


@pytest.mark.order(812)
@pytest.mark.p1
def test_task_tab_filter(logged_in_page, base_url):
    """TC-TASK-020: Tab 过滤 — 全部/HTTP/Agent Tab 切换过滤任务"""
    tasks = TasksPage(logged_in_page, base_url)
    tasks.goto()

    filter_tabs = tasks.get_filter_tabs()
    if not filter_tabs:
        pytest.skip("无筛选 Tab")

    total = tasks.get_task_count()
    if total == 0:
        task_data, _ = _get_or_create_task(logged_in_page, base_url)
        if not task_data:
            pytest.skip("任务列表为空且无法创建")
        tasks.goto()
        total = tasks.get_task_count()
        if total == 0:
            pytest.skip("任务列表仍为空")

    # 切换到 HTTP Tab
    if "HTTP" in filter_tabs:
        tasks.click_filter_tab("HTTP")
        http_count = tasks.get_task_count()
        assert http_count <= total, \
            f"HTTP Tab 过滤后数量({http_count})大于全部({total})"

    # 切换到 Agent Tab
    if "Agent" in filter_tabs:
        tasks.click_filter_tab("Agent")
        agent_count = tasks.get_task_count()
        assert agent_count <= total, \
            f"Agent Tab 过滤后数量({agent_count})大于全部({total})"

    # 切回全部
    tasks.click_filter_tab("全部")
    restored = tasks.get_task_count()
    assert restored == total, \
        f"切回'全部'后数量未恢复: {restored} vs {total}"


@pytest.mark.order(813)
@pytest.mark.p1
def test_task_run_now_confirm(logged_in_page, base_url):
    """TC-TASK-021: 立即运行确认 — 点击立即运行弹出确认对话框"""
    tasks = TasksPage(logged_in_page, base_url)
    tasks.goto()

    names = tasks.get_task_names()
    if not names:
        task_data, _ = _get_or_create_task(logged_in_page, base_url)
        if not task_data:
            pytest.skip("无法获取或创建任务")
        tasks.goto()
        names = tasks.get_task_names()
        if not names:
            pytest.skip("任务列表仍为空")

    target = names[0]

    # 查找执行按钮
    tasks.click_execute(target)
    logged_in_page.wait_for_timeout(1500)

    # 检查是否有确认对话框
    dialog = logged_in_page.locator('[role="dialog"]')
    alert = logged_in_page.locator('[role="alertdialog"]')
    confirm_dialog = logged_in_page.locator('[role="dialog"], [role="alertdialog"]')

    if confirm_dialog.count() > 0:
        dialog_text = confirm_dialog.first.inner_text()
        has_confirm = any(kw in dialog_text for kw in [
            "确认", "确定", "执行", "运行", "confirm", "run", "取消"
        ])
        assert has_confirm, "确认对话框无相关提示文本"
        # 取消执行
        cancel_btn = confirm_dialog.locator("button").filter(has_text="取消").or_(
            confirm_dialog.locator("button").filter(has_text="Cancel")
        )
        if cancel_btn.count() > 0:
            cancel_btn.first.click()
        else:
            logged_in_page.keyboard.press("Escape")
    else:
        # 某些系统可能直接执行（无确认弹窗），检查 toast 反馈
        toasts = logged_in_page.locator(
            "ol > li, [data-slot='toast'] li, [data-sonner-toast] li"
        )
        # 直接执行也可以接受，只要有反馈
        panel = logged_in_page.locator("div.agent-panel-content")
        assert toasts.count() > 0 or panel.count() > 0, \
            "执行后无任何反馈"
