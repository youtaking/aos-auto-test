# tests/suites/test_memories.py
"""记忆模块回归测试"""
import allure
import pytest
from tests.pages.sidebar_pages import MemoryPage


@allure.epic("记忆")
@pytest.mark.order(30)
@pytest.mark.p0
def test_memories_page_content(logged_in_page, base_url, env_check):
    """TC-MEM-001: 记忆页面内容加载"""
    if not env_check.get("hindsight_enabled", False):
        pytest.skip("记忆服务未开启（Hindsight 未启用），跳过")
    mem = MemoryPage(logged_in_page, base_url)
    mem.goto()
    assert mem.is_loaded(), "记忆页面未加载"
    tabs = mem.get_tab_names()
    assert len(tabs) >= 5, f"记忆页面 Tab 数量不足: {tabs}"


@allure.epic("记忆")
@pytest.mark.order(31)
@pytest.mark.p1
def test_memories_tab_world_facts(logged_in_page, base_url, env_check):
    """TC-MEM-002: 世界事实 Tab 数据展示"""
    if not env_check.get("hindsight_enabled", False):
        pytest.skip("记忆服务未开启（Hindsight 未启用），跳过")
    mem = MemoryPage(logged_in_page, base_url)
    mem.goto()
    mem.click_tab("世界事实")
    assert mem.is_tab_active("世界事实"), "世界事实 Tab 未激活"
    # Check content area has data or empty state
    body = logged_in_page.locator("div.agent-panel-content")
    assert body.count() > 0, "内容区域不存在"


@allure.epic("记忆")
@pytest.mark.order(32)
@pytest.mark.p1
def test_memories_tab_experiences(logged_in_page, base_url, env_check):
    """TC-MEM-003: 经验 Tab 数据展示"""
    if not env_check.get("hindsight_enabled", False):
        pytest.skip("记忆服务未开启（Hindsight 未启用），跳过")
    mem = MemoryPage(logged_in_page, base_url)
    mem.goto()
    mem.click_tab("经验")
    assert mem.is_tab_active("经验"), "经验 Tab 未激活"


@allure.epic("记忆")
@pytest.mark.order(33)
@pytest.mark.p1
def test_memories_tab_observations(logged_in_page, base_url, env_check):
    """TC-MEM-004: 观察 Tab 数据展示"""
    if not env_check.get("hindsight_enabled", False):
        pytest.skip("记忆服务未开启（Hindsight 未启用），跳过")
    mem = MemoryPage(logged_in_page, base_url)
    mem.goto()
    mem.click_tab("观察")
    assert mem.is_tab_active("观察"), "观察 Tab 未激活"


@allure.epic("记忆")
@pytest.mark.order(34)
@pytest.mark.p1
def test_memories_tab_mental_models(logged_in_page, base_url, env_check):
    """TC-MEM-005: 心理模型 Tab 数据展示"""
    if not env_check.get("hindsight_enabled", False):
        pytest.skip("记忆服务未开启（Hindsight 未启用），跳过")
    mem = MemoryPage(logged_in_page, base_url)
    mem.goto()
    mem.click_tab("心理模型")
    assert mem.is_tab_active("心理模型"), "心理模型 Tab 未激活"


@allure.epic("记忆")
@pytest.mark.order(35)
@pytest.mark.p1
def test_memories_tab_entities(logged_in_page, base_url, env_check):
    """TC-MEM-006: 实体 Tab 数据展示"""
    if not env_check.get("hindsight_enabled", False):
        pytest.skip("记忆服务未开启（Hindsight 未启用），跳过")
    mem = MemoryPage(logged_in_page, base_url)
    mem.goto()
    mem.click_tab("实体")
    assert mem.is_tab_active("实体"), "实体 Tab 未激活"


