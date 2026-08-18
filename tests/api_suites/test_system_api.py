# tests/api_suites/test_system_api.py
"""System API 接口测试：功能验证 + 契约验证

覆盖 System Management API：
- TestSystemUserAPI: /api/system/users（用户管理）
- TestSystemOrganizationAPI: /api/system/organizations（组织管理）
- TestSystemApiKeyAPI: /api/system/api-keys（API Key 管理）

认证方式：System API Key（RCS_SYSTEM_API_KEYS 环境变量）
响应格式：裸数据（无 {success, data} 包装），列表带分页 {items, total, page, pageSize}

数据安全规则：
- 只读操作（list/get）可调用已有数据
- 写操作（create/delete）必须先自建对象，try/finally 清理
- 密码重置仅对自建用户执行
"""
import time
import uuid
import httpx
import pytest
from tests.api_contracts.system_api_schemas import (
    SYSTEM_USER_LIST_RESPONSE,
    SYSTEM_USER_DETAIL_RESPONSE,
    SYSTEM_CREATE_USER_RESPONSE,
    SYSTEM_ORGANIZATION_LIST_RESPONSE,
    SYSTEM_ORGANIZATION_DETAIL_RESPONSE,
    SYSTEM_CREATE_ORGANIZATION_RESPONSE,
    SYSTEM_API_KEY_LIST_RESPONSE,
    SYSTEM_CREATE_API_KEY_RESPONSE,
    SYSTEM_DELETE_RESPONSE,
    SYSTEM_UPDATE_RESPONSE,
    SYSTEM_USER_ORGANIZATION_LIST_RESPONSE,
)


# ── 工具函数 ──

def _check_system_access(api_client, max_retries=3):
    """检查是否有 System API 访问权限。
    返回 True 表示可用，False 表示需跳过。
    自动重试 429 限流，最多重试 max_retries 次。
    """
    for attempt in range(max_retries):
        try:
            api_client.list_users(params={"page": 1, "pageSize": 1})
            return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                time.sleep(2 * (attempt + 1))  # 递增等待
                continue
            if e.response.status_code in (401, 403):
                return False
            raise
    return False  # 重试耗尽，视为无权限


@pytest.fixture(scope="module")
def _system_access(api_client):
    """模块级 System API 访问检查 fixture"""
    if not _check_system_access(api_client):
        pytest.skip("System API Key 未配置或无权限，跳过所有 System API 测试")


def _generate_test_email():
    """生成唯一测试邮箱"""
    return f"sys-test-{uuid.uuid4().hex[:8]}@test.local"


def _generate_test_slug():
    """生成唯一测试 slug"""
    return f"sys-test-org-{uuid.uuid4().hex[:8]}"


# ── 用户管理测试 ──

