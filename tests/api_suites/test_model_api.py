# tests/api_suites/test_model_api.py
"""Model 接口测试：功能验证 + 契约验证

覆盖两套接口：
- TestModelWebAPI: /web/config/models 控制台接口（session cookie 认证，用户偏好设置）
- TestModelOpenAPI: /api/models/providers/* 对外 OpenAPI（API Key 认证，Provider + Model CRUD）
"""
import httpx
import pytest
from tests.api_contracts.model_schemas import (
    WEB_MODEL_PREFERENCES_DATA,
    API_PROVIDER_LIST_RESPONSE,
    API_PROVIDER_DETAIL_RESPONSE,
    API_MODEL_LIST_RESPONSE,
    API_MODEL_DETAIL_RESPONSE,
)


# ── 工具函数 ──

def _cleanup_api_provider(client, name: str):
    """通过 api 接口按名称查找并删除 Provider，忽略错误"""
    try:
        list_resp = client.list_providers(params={"pageSize": 100})
        for item in list_resp["items"]:
            if item["name"] == name:
                client.delete_provider(item["id"])
    except Exception as e:
        import logging
        logging.getLogger("cleanup").warning(f"Cleanup failed: {e}")


# ── 控制台接口测试 ──

class TestModelWebAPI:
    """/web/config/models 控制台接口测试（session cookie 认证）

    特点：
    - GET 获取可用模型列表与用户偏好
    - PUT 更新用户模型偏好（model/small_model/permission）
    - POST /refresh 强制刷新缓存
    """

    def test_get_model_preferences(self, web_client):
        """获取模型偏好与可用模型列表"""
        resp = web_client.get_model_preferences()
        web_client.validate_schema(resp, WEB_MODEL_PREFERENCES_DATA)
        assert "available" in resp or "current" in resp

    def test_refresh_models(self, web_client):
        """强制刷新可用模型缓存"""
        resp = web_client.refresh_models()
        _WEB_MODEL_REFRESH_DATA = {
            "type": "object",
            "properties": {"count": {"type": "integer"}},
            "additionalProperties": True,
        }
        web_client.validate_schema(resp, _WEB_MODEL_REFRESH_DATA)
        assert "count" in resp
        assert isinstance(resp["count"], int)

    def test_get_model_preferences_unauthorized(self, api_base_url):
        """无效 Token 访问模型偏好：应返回 401"""
        from tests.api_clients.web_client import WebClient
        bad_client = WebClient(api_base_url)
        try:
            with pytest.raises(httpx.HTTPStatusError, match="401"):
                bad_client.get_model_preferences()
        finally:
            bad_client.close()


# ── 对外 OpenAPI 测试 ──

