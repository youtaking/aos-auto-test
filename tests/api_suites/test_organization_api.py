# tests/api_suites/test_organization_api.py
"""Organization 接口测试：功能验证 + 契约验证

覆盖控制台接口：
- TestOrganizationWebAPI: /web/organizations（session cookie 认证，RESTful /:id 风格）

注：组织创建/删除是管理员操作，测试中以只读验证为主，写操作用 try/finally 清理。
"""
import uuid

import httpx
import jsonschema
import pytest
from tests.api_contracts.organization_schemas import (
    ORGANIZATION_CREATE_REQUEST,
    ORGANIZATION_INFO,
    ORGANIZATION_MEMBER,
    ORGANIZATION_UPDATE_REQUEST,
    WEB_VALIDATION_ERROR_RESPONSE,
)


# ── 工具函数 ──

def _assert_web_validation_error(exc_info, expected_status: int = 400, message_part: str | None = None):
    """断言宿主 schema 校验错误：HTTP 400 + {error:{type:VALIDATION_ERROR,message}} 信封"""
    response = exc_info.value.response
    assert response.status_code == expected_status, \
        f"预期 HTTP {expected_status}，实际 {response.status_code}: {response.text[:300]}"
    body = response.json()
    error = body["error"]
    assert error.get("type") == "VALIDATION_ERROR", \
        f"预期 VALIDATION_ERROR，实际 {error!r}"
    assert isinstance(error.get("message"), str) and error["message"], \
        "校验错误缺少 error.message"
    if message_part is not None:
        assert message_part in error["message"], \
            f"错误信息未指向字段 {message_part!r}: {error['message']!r}"
    # 错误信封结构必须符合契约
    jsonschema.validate(instance=body, schema=WEB_VALIDATION_ERROR_RESPONSE)
    return body


def _create_temp_organization(web_client) -> str:
    """创建测试专用组织并返回 id；调用方必须在 finally 中删除，禁止碰既有组织。"""
    slug = f"api-test-org-tmp-{uuid.uuid4().hex[:8]}"
    created = web_client.create_organization({"name": f"tmp-{slug}", "slug": slug})
    return created["id"]


def _delete_organization_quietly(web_client, org_id: str) -> None:
    try:
        web_client.delete_organization(org_id)
    except Exception as e:
        import logging
        logging.getLogger("cleanup").warning(f"Cleanup failed: {e}")


# ── 控制台接口测试 ──

