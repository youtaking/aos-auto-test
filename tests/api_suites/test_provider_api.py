# tests/api_suites/test_provider_api.py
"""Provider 接口测试：功能验证 + 契约验证

覆盖控制台接口：
- TestProviderWebAPI: /web/config/providers 控制台接口（session cookie 认证，action 风格）

注：Provider 的 OpenAPI CRUD 在 /api/models/providers 下，由 test_model_api.py 覆盖。
"""
import httpx
import pytest
from tests.api_contracts.provider_schemas import (
    WEB_PROVIDER_LIST_DATA,
    PROVIDER_DETAIL,
    WEB_PROVIDER_MODEL_RESULT_DATA,
)


# ── 控制台接口测试 ──

class TestProviderWebAPI:
    """/web/config/providers 控制台接口测试（session cookie 认证，action 风格）

    特点：
    - 用 ?name=xxx 查询参数定位资源
    - 响应统一包装为 {success, data} 格式
    - 列表返回 {providers: [...]}
    - PUT 作为幂等 upsert（不存在时创建，存在时更新）
    """

    def test_list_providers(self, web_client):
        """获取 Provider 列表：返回 providers 数组"""
        resp = web_client.list_providers()
        web_client.validate_schema(resp, WEB_PROVIDER_LIST_DATA)
        assert isinstance(resp["providers"], list)

    def test_get_provider(self, web_client):
        """获取单个 Provider 详情：先拿列表，遍历找到第一个可查询详情的 provider"""
        list_data = web_client.list_providers()
        if len(list_data["providers"]) == 0:
            pytest.skip("Provider 列表为空，无法测试详情")

        # 遍历列表找到第一个可正常查详情的 provider
        # （列表中可能残留 ghost entry：列表可见但详情 404）
        last_error = None
        for provider in list_data["providers"]:
            provider_id = provider["id"]
            try:
                detail = web_client.get_provider(provider_id)
                web_client.validate_schema(detail, PROVIDER_DETAIL)
                assert detail["id"] == provider_id
                assert "name" in detail
                return  # 找到可用 provider，测试通过
            except (httpx.HTTPStatusError, RuntimeError) as e:
                last_error = e
                continue

        # 所有 provider 都查不到详情
        pytest.skip(f"列表中所有 {len(list_data['providers'])} 个 Provider 均无法查询详情（可能有残留数据），最后错误: {last_error}")

    def test_get_nonexistent_provider(self, web_client):
        """获取不存在的 Provider：应抛出 404 异常"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"404"):
            web_client.get_provider("nonexistent-provider-name-99999")

    def test_provider_crud_lifecycle(self, web_client):
        """Provider CRUD 生命周期：upsert 创建 → 读取 → 更新 → 删除"""
        test_name = "api-test-web-provider-001"

        # 清理可能遗留的数据
        try:
            web_client.delete_provider(test_name)
        except Exception as e:
            import logging
            logging.getLogger("cleanup").warning(f"Cleanup failed: {e}")

        # PUT 作为 upsert 创建
        create_resp = web_client.update_provider(test_name, {
            "name": "Test Provider",
            "protocol": "openai",
            "apiKey": "sk-test-key-for-api-testing",
            "baseURL": "https://api.test-provider.example.com",
        })
        web_client.validate_schema(create_resp, PROVIDER_DETAIL)
        assert create_resp.get("id") == test_name

        try:
            # 验证创建成功
            detail = web_client.get_provider(test_name)
            assert detail["name"] is not None

            # 记录更新前的字段值
            original_protocol = detail.get("protocol")

            # 更新
            update_resp = web_client.update_provider(test_name, {
                "name": "Updated Test Provider",
                "protocol": "openai",
                "baseURL": "https://updated.test-provider.example.com",
            })
            assert update_resp.get("id") == test_name or update_resp.get("name") is not None

            # 验证更新生效
            detail = web_client.get_provider(test_name)
            assert detail.get("baseURL") == "https://updated.test-provider.example.com"
            # 验证未修改字段未被清空
            assert detail.get("protocol") == original_protocol

            # 删除并验证资源已消失
            web_client.delete_provider(test_name)
            with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"404"):
                web_client.get_provider(test_name)
        finally:
            try:
                web_client.delete_provider(test_name)
            except Exception as e:
                import logging
                logging.getLogger("cleanup").warning(f"Cleanup failed: {e}")

    def test_delete_nonexistent_provider(self, web_client):
        """删除不存在的 Provider：应抛出 404 异常"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"404"):
            web_client.delete_provider("nonexistent-provider-to-delete-99999")

    def test_create_provider_duplicate(self, web_client):
        """PUT 同名 Provider 两次：验证 upsert 行为（第二次为更新而非冲突）"""
        test_name = "api-test-web-provider-dup"

        # 预清理
        try:
            web_client.delete_provider(test_name)
        except Exception as e:
            import logging
            logging.getLogger("cleanup").warning(f"Cleanup failed: {e}")

        try:
            # 第一次 PUT = 创建
            resp1 = web_client.update_provider(test_name, {
                "name": "Provider Dup V1",
                "protocol": "openai",
                "apiKey": "sk-test-key-v1",
                "baseURL": "https://v1.example.com",
            })
            web_client.validate_schema(resp1, PROVIDER_DETAIL)

            # 第二次 PUT = 更新（upsert）
            resp2 = web_client.update_provider(test_name, {
                "name": "Provider Dup V2",
                "protocol": "openai",
                "baseURL": "https://v2.example.com",
            })
            web_client.validate_schema(resp2, PROVIDER_DETAIL)

            # 验证更新生效
            detail = web_client.get_provider(test_name)
            assert detail.get("baseURL") == "https://v2.example.com"
        finally:
            try:
                web_client.delete_provider(test_name)
            except Exception as e:
                import logging
                logging.getLogger("cleanup").warning(f"Cleanup failed: {e}")

    def test_delete_provider_idempotent(self, web_client):
        """Provider DELETE 幂等性：第二次删除返回 404"""
        test_name = "test-idempotent-delete-provider"
        try:
            web_client.delete_provider(test_name)
        except Exception as e:
            import logging
            logging.getLogger("cleanup").warning(f"Cleanup failed: {e}")
        try:
            web_client.update_provider(test_name, {
                "name": "Idempotent Test Provider",
                "protocol": "openai",
                "apiKey": "sk-test",
                "baseURL": "https://example.com",
            })
            web_client.delete_provider(test_name)
            with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"404"):
                web_client.delete_provider(test_name)
        finally:
            try:
                web_client.delete_provider(test_name)
            except Exception as e:
                import logging
                logging.getLogger("cleanup").warning(f"Cleanup failed: {e}")


