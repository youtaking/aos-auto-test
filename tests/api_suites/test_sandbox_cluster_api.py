# tests/api_suites/test_sandbox_cluster_api.py
"""Sandbox Cluster 接口测试（System API Key，只读）

覆盖：
- /api/system/sandbox-cluster/pools
- /api/system/sandbox-cluster/servers
- /api/system/sandbox-server/servers/:serverId/sandboxes

创建/更新/删除属于集群管理动作，只覆盖只读查询、不存在资源与必填校验（校验失败不落库）。
"""
import httpx
import pytest


class TestSandboxClusterSystemAPI:
    """/api/system/sandbox-cluster 只读接口测试"""

    @pytest.mark.p1
    def test_list_pools(self, api_client, system_access):
        """获取沙盒池列表：返回数组且元素含 id/name/status"""
        pools = api_client.list_sandbox_cluster_pools()
        assert isinstance(pools, list)
        for pool in pools:
            assert isinstance(pool.get("id"), str)
            assert isinstance(pool.get("name"), str)
            assert isinstance(pool.get("status"), str)

    @pytest.mark.p1
    def test_get_pool(self, api_client, system_access):
        """获取沙盒池详情：先取列表首个 id"""
        pools = api_client.list_sandbox_cluster_pools()
        if not pools:
            pytest.skip("沙盒池列表为空，无法测试详情")
        pool_id = pools[0]["id"]

        detail = api_client.get_sandbox_cluster_pool(pool_id)
        assert detail.get("id") == pool_id
        assert isinstance(detail.get("capacitySandboxes"), int)

    @pytest.mark.p1
    def test_list_servers(self, api_client, system_access):
        """获取沙盒服务器列表：返回数组且元素含 id/poolId/status"""
        servers = api_client.list_sandbox_cluster_servers()
        assert isinstance(servers, list)
        for server in servers:
            assert isinstance(server.get("id"), str)
            assert isinstance(server.get("poolId"), str)
            assert isinstance(server.get("status"), str)

    @pytest.mark.p1
    def test_get_server(self, api_client, system_access):
        """获取沙盒服务器详情：先取列表首个 id"""
        servers = api_client.list_sandbox_cluster_servers()
        if not servers:
            pytest.skip("沙盒服务器列表为空，无法测试详情")
        server_id = servers[0]["id"]

        detail = api_client.get_sandbox_cluster_server(server_id)
        assert detail.get("id") == server_id
        assert isinstance(detail.get("baseUrl"), str)

    @pytest.mark.p1
    def test_list_server_sandboxes(self, api_client, system_access):
        """列出服务器上的沙盒：items 为数组"""
        servers = api_client.list_sandbox_cluster_servers()
        if not servers:
            pytest.skip("沙盒服务器列表为空，无法测试沙盒列表")
        server_id = servers[0]["id"]

        data = api_client.list_sandbox_server_sandboxes(server_id, params={"page": 1, "pageSize": 10})
        assert isinstance(data.get("items"), list)

    @pytest.mark.p2
    def test_get_nonexistent_pool(self, api_client, system_access):
        """获取不存在的沙盒池：应返回 404 NOT_FOUND"""
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            api_client.get_sandbox_cluster_pool("nonexistent-pool-id-99999")
        assert exc_info.value.response.status_code == 404
        assert exc_info.value.response.json().get("error", {}).get("code") == "NOT_FOUND"

    @pytest.mark.p2
    def test_get_nonexistent_server(self, api_client, system_access):
        """获取不存在的沙盒服务器：应返回 404 NOT_FOUND"""
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            api_client.get_sandbox_cluster_server("nonexistent-server-id-99999")
        assert exc_info.value.response.status_code == 404
        assert exc_info.value.response.json().get("error", {}).get("code") == "NOT_FOUND"

    @pytest.mark.p2
    def test_list_sandboxes_of_nonexistent_server(self, api_client, system_access):
        """不存在服务器的沙盒列表：应返回 404 NOT_FOUND"""
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            api_client.list_sandbox_server_sandboxes("nonexistent-server-id-99999")
        assert exc_info.value.response.status_code == 404
        assert exc_info.value.response.json().get("error", {}).get("code") == "NOT_FOUND"

    @pytest.mark.p2
    def test_create_pool_missing_id(self, api_client, system_access):
        """创建沙盒池缺少 id：应返回 400 VALIDATION_ERROR（不落库）"""
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            api_client._system_request("post", "/api/system/sandbox-cluster/pools", json={})
        assert exc_info.value.response.status_code == 400
        err = exc_info.value.response.json().get("error", {})
        assert err.get("type") == "VALIDATION_ERROR"
        assert "id" in err.get("message", "")

    @pytest.mark.p2
    def test_create_server_missing_id(self, api_client, system_access):
        """创建沙盒服务器缺少 id：应返回 400 VALIDATION_ERROR（不落库）"""
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            api_client._system_request("post", "/api/system/sandbox-cluster/servers", json={})
        assert exc_info.value.response.status_code == 400
        err = exc_info.value.response.json().get("error", {})
        assert err.get("type") == "VALIDATION_ERROR"
        assert "id" in err.get("message", "")
