# tests/api_suites/test_system_people_tree_api.py
"""System People Tree API 接口测试：功能验证 + 契约验证

覆盖 System People Tree API：
- TestSystemPeopleTreeAPI: /api/system/people-tree（组织人员智能体层级）

认证方式：System API Key（RCS_SYSTEM_API_KEYS 环境变量）
响应格式：{success: true, data: {organizations: [...]}} 包装

数据安全规则：
- 全部只读接口，不创建/修改/删除数据
"""
import time
import httpx
import pytest
from tests.api_contracts.system_people_tree_schemas import SYSTEM_PEOPLE_TREE_RESPONSE


# ── 工具函数 ──

def _check_system_access(api_client, max_retries=3):
    """检查是否有 System API 访问权限（使用 system_api_key）"""
    if not api_client._system_api_key:
        return False
    for attempt in range(max_retries):
        try:
            api_client.get_people_tree()
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
        pytest.skip("System API Key 未配置或 /api/system/people-tree 不可用，跳过测试")


# ── People Tree 测试 ──

class TestSystemPeopleTreeAPI:
    """/api/system/people-tree 组织人员智能体层级接口（System API Key 认证）"""

    # ── 正向场景（P0） ──

    def test_get_people_tree(self, api_client, _system_access):
        """获取人员层级：返回 {organizations: [...]}"""
        data = api_client.get_people_tree()
        api_client.validate_schema(data, SYSTEM_PEOPLE_TREE_RESPONSE)
        assert isinstance(data["organizations"], list)

    def test_get_people_tree_organization_structure(self, api_client, _system_access):
        """组织结构：每个组织包含 id、name、slug、users"""
        data = api_client.get_people_tree()
        api_client.validate_schema(data, SYSTEM_PEOPLE_TREE_RESPONSE)
        if not data["organizations"]:
            pytest.skip("组织列表为空，无法校验组织结构")
        org = data["organizations"][0]
        assert "id" in org
        assert "name" in org
        assert "slug" in org
        assert "users" in org
        assert isinstance(org["users"], list)

    def test_get_people_tree_user_structure(self, api_client, _system_access):
        """用户结构：每个用户包含 id、name、email、agents"""
        data = api_client.get_people_tree()
        api_client.validate_schema(data, SYSTEM_PEOPLE_TREE_RESPONSE)
        # 找到至少一个有用户的组织
        for org in data["organizations"]:
            if org["users"]:
                user = org["users"][0]
                assert "id" in user
                assert "name" in user
                assert "email" in user
                assert "agents" in user
                assert isinstance(user["agents"], list)
                return
        pytest.skip("所有组织均无用户，无法校验用户结构")

    def test_get_people_tree_agent_structure(self, api_client, _system_access):
        """智能体结构：每个 agent 包含 id、name"""
        data = api_client.get_people_tree()
        api_client.validate_schema(data, SYSTEM_PEOPLE_TREE_RESPONSE)
        # 找到至少一个有 agent 的用户
        for org in data["organizations"]:
            for user in org["users"]:
                if user["agents"]:
                    agent = user["agents"][0]
                    assert "id" in agent
                    assert "name" in agent
                    return
        pytest.skip("所有用户均无智能体，无法校验 agent 结构")

    # ── 权限场景（P0） ──

    def test_get_people_tree_unauthorized(self, api_base_url):
        """无认证访问 people-tree：应返回 401"""
        client = httpx.Client(base_url=api_base_url, timeout=10, verify=False)
        try:
            resp = client.get("/api/system/people-tree")
            assert resp.status_code == 401
        finally:
            client.close()
