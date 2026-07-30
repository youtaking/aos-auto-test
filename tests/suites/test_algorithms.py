# tests/suites/test_algorithms.py
"""算法库模块回归测试 — 静态展示页面，算法数据为前端硬编码"""
import pytest
import allure
from tests.pages.algorithms_page import AlgorithmsPage


@allure.epic("算法库")
@pytest.mark.order(110)
@pytest.mark.p0
def test_algorithms_page_loads(logged_in_page, base_url):
    """TC-ALGO-001: 算法库页面加载 | ✅ 人工评审通过 |"""
    algo = AlgorithmsPage(logged_in_page, base_url)
    algo.goto()
    assert algo.is_loaded(), "算法库页面未加载"


@allure.epic("算法库")
@pytest.mark.order(111)
@pytest.mark.p0
def test_algorithms_list_not_empty(logged_in_page, base_url):
    """TC-ALGO-002: 算法库列表不为空 | ✅ 人工评审通过 |"""
    algo = AlgorithmsPage(logged_in_page, base_url)
    algo.goto()
    count = algo.get_algo_count()
    assert count > 0, "算法库列表为空"


@allure.epic("算法库")
@pytest.mark.order(112)
@pytest.mark.p1
def test_algorithms_has_category_tabs(logged_in_page, base_url):
    """TC-ALGO-003: 算法库包含分类筛选 Tab | ✅ 人工评审通过 |"""
    algo = AlgorithmsPage(logged_in_page, base_url)
    algo.goto()

    tabs = algo.get_category_tabs()
    assert len(tabs) > 0, "未找到分类筛选 Tab"
    # DOM 探查确认有 11 个 Tab: 全部/分类/回归/聚类/降维/排序/异常检测/时序预测/深度学习/推荐/优化
    assert "全部" in tabs, f"分类 Tab 中缺少'全部': {tabs}"


@allure.epic("算法库")
@pytest.mark.order(113)
@pytest.mark.p1
def test_algorithms_filter_by_category(logged_in_page, base_url):
    """TC-ALGO-004: 算法库分类筛选功能 | ✅ 人工评审通过 |"""
    algo = AlgorithmsPage(logged_in_page, base_url)
    algo.goto()

    total = algo.get_algo_count()
    assert total > 0, "算法列表为空，无法测试分类筛选"

    # 切换到"分类"筛选
    tabs = algo.get_category_tabs()
    assert "分类" in tabs, f"无'分类' Tab，可用: {tabs}"

    algo.filter_by_category("分类")
    filtered = algo.get_algo_count()
    assert filtered <= total, \
        f"分类筛选后数量({filtered})大于全部({total})"
    assert filtered > 0, "分类筛选后列表为空"

    # 切回"全部"
    algo.filter_by_category("全部")
    restored = algo.get_algo_count()
    assert restored == total, \
        f"切回全部后数量未恢复: {restored} vs {total}"


@allure.epic("算法库")
@pytest.mark.order(114)
@pytest.mark.p1
def test_algorithms_search_filter(logged_in_page, base_url):
    """TC-ALGO-005: 算法库搜索过滤功能 | ✅ 人工评审通过 |"""
    algo = AlgorithmsPage(logged_in_page, base_url)
    algo.goto()

    total = algo.get_algo_count()
    assert total > 0, "算法列表为空，无法测试搜索"

    # 搜索不存在的关键词，验证过滤效果
    algo.search("zzz_不存在的算法_zzz")
    filtered = algo.get_algo_count()
    assert filtered < total, \
        f"搜索不存在关键词后数量未减少: {filtered} vs {total}"

    # 清空搜索恢复
    algo.clear_search()
    restored = algo.get_algo_count()
    assert restored == total, \
        f"清空搜索后数量未恢复: {restored} vs {total}"

    # 搜索已知存在的算法名称，验证搜索结果正确
    names = algo.get_algo_names()
    if names:
        # 取第一个算法名称的后半部分作为搜索词（避免 emoji 前缀干扰）
        search_term = names[0].split()[-1] if " " in names[0] else names[0]
        algo.search(search_term)
        found = algo.get_algo_count()
        assert found >= 1, f"搜索已知算法名称 '{search_term}' 未找到结果"
        algo.clear_search()


@allure.epic("算法库")
@pytest.mark.order(115)
@pytest.mark.p1
def test_algorithms_view_detail(logged_in_page, base_url):
    """TC-ALGO-006: 算法库查看详情按钮 | ✅ 人工评审通过 |"""
    algo = AlgorithmsPage(logged_in_page, base_url)
    algo.goto()

    names = algo.get_algo_names()
    assert len(names) > 0, "算法列表为空，无法测试查看详情"

    # 点击第一个算法的"查看详情"
    algo.click_view_detail(names[0])

    # 验证有反馈：弹窗出现或页面内容变化
    dialog = logged_in_page.locator("[role='dialog']")
    body = logged_in_page.locator("div.agent-panel-content").inner_text()
    has_feedback = (
        dialog.count() > 0
        or any(kw in body for kw in ["详情", "说明", "场景", "参数", "使用"])
    )
    assert has_feedback, "查看详情后无任何反馈"

    # 关闭可能的弹窗
    if dialog.count() > 0:
        close = dialog.get_by_role("button", name="关闭").or_(
            dialog.get_by_role("button", name="Close")
        )
        if close.count() > 0:
            close.first.click()


@allure.epic("算法库")
@pytest.mark.order(116)
@pytest.mark.p2
def test_algorithms_copy_code(logged_in_page, base_url):
    """TC-ALGO-007: 算法库复制代码按钮 | ✅ 人工评审通过 |"""
    algo = AlgorithmsPage(logged_in_page, base_url)
    algo.goto()

    names = algo.get_algo_names()
    assert len(names) > 0, "算法列表为空，无法测试复制代码"

    # 拦截剪贴板写入
    logged_in_page.evaluate("""() => {
        window.__clipboardText = '';
        if (navigator.clipboard) {
            navigator.clipboard.writeText = (text) => {
                window.__clipboardText = text;
                return Promise.resolve();
            };
        }
    }""")

    # 点击第一个算法的"复制代码"
    algo.click_copy_code(names[0])

    # 验证剪贴板中有代码内容
    logged_in_page.wait_for_timeout(500)
    clipboard = logged_in_page.evaluate("() => window.__clipboardText")
    assert len(clipboard) > 0, "复制代码后剪贴板为空"
    assert any(kw in clipboard for kw in ["def ", "import ", "class ", "function ", "async ", "#"]), \
        f"剪贴板内容不像代码: {clipboard[:80]}"
