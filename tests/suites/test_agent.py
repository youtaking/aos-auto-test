# tests/suites/test_agent.py
"""智能体管理模块回归测试"""
import pytest
from tests.pages.agent_page import AgentPage


@pytest.mark.order(5)
@pytest.mark.p0
def test_agent_page_loads(logged_in_page, base_url):
    """智能体管理页面能正常加载"""
    agent_page = AgentPage(logged_in_page, base_url)
    agent_page.goto()
    assert agent_page.is_loaded()


@pytest.mark.order(6)
@pytest.mark.p0
def test_agent_list_has_items(logged_in_page, base_url):
    """智能体列表不为空"""
    agent_page = AgentPage(logged_in_page, base_url)
    agent_page.goto()
    count = agent_page.get_agent_count()
    assert count > 0, f"智能体列表为空"


@pytest.mark.order(7)
@pytest.mark.p1
def test_agent_search(logged_in_page, base_url):
    """搜索智能体功能正常"""
    agent_page = AgentPage(logged_in_page, base_url)
    agent_page.goto()

    # 动态获取已知存在的智能体名称
    initial_count = agent_page.get_agent_count()
    if initial_count == 0:
        pytest.skip("智能体列表为空")

    # 获取第一个智能体名称用于搜索
    names = agent_page.get_agent_names()
    if not names:
        pytest.skip("无法获取智能体名称")
    first_name = names[0]

    agent_page.search_agent(first_name)
    assert agent_page.has_agent(first_name), f"搜索 '{first_name}' 后未找到"


@pytest.mark.order(8)
@pytest.mark.p1
def test_agent_search_no_result(logged_in_page, base_url):
    """搜索不存在的智能体显示空状态"""
    agent_page = AgentPage(logged_in_page, base_url)
    agent_page.goto()
    agent_page.search_agent("zzz_不存在的智能体_zzz")
    # 搜索后应无可匹配的智能体（可见卡片为 0 或显示空状态提示）
    visible_count = agent_page.get_agent_count()
    has_empty_state = logged_in_page.locator(
        "text=暂无, text=没有结果, text=empty, text=no result, text=无数据"
    ).count() > 0
    assert visible_count == 0 or has_empty_state, \
        f"搜索不存在的智能体后可见卡片仍有 {visible_count} 个且无空状态提示"
    agent_page.clear_search()


@pytest.mark.order(9)
@pytest.mark.p1
def test_agent_filter_by_category(logged_in_page, base_url):
    """按分类筛选智能体"""
    agent_page = AgentPage(logged_in_page, base_url)
    agent_page.goto()

    agent_page.filter_by_category("全部")
    total = agent_page.get_agent_count()
    assert total > 0, "全部分类下无智能体"

    # 尝试切换到另一个分类并验证列表变化
    filter_buttons = agent_page.get_filter_buttons()
    other_category = None
    for btn in filter_buttons:
        if btn and btn != "全部":
            other_category = btn
            break

    if other_category:
        agent_page.filter_by_category(other_category)
        filtered = agent_page.get_agent_count()
        assert filtered <= total, \
            f"分类 '{other_category}' 下数量({filtered})大于全部({total})"
        # 切回全部
        agent_page.filter_by_category("全部")
    else:
        pytest.skip("只有一个分类，无法测试切换")


@pytest.mark.order(10)
@pytest.mark.p0
def test_agent_create_dialog_opens(logged_in_page, base_url):
    """点击新建按钮能打开创建页面"""
    agent_page = AgentPage(logged_in_page, base_url)
    agent_page.goto()
    agent_page.click_create_button()

    # 验证创建对话框或创建表单出现
    is_dialog = agent_page.is_create_dialog_open()
    is_home = agent_page.is_on_home_page()
    assert is_dialog or is_home, \
        f"点击新建后既没有对话框也没有跳转到 home 页: {logged_in_page.url}"

    # 导航回 agents 页面供后续测试使用
    agent_page.goto()
