# tests/suites/test_memories.py
"""记忆模块回归测试"""
import allure
import pytest
from tests.pages.sidebar_pages import MemoryPage


@allure.epic("记忆")
@pytest.mark.order(30)
@pytest.mark.p0
def test_memories_page_content(logged_in_page, base_url):
    """TC-MEM-001: 记忆页面内容加载"""
    mem = MemoryPage(logged_in_page, base_url)
    mem.goto()
    assert mem.is_loaded(), "记忆页面未加载"
    tabs = mem.get_tab_names()
    assert len(tabs) >= 5, f"记忆页面 Tab 数量不足: {tabs}"


@allure.epic("记忆")
@pytest.mark.order(31)
@pytest.mark.p1
def test_memories_tab_world_facts(logged_in_page, base_url):
    """TC-MEM-002: 世界事实 Tab 数据展示"""
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
def test_memories_tab_experiences(logged_in_page, base_url):
    """TC-MEM-003: 经验 Tab 数据展示"""
    mem = MemoryPage(logged_in_page, base_url)
    mem.goto()
    mem.click_tab("经验")
    assert mem.is_tab_active("经验"), "经验 Tab 未激活"


@allure.epic("记忆")
@pytest.mark.order(33)
@pytest.mark.p1
def test_memories_tab_observations(logged_in_page, base_url):
    """TC-MEM-004: 观察 Tab 数据展示"""
    mem = MemoryPage(logged_in_page, base_url)
    mem.goto()
    mem.click_tab("观察")
    assert mem.is_tab_active("观察"), "观察 Tab 未激活"


@allure.epic("记忆")
@pytest.mark.order(34)
@pytest.mark.p1
def test_memories_tab_mental_models(logged_in_page, base_url):
    """TC-MEM-005: 心理模型 Tab 数据展示"""
    mem = MemoryPage(logged_in_page, base_url)
    mem.goto()
    mem.click_tab("心理模型")
    assert mem.is_tab_active("心理模型"), "心理模型 Tab 未激活"


@allure.epic("记忆")
@pytest.mark.order(35)
@pytest.mark.p1
def test_memories_tab_entities(logged_in_page, base_url):
    """TC-MEM-006: 实体 Tab 数据展示"""
    mem = MemoryPage(logged_in_page, base_url)
    mem.goto()
    mem.click_tab("实体")
    assert mem.is_tab_active("实体"), "实体 Tab 未激活"


@allure.epic("记忆")
@pytest.mark.order(36)
@pytest.mark.p1
def test_memories_search_filter(logged_in_page, base_url):
    """TC-MEM-007: 记忆搜索过滤功能"""
    mem = MemoryPage(logged_in_page, base_url)
    mem.goto()
    # Check if search input exists
    search = logged_in_page.locator("div.agent-panel-content input[type='text']")
    if search.count() == 0:
        pytest.skip("记忆页面无搜索输入框")
    search.first.fill("test")
    logged_in_page.wait_for_timeout(500)
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

    # 检查是否有视图切换按钮（星座图/图谱/表格等）
    if not mem.has_view_buttons():
        pytest.skip("记忆页面无图谱可视化切换按钮")

    # 尝试切换到图谱视图
    graph_btn = logged_in_page.get_by_role("button", name="图谱").or_(
        logged_in_page.get_by_role("button", name="星座图")
    )
    if graph_btn.count() > 0:
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
        pytest.skip("记忆页面无数据项可点击")

    # 点击第一个记忆项
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
            close_btn.first.click()
    elif detail_panel.count() > 0:
        detail_text = detail_panel.first.inner_text()
        assert len(detail_text.strip()) > 0, "详情面板内容为空"
