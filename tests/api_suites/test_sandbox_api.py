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
from tests.api_contracts.sandbox_schemas import SANDBOX_POOL_ITEM, SANDBOX_INSTANCE_ITEM


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
        # 验证列表项结构
        if isinstance(result, list) and len(result) > 0:
            item = result[0]
            api_client.validate_schema(item, SANDBOX_POOL_ITEM)
            assert "id" in item or "poolId" in item, f"沙盒池项缺少 ID 字段: {list(item.keys())}"
        elif isinstance(result, dict):
            items = result.get("items", result.get("pools", []))
            assert isinstance(items, list), f"分页结构中 items/pools 应为 list，实际: {type(items)}"
            if len(items) > 0:
                api_client.validate_schema(items[0], SANDBOX_POOL_ITEM)

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
        api_client.validate_schema(detail, SANDBOX_POOL_ITEM)
        # 验证详情包含 ID 字段
        detail_id = detail.get("id") or detail.get("poolId")
        assert detail_id is not None, f"沙盒池详情缺少 ID 字段: {list(detail.keys())}"
        assert detail_id == pool_id, f"沙盒池详情 ID 不匹配: 期望 {pool_id}，实际 {detail_id}"

    def test_get_nonexistent_pool(self, api_client):
        """获取不存在的沙盒池：应返回 404"""
        access = _check_sandbox_access(api_client)
        if access is None:
            pytest.skip("System API Key 未配置或无权限")

        with pytest.raises(httpx.HTTPStatusError, match=r"404"):
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
        # 验证列表项结构
        if isinstance(result, list) and len(result) > 0:
            item = result[0]
            api_client.validate_schema(item, SANDBOX_INSTANCE_ITEM)
            assert "id" in item or "instanceId" in item, \
                f"沙盒实例项缺少 ID 字段: {list(item.keys())}"
        elif isinstance(result, dict):
            items = result.get("items", result.get("instances", []))
            assert isinstance(items, list), f"分页结构中 items/instances 应为 list，实际: {type(items)}"
            if len(items) > 0:
                api_client.validate_schema(items[0], SANDBOX_INSTANCE_ITEM)

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
        api_client.validate_schema(detail, SANDBOX_INSTANCE_ITEM)
        # 验证详情包含 ID 字段
        detail_id = detail.get("id") or detail.get("instanceId")
        assert detail_id is not None, f"沙盒实例详情缺少 ID 字段: {list(detail.keys())}"
        assert detail_id == instance_id, f"沙盒实例详情 ID 不匹配: 期望 {instance_id}，实际 {detail_id}"

    def test_get_nonexistent_instance(self, api_client):
        """获取不存在的沙盒实例：应返回 404"""
        access = _check_sandbox_access(api_client)
        if access is None:
            pytest.skip("System API Key 未配置或无权限")

        with pytest.raises(httpx.HTTPStatusError, match=r"404"):
            api_client.get_sandbox_instance("nonexistent-instance-id-99999")
