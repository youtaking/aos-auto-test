# tests/api_suites/test_skill_api.py
"""Skill 接口测试：功能验证 + 契约验证

覆盖两套接口：
- TestSkillWebAPI: /web/config/skills 控制台接口（session cookie 认证，RESTful /:name 风格）
- TestSkillOpenAPI: /api/skills 对外 OpenAPI（API Key 认证，RESTful /:id 风格）
"""
import httpx
import pytest
from tests.api_contracts.skill_schemas import (
    WEB_SKILL_LIST_DATA,
    SKILL_DETAIL,
    API_SKILL_LIST_RESPONSE,
    API_SKILL_DETAIL_RESPONSE,
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

    def test_list_skills(self, web_client):
        """获取 Skill 列表：返回 skills 数组"""
        resp = web_client.list_skills()
        web_client.validate_schema(resp, WEB_SKILL_LIST_DATA)
        assert isinstance(resp["skills"], list)

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
        web_client.validate_schema(create_resp, SKILL_DETAIL)
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

    def test_get_nonexistent_skill(self, web_client):
        """获取不存在的 Skill：应抛出 404 异常"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"404"):
            web_client.get_skill("nonexistent-skill-name-99999")

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

    def test_download_skill_missing_token(self, api_base_url):
        """缺少 token 参数下载 Skill — 应返回 400（Zod 校验）或 403"""
        import httpx as _httpx
        with _httpx.Client(base_url=api_base_url, timeout=30, verify=False) as client:
            resp = client.get("/skills/test-skill/download")
            assert resp.status_code in (400, 403), \
                f"缺少 token 预期 400/403，实际: {resp.status_code}"

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
    """/api/skills 对外 OpenAPI 测试（API Key 认证，RESTful /:id 风格）

    特点：
    - 用 ID 定位资源（/:id）
    - 列表带分页 {items, total, page, pageSize}
    - 响应为裸数据，无 {success, data} 包装
    - 创建使用 multipart/form-data（此处仅测试 list/get/delete）
    """

    def test_list_skills(self, api_client, _openapi_access):
        """获取 Skill 列表：返回分页结构"""

        resp = api_client.list_skills()
        api_client.validate_schema(resp, API_SKILL_LIST_RESPONSE)
        assert isinstance(resp["items"], list)

    def test_get_skill(self, api_client, _openapi_access):
        """获取单个 Skill 详情：先拿列表取第一个 ID，再查详情"""

        list_resp = api_client.list_skills()
        if len(list_resp["items"]) == 0:
            pytest.skip("Skill 列表为空，跳过详情测试")
        skill_id = list_resp["items"][0]["id"]

        resp = api_client.get_skill(skill_id)
        api_client.validate_schema(resp, API_SKILL_DETAIL_RESPONSE)
        assert resp["id"] == skill_id

    @pytest.mark.xfail(reason="应用 Bug：不存在 Skill 返回 500 而非 404（源码头 404，已确认）", strict=True)
    def test_get_nonexistent_skill(self, api_client, _openapi_access):
        """获取不存在的 Skill：契约应返回 404（当前 500，应用 Bug）"""

        with pytest.raises(httpx.HTTPStatusError, match=r"404"):
            api_client.get_skill("nonexistent-skill-id-99999")

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
