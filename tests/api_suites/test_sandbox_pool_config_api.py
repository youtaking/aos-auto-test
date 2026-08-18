# tests/api_suites/test_sandbox_pool_config_api.py
"""Sandbox Pool Config 接口测试：功能验证 + 契约验证

覆盖控制台接口：
- TestSandboxPoolConfigAPI: GET /web/config/sandbox-pools（session cookie 认证）

Sandbox Pool Config 是 refactor/yjs 分支新增的配置查询端点，
返回当前组织可用的 sandbox pool 列表及是否启用 sandbox 功能。
"""
import httpx
import pytest


class TestSandboxPoolConfigAPI:
    """GET /web/config/sandbox-pools 沙盒池配置查询接口

    特点：
    - 只读查询接口
    - 返回 {enabled: bool, pools: [{id, name}, ...]}
    - 依赖 sandbox 功能是否启用
    """

    def test_get_sandbox_pool_options(self, web_client):
        """获取 sandbox pool 可选项：返回 enabled + pools 结构"""
        try:
            resp = web_client.get("/web/config/sandbox-pools")
            data = web_client._unwrap(resp)
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "503" in err_str or "SERVICE_UNAVAILABLE" in err_str:
                pytest.skip("Sandbox 服务未启用")
            raise

        assert isinstance(data, dict), f"响应应为 dict，实际: {type(data)}"

        # enabled 字段
        assert "enabled" in data, f"响应缺少 enabled 字段: {list(data.keys())}"
        assert isinstance(data["enabled"], bool)

        # pools 字段
        assert "pools" in data, f"响应缺少 pools 字段: {list(data.keys())}"
        assert isinstance(data["pools"], list)

        if data["enabled"] and len(data["pools"]) > 0:
            pool = data["pools"][0]
            assert isinstance(pool, dict)
            assert "id" in pool, f"pool 条目缺少 id: {list(pool.keys())}"
            assert "name" in pool, f"pool 条目缺少 name: {list(pool.keys())}"

    def test_get_sandbox_pool_options_schema(self, web_client):
        """验证 sandbox pool 响应结构完整性"""
        try:
            resp = web_client.get("/web/config/sandbox-pools")
            data = web_client._unwrap(resp)
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "503" in err_str:
                pytest.skip("Sandbox 服务未启用")
            raise

        # schema 校验
        schema = {
            "type": "object",
            "required": ["enabled", "pools"],
            "properties": {
                "enabled": {"type": "boolean"},
                "pools": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["id", "name"],
                        "properties": {
                            "id": {"type": "string"},
                            "name": {"type": "string"},
                        },
                    },
                },
            },
        }
        web_client.validate_schema(data, schema)

    def test_sandbox_pool_options_unauthorized(self, api_base_url):
        """未登录访问 sandbox pool 配置：应返回 401"""
        from tests.api_clients.web_client import WebClient
        bad_client = WebClient(api_base_url)
        try:
            with pytest.raises(httpx.HTTPStatusError, match="401"):
                bad_client.get("/web/config/sandbox-pools")
        finally:
            bad_client.close()
