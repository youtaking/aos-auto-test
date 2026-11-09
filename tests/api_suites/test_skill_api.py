# tests/api_suites/test_skill_api.py
"""Skill 接口测试：功能验证 + 契约验证

覆盖两套接口：
- TestSkillWebAPI: /web/config/skills 控制台接口（session cookie 认证，RESTful /:name 风格）
- TestSkillOpenAPI: /api/v1/skills 对外 OpenAPI（API Key 认证，RESTful /:id 风格）
"""
import httpx
import pytest
from tests.api_contracts.skill_schemas import (
    WEB_SKILL_LIST_DATA,
    SKILL_LIST_ITEM,
    SKILL_DETAIL,
    API_SKILL_LIST_RESPONSE,
    API_SKILL_DETAIL_RESPONSE,
    API_DELETE_SKILL_RESPONSE,
)


# ── 工具函数 ──

def _cleanup_web_skill(client, name: str):
    """通过 web 接口按名称删除 Skill，忽略错误"""
    try:
        client.delete_skill(name)
    except Exception as e:
        import logging
        logging.getLogger("cleanup").warning(f"Cleanup failed: {e}")


def _cleanup_api_skill(client, name: str):
    """通过 api 接口按名称查找并删除 Skill，忽略错误"""
    try:
        list_resp = client.list_skills(params={"pageSize": 100})
        for item in list_resp["items"]:
            if item["name"] == name:
                client.delete_skill(item["id"])
    except Exception as e:
        import logging
        logging.getLogger("cleanup").warning(f"Cleanup failed: {e}")


# ── 控制台接口测试 ──

