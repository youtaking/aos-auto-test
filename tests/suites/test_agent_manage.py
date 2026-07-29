# tests/suites/test_agent_manage.py
"""智能体管理模块回归测试"""
import pytest
from tests.pages.agent_page import AgentPage


@pytest.mark.order(5)
@pytest.mark.p0
def test_agent_page_loads(logged_in_page, base_url):
    """✅ 人工评审通过 | 智能体管理页面能正常加载"""
    agent_page = AgentPage(logged_in_page, base_url)
    agent_page.goto()
    assert agent_page.is_loaded()


@pytest.mark.order(6)
@pytest.mark.p0
def test_agent_list_has_items(logged_in_page, base_url):
    """✅ 人工评审通过 | 智能体列表不为空"""
    agent_page = AgentPage(logged_in_page, base_url)
    agent_page.goto()
    count = agent_page.get_agent_count()
    assert count > 0, f"智能体列表为空"


@pytest.mark.order(7)
@pytest.mark.p1
def test_agent_search(logged_in_page, base_url):
    """✅ 人工评审通过 | 搜索智能体功能正常"""
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
    """✅ 人工评审通过 | 搜索不存在的智能体显示空状态"""
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
    """✅ 人工评审通过 | 按分类筛选智能体"""
    agent_page = AgentPage(logged_in_page, base_url)
    agent_page.goto()

    agent_page.filter_by_category("全部")
    total = agent_page.get_agent_count()
    assert total > 0, "全部分类下无智能体"

    # 遍历所有分类按钮，逐个点击验证
    filter_buttons = agent_page.get_filter_buttons()
    for btn_name in filter_buttons:
        if btn_name and btn_name != "全部":
            agent_page.filter_by_category(btn_name)
            filtered = agent_page.get_agent_count()
            assert filtered <= total, \
                f"分类 '{btn_name}' 下数量({filtered})大于全部({total})"

    # 切回全部
    agent_page.filter_by_category("全部")


@pytest.mark.order(10)
@pytest.mark.p0
def test_agent_create_dialog_opens(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-AGENT-MANAGE-006: 通过管理页面创建智能体"""
    agent_page = AgentPage(logged_in_page, base_url)
    agent_page.goto()

    # 记录创建前的智能体数量
    initial_count = agent_page.get_agent_count()

    # 1. 点击页面内容区「创建智能体」按钮
    agent_page.click_create_button()
    logged_in_page.wait_for_timeout(2000)

    # 2. 验证内联创建表单出现
    body_text = logged_in_page.locator("body").inner_text()
    assert "新建Agent" in body_text, "点击创建智能体后未出现「新建Agent」表单"
    assert all(tab in body_text for tab in ["基础", "知识库", "高级配置"]), \
        "创建表单缺少配置 Tab"

    # 3. 填写名称（必填）
    import uuid
    agent_name = f"manage-test-{uuid.uuid4().hex[:6]}"
    name_input = logged_in_page.locator("input[placeholder='例如 my-agent']")
    assert name_input.count() > 0 and name_input.first.is_visible(), "名称输入框未出现"
    name_input.first.fill(agent_name)

    # 4. 填写描述（可选）
    desc_input = logged_in_page.locator("input[placeholder*='可选，Agent 的简短描述']")
    if desc_input.count() > 0:
        desc_input.first.fill("E2E 管理页面创建测试")

    # 5. 点击「创建」按钮
    create_btn = logged_in_page.get_by_role("button", name="创建").last
    assert create_btn.is_visible(), "「创建」按钮不可见"
    create_btn.click()
    logged_in_page.wait_for_timeout(3000)

    # 6. 验证创建成功 — 新智能体出现在列表中
    agent_page.goto()
    logged_in_page.wait_for_timeout(2000)
    assert agent_page.has_agent(agent_name), \
        f"创建后智能体 '{agent_name}' 未出现在列表中"

    # 7. 验证数量增加
    new_count = agent_page.get_agent_count()
    assert new_count == initial_count + 1, \
        f"智能体数量未增加: 创建前 {initial_count}，创建后 {new_count}"

    # 8. 清理：通过 API 删除
    from tests.pages.agent_config_page import AgentConfigPage
    ac = AgentConfigPage(logged_in_page, base_url)
    status = ac.delete_agent_api(agent_name)
    assert status in (200, 204), f"清理智能体失败: status={status}"
