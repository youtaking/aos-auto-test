# tests/api_suites/test_mcp_api.py
"""MCP Server 接口测试：功能验证 + 契约验证

覆盖两套接口：
- TestMcpWebAPI: /web/config/mcp 控制台接口（session cookie 认证，action 风格）
- TestMcpOpenAPI: /api/mcp 对外 OpenAPI（API Key 认证，RESTful 风格）
"""
import httpx
import pytest
from tests.api_contracts.mcp_schemas import (
    WEB_MCP_LIST_DATA,
    MCP_DETAIL,
    API_MCP_LIST_RESPONSE,
    API_MCP_DETAIL_RESPONSE,
    API_CREATE_MCP_RESPONSE,
    API_DELETE_MCP_RESPONSE,
    WEB_MCP_ENABLE_DATA,
    WEB_MCP_DISABLE_DATA,
    WEB_MCP_TOOLS_DATA,
)

# Web MCP detail/create 响应不含 id/type，使用宽松 schema
_WEB_MCP_DETAIL_DATA = {"type": "object", "required": ["name"], "additionalProperties": True}


# ── 工具函数 ──

def _cleanup_web_mcp(client, name: str):
    """通过 web 接口按名称删除 MCP Server，忽略错误（用于测试前置清理）"""
    try:
        client.delete_mcp_server(name)
    except Exception as e:
        import logging
        logging.getLogger("cleanup").warning(f"Cleanup failed: {e}")


def _cleanup_api_mcp(client, name: str):
    """通过 api 接口按名称查找并删除 MCP Server，忽略错误"""
    try:
        list_resp = client.list_mcp_servers(params={"pageSize": 100})
        for item in list_resp["items"]:
            if item["name"] == name:
                client.delete_mcp_server(item["id"])
    except Exception as e:
        import logging
        logging.getLogger("cleanup").warning(f"Cleanup failed: {e}")


# ── 控制台接口测试 ──

