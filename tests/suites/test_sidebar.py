# tests/suites/test_sidebar.py
"""侧边栏新模块回归测试（智能体编排、记忆、知识库、定时任务、组织、API Key）"""
import pytest
from tests.pages.sidebar_pages import (
    WorkflowPage, MemoryPage, KnowledgeBasePage,
    TasksPage, OrganizationPage, ApiKeyPage,
)


# === 智能体编排 ===

@pytest.mark.order(19)
@pytest.mark.p0
def test_workflow_page_loads(logged_in_page, base_url):
    """智能体编排页面能正常加载"""
    page = WorkflowPage(logged_in_page, base_url)
    page.goto()
    assert page.is_loaded()


@pytest.mark.order(19)
@pytest.mark.p1
def test_workflow_has_create_button(logged_in_page, base_url):
    """智能体编排页面有新建工作流按钮"""
    page = WorkflowPage(logged_in_page, base_url)
    page.goto()
    assert page.has_create_button()


@pytest.mark.order(19)
@pytest.mark.p1
def test_workflow_search(logged_in_page, base_url):
    """智能体编排搜索功能可用"""
    page = WorkflowPage(logged_in_page, base_url)
    page.goto()

    initial = page.get_workflow_count()
    assert initial >= 0, "工作流列表加载失败"

    page.search("zzz_不存在_zzz")
    logged_in_page.wait_for_timeout(500)
    filtered = page.get_workflow_count()
    assert filtered == 0 or filtered < initial, \
        f"搜索不存在的内容后数量未减少: {filtered} vs {initial}"

    page.clear_search()
    restored = page.get_workflow_count()
    assert restored == initial, \
        f"清空搜索后未恢复: {restored} vs {initial}"


# === 记忆 ===

@pytest.mark.order(20)
@pytest.mark.p0
def test_memory_page_loads(logged_in_page, base_url):
    """记忆页面能正常加载"""
    page = MemoryPage(logged_in_page, base_url)
    page.goto()
    assert page.is_loaded()


@pytest.mark.order(20)
@pytest.mark.p1
def test_memory_has_tabs(logged_in_page, base_url):
    """记忆页面有分类 Tab"""
    page = MemoryPage(logged_in_page, base_url)
    page.goto()
    tabs = page.get_tab_names()
    assert len(tabs) > 0, "记忆页面没有分类 Tab"


@pytest.mark.order(20)
@pytest.mark.p1
def test_memory_switch_tab(logged_in_page, base_url):
    """记忆页面能切换 Tab"""
    page = MemoryPage(logged_in_page, base_url)
    page.goto()
    tabs = page.get_tab_names()
    if len(tabs) < 2:
        pytest.skip(f"记忆页面只有 {len(tabs)} 个 Tab，无法测试切换")
    page.click_tab(tabs[1])
    assert page.is_tab_active(tabs[1])


# === 知识库 ===

@pytest.mark.order(21)
@pytest.mark.p0
def test_knowledge_base_page_loads(logged_in_page, base_url):
    """知识库页面能正常加载"""
    page = KnowledgeBasePage(logged_in_page, base_url)
    page.goto()
    assert page.is_loaded()


@pytest.mark.order(21)
@pytest.mark.p1
def test_knowledge_base_has_create_button(logged_in_page, base_url):
    """知识库页面有新建按钮"""
    page = KnowledgeBasePage(logged_in_page, base_url)
    page.goto()
    assert page.has_create_button()


@pytest.mark.order(21)
@pytest.mark.p1
def test_knowledge_base_search(logged_in_page, base_url):
    """知识库搜索功能可用"""
    page = KnowledgeBasePage(logged_in_page, base_url)
    page.goto()

    initial = page.get_kb_count()
    assert initial >= 0, "知识库列表加载失败"

    page.search("zzz_不存在_zzz")
    logged_in_page.wait_for_timeout(500)
    filtered = page.get_kb_count()
    assert filtered == 0 or filtered < initial, \
        f"搜索不存在的内容后数量未减少: {filtered} vs {initial}"

    page.clear_search()
    restored = page.get_kb_count()
    assert restored == initial, \
        f"清空搜索后未恢复: {restored} vs {initial}"


# === 定时任务 ===

@pytest.mark.order(22)
@pytest.mark.p0
def test_tasks_page_loads(logged_in_page, base_url):
    """定时任务页面能正常加载"""
    page = TasksPage(logged_in_page, base_url)
    page.goto()
    assert page.is_loaded()


@pytest.mark.order(22)
@pytest.mark.p1
def test_tasks_has_table(logged_in_page, base_url):
    """定时任务页面有表格"""
    page = TasksPage(logged_in_page, base_url)
    page.goto()
    assert page.has_table()


@pytest.mark.order(22)
@pytest.mark.p1
def test_tasks_filter_tabs(logged_in_page, base_url):
    """定时任务有筛选 Tab"""
    page = TasksPage(logged_in_page, base_url)
    page.goto()
    tabs = page.get_tab_names()
    assert len(tabs) > 0, "定时任务没有筛选 Tab"


# === 组织 ===

@pytest.mark.order(23)
@pytest.mark.p0
def test_organization_page_loads(logged_in_page, base_url):
    """组织管理页面能正常加载"""
    page = OrganizationPage(logged_in_page, base_url)
    page.goto()
    assert page.is_loaded()


@pytest.mark.order(23)
@pytest.mark.p1
def test_organization_has_members(logged_in_page, base_url):
    """组织管理页面有成员区域"""
    page = OrganizationPage(logged_in_page, base_url)
    page.goto()
    assert page.has_member_section()
    name = page.get_org_name()
    assert len(name) > 0, "组织名称为空"


# === API Key ===

@pytest.mark.order(24)
@pytest.mark.p0
def test_apikey_page_loads(logged_in_page, base_url):
    """API 密钥页面能正常加载"""
    page = ApiKeyPage(logged_in_page, base_url)
    page.goto()
    assert page.is_loaded()


@pytest.mark.order(24)
@pytest.mark.p1
def test_apikey_has_create_button(logged_in_page, base_url):
    """API 密钥页面有创建按钮"""
    page = ApiKeyPage(logged_in_page, base_url)
    page.goto()
    assert page.has_create_button()


@pytest.mark.order(24)
@pytest.mark.p1
def test_apikey_search(logged_in_page, base_url):
    """API 密钥搜索功能可用"""
    page = ApiKeyPage(logged_in_page, base_url)
    page.goto()

    initial = page.get_key_count()
    assert initial >= 0, "密钥列表加载失败"

    page.search("zzz_不存在_zzz")
    logged_in_page.wait_for_timeout(500)
    filtered = page.get_key_count()
    assert filtered == 0 or filtered < initial, \
        f"搜索不存在的内容后数量未减少: {filtered} vs {initial}"

    page.clear_search()
    restored = page.get_key_count()
    assert restored == initial, \
        f"清空搜索后未恢复: {restored} vs {initial}"