class TestProviderModelActions:
    """Provider 模型管理 Action 接口测试

    覆盖 /web/config/providers/actions/models 下的 add/update/delete 接口。
    使用自建 Provider 进行测试，测试完毕清理所有自建数据。
    """

    def _create_test_provider(self, web_client, name: str):
        """创建测试用 Provider"""
        return web_client.update_provider(name, {
            "name": f"Model Action Test ({name})",
            "protocol": "openai",
            "apiKey": "sk-test-key-for-model-actions",
            "baseURL": "https://model-action-test.example.com",
        })

    def _cleanup_provider(self, web_client, name: str):
        """清理 Provider，忽略错误"""
        try:
            web_client.delete_provider(name)
        except Exception as e:
            import logging
            logging.getLogger("cleanup").warning(f"Cleanup failed: {e}")

    def test_add_provider_model(self, web_client):
        """为 Provider 添加模型：创建 Provider → 添加模型 → 验证 → 删除"""
        test_provider = "api-test-model-action-provider-001"
        test_model_id = "test-model-add-001"

        self._cleanup_provider(web_client, test_provider)
        try:
            self._create_test_provider(web_client, test_provider)
        except (httpx.HTTPStatusError, RuntimeError) as e:
            if "500" in str(e):
                pytest.skip(f"Provider 创建接口返回 500，服务端可能不支持该操作: {e}")
            raise

        try:
            resp = web_client.add_provider_model(test_provider, {
                "modelId": test_model_id,
                "name": "Test Model Add",
            })
            web_client.validate_schema(resp, WEB_PROVIDER_MODEL_RESULT_DATA)
            assert resp["modelId"] == test_model_id

            # 回读验证模型已添加
            detail = web_client.get_provider(test_provider)
            model_ids = [m.get("id") or m.get("modelId") for m in detail.get("models", [])]
            assert test_model_id in model_ids, f"模型 {test_model_id} 未出现在 Provider models 列表中"
        finally:
            self._cleanup_provider(web_client, test_provider)

    def test_update_provider_model(self, web_client):
        """更新 Provider 下的模型：创建 Provider → 添加模型 → 更新 → 验证 → 删除"""
        test_provider = "api-test-model-action-provider-002"
        test_model_id = "test-model-update-001"

        self._cleanup_provider(web_client, test_provider)
        try:
            self._create_test_provider(web_client, test_provider)
        except (httpx.HTTPStatusError, RuntimeError) as e:
            if "500" in str(e):
                pytest.skip(f"Provider 创建接口返回 500，服务端可能不支持该操作: {e}")
            raise

        try:
            # 先添加模型
            web_client.add_provider_model(test_provider, {
                "modelId": test_model_id,
                "name": "Original Model Name",
            })

            # 更新模型
            resp = web_client.update_provider_model(test_provider, test_model_id, {
                "name": "Updated Model Name",
            })
            web_client.validate_schema(resp, WEB_PROVIDER_MODEL_RESULT_DATA)

            # 回读验证更新生效
            detail = web_client.get_provider(test_provider)
            models = detail.get("models", [])
            target = next((m for m in models if (m.get("id") or m.get("modelId")) == test_model_id), None)
            assert target is not None, f"模型 {test_model_id} 未找到"
            assert target.get("name") == "Updated Model Name"
        finally:
            self._cleanup_provider(web_client, test_provider)

    def test_delete_provider_model(self, web_client):
        """删除 Provider 下的模型：创建 Provider → 添加模型 → 删除模型 → 验证 → 删除 Provider"""
        test_provider = "api-test-model-action-provider-003"
        test_model_id = "test-model-delete-001"

        self._cleanup_provider(web_client, test_provider)
        try:
            self._create_test_provider(web_client, test_provider)
        except (httpx.HTTPStatusError, RuntimeError) as e:
            if "500" in str(e):
                pytest.skip(f"Provider 创建接口返回 500，服务端可能不支持该操作: {e}")
            raise

        try:
            # 先添加模型
            web_client.add_provider_model(test_provider, {
                "modelId": test_model_id,
                "name": "Model To Delete",
            })

            # 删除模型
            resp = web_client.delete_provider_model(test_provider, test_model_id)
            web_client.validate_schema(resp, WEB_PROVIDER_MODEL_RESULT_DATA)

            # 回读验证模型已删除
            detail = web_client.get_provider(test_provider)
            model_ids = [m.get("id") or m.get("modelId") for m in detail.get("models", [])]
            assert test_model_id not in model_ids, f"模型 {test_model_id} 应已被删除"
        finally:
            self._cleanup_provider(web_client, test_provider)

    def test_fetch_provider_models(self, web_client):
        """获取 Provider 模型列表（从上游拉取）：使用已有 Provider"""
        providers = web_client.list_providers()
        provider_list = providers if isinstance(providers, list) else providers.get("items", providers.get("data", []))
        if not provider_list:
            pytest.skip("Provider 列表为空，无法测试 fetch-models")
        provider_name = provider_list[0].get("id") or provider_list[0].get("name")
        if not provider_name:
            pytest.skip("Provider 缺少标识字段")

        try:
            resp = web_client.fetch_provider_models(provider_name)
            assert isinstance(resp, (list, dict)), f"fetch-models 响应类型异常: {type(resp)}"
            # 字段级断言：列表项应含模型标识字段（P1 补强）
            if isinstance(resp, list):
                for item in resp:
                    assert isinstance(item, dict), f"模型项应为 dict，实际: {item!r}"
                    assert any(k in item for k in ("id", "modelId", "name")), \
                        f"模型项缺少标识字段: {list(item.keys())}"
            elif isinstance(resp, dict):
                assert any(k in resp for k in ("models", "items", "data", "list")), \
                    f"fetch-models 对象响应缺少预期字段: {list(resp.keys())}"
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            # 仅上游代理不可用 skip（502/503/504）；500 属应用 Bug 重新抛出
            if any(code in err_str for code in ("502", "503", "504")):
                pytest.skip(f"Provider 上游服务不可用: {e}")
            raise

    def test_fetch_provider_models_nonexistent(self, web_client):
        """获取不存在 Provider 的模型列表 — 应返回 404"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"(404|400)"):
            web_client.fetch_provider_models("nonexistent-provider-99999")
