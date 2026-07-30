# tests/suites/test_environments.py
"""环境管理模块回归测试（P2 — 后端功能，无独立 UI 页面）"""
import allure
import pytest

pytestmark = pytest.mark.skip(reason="环境管理为后端功能，无对应 UI 页面")


@allure.epic("环境管理")
@pytest.mark.order(50)
@pytest.mark.p2
def test_environments_list(logged_in_page, base_url):
    """TC-ENV-001: 环境列表数据加载（通过工作流页面间接验证）"""
    # 环境管理为后端功能，无独立 UI 页面
    # 通过工作流/智能体配置间接使用，API 层已有测试覆盖
    pass


@allure.epic("环境管理")
@pytest.mark.order(51)
@pytest.mark.p2
def test_environments_crud(logged_in_page, base_url):
    """TC-ENV-002: 环境 CRUD 完整流程"""
    # 环境管理为后端功能，无独立 UI 页面
    # CRUD 操作通过 API 测试覆盖
    pass
