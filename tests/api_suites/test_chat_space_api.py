# tests/api_suites/test_chat_space_api.py
"""Chat Spaces（会话分组）接口测试

覆盖 /web/chat-spaces（session cookie 认证，按 instanceUid 作用域）：
- 只读与参数校验、不存在资源、幂等摘除
- 该模块没有删除分组的端点，因此不创建任何分组，避免遗留数据
"""
import httpx
import pytest


def _get_instance_uid(web_client) -> str | None:
    """取环境下的实例 UID；分组以持久实例为作用域。"""
    envs = web_client.list_environments()
    items = envs if isinstance(envs, list) else envs.get("items", [])
    for env in items:
        result = web_client.list_environment_instances(env["id"])
        instances = result if isinstance(result, list) else result.get("instances", result.get("items", []))
        if instances:
            return instances[0].get("instanceUid") or instances[0].get("id")
    return None


class TestChatSpaceWebAPI:
    """/web/chat-spaces 控制台接口测试"""

    @pytest.mark.p0
    def test_list_chat_spaces(self, web_client):
        """列出实例下的会话分组：spaces 为数组，元素字段齐全"""
        instance_uid = _get_instance_uid(web_client)
        if not instance_uid:
            pytest.skip("环境无实例，无法测试会话分组")

        data = web_client.list_chat_spaces(instance_uid)
        assert isinstance(data, dict), f"期望对象响应，实际 {type(data)}"
        assert isinstance(data.get("spaces"), list)
        for space in data["spaces"]:
            assert isinstance(space.get("id"), str)
            assert isinstance(space.get("name"), str)
            assert isinstance(space.get("sessionIds"), list)
            assert space.get("instanceUid") == instance_uid

    @pytest.mark.p1
    def test_list_chat_spaces_invalid_instance(self, web_client):
        """不存在的实例：应返回 404 not_found"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"(404|not_found)"):
            web_client.list_chat_spaces("nonexistent-instance-uid-99999")

    @pytest.mark.p0
    def test_create_chat_space_missing_instance(self, web_client):
        """创建分组缺少 instanceUid：应返回 400 VALIDATION_ERROR（不落库）"""
        resp = web_client.client.post("/web/chat-spaces", json={"name": "api-test-space"})
        assert resp.status_code == 400, f"期望 400，实际 {resp.status_code}: {resp.text[:200]}"
        err = resp.json().get("error", {})
        assert err.get("type") == "VALIDATION_ERROR"
        assert "instanceUid" in err.get("message", "")

    @pytest.mark.p1
    def test_create_chat_space_empty_name(self, web_client):
        """创建分组名称空串：应返回 400 invalid_name（不落库）"""
        instance_uid = _get_instance_uid(web_client)
        if not instance_uid:
            pytest.skip("环境无实例，无法测试会话分组")

        resp = web_client.client.post(
            "/web/chat-spaces", json={"instanceUid": instance_uid, "name": ""}
        )
        assert resp.status_code == 400, f"期望 400，实际 {resp.status_code}: {resp.text[:200]}"
        err = resp.json().get("error", {})
        assert err.get("code") == "invalid_name"
        assert "1-100" in err.get("message", "")

    @pytest.mark.p2
    def test_create_chat_space_name_too_long(self, web_client):
        """创建分组名称超 100 字符：应返回 400 invalid_name（不落库）"""
        instance_uid = _get_instance_uid(web_client)
        if not instance_uid:
            pytest.skip("环境无实例，无法测试会话分组")

        resp = web_client.client.post(
            "/web/chat-spaces", json={"instanceUid": instance_uid, "name": "x" * 101}
        )
        assert resp.status_code == 400, f"期望 400，实际 {resp.status_code}: {resp.text[:200]}"
        assert resp.json().get("error", {}).get("code") == "invalid_name"

    @pytest.mark.p1
    def test_rename_nonexistent_space(self, web_client):
        """重命名不存在的分组：应返回 404 not_found"""
        instance_uid = _get_instance_uid(web_client)
        if not instance_uid:
            pytest.skip("环境无实例，无法测试会话分组")

        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"(404|not_found)"):
            web_client.rename_chat_space(
                "nonexistent-space-id-99999", instance_uid, "renamed-by-api-test"
            )

    @pytest.mark.p1
    def test_assign_session_to_nonexistent_space(self, web_client):
        """把会话移入不存在的分组：应返回 404 not_found"""
        instance_uid = _get_instance_uid(web_client)
        if not instance_uid:
            pytest.skip("环境无实例，无法测试会话分组")

        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"(404|not_found)"):
            web_client.assign_chat_session(
                "nonexistent-space-id-99999", "nonexistent-session-id-99999", instance_uid
            )

    @pytest.mark.p1
    def test_remove_session_not_in_any_space_is_idempotent(self, web_client):
        """摘除未归属任何分组的会话：幂等成功，space 为 null"""
        instance_uid = _get_instance_uid(web_client)
        if not instance_uid:
            pytest.skip("环境无实例，无法测试会话分组")

        data = web_client.remove_chat_session("nonexistent-session-id-99999", instance_uid)
        assert data == {"space": None}
