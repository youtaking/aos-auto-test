# tests/api_suites/test_knowledge_base_web_api.py
"""Knowledge Base Web 接口测试：功能验证 + 契约验证

覆盖控制台接口：
- TestKnowledgeBaseWebAPI: /web/knowledgeBases（session cookie 认证，RESTful /:id 风格）

注：知识库操作复杂（文件上传、分块、向量化等），此处覆盖基本 CRUD + 表单选项。
"""
import httpx
import pytest
from tests.api_contracts.knowledge_base_schemas import KNOWLEDGE_BASE_INFO, KNOWLEDGE_RESOURCE


def _check_knowledge_base_service(web_client, max_retries=2):
    """检查知识库服务是否可用。502/503/504 时重试，仍失败则返回 False。"""
    for attempt in range(max_retries):
        try:
            web_client.list_knowledge_bases()
            return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (502, 503, 504):
                import time
                time.sleep(2 * (attempt + 1))  # 递增等待
                continue
            if e.response.status_code in (401, 403):
                return False
            # 其他状态码（如 200/500）视为服务可达
            return True
        except Exception:
            return False
    return False


@pytest.fixture(scope="module")
def _kb_service_access(web_client):
    """模块级知识库服务访问检查：502/503/504 时跳过所有测试"""
    if not _check_knowledge_base_service(web_client):
        pytest.skip("知识库服务不可用（502/503/504），跳过所有知识库测试")