class TestSystemUserAPI:
    """/api/system/users 用户管理接口（System API Key 认证）"""

    def test_list_users(self, api_client, _system_access):
        """获取用户列表：返回分页结构"""
        resp = api_client.list_users(params={"page": 1, "pageSize": 10})
        api_client.validate_schema(resp, SYSTEM_USER_LIST_RESPONSE)
        assert isinstance(resp["items"], list)
        assert resp["total"] >= 0

    def test_get_user(self, api_client, _system_access):
        """获取用户详情：先拿列表取第一个 ID，再查详情"""
        list_resp = api_client.list_users(params={"page": 1, "pageSize": 5})
        if not list_resp["items"]:
            pytest.skip("用户列表为空，无法测试详情")

        user_id = list_resp["items"][0]["id"]
        detail = api_client.get_user(user_id)
        api_client.validate_schema(detail, SYSTEM_USER_DETAIL_RESPONSE)
        assert detail["id"] == user_id
        assert "name" in detail
        assert "email" in detail

    def test_create_and_delete_user(self, api_client, _system_access):
        """创建并删除用户：自建用户 → 验证 → 清理"""
        test_email = _generate_test_email()
        test_name = "System API Test User"
        test_password = "TestPass12345678"

        create_resp = api_client.create_user({
            "email": test_email,
            "name": test_name,
            "password": test_password,
        })
        api_client.validate_schema(create_resp, SYSTEM_CREATE_USER_RESPONSE)
        user_id = create_resp["id"]
        assert create_resp["email"] == test_email
        assert create_resp["name"] == test_name

        try:
            # 验证创建成功
            detail = api_client.get_user(user_id)
            assert detail["id"] == user_id
            assert detail["email"] == test_email
        finally:
            # 清理：删除自建用户
            try:
                api_client.delete_user(user_id)
            except Exception:
                pass

    def test_get_nonexistent_user(self, api_client, _system_access):
        """获取不存在的用户：应返回 404"""
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            api_client.get_user(f"nonexistent-user-{uuid.uuid4().hex[:8]}")
        assert exc_info.value.response.status_code == 404

    def test_reset_user_password(self, api_client, _system_access):
        """重置用户密码：自建用户 → 重置密码 → 清理"""
        test_email = _generate_test_email()
        test_password = "InitialPass12345678"
        new_password = "NewPass87654321"

        # 先创建测试用户
        create_resp = api_client.create_user({
            "email": test_email,
            "name": "Password Reset Test User",
            "password": test_password,
        })
        user_id = create_resp["id"]

        try:
            # 重置密码
            resp = api_client.reset_user_password({
                "userId": user_id,
                "password": new_password,
            })
            api_client.validate_schema(resp, SYSTEM_UPDATE_RESPONSE)
            assert resp.get("updated") is True
        finally:
            try:
                api_client.delete_user(user_id)
            except Exception:
                pass

    def test_list_user_api_keys(self, api_client, _system_access):
        """获取用户 API Key 列表：先拿用户列表取第一个 ID"""
        list_resp = api_client.list_users(params={"page": 1, "pageSize": 5})
        if not list_resp["items"]:
            pytest.skip("用户列表为空，无法测试 API Key 列表")

        user_id = list_resp["items"][0]["id"]
        keys_resp = api_client.list_user_api_keys(user_id, params={"page": 1, "pageSize": 10})
        api_client.validate_schema(keys_resp, SYSTEM_API_KEY_LIST_RESPONSE)
        assert isinstance(keys_resp["items"], list)

    def test_list_user_organizations(self, api_client, _system_access):
        """获取用户所属组织列表：先拿用户列表取第一个 ID"""
        list_resp = api_client.list_users(params={"page": 1, "pageSize": 5})
        if not list_resp["items"]:
            pytest.skip("用户列表为空，无法测试用户组织列表")

        user_id = list_resp["items"][0]["id"]
        orgs_resp = api_client.list_user_organizations(user_id, params={"page": 1, "pageSize": 10})
        api_client.validate_schema(orgs_resp, SYSTEM_USER_ORGANIZATION_LIST_RESPONSE)
        assert isinstance(orgs_resp["items"], list)


# ── 组织管理测试 ──