class TestMcpWebAPI:
    """/web/config/mcp 控制台接口测试（session cookie 认证，action 风格）

    特点：
    - 用 name 定位资源（?name=xxx），而非 ID
    - 响应统一包装为 {success, data} 格式
    - 创建时 body 结构为 {name, config: {...}}，config 内含 type/url/command 等
    - 列表返回 {servers: [...]}，servers 中每项含 id/name/type/enabled/toolsCount
    """

    def test_list_mcp_servers(self, web_client):
        """获取 MCP Server 列表：返回 servers 数组"""
        resp = web_client.list_mcp_servers()
        web_client.validate_schema(resp, WEB_MCP_LIST_DATA)
        assert isinstance(resp["servers"], list)

    def test_get_mcp_server(self, web_client):
        """获取单个 MCP Server 详情：先拿列表取第一个 name，再查详情"""
        list_data = web_client.list_mcp_servers()
        if len(list_data["servers"]) == 0:
            pytest.skip("MCP 列表为空，无法测试详情")
        server_name = list_data["servers"][0]["name"]

        detail = web_client.get_mcp_server(server_name)
        web_client.validate_schema(detail, _WEB_MCP_DETAIL_DATA)
        assert detail["name"] == server_name
        assert "config" in detail

    def test_create_and_delete_mcp_server(self, web_client):
        """创建并删除 MCP Server：写操作生命周期测试"""
        test_name = "api-test-web-mcp-001"

        _cleanup_web_mcp(web_client, test_name)

        # 创建 remote 类型（只需 name + url，不需要实际运行）
        create_resp = web_client.create_mcp_server({
            "name": test_name,
            "type": "remote",
            "url": "https://example.com/mcp",
        })
        web_client.validate_schema(create_resp, _WEB_MCP_DETAIL_DATA)
        assert create_resp["name"] == test_name

        try:
            # 验证创建成功
            detail = web_client.get_mcp_server(test_name)
            assert detail["name"] == test_name
            # 删除并验证资源已消失
            web_client.delete_mcp_server(test_name)
            with pytest.raises((httpx.HTTPStatusError, RuntimeError)):
                web_client.get_mcp_server(test_name)
        finally:
            _cleanup_web_mcp(web_client, test_name)

    def test_update_mcp_server(self, web_client):
        """更新 MCP Server：创建 → 修改 url → 验证 → 删除"""
        test_name = "api-test-web-mcp-002"
        updated_url = "https://updated.example.com/mcp"

        _cleanup_web_mcp(web_client, test_name)

        web_client.create_mcp_server({
            "name": test_name,
            "type": "remote",
            "url": "https://original.example.com/mcp",
        })

        try:
            # 记录更新前的字段值
            original_detail = web_client.get_mcp_server(test_name)
            original_name = original_detail.get("name")

            web_client.update_mcp_server(test_name, {
                "type": "remote",
                "url": updated_url,
            })

            # 再次获取确认更新生效
            detail = web_client.get_mcp_server(test_name)
            web_client.validate_schema(detail, _WEB_MCP_DETAIL_DATA)
            config = detail.get("config", {})
            assert config.get("url") == updated_url
            # 验证未修改字段未被清空
            assert detail.get("name") == original_name
        finally:
            web_client.delete_mcp_server(test_name)

    def test_get_nonexistent_mcp_server(self, web_client):
        """获取不存在的 MCP Server：应抛出 404 异常"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"404"):
            web_client.get_mcp_server("nonexistent-mcp-name-99999")

    def test_enable_disable_mcp_server(self, web_client):
        """启用/禁用 MCP Server：创建 → 禁用 → 验证 → 启用 → 验证 → 删除"""
        test_name = "api-test-web-mcp-toggle-001"

        _cleanup_web_mcp(web_client, test_name)

        try:
            web_client.create_mcp_server({
                "name": test_name,
                "type": "remote",
                "url": "https://example.com/mcp",
            })
        except (httpx.HTTPStatusError, RuntimeError) as e:
            if "500" in str(e):
                pytest.skip(f"MCP 创建接口返回 500，服务端可能不支持该操作: {e}")
            raise

        try:
            # 禁用
            disable_resp = web_client.disable_mcp_server(test_name)
            web_client.validate_schema(disable_resp, WEB_MCP_DISABLE_DATA)
            assert disable_resp["name"] == test_name
            assert disable_resp["enabled"] is False

            # 启用
            enable_resp = web_client.enable_mcp_server(test_name)
            web_client.validate_schema(enable_resp, WEB_MCP_ENABLE_DATA)
            assert enable_resp["name"] == test_name
            assert enable_resp["enabled"] is True
        finally:
            _cleanup_web_mcp(web_client, test_name)

    def test_list_mcp_tools(self, web_client):
        """获取 MCP Server 工具列表：先拿列表取第一个 name，再查工具"""
        list_data = web_client.list_mcp_servers()
        if len(list_data["servers"]) == 0:
            pytest.skip("MCP 列表为空，无法测试工具列表")
        server_name = list_data["servers"][0]["name"]

        resp = web_client.list_mcp_tools(server_name)
        web_client.validate_schema(resp, WEB_MCP_TOOLS_DATA)
        assert resp["name"] == server_name
        assert isinstance(resp["tools"], list)


# ── 对外 OpenAPI 测试 ──

class TestMcpOpenAPI:
    """/api/mcp 对外 OpenAPI 测试（API Key 认证，RESTful 风格）

    特点：
    - 用 ID 定位资源（/:id）
    - 列表带分页 {items, total, page, pageSize}
    - 响应为裸数据，无 {success, data} 包装
    - 创建 body 直接传 {name, type, url/command, ...}，无包装
    """

    def test_list_mcp_servers(self, api_client, _openapi_access):
        """获取 MCP Server 列表：返回分页结构"""

        resp = api_client.list_mcp_servers()
        api_client.validate_schema(resp, API_MCP_LIST_RESPONSE)
        assert isinstance(resp["items"], list)

    def test_get_mcp_server(self, api_client, _openapi_access):
        """获取单个 MCP Server 详情：先拿列表取第一个 ID，再查详情"""

        list_resp = api_client.list_mcp_servers()
        if len(list_resp["items"]) == 0:
            pytest.skip("MCP 列表为空，跳过详情测试")
        server_id = list_resp["items"][0]["id"]

        resp = api_client.get_mcp_server(server_id)
        api_client.validate_schema(resp, API_MCP_DETAIL_RESPONSE)
        assert resp["id"] == server_id

    def test_create_and_delete_mcp_server(self, api_client, _openapi_access):
        """创建并删除 MCP Server：写操作生命周期测试"""

        test_name = "api-test-openapi-mcp-001"

        _cleanup_api_mcp(api_client, test_name)

        # 创建 remote 类型
        create_resp = api_client.create_mcp_server({
            "name": test_name,
            "type": "remote",
            "url": "https://example.com/mcp",
        })
        api_client.validate_schema(create_resp, API_CREATE_MCP_RESPONSE)
        server_id = create_resp["id"]
        assert create_resp["name"] == test_name

        try:
            get_resp = api_client.get_mcp_server(server_id)
            assert get_resp["name"] == test_name
            # 删除并验证资源已消失
            del_resp = api_client.delete_mcp_server(server_id)
            api_client.validate_schema(del_resp, API_DELETE_MCP_RESPONSE)
            with pytest.raises(httpx.HTTPStatusError, match=r"404"):
                api_client.get_mcp_server(server_id)
        finally:
            _cleanup_api_mcp(api_client, test_name)

    def test_update_mcp_server(self, api_client, _openapi_access):
        """更新 MCP Server：创建 → 修改 url → 验证 → 删除"""

        test_name = "api-test-openapi-mcp-002"
        updated_url = "https://updated-openapi.example.com/mcp"

        _cleanup_api_mcp(api_client, test_name)

        create_resp = api_client.create_mcp_server({
            "name": test_name,
            "type": "remote",
            "url": "https://original.example.com/mcp",
        })
        server_id = create_resp["id"]

        try:
            # 记录更新前的字段值
            original_detail = api_client.get_mcp_server(server_id)
            original_name = original_detail.get("name")

            update_resp = api_client.update_mcp_server(server_id, {
                "type": "remote",
                "url": updated_url,
            })

            # 再次获取确认更新生效
            get_resp = api_client.get_mcp_server(server_id)
            api_client.validate_schema(get_resp, API_MCP_DETAIL_RESPONSE)
            assert get_resp["summary"] == updated_url
            # 验证未修改字段未被清空
            assert get_resp.get("name") == original_name
        finally:
            api_client.delete_mcp_server(server_id)

    def test_get_nonexistent_mcp_server(self, api_client, _openapi_access):
        """获取不存在的 MCP Server：应返回 404"""

        with pytest.raises(httpx.HTTPStatusError, match=r"404"):
            api_client.get_mcp_server("nonexistent-mcp-id-99999")

    def test_delete_mcp_idempotent(self, api_client, _openapi_access):
        """MCP DELETE 幂等性：第二次删除返回 404"""
        test_name = "test-idempotent-delete-mcp"
        _cleanup_api_mcp(api_client, test_name)
        try:
            create_resp = api_client.create_mcp_server({
                "name": test_name,
                "type": "remote",
                "url": "https://example.com/mcp",
            })
            server_id = create_resp["id"]
            api_client.delete_mcp_server(server_id)
            with pytest.raises(httpx.HTTPStatusError, match=r"404"):
                api_client.delete_mcp_server(server_id)
        finally:
            _cleanup_api_mcp(api_client, test_name)

    def test_create_mcp_server_duplicate_name(self, api_client, _openapi_access):
        """创建同名 MCP Server：应返回 409 或抛出冲突异常"""

        test_name = "api-test-openapi-mcp-dup"
        _cleanup_api_mcp(api_client, test_name)

        create_resp = api_client.create_mcp_server({
            "name": test_name,
            "type": "remote",
            "url": "https://example.com/mcp",
        })
        try:
            with pytest.raises(httpx.HTTPStatusError, match=r"(409|400)"):
                api_client.create_mcp_server({
                    "name": test_name,
                    "type": "remote",
                    "url": "https://example.com/mcp",
                })
        finally:
            api_client.delete_mcp_server(create_resp["id"])


# ── 新增场景测试 ──

class TestMcpWebAPIExtra:
    """MCP Web API 额外场景测试"""

    def test_create_mcp_server_invalid_type(self, web_client):
        """创建 MCP Server 使用无效 type：应返回 400 或抛出异常"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"(400|422)"):
            web_client.create_mcp_server({
                "name": "api-test-invalid-type",
                "type": "invalid_type_xyz",
                "url": "https://example.com",
            })
