# tests/api_suites/test_sandbox_api.py
"""Sandbox 接口测试：功能验证 + 契约验证

覆盖 System API 接口：
- TestSandboxPoolAPI: /api/system/sandbox-pools（System API Key 认证，RESTful 风格）
- TestSandboxInstanceAPI: /api/system/sandbox-instances（System API Key 认证，RESTful 风格）

注意：sandbox 端点需要 System API Key（RCS_SYSTEM_API_KEYS），
普通 API Key 可能无权访问。测试会在 401/403 时跳过。
"""
import httpx
import pytest


def _check_sandbox_access(client):
    """检查是否有 sandbox API 访问权限，返回 pool 列表或 None"""
    try:
        result = client.list_sandbox_pools()
        return result
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (401, 403, 503):
            return None
        raise


class TestSandboxPoolAPI:
    """/api/system/sandbox-pools 沙盒池管理接口（System API Key 认证）"""

    def test_list_sandbox_pools(self, api_client):
        """获取沙盒池列表：返回数组或分页结构"""
        try:
            result = api_client.list_sandbox_pools()
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (401, 403, 503):
                pytest.skip("System API Key 未配置或无权限")
            raise

        assert isinstance(result, (list, dict))

    def test_get_sandbox_pool(self, api_client):
        """获取沙盒池详情：先拿列表取第一个 id"""
        try:
            pools = api_client.list_sandbox_pools()
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (401, 403, 503):
                pytest.skip("System API Key 未配置或无权限")
            raise

        # 处理列表格式
        if isinstance(pools, list):
            items = pools
        elif isinstance(pools, dict):
            items = pools.get("items", pools.get("pools", []))
        else:
            items = []

        if len(items) == 0:
            pytest.skip("沙盒池列表为空，无法测试详情")

        pool_id = items[0].get("id") or items[0].get("poolId")
        if not pool_id:
            pytest.skip("沙盒池无有效 ID 字段")

        detail = api_client.get_sandbox_pool(pool_id)
        assert isinstance(detail, dict)

    def test_get_nonexistent_pool(self, api_client):
        """获取不存在的沙盒池：应返回 404"""
        access = _check_sandbox_access(api_client)
        if access is None:
            pytest.skip("System API Key 未配置或无权限")

        with pytest.raises(httpx.HTTPStatusError, match=r"(404|400)"):
            api_client.get_sandbox_pool("nonexistent-pool-id-99999")


class TestSandboxInstanceAPI:
    """/api/system/sandbox-instances 沙盒实例管理接口（System API Key 认证）"""

    def test_list_sandbox_instances(self, api_client):
        """获取沙盒实例列表：返回数组或分页结构"""
        try:
            result = api_client.list_sandbox_instances()
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (401, 403, 503):
                pytest.skip("System API Key 未配置或无权限")
            raise

        assert isinstance(result, (list, dict))

    def test_get_sandbox_instance(self, api_client):
        """获取沙盒实例详情：先拿列表取第一个 id"""
        try:
            instances = api_client.list_sandbox_instances()
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (401, 403, 503):
                pytest.skip("System API Key 未配置或无权限")
            raise

        # 处理列表格式
        if isinstance(instances, list):
            items = instances
        elif isinstance(instances, dict):
            items = instances.get("items", instances.get("instances", []))
        else:
            items = []

        if len(items) == 0:
            pytest.skip("沙盒实例列表为空，无法测试详情")

        instance_id = items[0].get("id") or items[0].get("instanceId")
        if not instance_id:
            pytest.skip("沙盒实例无有效 ID 字段")

        detail = api_client.get_sandbox_instance(instance_id)
        assert isinstance(detail, dict)

    def test_get_nonexistent_instance(self, api_client):
        """获取不存在的沙盒实例：应返回 404"""
        access = _check_sandbox_access(api_client)
        if access is None:
            pytest.skip("System API Key 未配置或无权限")

        with pytest.raises(httpx.HTTPStatusError, match=r"(404|400)"):
            api_client.get_sandbox_instance("nonexistent-instance-id-99999")
