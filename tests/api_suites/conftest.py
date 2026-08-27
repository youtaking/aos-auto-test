# tests/api_suites/conftest.py
"""API 测试专用 pytest fixtures"""
import os
import pytest
import yaml
import httpx
from pathlib import Path
from tests.api_clients.web_client import WebClient
from tests.api_clients.api_client import ApiClient


@pytest.fixture(scope="session", autouse=True)
def _cleanup_leftover_test_providers():
    """覆盖根 conftest 的同名 fixture，API 测试不需要 Playwright 登录。"""
    return


@pytest.fixture(scope="session")
def api_test_config():
    """加载测试配置"""
    config_path = Path(__file__).parent.parent / "fixtures" / "test_data.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="session")
def api_base_url(request, api_test_config):
    """被测系统 URL：优先 CLI 参数 > 环境变量 > 配置文件（统一去除尾斜杠）"""
    cli_url = request.config.getoption("--base-url", default="")
    if cli_url:
        return cli_url.rstrip("/")
    env_url = os.environ.get("FENIX_URL")
    if env_url:
        return env_url.rstrip("/")
    return api_test_config["fenixagent"]["url"].rstrip("/")


@pytest.fixture(scope="session")
def web_client(api_base_url, api_test_config):
    """WebClient 实例，登录后复用（控制台 API 测试账号）"""
    client = WebClient(api_base_url)
    fenix = api_test_config["fenixagent"]
    email = os.environ.get("FENIX_API_EMAIL") or fenix.get("api_email") or fenix["admin"]["email"]
    password = os.environ.get("FENIX_API_PASSWORD") or fenix.get("api_password") or fenix["admin"]["password"]
    client.login(email, password)

    # 登录后获取组织 ID，设置 x-active-org-id header（PR 环境必须）
    try:
        orgs = client.list_organizations()
        if orgs and len(orgs) > 0:
            org_id = orgs[0].get("id")
            if org_id:
                client.client.headers["x-active-org-id"] = org_id
    except Exception:
        pass  # 如果获取失败，继续测试（某些环境可能不需要此 header）

    yield client
    client.close()


@pytest.fixture(scope="session")
def api_client(api_base_url, api_test_config):
    """ApiClient 实例，Open API Key 认证"""
    api_key = os.environ.get("FENIX_OPEN_API_KEY") or api_test_config["fenixagent"]["api_key"]
    system_api_key = os.environ.get("FENIX_SYSTEM_API_KEY") or api_test_config["fenixagent"].get("system_api_key", "")
    client = ApiClient(api_base_url, api_key, system_api_key=system_api_key)
    yield client
    client.close()


@pytest.fixture(scope="module")
def _openapi_access(api_client, api_test_config):
    """模块级 OpenAPI 访问检查：验证 API Key 是否有效

    用法：在 OpenAPI 测试类中添加为 fixture 依赖即可
    class TestXxxOpenAPI:
        def test_xxx(self, api_client, _openapi_access):
            ...
    """
    # 1. 检查 API Key 是否为占位符
    if api_test_config["fenixagent"]["api_key"] == "test-api-key-placeholder":
        pytest.skip("API Key 未配置，跳过 OpenAPI 测试")

    # 2. 发送简单请求验证 Key 是否有效
    try:
        api_client.list_agents(params={"page": 1, "pageSize": 1})
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            pytest.skip("API Key 无效或已过期（401），跳过 OpenAPI 测试")
        if e.response.status_code == 403:
            pytest.skip("API Key 权限不足（403），跳过 OpenAPI 测试")
        raise