class TestSystemOrganizationAPI:
    """/api/system/organizations 组织管理接口（System API Key 认证）"""

    def test_list_organizations(self, api_client, _system_access):
        """获取组织列表：返回分页结构"""
        resp = api_client.list_organizations(params={"page": 1, "pageSize": 10})
        api_client.validate_schema(resp, SYSTEM_ORGANIZATION_LIST_RESPONSE)
        assert isinstance(resp["items"], list)
        assert resp["total"] >= 0

    def test_get_organization(self, api_client, _system_access):
        """获取组织详情：先拿列表取第一个 ID"""
        list_resp = api_client.list_organizations(params={"page": 1, "pageSize": 5})
        if not list_resp["items"]:
            pytest.skip("组织列表为空，无法测试详情")

        org_id = list_resp["items"][0]["id"]
        detail = api_client.get_organization(org_id)
        api_client.validate_schema(detail, SYSTEM_ORGANIZATION_DETAIL_RESPONSE)
        assert detail["id"] == org_id
        assert "name" in detail
        assert "members" in detail
        assert isinstance(detail["members"], list)

    def test_create_and_delete_organization(self, api_client, _system_access):
        """创建并删除组织：自建 → 验证 → 清理"""
        test_name = "System API Test Org"
        test_slug = _generate_test_slug()

        create_resp = api_client.create_organization({
            "name": test_name,
            "slug": test_slug,
        })
        api_client.validate_schema(create_resp, SYSTEM_CREATE_ORGANIZATION_RESPONSE)
        org_id = create_resp["id"]
        assert create_resp["name"] == test_name
        assert create_resp["slug"] == test_slug

        try:
            # 验证创建成功
            detail = api_client.get_organization(org_id)
            assert detail["id"] == org_id
            assert detail["name"] == test_name
        finally:
            try:
                api_client.delete_organization(org_id)
            except Exception:
                pass

    def test_get_nonexistent_organization(self, api_client, _system_access):
        """获取不存在的组织：应返回 404"""
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            api_client.get_organization(f"nonexistent-org-{uuid.uuid4().hex[:8]}")
        assert exc_info.value.response.status_code == 404

    def test_add_organization_member(self, api_client, _system_access):
        """添加组织成员：自建组织 + 自建用户 → 添加成员 → 验证 → 清理"""
        # 创建测试组织
        org_slug = _generate_test_slug()
        org_resp = api_client.create_organization({
            "name": "Member Test Org",
            "slug": org_slug,
        })
        org_id = org_resp["id"]

        # 创建测试用户
        user_email = _generate_test_email()
        user_resp = api_client.create_user({
            "email": user_email,
            "name": "Member Test User",
            "password": "TestPass12345678",
        })
        user_id = user_resp["id"]

        try:
            # 添加成员
            member_resp = api_client.add_organization_member(org_id, {
                "userId": user_id,
                "role": "member",
            })
            assert member_resp["userId"] == user_id
            assert member_resp["organizationId"] == org_id
            assert member_resp["role"] == "member"

            # 验证：组织详情中包含新成员
            detail = api_client.get_organization(org_id)
            member_ids = [m["userId"] for m in detail["members"]]
            assert user_id in member_ids
        finally:
            # 清理：删除组织和用户
            try:
                api_client.delete_organization(org_id)
            except Exception:
                pass
            try:
                api_client.delete_user(user_id)
            except Exception:
                pass


# ── API Key 管理测试 ──

class TestSystemApiKeyAPI:
    """/api/system/api-keys API Key 管理接口（System API Key 认证）"""

    def test_create_and_delete_api_key(self, api_client, _system_access):
        """创建并删除 API Key：自建用户 → 创建 Key → 验证 → 清理"""
        # 先创建测试用户（API Key 需要绑定用户）
        user_email = _generate_test_email()
        user_resp = api_client.create_user({
            "email": user_email,
            "name": "API Key Test User",
            "password": "TestPass12345678",
        })
        user_id = user_resp["id"]

        # 获取用户所属组织（API Key 需要绑定组织）
        orgs_resp = api_client.list_user_organizations(user_id, params={"page": 1, "pageSize": 5})
        if not orgs_resp["items"]:
            # 新用户可能没有组织，取系统第一个组织
            sys_orgs = api_client.list_organizations(params={"page": 1, "pageSize": 5})
            if not sys_orgs["items"]:
                pytest.skip("无可用组织，跳过 API Key 创建测试")
            org_id = sys_orgs["items"][0]["id"]
        else:
            org_id = orgs_resp["items"][0]["id"]

        try:
            # 创建 API Key
            key_resp = api_client.create_api_key({
                "userId": user_id,
                "organizationId": org_id,
                "role": "member",
                "name": "system-api-test-key",
            })
            api_client.validate_schema(key_resp, SYSTEM_CREATE_API_KEY_RESPONSE)
            key_id = key_resp["id"]
            assert key_resp["userId"] == user_id
            assert key_resp["organizationId"] == org_id
            assert "key" in key_resp  # 创建时返回明文 key

            # 删除 API Key
            del_resp = api_client.delete_api_key(key_id)
            api_client.validate_schema(del_resp, SYSTEM_DELETE_RESPONSE)
            assert del_resp.get("deleted") is True
        finally:
            try:
                api_client.delete_user(user_id)
            except Exception:
                pass

    def test_delete_nonexistent_api_key(self, api_client, _system_access):
        """删除不存在的 API Key：应返回 404"""
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            api_client.delete_api_key(f"nonexistent-key-{uuid.uuid4().hex[:8]}")
        assert exc_info.value.response.status_code == 404