class TestOrganizationWebAPI:
    """/web/organizations 控制台接口测试（session cookie 认证，RESTful /:id 风格）

    特点：
    - 用 /:id 路径参数定位资源
    - 响应统一包装为 {success, data} 格式
    - 组织 CRUD + 成员管理
    """

    @pytest.mark.p1
    def test_list_organizations(self, web_client):
        """获取组织列表：返回数组"""
        resp = web_client.list_organizations()
        assert isinstance(resp, list)
        if len(resp) > 0:
            web_client.validate_schema(resp[0], ORGANIZATION_INFO)

    @pytest.mark.p1
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

    @pytest.mark.p1
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

    @pytest.mark.p1
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

    @pytest.mark.xfail(reason="应用 Bug：查询不存在的组织返回 500 而非 404（源码 schema 声明 404 但路由未做存在性检查，已确认）", strict=True)
    @pytest.mark.p2
    def test_get_nonexistent_organization(self, web_client):
        """获取不存在的组织：应返回 404（当前返回 500，属应用 Bug）"""
        with pytest.raises(httpx.HTTPStatusError, match=r"404"):
            web_client.get_organization("nonexistent-org-id-99999")

    @pytest.mark.xfail(reason="应用 Bug：删除组织后回读返回 500 而非 404（源码 schema 声明 404 但路由未做存在性检查，已确认）", strict=True)
    @pytest.mark.p1
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
        except Exception as e:
            import logging
            logging.getLogger("cleanup").warning(f"Cleanup failed: {e}")

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

                # 删除并验证（应返回 404，当前返回 500，属应用 Bug）
                web_client.delete_organization(org_id)
                with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"404"):
                    web_client.get_organization(org_id)
            finally:
                try:
                    web_client.delete_organization(org_id)
                except Exception as e:
                    import logging
                    logging.getLogger("cleanup").warning(f"Cleanup failed: {e}")
        except (httpx.HTTPStatusError, RuntimeError, ValueError) as e:
            if "400" in str(e) or "403" in str(e) or "409" in str(e):
                pytest.skip(f"组织创建接口不可用: {e}")
            raise

    # ── 参数校验（2026-11 main：name/slug 禁止纯空白）──

    @pytest.mark.p1
    @pytest.mark.parametrize(
        ("body", "field"),
        [
            ({"name": "", "slug": "valid-slug"}, "name"),
            ({"name": " \t ", "slug": "valid-slug"}, "name"),
            ({"name": "valid-name", "slug": ""}, "slug"),
            ({"name": "valid-name", "slug": " \t "}, "slug"),
        ],
    )
    def test_create_organization_rejects_blank_fields(self, web_client, body, field):
        """创建组织：空白 name/slug 在进入存储前返回 400 VALIDATION_ERROR"""
        with pytest.raises(httpx.HTTPStatusError) as exc:
            web_client.create_organization(body)
        error = _assert_web_validation_error(exc, 400, field)
        assert field in error["error"]["message"]

    @pytest.mark.p1
    def test_create_organization_accepts_valid_fields(self, web_client):
        """创建组织：合法请求体符合契约并能创建成功后清理"""
        slug = f"api-test-org-valid-{uuid.uuid4().hex[:8]}"
        body = {"name": f"valid-{slug}", "slug": slug, "description": "contract-check"}
        web_client.validate_schema(body, ORGANIZATION_CREATE_REQUEST)
        org_id = None
        try:
            created = web_client.create_organization(body)
            web_client.validate_schema(created, ORGANIZATION_INFO)
            org_id = created["id"]
            assert created["slug"] == slug
        finally:
            if org_id:
                try:
                    web_client.delete_organization(org_id)
                except Exception as e:
                    import logging
                    logging.getLogger("cleanup").warning(f"Cleanup failed: {e}")

    @pytest.mark.p1
    @pytest.mark.parametrize(
        "body",
        [
            {"name": ""},
            {"name": " \t "},
            {"slug": ""},
            {"slug": " \t "},
            {"data": {"name": ""}},
            {"data": {"name": " \t "}},
            {"data": {"slug": ""}},
            {"data": {"slug": " \t "}},
        ],
    )
    def test_update_organization_rejects_blank_fields(self, web_client, body):
        """更新组织：顶层或 data 内的空白 name/slug 均返回 400（不写入自建组织）"""
        try:
            org_id = _create_temp_organization(web_client)
        except (httpx.HTTPStatusError, RuntimeError) as e:
            if "400" in str(e) or "403" in str(e) or "409" in str(e):
                pytest.skip(f"当前账号无法创建组织: {e}")
            raise
        try:
            with pytest.raises(httpx.HTTPStatusError) as exc:
                web_client.update_organization(org_id, body)
            _assert_web_validation_error(exc, 400, "name" if "name" in str(body) else "slug")
        finally:
            _delete_organization_quietly(web_client, org_id)

    @pytest.mark.p1
    @pytest.mark.parametrize(
        "body",
        [
            {"name": "新名称", "data": {}},
            {"slug": "new-slug", "data": {"metadata": {"description": "说明"}}},
            {"name": "新名称", "data": {"slug": "new-slug"}},
        ],
    )
    def test_update_organization_rejects_mixed_fields(self, web_client, body):
        """更新组织：顶层 name/slug 与透传 data 混用返回 400，错误指向 data"""
        try:
            org_id = _create_temp_organization(web_client)
        except (httpx.HTTPStatusError, RuntimeError) as e:
            if "400" in str(e) or "403" in str(e) or "409" in str(e):
                pytest.skip(f"当前账号无法创建组织: {e}")
            raise
        try:
            with pytest.raises(httpx.HTTPStatusError) as exc:
                web_client.update_organization(org_id, body)
            _assert_web_validation_error(exc, 400, "data")
        finally:
            _delete_organization_quietly(web_client, org_id)

    @pytest.mark.p1
    @pytest.mark.parametrize(
        "format_kind",
        ["name", "slug", "data_name_slug", "data_metadata"],
    )
    def test_update_organization_accepts_partial_formats(self, web_client, format_kind):
        """更新组织：合法的单格式部分更新被服务端接受，回读自建组织可见变更"""
        try:
            org_id = _create_temp_organization(web_client)
        except (httpx.HTTPStatusError, RuntimeError) as e:
            if "400" in str(e) or "403" in str(e) or "409" in str(e):
                pytest.skip(f"当前账号无法创建组织: {e}")
            raise
        suffix = uuid.uuid4().hex[:8]
        new_name = f"更新名称-{suffix}"
        new_slug = f"api-test-org-upd-{suffix}"
        body = {
            "name": {"name": new_name},
            "slug": {"slug": new_slug},
            "data_name_slug": {"data": {"name": new_name, "slug": new_slug}},
            "data_metadata": {"data": {"metadata": {"description": "说明"}}},
        }[format_kind]
        try:
            web_client.validate_schema(body, ORGANIZATION_UPDATE_REQUEST)
            updated = web_client.update_organization(org_id, body)
            assert updated["id"] == org_id
            detail = web_client.get_organization(org_id)
            if format_kind == "name":
                assert detail["name"] == new_name
            elif format_kind == "slug":
                assert detail["slug"] == new_slug
            elif format_kind == "data_name_slug":
                assert detail["name"] == new_name
                assert detail["slug"] == new_slug
            else:
                assert detail["metadata"]["description"] == "说明"
        finally:
            _delete_organization_quietly(web_client, org_id)

    @pytest.mark.p1
    def test_create_organization_duplicate_slug_conflict(self, web_client):
        """创建组织：Slug 冲突返回 409 + ORGANIZATION_SLUG_ALREADY_TAKEN"""
        slug = f"api-test-org-conflict-{uuid.uuid4().hex[:8]}"
        try:
            created = web_client.create_organization({"name": f"{slug}-name", "slug": slug})
        except (httpx.HTTPStatusError, RuntimeError) as e:
            if "400" in str(e) or "403" in str(e):
                pytest.skip(f"当前账号无法创建组织: {e}")
            raise
        org_id = created["id"]
        second_org_id = None
        try:
            try:
                second = web_client.create_organization({"name": f"{slug}-other", "slug": slug})
                second_org_id = second.get("id")
            except httpx.HTTPStatusError as exc:
                response = exc.response
                assert response.status_code == 409
                body = response.json()
                assert body["success"] is False
                assert body["error"]["code"] == "ORGANIZATION_SLUG_ALREADY_TAKEN"
                assert body["error"]["message"]
            else:
                pytest.fail("重复 slug 创建未返回 409")
        finally:
            if second_org_id:
                _delete_organization_quietly(web_client, second_org_id)
            _delete_organization_quietly(web_client, org_id)
