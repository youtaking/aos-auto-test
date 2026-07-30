# tests/api_suites/test_organization_api.py
"""Organization 接口测试：功能验证 + 契约验证

覆盖控制台接口：
- TestOrganizationWebAPI: /web/organizations（session cookie 认证，RESTful /:id 风格）

注：组织创建/删除是管理员操作，测试中以只读验证为主，写操作用 try/finally 清理。
"""
import httpx
import pytest
from tests.api_contracts.organization_schemas import (
    ORGANIZATION_INFO,
    ORGANIZATION_MEMBER,
)


# ── 控制台接口测试 ──

class TestOrganizationWebAPI:
    """/web/organizations 控制台接口测试（session cookie 认证，RESTful /:id 风格）

    特点：
    - 用 /:id 路径参数定位资源
    - 响应统一包装为 {success, data} 格式
    - 组织 CRUD + 成员管理
    """

    def test_list_organizations(self, web_client):
        """获取组织列表：返回数组"""
        resp = web_client.list_organizations()
        assert isinstance(resp, list)
        if len(resp) > 0:
            web_client.validate_schema(resp[0], ORGANIZATION_INFO)

    def test_get_organization(self, web_client):
        """获取组织详情：先拿列表取第一个 id"""
        orgs = web_client.list_organizations()
        if len(orgs) == 0:
            pytest.skip("组织列表为空，无法测试详情")
        org_id = orgs[0]["id"]

        detail = web_client.get_organization(org_id)
        web_client.validate_schema(detail, ORGANIZATION_INFO)
        assert detail["id"] == org_id
        assert "name" in detail
        assert "slug" in detail

    def test_list_organization_members(self, web_client):
        """获取组织成员列表：先拿列表取第一个 id"""
        orgs = web_client.list_organizations()
        if len(orgs) == 0:
            pytest.skip("组织列表为空，无法测试成员")
        org_id = orgs[0]["id"]

        members = web_client.list_organization_members(org_id)
        assert isinstance(members, list)
        if len(members) > 0:
            web_client.validate_schema(members[0], ORGANIZATION_MEMBER)

    def test_search_member_candidates(self, web_client):
        """搜索成员候选项：空关键词返回空列表"""
        orgs = web_client.list_organizations()
        if len(orgs) == 0:
            pytest.skip("组织列表为空，无法测试候选项搜索")
        org_id = orgs[0]["id"]

        candidates = web_client.search_member_candidates(org_id, "")
        assert isinstance(candidates, list)

    def test_get_nonexistent_organization(self, web_client):
        """获取不存在的组织：应抛出异常"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError, ValueError)):
            web_client.get_organization("nonexistent-org-id-99999")
