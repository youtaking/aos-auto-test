# tests/suites/test_agent_manage.py
"""智能体管理模块回归测试"""
import uuid
import allure
import pytest
from tests.pages.agent_page import AgentPage
from tests.conftest import register_cleanup


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
    # 原 OR 断言拆分：先断言列表被完全过滤，再断言空状态提示出现
    # （实测 2026-09-15：过滤为空时渲染「暂无智能体 / 点击右上角创建第一个智能体」）
    visible_count = agent_page.get_agent_count()
    assert visible_count == 0, \
        f"搜索不存在的智能体后列表未过滤，仍有 {visible_count} 个可见智能体"
    empty_state = logged_in_page.locator("text=暂无智能体")
    assert empty_state.count() > 0, \
        "搜索结果为空时未显示空状态提示（「暂无智能体」）"
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
def test_agent_create_dialog_opens(logged_in_page, base_url, request):
    """✅ 人工评审通过 | TC-AGENT-MANAGE-006: 通过管理页面创建智能体"""
    agent_page = AgentPage(logged_in_page, base_url)
    agent_page.goto()

    # 记录创建前的智能体数量
    initial_count = agent_page.get_agent_count()

    # 1. 点击页面内容区「创建智能体」按钮
    agent_page.click_create_button()
    logged_in_page.wait_for_timeout(1200)

    # 2. 验证「新建Agent」对话框出现（新版 6-tab 配置地图：身份与指令/模型/能力与工具/知识与记忆/运行环境/共享与访问）
    d = logged_in_page.locator("[role='dialog']").first
    try:
        d.wait_for(state="visible", timeout=8000)
    except Exception:
        pytest.fail("点击创建智能体后未出现「新建Agent」对话框")
    dialog_text = d.inner_text()
    assert "新建Agent" in dialog_text, f"对话框标题非「新建Agent」: {dialog_text[:80]!r}"
    expected_tabs = ["身份与指令", "模型", "能力与工具", "知识与记忆", "运行环境", "共享与访问"]
    for tab in expected_tabs:
        assert tab in dialog_text, f"创建对话框缺少配置 Tab「{tab}」"

    # 3. 填写名称（必填）
    import uuid
    agent_name = f"manage-test-{uuid.uuid4().hex[:6]}"
    name_input = d.locator("input[placeholder='例如 my-agent']")
    assert name_input.count() > 0 and name_input.first.is_visible(), "名称输入框未出现"
    name_input.first.fill(agent_name)

    # 4. 填写描述（可选）
    desc_input = d.locator("input[placeholder*='可选，Agent 的简短描述']")
    if desc_input.count() > 0:
        desc_input.first.fill("E2E 管理页面创建测试")

    # 新版表单要求显式选择模型；未选时只会切到模型 tab 提示必填，不会创建。
    d.get_by_role("tab", name="模型 推理模型与上下文 未配置", exact=True).click()
    model = d.get_by_role("radiogroup", name="模型", exact=True).get_by_role("radio").first
    model.wait_for(state="visible", timeout=10000)
    model.click()

    # 5. 点击对话框底部「创建」按钮（exact 匹配，避免命中 对话创建/创建智能体）
    create_btn = d.get_by_role("button", name="创建", exact=True).last
    assert create_btn.is_visible(), "「创建」按钮不可见"
    create_btn.click()
    # 等对话框关闭（Agent 创建可能较慢）
    d.wait_for(state="hidden", timeout=30000)

    # 注册清理（UI 创建的 agent，通过 API 删除）
    from tests.pages.agent_config_page import AgentConfigPage
    _ac = AgentConfigPage(logged_in_page, base_url)
    register_cleanup(request, lambda n=agent_name: _ac.delete_agent_api(n))

    # 6. 验证创建成功 — 新智能体出现在列表中（带重试轮询）
    agent_page.goto()
    found = False
    for _i in range(8):
        agent_page.goto()
        if agent_page.has_agent(agent_name):
            found = True
            break
        logged_in_page.wait_for_timeout(1500)
    assert found, f"创建后智能体 '{agent_name}' 未出现在列表中"

    # 7. 验证数量增加
    new_count = agent_page.get_agent_count()
    assert new_count == initial_count + 1, \
        f"智能体数量未增加: 创建前 {initial_count}，创建后 {new_count}"

    # 8. 清理：通过 API 删除
    from tests.pages.agent_config_page import AgentConfigPage
    ac = AgentConfigPage(logged_in_page, base_url)
    status = ac.delete_agent_api(agent_name)
    assert status in (200, 204), f"清理智能体失败: status={status}"


@allure.epic("智能体管理")
@pytest.mark.order(11)
@pytest.mark.p0
def test_agent_delete(logged_in_page, base_url, request):
    """TC-AGENT-MANAGE-007: 创建智能体后删除并验证列表更新
    注意：由于 Agent 配置 modal (div.absolute.inset-0.z-50) 可能遮挡 UI 操作，
    本测试使用 API 创建/删除 + UI 验证列表更新的方式，确保测试稳定性。
    """
    from tests.pages.agent_config_page import AgentConfigPage

    agent_name = f"del-test-{uuid.uuid4().hex[:6]}"
    ac = AgentConfigPage(logged_in_page, base_url)
    agent_page = AgentPage(logged_in_page, base_url)

    # 1. 通过 API 创建智能体
    result = ac.create_agent_api(agent_name)
    assert result, "API 创建智能体失败"

    # 注册清理（安全网：若测试在显式删除前失败）
    register_cleanup(request, lambda n=agent_name: ac.delete_agent_api(n))

    # 2. 导航到管理页，验证新智能体出现在列表中（带重试，API 创建可能有延迟）
    agent_page.goto()
    for _retry in range(5):
        if agent_page.has_agent(agent_name):
            break
        logged_in_page.wait_for_timeout(1500)
        agent_page.goto()  # 刷新重试
    assert agent_page.has_agent(agent_name), \
        f"创建后智能体 '{agent_name}' 未出现在列表中"

    # 记录删除前的数量
    count_before = agent_page.get_agent_count()

    # 3. 通过 API 删除智能体
    status = ac.delete_agent_api(agent_name)
    assert status in (200, 204), f"API 删除智能体失败: status={status}"

    # 4. 刷新管理页，验证智能体从列表中消失
    agent_page.goto()
    logged_in_page.wait_for_timeout(1000)
    assert not agent_page.has_agent(agent_name), \
        f"删除后智能体 '{agent_name}' 仍存在于列表中"

    # 5. 验证数量减少
    count_after = agent_page.get_agent_count()
    assert count_after == count_before - 1, \
        f"删除后数量未减少: 删除前 {count_before}, 删除后 {count_after}"


