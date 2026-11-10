# tests/api_suites/test_api_key_api.py
"""API Key 接口测试：功能验证 + 契约验证

覆盖控制台接口：
- TestApiKeyWebAPI: /web/api-keys（session cookie 认证，RESTful /:id 风格）
"""
import time
import uuid

import httpx
import jsonschema
import pytest
from tests.api_contracts.api_key_schemas import (
    API_KEY_CREATE_REQUEST,
    API_KEY_ITEM,
    WEB_ERROR_RESPONSE,
)

# unwrapped schemas (data portion after _unwrap)
_WEB_API_KEY_LIST_DATA = {"type": "array", "items": API_KEY_ITEM}
_WEB_API_KEY_CREATE_DATA = {
    "type": "object",
    "properties": {"id": {"type": "string"}, "name": {"type": "string"}, "key": {"type": "string"}},
    "additionalProperties": True,
}


# ── 工具函数 ──

def _cleanup_api_key(client, name: str):
    """按名称查找并删除 API Key，忽略错误"""
    try:
        keys = client.list_api_keys()
        for key in keys:
            if key.get("name") == name:
                client.delete_api_key(key["id"])
    except Exception as e:
        import logging
        logging.getLogger("cleanup").warning(f"Cleanup failed: {e}")


def _assert_validation_error(exc_info):
    """断言 400 + {success:false, error:{code:VALIDATION_ERROR, message}}"""
    response = exc_info.value.response
    assert response.status_code == 400, \
        f"预期 HTTP 400，实际 {response.status_code}: {response.text[:300]}"
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR", \
        f"预期 VALIDATION_ERROR，实际 {body['error'].get('code')!r}: {body['error']}"
    assert "expiresAt" in body["error"]["message"], \
        f"错误信息未指向 expiresAt: {body['error']['message']!r}"
    jsonschema.validate(instance=body, schema=WEB_ERROR_RESPONSE)
    return body


# ── 控制台接口测试 ──

class TestApiKeyWebAPI:
    """/web/api-keys 控制台接口测试（session cookie 认证，RESTful /:id 风格）

    特点：
    - 用 /:id 路径参数定位资源
    - 响应统一包装为 {success, data} 格式
    - POST 创建返回含明文 key 的完整信息
    """

    @pytest.mark.p1
    def test_list_api_keys(self, web_client):
        """获取 API Key 列表：返回数组"""
        resp = web_client.list_api_keys()
        web_client.validate_schema(resp, _WEB_API_KEY_LIST_DATA)
        assert isinstance(resp, list)

    @pytest.mark.p1
    def test_create_and_delete_api_key(self, web_client):
        """创建并删除 API Key：写操作生命周期测试"""
        test_name = "api-test-web-apikey-001"
        _cleanup_api_key(web_client, test_name)

        create_resp = web_client.create_api_key({"name": test_name})
        web_client.validate_schema(create_resp, _WEB_API_KEY_CREATE_DATA)
        assert create_resp.get("name") == test_name or "id" in create_resp
        key_id = create_resp["id"]

        try:
            # 验证创建成功：列表中能找到
            keys = web_client.list_api_keys()
            found = any(k["id"] == key_id for k in keys)
            assert found, f"Created API key {key_id} not found in list"
            # 删除并验证资源已消失
            web_client.delete_api_key(key_id)
            keys_after = web_client.list_api_keys()
            found_after = any(k["id"] == key_id for k in keys_after)
            assert not found_after, f"Deleted API key {key_id} still in list"
        finally:
            _cleanup_api_key(web_client, test_name)


    @pytest.mark.xfail(reason="应用 Bug：删除不存在的 API Key 返回 500 而非 404（源码路由未做存在性检查，直接调用上游删除，已确认）", strict=True)
    @pytest.mark.p2
    def test_delete_nonexistent_api_key(self, web_client):
        """删除不存在的 API Key：应返回 404（当前返回 500，属应用 Bug）"""
        with pytest.raises(httpx.HTTPStatusError, match=r"404"):
            web_client.delete_api_key("nonexistent-api-key-id-99999")

    @pytest.mark.xfail(reason="应用 Bug：二次删除已删除的 API Key 返回 500 而非 404（源码路由未做存在性检查，已确认）", strict=True)
    @pytest.mark.p2
    def test_delete_api_key_idempotent(self, web_client):
        """API Key DELETE 幂等性：第二次删除应抛出异常"""
        test_name = "test-idempotent-delete-apikey"
        _cleanup_api_key(web_client, test_name)
        try:
            create_resp = web_client.create_api_key({"name": test_name})
            key_id = create_resp["id"]
            web_client.delete_api_key(key_id)
            # 第二次删除应返回 404（当前返回 500，属应用 Bug）
            with pytest.raises(httpx.HTTPStatusError, match=r"404"):
                web_client.delete_api_key(key_id)
        finally:
            _cleanup_api_key(web_client, test_name)

    # ── 过期时间校验（2026-11 main：必须晚于当前时间的合法时间）──

    @pytest.mark.p1
    @pytest.mark.parametrize(
        "expires_at",
        [
            "2020-01-01T00:00:00.000Z",
            0,
            "",
            "not-a-date",
        ],
    )
    def test_create_api_key_rejects_invalid_expires_at(self, web_client, expires_at):
        """创建 API Key：已过期、时间戳 0、空串与非法日期均返回 400 VALIDATION_ERROR"""
        body = {"name": f"api-test-exp-invalid-{uuid.uuid4().hex[:8]}", "expiresAt": expires_at}
        web_client.validate_schema(body, API_KEY_CREATE_REQUEST)
        with pytest.raises(httpx.HTTPStatusError) as exc:
            web_client.create_api_key(body)
        _assert_validation_error(exc)

    @pytest.mark.p1
    def test_create_api_key_accepts_future_expires_at(self, web_client):
        """创建 API Key：未来时间合法，创建成功后按名称清理"""
        test_name = f"api-test-web-apikey-exp-{uuid.uuid4().hex[:8]}"
        _cleanup_api_key(web_client, test_name)
        body = {"name": test_name, "expiresAt": int((time.time() + 86400) * 1000)}
        web_client.validate_schema(body, API_KEY_CREATE_REQUEST)
        try:
            created = web_client.create_api_key(body)
            web_client.validate_schema(created, _WEB_API_KEY_CREATE_DATA)
            assert created["name"] == test_name
            # 未来时间被接受：key 真实创建且可在列表中读回
            keys = web_client.list_api_keys()
            assert any(k["id"] == created["id"] and k["name"] == test_name for k in keys)
        finally:
            _cleanup_api_key(web_client, test_name)

    @pytest.mark.p2
    def test_create_api_key_without_expires_at(self, web_client):
        """创建 API Key：省略 expiresAt 时创建为无过期时间"""
        test_name = f"api-test-web-apikey-noexp-{uuid.uuid4().hex[:8]}"
        _cleanup_api_key(web_client, test_name)
        body = {"name": test_name}
        web_client.validate_schema(body, API_KEY_CREATE_REQUEST)
        try:
            created = web_client.create_api_key(body)
            assert created["name"] == test_name
            assert created.get("expiresAt") is None
        finally:
            _cleanup_api_key(web_client, test_name)
