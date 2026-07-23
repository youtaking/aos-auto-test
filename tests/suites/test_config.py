# tests/suites/test_config.py
"""配置管理模块回归测试（模型、技能、MCP、Agent Sites）"""
import pytest
from tests.pages.config_pages import ModelsPage, SkillsPage, McpPage, SitesPage


@pytest.mark.order(14)
@pytest.mark.p1
def test_models_page_loads(logged_in_page, base_url):
    """服务商与模型页面能正常加载"""
    models = ModelsPage(logged_in_page, base_url)
    models.goto()
    assert models.is_loaded()


@pytest.mark.order(15)
@pytest.mark.p1
def test_skills_page_loads(logged_in_page, base_url):
    """技能管理页面能正常加载"""
    skills = SkillsPage(logged_in_page, base_url)
    skills.goto()
    assert skills.is_loaded()


@pytest.mark.order(16)
@pytest.mark.p1
def test_mcp_page_loads(logged_in_page, base_url):
    """MCP 服务器页面能正常加载"""
    mcp = McpPage(logged_in_page, base_url)
    mcp.goto()
    assert mcp.is_loaded()


@pytest.mark.order(17)
@pytest.mark.p1
def test_sites_page_loads(logged_in_page, base_url):
    """Agent Sites 页面能正常加载"""
    sites = SitesPage(logged_in_page, base_url)
    sites.goto()
    assert sites.is_loaded()


@pytest.mark.order(18)
@pytest.mark.p1
def test_sites_has_filter_tabs(logged_in_page, base_url):
    """Agent Sites 页面有筛选 Tab"""
    sites = SitesPage(logged_in_page, base_url)
    sites.goto()
    tabs = sites.get_filter_tabs()
    assert len(tabs) > 0, "Agent Sites 没有筛选 Tab"


# === 增强：搜索功能测试 ===

@pytest.mark.order(25)
@pytest.mark.p1
def test_models_search(logged_in_page, base_url):
    """服务商与模型搜索功能可用"""
    models = ModelsPage(logged_in_page, base_url)
    models.goto()

    initial = models.get_provider_count()
    assert initial >= 0, "服务商列表加载失败"

    models.search("zzz_不存在_zzz")
    logged_in_page.wait_for_timeout(500)
    filtered = models.get_provider_count()
    assert filtered == 0 or filtered < initial, \
        f"搜索不存在的内容后数量未减少: {filtered} vs {initial}"

    models.clear_search()
    restored = models.get_provider_count()
    assert restored == initial, \
        f"清空搜索后未恢复: {restored} vs {initial}"


@pytest.mark.order(26)
@pytest.mark.p1
def test_skills_search(logged_in_page, base_url):
    """技能管理搜索功能可用"""
    skills = SkillsPage(logged_in_page, base_url)
    skills.goto()

    initial = skills.get_skill_count()
    assert initial >= 0, "技能列表加载失败"

    skills.search("zzz_不存在_zzz")
    logged_in_page.wait_for_timeout(500)
    filtered = skills.get_visible_skill_cards()
    assert filtered == 0 or filtered < initial, \
        f"搜索不存在的内容后数量未减少: {filtered} vs {initial}"

    skills.clear_search()
    restored = skills.get_visible_skill_cards()
    assert restored == initial, \
        f"清空搜索后未恢复: {restored} vs {initial}"


@pytest.mark.order(27)
@pytest.mark.p1
def test_mcp_search(logged_in_page, base_url):
    """MCP 服务器搜索功能可用"""
    mcp = McpPage(logged_in_page, base_url)
    mcp.goto()

    initial = mcp.get_server_count()
    assert initial >= 0, "MCP 服务器列表加载失败"

    mcp.search("zzz_不存在_zzz")
    logged_in_page.wait_for_timeout(500)
    filtered = mcp.get_server_count()
    assert filtered == 0 or filtered < initial, \
        f"搜索不存在的内容后数量未减少: {filtered} vs {initial}"

    mcp.clear_search()
    restored = mcp.get_server_count()
    assert restored == initial, \
        f"清空搜索后未恢复: {restored} vs {initial}"


@pytest.mark.order(28)
@pytest.mark.p1
def test_sites_search(logged_in_page, base_url):
    """Agent Sites 搜索功能可用"""
    sites = SitesPage(logged_in_page, base_url)
    sites.goto()

    initial = sites.get_app_count()
    assert initial >= 0, "App 列表加载失败"

    sites.search("zzz_不存在_zzz")
    logged_in_page.wait_for_timeout(500)
    filtered = sites.get_app_count()
    assert filtered == 0 or filtered < initial, \
        f"搜索不存在的内容后数量未减少: {filtered} vs {initial}"

    sites.clear_search()
    restored = sites.get_app_count()
    assert restored == initial, \
        f"清空搜索后未恢复: {restored} vs {initial}"
