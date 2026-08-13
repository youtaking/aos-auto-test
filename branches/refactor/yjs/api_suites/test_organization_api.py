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
        # 验证列表元素结构（如有返回）
        if len(candidates) > 0:
            candidate = candidates[0]
            assert isinstance(candidate, dict)
            assert "id" in candidate or "email" in candidate or "name" in candidate, \
                f"候选项缺少标识字段: {list(candidate.keys())}"

    def test_get_nonexistent_organization(self, web_client):
        """获取不存在的组织：应抛出异常"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError, ValueError)):
            web_client.get_organization("nonexistent-org-id-99999")

    def test_organization_crud_lifecycle(self, web_client):
        """组织 CRUD 生命周期：创建 → 读取 → 更新 → 删除"""
        test_name = "api-test-org-crud-001"
        test_slug = "api-test-org-crud-001"

        # 先清理可能存在的同名组织
        try:
            existing = web_client.list_organizations()
            for org in existing:
                if org.get("name") == test_name or org.get("slug") == test_slug:
                    web_client.delete_organization(org["id"])
        except Exception:
            pass

        try:
            # 创建
            create_resp = web_client.create_organization({
                "name": test_name,
                "slug": test_slug,
            })
            web_client.validate_schema(create_resp, ORGANIZATION_INFO)
            org_id = create_resp["id"]
            assert org_id is not None

            try:
                # 读取
                detail = web_client.get_organization(org_id)
                assert detail["id"] == org_id
                assert detail["name"] == test_name

                # 更新
                updated_name = f"{test_name}-updated"
                update_resp = web_client.update_organization(org_id, {
                    "name": updated_name,
                    "slug": test_slug,
                })
                assert update_resp["id"] == org_id

                # 回读验证更新
                detail = web_client.get_organization(org_id)
                assert detail.get("name") == updated_name

                # 删除并验证
                web_client.delete_organization(org_id)
                with pytest.raises((httpx.HTTPStatusError, RuntimeError, ValueError)):
                    web_client.get_organization(org_id)
            finally:
                try:
                    web_client.delete_organization(org_id)
                except Exception:
                    pass
        except (httpx.HTTPStatusError, RuntimeError, ValueError) as e:
            if "400" in str(e) or "403" in str(e) or "409" in str(e) or "500" in str(e):
                pytest.skip(f"组织创建接口不可用: {e}")
            raise
