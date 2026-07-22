# tests/conftest.py
"""pytest 全局 fixtures：浏览器、页面、登录状态"""
import pytest
import yaml
from pathlib import Path
from playwright.sync_api import sync_playwright


@pytest.fixture(scope="session")
def test_config():
    """加载测试配置"""
    config_path = Path(__file__).parent / "fixtures" / "test_data.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="session")
def base_url(test_config):
    """被测应用 URL"""
    return test_config["fenixagent"]["url"]


@pytest.fixture(scope="session")
def browser_context_args():
    """浏览器上下文参数"""
    return {
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
    }


@pytest.fixture(scope="function")
def page(browser_context_args):
    """每个测试函数一个干净的浏览器页面"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(**browser_context_args)
        page_obj = context.new_page()
        yield page_obj
        context.close()
        browser.close()


@pytest.fixture
def login_page(page, base_url):
    """LoginPage 实例"""
    from tests.pages.login_page import LoginPage
    return LoginPage(page, base_url)