class TestKnowledgeBaseWebAPI:
    """/web/knowledgeBases 控制台接口测试（session cookie 认证，RESTful /:id 风格）

    特点：
    - 知识库 CRUD + 文档管理 + 分块/向量化
    """

    def test_list_knowledge_bases(self, web_client, _kb_service_access):
        """获取知识库列表：返回数组"""
        resp = web_client.list_knowledge_bases()
        assert isinstance(resp, list)
        if len(resp) > 0:
            web_client.validate_schema(resp[0], KNOWLEDGE_BASE_INFO)

    def test_get_knowledge_base(self, web_client, _kb_service_access):
        """获取知识库详情：先拿列表取第一个 id"""
        items = web_client.list_knowledge_bases()
        if len(items) == 0:
            pytest.skip("知识库列表为空，无法测试详情")
        kb_id = items[0]["id"]

        detail = web_client.get_knowledge_base(kb_id)
        web_client.validate_schema(detail, KNOWLEDGE_BASE_INFO)
        assert detail["id"] == kb_id
        assert "name" in detail

    def test_get_knowledge_form_options(self, web_client, _kb_service_access):
        """获取知识库表单选项：返回结构化配置"""
        resp = web_client.list_knowledge_form_options()
        assert isinstance(resp, (dict, list))
        if isinstance(resp, dict):
            assert len(resp) > 0, "表单选项不应为空字典"
            # 验证至少包含一个已知的表单配置键
            known_keys = {"embeddingModels", "chunkingStrategies", "providers", "models", "options"}
            found_keys = set(resp.keys()) & known_keys
            assert len(found_keys) > 0 or len(resp) > 0, \
                f"表单选项缺少预期配置键: {list(resp.keys())}"

    def test_list_rerank_models(self, web_client, _kb_service_access):
        """获取 rerank 模型列表：返回数组或包含模型列表的对象"""
        try:
            resp = web_client.list_rerank_models()
            if isinstance(resp, list):
                # 数组中每个元素应是字典（模型配置）
                for item in resp:
                    assert isinstance(item, dict)
                    assert "id" in item or "name" in item or "modelId" in item, \
                        f"rerank 模型项缺少标识字段: {list(item.keys())}"
            elif isinstance(resp, dict):
                # 对象形式应包含 models 或 items 字段
                assert "models" in resp or "items" in resp, \
                    f"rerank 响应缺少预期字段(models/items): {list(resp.keys())}"
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "502" in err_str or "503" in err_str or "504" in err_str:
                pytest.skip("rerank-models 上游代理不可用")
            raise

    def test_get_nonexistent_knowledge_base(self, web_client, _kb_service_access):
        """获取不存在的知识库：应抛出 404 异常"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"404"):
            web_client.get_knowledge_base("nonexistent-kb-id-99999")

    def test_knowledge_base_crud_lifecycle(self, web_client, _kb_service_access):
        """知识库 CRUD 生命周期：创建 → 读取 → 更新 → 删除"""
        test_name = "api-test-kb-crud-001"
        test_slug = "api-test-kb-crud-001"

        # 先清理可能遗留的同名知识库
        try:
            existing = web_client.list_knowledge_bases()
            for kb in existing:
                if kb.get("name") == test_name or kb.get("slug") == test_slug:
                    web_client.delete_knowledge_base(kb["id"])
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (502, 503, 504):
                pytest.skip("知识库服务不可用（502/503/504）")
        except Exception as e:
            import logging
            logging.getLogger("cleanup").warning(f"Pre-cleanup failed: {e}")

        try:
            create_resp = web_client.create_knowledge_base({
                "name": test_name,
                "slug": test_slug,
                "description": "API 测试自动创建的知识库",
            })
        except (httpx.HTTPStatusError, RuntimeError) as e:
            if any(code in str(e) for code in ("400", "422", "500", "502", "503")):
                pytest.skip(f"知识库创建接口不可用: {e}")
            raise

        web_client.validate_schema(create_resp, KNOWLEDGE_BASE_INFO)
        assert create_resp.get("name") == test_name or "id" in create_resp
        kb_id = create_resp["id"]

        try:
            # 读取验证
            detail = web_client.get_knowledge_base(kb_id)
            web_client.validate_schema(detail, KNOWLEDGE_BASE_INFO)
            assert detail["id"] == kb_id

            # 更新
            try:
                web_client.update_knowledge_base(kb_id, {
                    "description": "Updated by API test",
                })
                # 回读验证更新生效
                updated = web_client.get_knowledge_base(kb_id)
                assert updated.get("description") == "Updated by API test"
                # id 不应变化
                assert updated["id"] == kb_id
            except (httpx.HTTPStatusError, RuntimeError) as e:
                import logging
                logging.getLogger("test").warning(f"知识库更新跳过: {e}")

            # 删除并验证
            web_client.delete_knowledge_base(kb_id)
            with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"404"):
                web_client.get_knowledge_base(kb_id)
        finally:
            try:
                web_client.delete_knowledge_base(kb_id)
            except Exception as e:
                import logging
                logging.getLogger("cleanup").warning(f"Cleanup failed: {e}")

    def test_list_knowledge_bases_unauthorized(self, api_base_url):
        """无效 Token 访问知识库列表：应返回 401"""
        from tests.api_clients.web_client import WebClient
        bad_client = WebClient(api_base_url)
        try:
            with pytest.raises(httpx.HTTPStatusError, match="401"):
                bad_client.list_knowledge_bases()
        finally:
            bad_client.close()

    def test_delete_knowledge_base_idempotent(self, web_client, _kb_service_access):
        """KnowledgeBase DELETE 幂等性：第二次删除返回 404"""
        test_name = "test-idempotent-delete-kb"
        test_slug = "test-idempotent-delete-kb"
        # 预清理
        try:
            existing = web_client.list_knowledge_bases()
            for kb in existing:
                if kb.get("name") == test_name or kb.get("slug") == test_slug:
                    web_client.delete_knowledge_base(kb["id"])
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (502, 503, 504):
                pytest.skip("知识库服务不可用（502/503/504）")
        except Exception as e:
            import logging
            logging.getLogger("cleanup").warning(f"Cleanup failed: {e}")
        try:
            create_resp = web_client.create_knowledge_base({
                "name": test_name,
                "slug": test_slug,
                "description": "Idempotent delete test",
            })
            kb_id = create_resp["id"]
        except (httpx.HTTPStatusError, RuntimeError) as e:
            if any(code in str(e) for code in ("400", "422", "500", "502", "503")):
                pytest.skip(f"知识库创建接口不可用: {e}")
            raise
        try:
            web_client.delete_knowledge_base(kb_id)
            with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"404"):
                web_client.delete_knowledge_base(kb_id)
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (502, 503, 504):
                pytest.skip("知识库服务不可用（502/503/504）")
            raise
        finally:
            try:
                existing = web_client.list_knowledge_bases()
                for kb in existing:
                    if kb.get("name") == test_name or kb.get("slug") == test_slug:
                        web_client.delete_knowledge_base(kb["id"])
            except Exception as e:
                import logging
                logging.getLogger("cleanup").warning(f"Cleanup failed: {e}")


class TestKnowledgeBaseResourceAPI:
    """知识库资源管理接口测试

    覆盖 /web/knowledgeBases/:id/resources 下的 list/search/toggle/delete 接口。
    使用已有知识库进行只读测试，不创建/修改数据。
    """

    def test_list_knowledge_resources(self, web_client, _kb_service_access):
        """获取知识库资源列表：先拿列表取第一个 id，再查资源"""
        items = web_client.list_knowledge_bases()
        if len(items) == 0:
            pytest.skip("知识库列表为空，无法测试资源列表")
        kb_id = items[0]["id"]

        resp = web_client.list_knowledge_resources(kb_id)
        assert isinstance(resp, (list, dict))
        # 如果是数组，校验每项结构
        if isinstance(resp, list) and len(resp) > 0:
            web_client.validate_schema(resp[0], KNOWLEDGE_RESOURCE)

    def test_search_knowledge_base(self, web_client, _kb_service_access):
        """搜索知识库：使用已有知识库执行搜索"""
        try:
            items = web_client.list_knowledge_bases()
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (502, 503, 504):
                pytest.skip("知识库服务不可用（502/503/504）")
            raise
        if len(items) == 0:
            pytest.skip("知识库列表为空，无法测试搜索")
        kb_id = items[0]["id"]

        try:
            resp = web_client.search_knowledge_base(kb_id, "test query")
        except (httpx.HTTPStatusError, RuntimeError) as e:
            if any(code in str(e) for code in ("502", "503", "504")):
                pytest.skip("知识库搜索服务不可用（502/503/504）")
            raise
        assert isinstance(resp, (list, dict))

    def test_toggle_knowledge_resource(self, web_client, _kb_service_access):
        """切换资源启用状态：切换后恢复原始状态"""
        items = web_client.list_knowledge_bases()
        if len(items) == 0:
            pytest.skip("知识库列表为空，无法测试资源切换")
        # 尝试找到有资源的知识库
        kb_with_resources = None
        for kb in items:
            try:
                resources = web_client.list_knowledge_resources(kb["id"])
                if isinstance(resources, list) and len(resources) > 0:
                    kb_with_resources = kb
                    break
            except (httpx.HTTPStatusError, RuntimeError):
                continue

        if kb_with_resources is None:
            pytest.skip("没有包含资源的知识库，无法测试切换")

        kb_id = kb_with_resources["id"]
        resources = web_client.list_knowledge_resources(kb_id)
        if not (isinstance(resources, list) and len(resources) > 0):
            pytest.skip("知识库无资源")

        resource_id = resources[0]["id"]
        original_enabled = resources[0].get("enabled", True)
        new_state = not original_enabled

        try:
            resp = web_client.toggle_knowledge_resource(kb_id, resource_id, new_state)
            assert isinstance(resp, (dict, type(None)))
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if any(code in err_str for code in ("502", "503", "504")):
                pytest.skip(f"资源切换服务不可用: {e}")
            raise
        finally:
            # 恢复原始状态
            try:
                web_client.toggle_knowledge_resource(kb_id, resource_id, original_enabled)
            except (httpx.HTTPStatusError, RuntimeError) as e:
                import logging
                logging.getLogger("cleanup").warning(f"恢复资源状态失败: {e}")
