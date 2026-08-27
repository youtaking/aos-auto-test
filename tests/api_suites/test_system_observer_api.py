# tests/api_suites/test_system_observer_api.py
"""System Observer API 接口测试：功能验证 + 契约验证

覆盖 System Observer API：
- TestSystemObserverAPI: /api/system/observer/acp-link（ACP 活跃链接观察视图）

认证方式：System API Key（RCS_SYSTEM_API_KEYS 环境变量）
响应格式：{success: true, data: {...}} 包装

数据安全规则：
- 全部只读接口，不创建/修改/删除数据
"""
import time
import httpx
import pytest
from tests.api_contracts.system_observer_schemas import OBSERVER_ACP_LINK_DATA


# ── 工具函数 ──

def _check_system_access(api_client, max_retries=3):
    """检查是否有 System API 访问权限（使用 system_api_key）"""
    if not api_client._system_api_key:
        return False
    for attempt in range(max_retries):
        try:
            api_client.get_observer_acp_link()
            return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                time.sleep(2 * (attempt + 1))
                continue
            if e.response.status_code in (401, 403, 404):
                return False
            raise
    return False


@pytest.fixture(scope="module")
def _system_access(api_client):
    """模块级 System API 访问检查 fixture"""
    if not _check_system_access(api_client):
        pytest.skip("System API Key 未配置或 /api/system/observer 不可用，跳过测试")


# ── Observer 测试 ──

class TestSystemObserverAPI:
    """/api/system/observer/acp-link ACP 活跃链接观察视图接口（System API Key 认证）"""

    # ── 正向场景（P0） ──

    def test_get_acp_link_tree(self, api_client, _system_access):
        """获取 ACP 链接观察树：返回完整视图结构"""
        data = api_client.get_observer_acp_link()
        api_client.validate_schema(data, OBSERVER_ACP_LINK_DATA)
        assert data["kind"] == "acp-link"
        assert isinstance(data["total"], int)
        assert data["total"] >= 0

    def test_get_acp_link_tree_structure(self, api_client, _system_access):
        """观察树结构：trees 包含 byEntity 和 byOrg 两棵树"""
        data = api_client.get_observer_acp_link()
        api_client.validate_schema(data, OBSERVER_ACP_LINK_DATA)
        assert "trees" in data
        assert "byEntity" in data["trees"]
        assert "byOrg" in data["trees"]
        assert isinstance(data["trees"]["byEntity"], list)
        assert isinstance(data["trees"]["byOrg"], list)

    def test_get_acp_link_integrity(self, api_client, _system_access):
        """一致性汇总：integrity 包含 checked、mismatched、mismatchedItems"""
        data = api_client.get_observer_acp_link()
        api_client.validate_schema(data, OBSERVER_ACP_LINK_DATA)
        integrity = data["integrity"]
        assert isinstance(integrity["checked"], int)
        assert isinstance(integrity["mismatched"], int)
        assert isinstance(integrity["mismatchedItems"], list)
        assert integrity["checked"] >= 0
        assert integrity["mismatched"] >= 0

    def test_get_acp_link_names(self, api_client, _system_access):
        """名称字典：names 包含各角色 id→名称映射"""
        data = api_client.get_observer_acp_link()
        api_client.validate_schema(data, OBSERVER_ACP_LINK_DATA)
        names = data["names"]
        assert isinstance(names, dict)

    def test_get_acp_link_generated_at(self, api_client, _system_access):
        """生成时间：generatedAt 为 ISO 8601 格式字符串"""
        data = api_client.get_observer_acp_link()
        api_client.validate_schema(data, OBSERVER_ACP_LINK_DATA)
        assert isinstance(data["generatedAt"], str)
        assert len(data["generatedAt"]) > 0

    # ── 权限场景（P0） ──

    def test_get_acp_link_unauthorized(self, api_base_url):
        """无认证访问 observer：应返回 401"""
        client = httpx.Client(base_url=api_base_url, timeout=10, verify=False)
        try:
            resp = client.get("/api/system/observer/acp-link")
            assert resp.status_code == 401
        finally:
            client.close()