class TestSkillWebAPI:
    """/web/config/skills 控制台接口测试（session cookie 认证，RESTful /:name 风格）

    特点：
    - 用 /:name 路径参数定位资源
    - 响应统一包装为 {success, data} 格式
    - 创建 body 为 {name, data: {description, content}}
    - 列表返回 {skills: [...]}
    """

    @pytest.mark.p0
    def test_list_skills(self, web_client):
        """获取 Skill 列表：返回 skills 数组"""
        resp = web_client.list_skills()
        web_client.validate_schema(resp, WEB_SKILL_LIST_DATA)
        assert isinstance(resp["skills"], list)

    @pytest.mark.p0
    def test_get_skill(self, web_client):
        """获取单个 Skill 详情：先拿列表取第一个 name，再查详情"""
        list_data = web_client.list_skills()
        if len(list_data["skills"]) == 0:
            pytest.skip("Skill 列表为空，无法测试详情")
        skill_name = list_data["skills"][0]["name"]

        detail = web_client.get_skill(skill_name)
        web_client.validate_schema(detail, SKILL_DETAIL)
        assert detail["name"] == skill_name
        assert "content" in detail or "description" in detail

    @pytest.mark.p0
    def test_create_and_delete_skill(self, web_client):
        """创建并删除 Skill：写操作生命周期测试"""
        test_name = "api-test-web-skill-001"

        _cleanup_web_skill(web_client, test_name)

        create_resp = web_client.create_skill({
            "name": test_name,
            "data": {
                "description": "Web API 测试自动创建的 Skill",
                "content": "# Test Skill\nThis is a test skill.",
            },
        })
        # 创建/更新返回的是保存结果片段（无 content），详情才含正文
        web_client.validate_schema(create_resp, SKILL_LIST_ITEM)
        assert create_resp["name"] == test_name

        try:
            detail = web_client.get_skill(test_name)
            assert detail["name"] == test_name
            # 删除并验证资源已消失
            web_client.delete_skill(test_name)
            with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"404"):
                web_client.get_skill(test_name)
        finally:
            _cleanup_web_skill(web_client, test_name)

    @pytest.mark.p1
    def test_update_skill(self, web_client):
        """更新 Skill：创建 → 修改内容 → 验证 → 删除"""
        test_name = "api-test-web-skill-002"
        updated_desc = "updated by web api test"

        _cleanup_web_skill(web_client, test_name)

        web_client.create_skill({
            "name": test_name,
            "data": {
                "description": "original description",
                "content": "# Original",
            },
        })

        try:
            # 记录更新前的字段值
            original_detail = web_client.get_skill(test_name)
            original_name = original_detail.get("name")

            web_client.update_skill(test_name, {
                "description": updated_desc,
                "content": "# Updated Content",
            })

            detail = web_client.get_skill(test_name)
            web_client.validate_schema(detail, SKILL_DETAIL)
            assert detail["description"] == updated_desc
            # 验证未修改字段未被清空
            assert detail.get("name") == original_name
        finally:
            web_client.delete_skill(test_name)

    @pytest.mark.p2
    def test_get_nonexistent_skill(self, web_client):
        """获取不存在的 Skill：应抛出 404 异常"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"404"):
            web_client.get_skill("nonexistent-skill-name-99999")

    @pytest.mark.p2
    def test_delete_skill_idempotent(self, web_client):
        """Skill DELETE 幂等性：第二次删除返回 404"""
        test_name = "test-idempotent-delete-skill"
        _cleanup_web_skill(web_client, test_name)
        try:
            web_client.create_skill({
                "name": test_name,
                "data": {
                    "description": "Idempotent delete test",
                    "content": "# Test\nIdempotent.",
                },
            })
            web_client.delete_skill(test_name)
            with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"404"):
                web_client.delete_skill(test_name)
        finally:
            _cleanup_web_skill(web_client, test_name)


# ── Skill 下载接口测试 ──

class TestSkillDownloadAPI:
    """/skills/:name/download 技能下载接口（token 认证，返回二进制 zip）

    特点：
    - GET /skills/:name/download?token=xxx
    - 需要有效的下载 token（由 skill-download-token 服务签发）
    - 返回 application/zip 二进制流
    - 无效 token 返回 403
    - 不存在的 skill 返回 404
    """

    @pytest.mark.p2
    def test_download_skill_invalid_token(self, web_client):
        """无效 token 下载 Skill — 应返回 403"""
        list_data = web_client.list_skills()
        if len(list_data["skills"]) == 0:
            pytest.skip("Skill 列表为空，无法测试下载")
        skill_name = list_data["skills"][0]["name"]

        try:
            web_client.download_skill(skill_name, "invalid-token-99999")
            pytest.fail("无效 token 应抛出异常")
        except httpx.HTTPStatusError as e:
            assert e.response.status_code == 403, \
                f"无效 token 预期 403，实际: {e.response.status_code}"
        except RuntimeError as e:
            assert "403" in str(e), f"无效 token 预期 403，实际: {e}"

    @pytest.mark.p2
    def test_download_skill_empty_token(self, web_client):
        """空 token 下载 Skill — 应返回 400（Zod 校验 min(1)）或 403"""
        list_data = web_client.list_skills()
        if len(list_data["skills"]) == 0:
            pytest.skip("Skill 列表为空，无法测试下载")
        skill_name = list_data["skills"][0]["name"]

        try:
            web_client.download_skill(skill_name, "")
            pytest.fail("空 token 应抛出异常")
        except httpx.HTTPStatusError as e:
            assert e.response.status_code in (400, 403), \
                f"空 token 预期 400/403，实际: {e.response.status_code}"
        except RuntimeError as e:
            assert "400" in str(e) or "403" in str(e), f"空 token 预期 400/403，实际: {e}"

    @pytest.mark.p2
    def test_download_skill_missing_token(self, api_base_url):
        """缺少 token 参数下载 Skill — 应返回 400（Zod 校验）或 403"""
        import httpx as _httpx
        with _httpx.Client(base_url=api_base_url, timeout=30, verify=False) as client:
            resp = client.get("/skills/test-skill/download")
            assert resp.status_code in (400, 403), \
                f"缺少 token 预期 400/403，实际: {resp.status_code}"

    @pytest.mark.p2
    def test_download_nonexistent_skill(self, web_client):
        """下载不存在的 Skill — 应返回 403（token 校验先于 skill 存在性检查）"""
        try:
            web_client.download_skill("nonexistent-skill-99999", "some-token")
            pytest.fail("不存在的 skill 应抛出异常")
        except httpx.HTTPStatusError as e:
            # token 校验在 skill 查找之前，所以返回 403 而非 404
            assert e.response.status_code in (403, 404), \
                f"不存在的 skill 预期 403/404，实际: {e.response.status_code}"
        except RuntimeError as e:
            assert "403" in str(e) or "404" in str(e), \
                f"不存在的 skill 预期 403/404，实际: {e}"

    @pytest.mark.p2
    def test_download_skill_invalid_name(self, web_client):
        """非法 skill name 下载 — 路由层可能过滤路径，token 无效则 403"""
        try:
            web_client.download_skill("invalid..name", "bad-token")
            pytest.fail("非法 name 或无效 token 应抛出异常")
        except httpx.HTTPStatusError as e:
            # 非法 name 可能返回 400（name 校验）或 403（token 校验）或 404（not found）
            assert e.response.status_code in (400, 403, 404), \
                f"非法 name 预期 400/403/404，实际: {e.response.status_code}"
        except RuntimeError as e:
            assert any(code in str(e) for code in ("400", "403", "404")), \
                f"非法 name 预期 400/403/404，实际: {e}"


# ── 对外 OpenAPI 测试 ──

class TestSkillOpenAPI:
    """/api/v1/skills 对外 OpenAPI 测试（API Key 认证，RESTful /:id 风格）

    特点：
    - 用 ID 定位资源（/:id），更新用 PATCH
    - 列表带分页 {items, total, page, pageSize}
    - 响应为 {success, data} 信封，client 已解包为裸数据；删除返回 data: null
    - 创建/覆盖走 multipart/form-data：manifest（JSON 字符串）+ files（≥1）+ overwrite
    """

    @staticmethod
    def _payload(name: str, description: str, body: str = "# Test Skill") -> tuple[list, list]:
        """构造导入 Skill 的 manifest 与文件：manifest 与 files 顺序一一对应"""
        manifest = [{"skillName": name, "relativePath": "SKILL.md"}]
        content = f"---\nname: {name}\ndescription: {description}\n---\n\n{body}\n"
        files = [(f"{name}.md", content.encode("utf-8"))]
        return manifest, files

    @pytest.mark.p0
    def test_list_skills(self, api_client, _openapi_access):
        """获取 Skill 列表：返回分页结构"""

        resp = api_client.list_skills()
        api_client.validate_schema(resp, API_SKILL_LIST_RESPONSE)
        assert isinstance(resp["items"], list)

    @pytest.mark.p0
    def test_get_skill(self, api_client, _openapi_access):
        """获取单个 Skill 详情：先拿列表取第一个 ID，再查详情"""

        list_resp = api_client.list_skills()
        if len(list_resp["items"]) == 0:
            pytest.skip("Skill 列表为空，跳过详情测试")
        skill_id = list_resp["items"][0]["id"]

        resp = api_client.get_skill(skill_id)
        api_client.validate_schema(resp, API_SKILL_DETAIL_RESPONSE)
        assert resp["id"] == skill_id

    @pytest.mark.p0
    def test_create_and_delete_skill(self, api_client, _openapi_access):
        """创建并删除 Skill：multipart 导入 → 读取 → 删除 → 读取 404"""
        test_name = "api-test-openapi-skill-001"

        _cleanup_api_skill(api_client, test_name)

        manifest, files = self._payload(test_name, "created by openapi test")
        create_resp = api_client.create_skill(manifest, files)
        api_client.validate_schema(create_resp, API_SKILL_DETAIL_RESPONSE)
        skill_id = create_resp["id"]
        assert create_resp["name"] == test_name

        try:
            detail = api_client.get_skill(skill_id)
            assert detail["name"] == test_name
            assert "content" in detail

            del_resp = api_client.delete_skill(skill_id)
            api_client.validate_schema(del_resp, API_DELETE_SKILL_RESPONSE)

            with pytest.raises(httpx.HTTPStatusError) as caught:
                api_client.get_skill(skill_id)
            assert caught.value.response.status_code == 404
            body = caught.value.response.json()
            assert body["success"] is False
            assert body["error"]["code"] == "NOT_FOUND"
        finally:
            _cleanup_api_skill(api_client, test_name)

    @pytest.mark.p1
    def test_update_skill(self, api_client, _openapi_access):
        """更新 Skill：创建 → PATCH description → 验证生效且 name 不变 → 删除"""
        test_name = "api-test-openapi-skill-002"
        updated_desc = "updated by openapi test"

        _cleanup_api_skill(api_client, test_name)

        manifest, files = self._payload(test_name, "original description")
        create_resp = api_client.create_skill(manifest, files)
        skill_id = create_resp["id"]

        try:
            original = api_client.get_skill(skill_id)
            assert original["description"] == "original description"

            update_resp = api_client.update_skill(skill_id, {"description": updated_desc})
            api_client.validate_schema(update_resp, API_SKILL_DETAIL_RESPONSE)
            assert update_resp["description"] == updated_desc

            detail = api_client.get_skill(skill_id)
            assert detail["description"] == updated_desc
            # 验证未修改字段未被清空
            assert detail["name"] == original["name"]
        finally:
            _cleanup_api_skill(api_client, test_name)

    @pytest.mark.p2
    def test_get_nonexistent_skill(self, api_client, _openapi_access):
        """获取不存在的 Skill：返回 404 + NOT_FOUND"""

        with pytest.raises(httpx.HTTPStatusError) as caught:
            api_client.get_skill("nonexistent-skill-id-99999")
        assert caught.value.response.status_code == 404
        body = caught.value.response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "NOT_FOUND"

    @pytest.mark.p2
    def test_list_skills_pagination_page2(self, api_client, _openapi_access):
        """验证获取 Skill 第 2 页数据，不与第 1 页重复"""

        page1 = api_client.list_skills({"page": 1, "pageSize": 1})
        if page1["total"] <= 1:
            pytest.skip("Not enough skills for pagination")
        page2 = api_client.list_skills({"page": 2, "pageSize": 1})
        api_client.validate_schema(page2, API_SKILL_LIST_RESPONSE)
        assert page2["page"] == 2
        if page1["items"] and page2["items"]:
            assert page1["items"][0]["id"] != page2["items"][0]["id"]

    @pytest.mark.p1
    def test_create_skill_duplicate_name(self, api_client, _openapi_access):
        """重复导入同名 Skill 且未指定 overwrite：返回 409 ALREADY_EXISTS"""
        test_name = "api-test-openapi-skill-dup"
        manifest, files = self._payload(test_name, "duplicate test")

        _cleanup_api_skill(api_client, test_name)

        try:
            api_client.create_skill(manifest, files)
            with pytest.raises(httpx.HTTPStatusError) as caught:
                api_client.create_skill(manifest, files)
            assert caught.value.response.status_code == 409
            body = caught.value.response.json()
            assert body["success"] is False
            assert body["error"]["code"] == "ALREADY_EXISTS"
        finally:
            _cleanup_api_skill(api_client, test_name)

    @pytest.mark.p1
    def test_create_skill_with_overwrite(self, api_client, _openapi_access):
        """覆盖导入同名 Skill（overwrite=true）：成功且内容被替换"""
        test_name = "api-test-openapi-skill-overwrite"
        manifest, files = self._payload(test_name, "first version")
        manifest2, files2 = self._payload(test_name, "second version")

        _cleanup_api_skill(api_client, test_name)

        try:
            create_resp = api_client.create_skill(manifest, files)
            skill_id = create_resp["id"]

            overwrite_resp = api_client.create_skill(manifest2, files2, overwrite="true")
            api_client.validate_schema(overwrite_resp, API_SKILL_DETAIL_RESPONSE)
            assert overwrite_resp["name"] == test_name
            assert overwrite_resp["description"] == "second version"

            detail = api_client.get_skill(skill_id)
            assert detail["description"] == "second version"
        finally:
            _cleanup_api_skill(api_client, test_name)

    @pytest.mark.p2
    def test_create_skill_missing_manifest(self, api_client, _openapi_access):
        """导入 Skill 缺少 manifest：返回 400 VALIDATION_ERROR"""
        resp = api_client.client.post(
            "/api/v1/skills",
            files=[("files", ("SKILL.md", b"# Test", "application/octet-stream"))],
        )
        assert resp.status_code == 400, f"期望 400，实际 {resp.status_code}: {resp.text[:200]}"
        body = resp.json()
        assert body["success"] is False
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert "manifest" in body["error"]["message"]

    @pytest.mark.p2
    def test_create_skill_missing_files(self, api_client, _openapi_access):
        """导入 Skill 只有 manifest 没有文件：返回 400 VALIDATION_ERROR"""
        resp = api_client.client.post(
            "/api/v1/skills",
            data={"manifest": '[{"skillName": "api-test-skill-no-files", "relativePath": "SKILL.md"}]'},
        )
        assert resp.status_code == 400, f"期望 400，实际 {resp.status_code}: {resp.text[:200]}"
        body = resp.json()
        assert body["success"] is False
        assert body["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.p2
    def test_create_skill_invalid_manifest(self, api_client, _openapi_access):
        """导入 Skill 的 manifest 不是合法 JSON：返回 400 VALIDATION_ERROR"""
        resp = api_client.client.post(
            "/api/v1/skills",
            data={"manifest": "not-a-json"},
            files=[("files", ("SKILL.md", b"# Test", "application/octet-stream"))],
        )
        assert resp.status_code == 400, f"期望 400，实际 {resp.status_code}: {resp.text[:200]}"
        body = resp.json()
        assert body["success"] is False
        assert body["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.p2
    def test_update_skill_empty_body(self, api_client, _openapi_access):
        """PATCH 空 body：返回 400 VALIDATION_ERROR（schema 拒绝空更新）"""
        with pytest.raises(httpx.HTTPStatusError) as caught:
            api_client.update_skill("nonexistent-skill-id-99999", {})
        assert caught.value.response.status_code == 400
        body = caught.value.response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.p2
    def test_delete_skill_idempotent(self, api_client, _openapi_access):
        """DELETE 同一 Skill 两次：第二次返回 404 NOT_FOUND"""
        test_name = "api-test-openapi-skill-idempotent"
        manifest, files = self._payload(test_name, "idempotent delete test")

        _cleanup_api_skill(api_client, test_name)

        try:
            create_resp = api_client.create_skill(manifest, files)
            skill_id = create_resp["id"]
            api_client.delete_skill(skill_id)

            with pytest.raises(httpx.HTTPStatusError) as caught:
                api_client.delete_skill(skill_id)
            assert caught.value.response.status_code == 404
            body = caught.value.response.json()
            assert body["success"] is False
            assert body["error"]["code"] == "NOT_FOUND"
        finally:
            _cleanup_api_skill(api_client, test_name)


class TestSkillWebAPIExtra:
    """/web/config/skills 可见范围与下载接口"""

    @pytest.mark.p1
    def test_update_access_missing_public_readable(self, web_client):
        """更新可见范围缺少 publicReadable：应返回 400 VALIDATION_ERROR"""
        resp = web_client.client.patch("/web/config/skills/nonexistent-skill/access", json={})
        assert resp.status_code == 400, f"期望 400，实际 {resp.status_code}: {resp.text[:200]}"
        err = resp.json().get("error", {})
        assert err.get("code") == "VALIDATION_ERROR"
        assert "publicReadable" in err.get("message", "")

    @pytest.mark.p2
    def test_download_nonexistent_skill(self, web_client):
        """下载不存在的 Skill：应返回 404 NOT_FOUND"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"(404|NOT_FOUND)"):
            web_client.download_skill_file("nonexistent-skill-id-99999")

    @pytest.mark.p1
    def test_download_skill_package(self, web_client):
        """下载已有 Skill：返回非空 zip 字节流"""
        data = web_client.list_skills()
        if not data["skills"]:
            pytest.skip("Skill 列表为空，无法测试下载")
        skill_id = data["skills"][0]["id"]

        content = web_client.download_skill_file(skill_id)
        assert len(content) > 0
        assert content[:2] == b"PK", f"期望 zip 魔数 PK，实际 {content[:8]!r}"
