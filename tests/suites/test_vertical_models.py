# tests/suites/test_vertical_models.py
"""垂直模型库模块回归测试"""
import pytest
from tests.pages.vertical_models_page import VerticalModelsPage


@pytest.mark.order(100)
@pytest.mark.p0
def test_vertical_models_page_loads(logged_in_page, base_url):
    """垂直模型库页面能正常加载"""
    vm = VerticalModelsPage(logged_in_page, base_url)
    vm.goto()
    assert vm.is_loaded(), "垂直模型库页面未加载"


@pytest.mark.order(101)
@pytest.mark.p0
def test_vertical_models_list_not_empty(logged_in_page, base_url):
    """垂直模型库列表不为空"""
    vm = VerticalModelsPage(logged_in_page, base_url)
    vm.goto()
    count = vm.get_model_count()
    assert count > 0, "垂直模型库列表为空"


@pytest.mark.order(102)
@pytest.mark.p1
def test_vertical_models_has_known_models(logged_in_page, base_url):
    """垂直模型库包含已知模型"""
    vm = VerticalModelsPage(logged_in_page, base_url)
    vm.goto()
    # DOM 探查确认存在的模型关键词
    known_keywords = ["风机物流", "PPE检测", "装配质量", "电力抢修"]
    found = []
    for kw in known_keywords:
        if vm.has_model(kw):
            found.append(kw)
    assert len(found) > 0, f"未找到任何已知模型关键词: {known_keywords}"


@pytest.mark.order(103)
@pytest.mark.p1
def test_vertical_models_search_filter(logged_in_page, base_url):
    """垂直模型库搜索过滤功能"""
    vm = VerticalModelsPage(logged_in_page, base_url)
    vm.goto()

    total = vm.get_model_count()
    if total == 0:
        pytest.skip("模型列表为空")

    # 搜索不存在的关键词
    vm.search("zzz_不存在的模型_zzz")
    filtered_count = vm.get_model_count()
    assert filtered_count < total, \
        f"搜索不存在关键词后数量未减少: {filtered_count} vs {total}"

    # 清空搜索恢复
    vm.clear_search()
    restored = vm.get_model_count()
    assert restored == total, \
        f"清空搜索后数量未恢复: {restored} vs {total}"


@pytest.mark.order(104)
@pytest.mark.p1
def test_vertical_models_card_structure(logged_in_page, base_url):
    """垂直模型库卡片结构完整"""
    vm = VerticalModelsPage(logged_in_page, base_url)
    vm.goto()

    cards = vm.get_model_cards()
    if cards.count() == 0:
        pytest.skip("模型列表为空")

    # 验证第一张卡片包含关键信息
    first_card_text = cards.first.inner_text()
    # 卡片应包含：模型名称、状态标签（如"已落地"）、基础模型信息、提供方
    assert len(first_card_text) > 20, \
        f"卡片内容过短，可能结构不完整: {first_card_text[:60]}"
    # 验证有"已落地"或类似状态标签
    has_status = any(kw in first_card_text for kw in ["已落地", "开发中", "已上线"])
    assert has_status, f"卡片缺少状态标签: {first_card_text[:80]}"
