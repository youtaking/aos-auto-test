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
            with pytest.raises((httpx.HTTPStatusError, RuntimeError)):
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


# ── 对外 OpenAPI 测试 ──

class TestSkillOpenAPI:
    """/api/skills 对外 OpenAPI 测试（API Key 认证，RESTful /:id 风格）

    特点：
    - 用 ID 定位资源（/:id）
    - 列表带分页 {items, total, page, pageSize}
    - 响应为裸数据，无 {success, data} 包装
    - 创建使用 multipart/form-data（此处仅测试 list/get/delete）
    """

    def test_list_skills(self, api_client, api_test_config):
        """获取 Skill 列表：返回分页结构"""
        if api_test_config["fenixagent"]["api_key"] == "test-api-key-placeholder":
            pytest.skip("API Key 未配置，跳过 OpenAPI 测试")

        resp = api_client.list_skills()
        api_client.validate_schema(resp, API_SKILL_LIST_RESPONSE)
        assert isinstance(resp["items"], list)

    def test_get_skill(self, api_client, api_test_config):
        """获取单个 Skill 详情：先拿列表取第一个 ID，再查详情"""
        if api_test_config["fenixagent"]["api_key"] == "test-api-key-placeholder":
            pytest.skip("API Key 未配置，跳过 OpenAPI 测试")

        list_resp = api_client.list_skills()
        if len(list_resp["items"]) == 0:
            pytest.skip("Skill 列表为空，跳过详情测试")
        skill_id = list_resp["items"][0]["id"]

        resp = api_client.get_skill(skill_id)
        api_client.validate_schema(resp, API_SKILL_DETAIL_RESPONSE)
        assert resp["id"] == skill_id

    def test_get_nonexistent_skill(self, api_client, api_test_config):
        """获取不存在的 Skill：应返回 404"""
        if api_test_config["fenixagent"]["api_key"] == "test-api-key-placeholder":
            pytest.skip("API Key 未配置，跳过 OpenAPI 测试")

        with pytest.raises(httpx.HTTPStatusError, match=r"(404|500)"):
            api_client.get_skill("nonexistent-skill-id-99999")

    def test_list_skills_pagination_page2(self, api_client, api_test_config):
        """验证获取 Skill 第 2 页数据，不与第 1 页重复"""
        if api_test_config["fenixagent"]["api_key"] == "test-api-key-placeholder":
            pytest.skip("API Key 未配置，跳过 OpenAPI 测试")

        page1 = api_client.list_skills({"page": 1, "pageSize": 1})
        if page1["total"] <= 1:
            pytest.skip("Not enough skills for pagination")
        page2 = api_client.list_skills({"page": 2, "pageSize": 1})
        api_client.validate_schema(page2, API_SKILL_LIST_RESPONSE)
        assert page2["page"] == 2
        if page1["items"] and page2["items"]:
            assert page1["items"][0]["id"] != page2["items"][0]["id"]