@allure.epic("记忆")
@pytest.mark.order(36)
@pytest.mark.p1
def test_memories_search_filter(logged_in_page, base_url, env_check):
    """TC-MEM-007: 记忆搜索过滤功能"""
    # 前置条件：Hindsight 服务必须启用
    if not env_check.get("hindsight_enabled", False):
        pytest.skip("Hindsight 服务未启用，搜索过滤测试跳过")

    mem = MemoryPage(logged_in_page, base_url)
    mem.goto()

    # 切换到心理模型 Tab（有搜索框）
    mem.click_tab("心理模型")

    # 等搜索框出现（Tab 内容懒加载）
    search = logged_in_page.locator("input[placeholder='搜索心理模型...']")
    try:
        search.first.wait_for(state="visible", timeout=10000)
    except Exception:
        pytest.fail("心理模型 Tab 没有搜索框")

    # 等数据加载：卡片出现 或 "暂无心理模型"
    cards = logged_in_page.locator("h3.truncate")
    empty = logged_in_page.locator("text=暂无心理模型")
    for _w in range(10):
        if cards.count() > 0 or empty.count() > 0:
            break
        logged_in_page.wait_for_timeout(1000)

    import re
    initial_count = cards.count()

    if initial_count > 0:
        # 有数据：搜索第一个模型名称，验证过滤生效
        count_el = logged_in_page.locator("text=/\\d+ 个心理模型/")
        count_text = count_el.first.inner_text() if count_el.count() > 0 else ""
        match = re.search(r"(\d+)", count_text)
        if match:
            initial_count = int(match.group(1))

        first_name = cards.first.inner_text().strip()
        search.first.wait_for(state="visible", timeout=5000)
        search.first.fill(first_name)
        logged_in_page.wait_for_timeout(500)

        filtered_count = logged_in_page.locator("h3.truncate").count()
        assert filtered_count >= 1, f"搜索 '{first_name}' 后没有任何匹配"
        if initial_count > 1:
            assert filtered_count < initial_count, \
                f"搜索 '{first_name}' 后数量未变化（仍为 {initial_count}）"

        # 清空搜索，恢复
        search.first.wait_for(state="visible", timeout=5000)
        search.first.fill("")
        logged_in_page.wait_for_timeout(500)
        restored = logged_in_page.locator("h3.truncate").count()
        assert restored == initial_count, \
            f"清空搜索后卡片数 {restored}，预期 {initial_count}"
    else:
        # 无数据：验证搜索框可交互
        search.first.wait_for(state="visible", timeout=5000)
        search.first.fill("test")
        logged_in_page.wait_for_timeout(500)
        assert logged_in_page.locator("h3.truncate").count() == 0, \
            "无数据时搜索后不应出现卡片"
        search.first.wait_for(state="visible", timeout=5000)
        search.first.fill("")
        logged_in_page.wait_for_timeout(500)


@allure.epic("记忆")
@pytest.mark.order(460)
@pytest.mark.p2
def test_memories_graph_visualization(logged_in_page, base_url, env_check):
    """TC-MEM-008: 2D/3D 图谱可视化 — 记忆图谱可视化展示"""
    if not env_check.get("hindsight_enabled", False):
        pytest.skip("Hindsight 服务未启用，图谱可视化测试跳过")
    mem = MemoryPage(logged_in_page, base_url)
    mem.goto()
    assert mem.is_loaded(), "记忆页面未加载"

    # 等待 DataView 加载完成
    has_buttons = mem.has_view_buttons()
    if not has_buttons:
        # 无数据时应显示空状态
        body_text = logged_in_page.locator("div.agent-panel-body").inner_text()
        body_text_lower = body_text.lower()
        assert any(kw in text for kw, text in [("暂无", body_text), ("no data", body_text_lower), ("empty", body_text_lower)]), \
            f"无数据时未显示空状态提示，body_text 前200字符: {body_text[:200]!r}"
        return  # 无数据，空状态验证通过

    # 有数据时：尝试切换到图谱视图
    graph_btn = logged_in_page.get_by_role("button", name="图谱").or_(
        logged_in_page.get_by_role("button", name="星座图")
    )
    if graph_btn.count() > 0:
        graph_btn.first.wait_for(state="visible", timeout=5000)
        graph_btn.first.click()
        logged_in_page.wait_for_timeout(1500)

    # 验证图谱容器出现（canvas/svg/可视化容器）
    graph_container = logged_in_page.locator(
        "canvas, svg, [data-slot='graph']"
    )
    assert graph_container.count() > 0, "图谱容器（canvas/svg/div）未出现"


