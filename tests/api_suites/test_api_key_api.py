# tests/api_suites/test_api_key_api.py
"""API Key 接口测试：功能验证 + 契约验证

覆盖控制台接口：
- TestApiKeyWebAPI: /web/api-keys（session cookie 认证，RESTful /:id 风格）
"""
import httpx
import pytest
from tests.api_contracts.api_key_schemas import (
    API_KEY_ITEM,
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


# ── 控制台接口测试 ──

class TestApiKeyWebAPI:
    """/web/api-keys 控制台接口测试（session cookie 认证，RESTful /:id 风格）

    特点：
    - 用 /:id 路径参数定位资源
    - 响应统一包装为 {success, data} 格式
    - POST 创建返回含明文 key 的完整信息
    """

    def test_list_api_keys(self, web_client):
        """获取 API Key 列表：返回数组"""
        resp = web_client.list_api_keys()
        web_client.validate_schema(resp, _WEB_API_KEY_LIST_DATA)
        assert isinstance(resp, list)

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


    def test_delete_nonexistent_api_key(self, web_client):
        """删除不存在的 API Key：应抛出异常"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError, ValueError)):
            web_client.delete_api_key("nonexistent-api-key-id-99999")

    def test_delete_api_key_idempotent(self, web_client):
        """API Key DELETE 幂等性：第二次删除应抛出异常"""
        test_name = "test-idempotent-delete-apikey"
        _cleanup_api_key(web_client, test_name)
        try:
            create_resp = web_client.create_api_key({"name": test_name})
            key_id = create_resp["id"]
            web_client.delete_api_key(key_id)
            # 第二次删除应抛出异常（404/400/ValueError）
            with pytest.raises((httpx.HTTPStatusError, RuntimeError, ValueError)):
                web_client.delete_api_key(key_id)
        finally:
            _cleanup_api_key(web_client, test_name)