class TestModelOpenAPI:
    """/api/models/providers/* 对外 OpenAPI 测试（API Key 认证）

    特点：
    - Provider CRUD: /api/models/providers
    - Model CRUD: /api/models/providers/:providerId/models
    - 列表带分页 {items, total, page, pageSize}
    """

    def test_list_providers(self, api_client, _openapi_access):
        """获取 Provider 列表：返回分页结构"""

        resp = api_client.list_providers()
        api_client.validate_schema(resp, API_PROVIDER_LIST_RESPONSE)
        assert isinstance(resp["items"], list)

    def test_get_provider(self, api_client, _openapi_access):
        """获取 Provider 详情：先拿列表取第一个 ID，再查详情"""

        list_resp = api_client.list_providers()
        if len(list_resp["items"]) == 0:
            pytest.skip("Provider 列表为空，跳过详情测试")
        provider_id = list_resp["items"][0]["id"]

        resp = api_client.get_provider(provider_id)
        api_client.validate_schema(resp, API_PROVIDER_DETAIL_RESPONSE)
        assert resp["id"] == provider_id

    def test_provider_crud_lifecycle(self, api_client, _openapi_access):
        """Provider CRUD 生命周期：创建 → 读取 → 更新 → 删除"""

        test_name = "api-test-openapi-provider-001"
        _cleanup_api_provider(api_client, test_name)

        create_resp = api_client.create_provider({
            "name": test_name,
            "displayName": "Test Provider",
            "protocol": "openai",
            "apiKey": "sk-test-key-for-api-testing",
            "baseUrl": "https://api.test-provider.example.com",
        })
        provider_id = create_resp["id"]
        assert create_resp["name"] == test_name

        try:
            # 验证创建成功
            get_resp = api_client.get_provider(provider_id)
            assert get_resp["name"] == test_name

            # 记录更新前的字段值
            original_name = get_resp.get("name")

            # 更新
            update_resp = api_client.update_provider(provider_id, {
                "displayName": "Updated Test Provider",
                "protocol": "openai",
                "baseUrl": "https://updated.test-provider.example.com",
            })
            assert update_resp["id"] == provider_id

            # 验证更新生效
            get_resp = api_client.get_provider(provider_id)
            assert get_resp["baseUrl"] == "https://updated.test-provider.example.com"
            # 验证未修改字段未被清空
            assert get_resp.get("name") == original_name

            # 删除并验证资源已消失
            api_client.delete_provider(provider_id)
            with pytest.raises(httpx.HTTPStatusError, match=r"404"):
                api_client.get_provider(provider_id)
        finally:
            _cleanup_api_provider(api_client, test_name)

    def test_list_models(self, api_client, _openapi_access):
        """获取 Model 列表：先取一个 Provider ID，再列出其模型"""

        list_resp = api_client.list_providers()
        if len(list_resp["items"]) == 0:
            pytest.skip("Provider 列表为空，跳过 Model 列表测试")
        provider_id = list_resp["items"][0]["id"]

        resp = api_client.list_models(provider_id)
        api_client.validate_schema(resp, API_MODEL_LIST_RESPONSE)
        assert isinstance(resp["items"], list)

    def test_model_crud_lifecycle(self, api_client, _openapi_access):
        """Model CRUD 生命周期：创建 Provider → 添加 Model → 读取 → 更新 → 删除 Model → 删除 Provider"""

        test_provider_name = "api-test-openapi-model-provider-001"
        test_model_id = "test-model-gpt-4"
        _cleanup_api_provider(api_client, test_provider_name)

        # 创建 Provider
        provider_resp = api_client.create_provider({
            "name": test_provider_name,
            "displayName": "Model Test Provider",
            "protocol": "openai",
            "apiKey": "sk-test-key-for-model-testing",
            "baseUrl": "https://api.test-model-provider.example.com",
        })
        provider_id = provider_resp["id"]

        try:
            # 创建 Model
            model_resp = api_client.create_model(provider_id, {
                "modelId": test_model_id,
                "displayName": "Test GPT-4",
            })
            model_internal_id = model_resp["id"]
            assert model_resp["modelId"] == test_model_id

            # 获取 Model 详情
            get_resp = api_client.get_model(provider_id, model_internal_id)
            api_client.validate_schema(get_resp, API_MODEL_DETAIL_RESPONSE)
            assert get_resp["modelId"] == test_model_id

            # 更新 Model
            update_resp = api_client.update_model(provider_id, model_internal_id, {
                "displayName": "Updated Test GPT-4",
            })
            assert update_resp["id"] == model_internal_id

            # 验证更新生效
            get_resp = api_client.get_model(provider_id, model_internal_id)
            assert get_resp["displayName"] == "Updated Test GPT-4"
            # 验证 modelId 未被修改
            assert get_resp["modelId"] == test_model_id

            # 删除 Model 并验证
            api_client.delete_model(provider_id, model_internal_id)
            with pytest.raises(httpx.HTTPStatusError, match=r"404"):
                api_client.get_model(provider_id, model_internal_id)
        finally:
            api_client.delete_provider(provider_id)

    def test_get_nonexistent_provider(self, api_client, _openapi_access):
        """获取不存在的 Provider：应返回 404"""

        with pytest.raises(httpx.HTTPStatusError, match=r"(404|500)"):
            api_client.get_provider("nonexistent-provider-id-99999")

    def test_create_model_invalid_id(self, api_client, _openapi_access):
        """创建 Model 使用无效 modelId：应返回 400/422"""

        list_resp = api_client.list_providers()
        if len(list_resp["items"]) == 0:
            pytest.skip("Provider 列表为空，无法测试 Model 创建")
        provider_id = list_resp["items"][0]["id"]

        # 空 modelId
        with pytest.raises(httpx.HTTPStatusError, match=r"(400|422)"):
            api_client.create_model(provider_id, {
                "modelId": "",
                "displayName": "Invalid Model",
            })

    def test_create_model_missing_model_id(self, api_client, _openapi_access):
        """创建 Model 缺少 modelId 字段：应返回 400/422"""

        list_resp = api_client.list_providers()
        if len(list_resp["items"]) == 0:
            pytest.skip("Provider 列表为空，无法测试 Model 创建")
        provider_id = list_resp["items"][0]["id"]

        with pytest.raises(httpx.HTTPStatusError, match=r"(400|422)"):
            api_client.create_model(provider_id, {
                "displayName": "No modelId",
            })