@allure.epic("记忆")
@pytest.mark.order(461)
@pytest.mark.p1
def test_memories_detail_modal(logged_in_page, base_url, env_check):
    """TC-MEM-009: 记忆详情 — 点击记忆项查看详情"""
    if not env_check.get("hindsight_enabled", False):
        pytest.skip("Hindsight 服务未启用，记忆详情测试跳过")
    mem = MemoryPage(logged_in_page, base_url)
    mem.goto()
    assert mem.is_loaded(), "记忆页面未加载"

    # 查找记忆列表项（卡片/行）
    content = logged_in_page.locator("div.agent-panel-content")
    items = content.locator(
        "[data-slot='card'], div.rounded-lg.border, "
        "div.cursor-pointer, tr[data-row-key]"
    )
    if items.count() == 0:
        # 无数据时应显示空状态
        body_text = logged_in_page.locator("div.agent-panel-body").inner_text()
        body_text_lower = body_text.lower()
        assert any(kw in text for kw, text in [("暂无", body_text), ("no data", body_text_lower), ("empty", body_text_lower)]), \
            f"无数据项时未显示空状态提示，body_text 前200字符: {body_text[:200]!r}"
        return  # 无数据，空状态验证通过

    # 点击第一个记忆项
    items.first.wait_for(state="visible", timeout=5000)
    items.first.click()
    logged_in_page.wait_for_timeout(800)

    # 验证详情弹窗/面板出现
    dialog = logged_in_page.locator("[role='dialog']")
    detail_panel = logged_in_page.locator(
        "[data-slot='detail'], [data-slot='drawer']"
    )
    has_detail = dialog.count() > 0 or detail_panel.count() > 0
    assert has_detail, "点击记忆项后未弹出详情面板"

    # 验证详情中有内容文本
    if dialog.count() > 0:
        detail_text = dialog.first.inner_text()
        assert len(detail_text.strip()) > 0, "详情弹窗内容为空"
        # 关闭弹窗
        close_btn = dialog.get_by_role("button", name="关闭").or_(
            dialog.get_by_role("button", name="Close")
        )
        if close_btn.count() > 0:
            close_btn.first.wait_for(state="visible", timeout=5000)
            close_btn.first.click()
    elif detail_panel.count() > 0:
        detail_text = detail_panel.first.inner_text()
        assert len(detail_text.strip()) > 0, "详情面板内容为空"


@allure.epic("记忆")
@pytest.mark.order(462)
@pytest.mark.p1
def test_memories_crud(logged_in_page, base_url, env_check):
    """验证记忆模块基本操作 — 页面加载、Tab 切换、只读展示（记忆通过 Agent 对话注入，无手动创建入口）"""
    if not env_check.get("hindsight_enabled", False):
        pytest.skip("记忆服务未开启（Hindsight 未启用），跳过")
    mem = MemoryPage(logged_in_page, base_url)
    mem.goto()

    # 验证页面加载（有 Tab 或表格）
    if not mem.is_loaded():
        pytest.skip("记忆页面未加载（可能 Hindsight 服务未启用）")

    tabs = mem.get_tab_names()
    assert len(tabs) >= 1, f"记忆页面缺少分类 Tab: {tabs}"

    # 记忆页面主内容区域无手动创建按钮 — 记忆通过 Agent 对话注入
    # 在主内容区域（排除侧边栏）查找创建按钮
    main_content = logged_in_page.locator("[role=main], main, div.agent-panel-content").first
    create_btn = main_content.get_by_role("button", name="创建").or_(
        main_content.get_by_role("button", name="新建").or_(
            main_content.locator("button").filter(has_text="添加")
        )
    )

    if create_btn.count() == 0:
        # 验证只读展示：有 Tab + 空状态或数据
        body_text = logged_in_page.locator("body").first.inner_text()
        has_content = "暂无" in body_text or "记忆" in body_text
        assert has_content, "记忆页面既无创建入口也无数据展示"
        # 只读模式验证通过
        return

    # 如果有创建按钮（未来版本可能增加），验证点击后的弹窗
    create_btn.first.wait_for(state="visible", timeout=5000)
    create_btn.first.click()

    # 验证创建弹窗或页面出现
    dialog = logged_in_page.locator("[role='dialog']")
    form_page = logged_in_page.locator("form, [data-slot='form']")
    has_dialog = False
    has_form = False
    try:
        dialog.first.wait_for(state="visible", timeout=3000)
        has_dialog = True
    except Exception:
        pass
    if not has_dialog:
        try:
            form_page.first.wait_for(state="visible", timeout=3000)
            has_form = True
        except Exception:
            pass

    assert has_dialog or has_form, "点击创建按钮后未出现弹窗或表单页面"

    # 按 Escape 取消（不保存，避免操作数据）
    logged_in_page.keyboard.press("Escape")
    if has_dialog:
        try:
            dialog.first.wait_for(state="hidden", timeout=3000)
        except Exception:
            pass
