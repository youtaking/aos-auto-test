# tests/api_suites/test_knowledge_base_advanced_api.py
"""Knowledge Base 高级接口测试：chunks、graph、embedding models

覆盖 refactor/yjs 分支新增的知识库高级接口：
- TestKnowledgeChunkAPI: /web/knowledgeBases/:id/resources/:resourceId/chunks
- TestKnowledgeGraphAPI: /web/knowledgeBases/:id/graph
- TestKnowledgeEmbeddingModelAPI: POST /web/knowledgeBases/models (action 分发)

这些端点在 refactor/yjs 分支中有增强或新增，
包括分片查询/切换、知识图谱 CRUD 和 embedding 模型管理。
"""
import httpx
import pytest


# ── 工具函数 ──

def _get_kb_with_resources(web_client):
    """获取第一个有资源的知识库及其资源，返回 (kb_id, resources) 或 None"""
    try:
        kbs = web_client.list_knowledge_bases()
    except (httpx.HTTPStatusError, RuntimeError):
        return None

    for kb in kbs:
        kb_id = kb.get("id")
        if not kb_id:
            continue
        try:
            resources = web_client.list_knowledge_resources(kb_id)
            if isinstance(resources, list) and len(resources) > 0:
                return kb_id, resources
        except (httpx.HTTPStatusError, RuntimeError):
            continue
    return None


# ── Chunk 接口测试 ──

class TestKnowledgeChunkAPI:
    """/web/knowledgeBases/:id/resources/:resourceId/chunks 资源分片接口

    特点：
    - GET /chunks?page=1&pageSize=20&keyword=xxx — 分页查询切片
    - PATCH /chunks/:chunkId/enabled — 切换单个切片启用状态
    """

    def test_list_chunks(self, web_client):
        """分页获取资源切片列表"""
        result = _get_kb_with_resources(web_client)
        if result is None:
            pytest.skip("没有包含资源的知识库，无法测试切片列表")

        kb_id, resources = result
        resource_id = resources[0]["id"]

        try:
            resp = web_client.get(
                f"/web/knowledgeBases/{kb_id}/resources/{resource_id}/chunks",
                params={"page": 1, "pageSize": 10},
            )
            data = web_client._unwrap(resp)
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "502" in err_str or "PROVIDER" in err_str:
                pytest.skip("知识库上游服务不可用")
            if "NO_REMOTE" in err_str or "NOT_SYNCED" in err_str:
                pytest.skip("资源未同步到远端，无切片数据")
            raise

        assert isinstance(data, dict)
        # 期望返回 items + total + page + pageSize
        if "items" in data:
            assert isinstance(data["items"], list)
        if "total" in data:
            assert isinstance(data["total"], int)

    def test_list_chunks_with_keyword(self, web_client):
        """按关键词搜索切片"""
        result = _get_kb_with_resources(web_client)
        if result is None:
            pytest.skip("没有包含资源的知识库")

        kb_id, resources = result
        resource_id = resources[0]["id"]

        try:
            resp = web_client.get(
                f"/web/knowledgeBases/{kb_id}/resources/{resource_id}/chunks",
                params={"page": 1, "pageSize": 10, "keyword": "test"},
            )
            data = web_client._unwrap(resp)
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "502" in err_str or "PROVIDER" in err_str or "NOT_SYNCED" in err_str:
                pytest.skip("知识库上游服务不可用或资源未同步")
            raise

        assert isinstance(data, dict)

    def test_list_chunks_nonexistent_resource(self, web_client):
        """查询不存在资源的切片：应返回 404"""
        kbs = web_client.list_knowledge_bases()
        if len(kbs) == 0:
            pytest.skip("知识库列表为空")
        kb_id = kbs[0]["id"]

        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"(404|400)"):
            web_client.get(
                f"/web/knowledgeBases/{kb_id}/resources/nonexistent-resource-99999/chunks",
                params={"page": 1},
            )

    def test_toggle_chunk_enabled(self, web_client):
        """切换切片启用状态"""
        result = _get_kb_with_resources(web_client)
        if result is None:
            pytest.skip("没有包含资源的知识库")

        kb_id, resources = result
        resource_id = resources[0]["id"]

        # 先获取切片列表
        try:
            resp = web_client.get(
                f"/web/knowledgeBases/{kb_id}/resources/{resource_id}/chunks",
                params={"page": 1, "pageSize": 5},
            )
            data = web_client._unwrap(resp)
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "502" in err_str or "NOT_SYNCED" in err_str:
                pytest.skip("知识库上游服务不可用或资源未同步")
            raise

        items = data.get("items", []) if isinstance(data, dict) else []
        if len(items) == 0:
            pytest.skip("该资源无切片数据")

        chunk_id = items[0].get("id") or items[0].get("chunkId")
        if not chunk_id:
            pytest.skip(f"切片缺少 ID 字段: {list(items[0].keys())}")

        original_enabled = items[0].get("available", items[0].get("enabled", True))
        new_state = not original_enabled

        try:
            resp = web_client.patch(
                f"/web/knowledgeBases/{kb_id}/resources/{resource_id}/chunks/{chunk_id}/enabled",
                json={"enabled": new_state},
            )
            result_data = web_client._unwrap(resp)
            assert isinstance(result_data, dict)
            assert "enabled" in result_data or "available" in result_data
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "502" in err_str or "CHUNK_SWITCH_FAILED" in err_str:
                pytest.skip("上游切换切片状态失败")
            raise
        finally:
            # 恢复原始状态
            try:
                web_client.patch(
                    f"/web/knowledgeBases/{kb_id}/resources/{resource_id}/chunks/{chunk_id}/enabled",
                    json={"enabled": original_enabled},
                )
            except Exception:
                pass


# ── 知识图谱接口测试 ──

class TestKnowledgeGraphAPI:
    """/web/knowledgeBases/:id/graph 知识图谱接口

    特点：
    - POST /graph/generate — 触发 GraphRAG 知识图谱生成
    - GET /graph — 获取知识图谱数据（节点 + 边）
    - DELETE /graph — 删除知识图谱
    - GET /graph/progress — 轮询生成进度
    """

    def test_get_knowledge_graph(self, web_client):
        """获取知识图谱数据"""
        kbs = web_client.list_knowledge_bases()
        if len(kbs) == 0:
            pytest.skip("知识库列表为空")
        kb_id = kbs[0]["id"]

        try:
            resp = web_client.get(f"/web/knowledgeBases/{kb_id}/graph")
            data = web_client._unwrap(resp)
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "502" in err_str or "KNOWLEDGE_PROVIDER_ERROR" in err_str:
                pytest.skip("知识库上游服务不可用")
            raise

        assert isinstance(data, (dict, list, type(None)))

    def test_get_graph_progress(self, web_client):
        """查询知识图谱生成进度"""
        kbs = web_client.list_knowledge_bases()
        if len(kbs) == 0:
            pytest.skip("知识库列表为空")
        kb_id = kbs[0]["id"]

        try:
            resp = web_client.get(f"/web/knowledgeBases/{kb_id}/graph/progress")
            data = web_client._unwrap(resp)
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "502" in err_str or "KNOWLEDGE_PROVIDER_ERROR" in err_str:
                pytest.skip("知识库上游服务不可用")
            raise

        assert isinstance(data, (dict, type(None)))

    def test_generate_knowledge_graph(self, web_client):
        """触发知识图谱生成：异步操作"""
        result = _get_kb_with_resources(web_client)
        if result is None:
            pytest.skip("没有包含资源的知识库，无法触发图谱生成")

        kb_id, _ = result
        try:
            resp = web_client.post(f"/web/knowledgeBases/{kb_id}/graph/generate")
            data = web_client._unwrap(resp)
            # 触发成功返回 null 或状态
            assert data is None or isinstance(data, dict)
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "502" in err_str or "KNOWLEDGE_PROVIDER_ERROR" in err_str:
                pytest.skip("知识库上游服务不可用，无法触发图谱生成")
            raise

    def test_delete_knowledge_graph(self, web_client):
        """删除知识图谱"""
        kbs = web_client.list_knowledge_bases()
        if len(kbs) == 0:
            pytest.skip("知识库列表为空")
        kb_id = kbs[0]["id"]

        try:
            resp = web_client.delete(f"/web/knowledgeBases/{kb_id}/graph")
            data = web_client._unwrap(resp)
            assert data is None or isinstance(data, dict)
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "502" in err_str or "KNOWLEDGE_PROVIDER_ERROR" in err_str:
                pytest.skip("知识库上游服务不可用")
            raise

    def test_graph_nonexistent_kb(self, web_client):
        """查询不存在知识库的图谱：应返回 404 或 502"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError)):
            web_client.get("/web/knowledgeBases/nonexistent-kb-99999/graph")


# ── Embedding 模型管理接口测试 ──

class TestKnowledgeEmbeddingModelAPI:
    """POST /web/knowledgeBases/models Embedding 模型管理（action 分发）

    特点：
    - 统一 POST 入口，通过 body.action 分发
    - actions: list / list-factories / verify / list-provider-models /
               list-instance-models / add / delete / set-model-status
    """

    def test_list_embedding_models(self, web_client):
        """列出已配置的 embedding provider 树"""
        try:
            resp = web_client.post(
                "/web/knowledgeBases/models",
                json={"action": "list"},
            )
            data = web_client._unwrap(resp)
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "502" in err_str or "KNOWLEDGE_PROVIDER_ERROR" in err_str:
                pytest.skip("知识库上游服务不可用")
            raise

        assert isinstance(data, (list, dict))

    def test_list_embedding_factories(self, web_client):
        """列出可用的 embedding factory（提供商工厂）"""
        try:
            resp = web_client.post(
                "/web/knowledgeBases/models",
                json={"action": "list-factories"},
            )
            data = web_client._unwrap(resp)
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "502" in err_str or "KNOWLEDGE_PROVIDER_ERROR" in err_str:
                pytest.skip("知识库上游服务不可用")
            raise

        assert isinstance(data, (list, dict))

    def test_verify_provider_missing_fields(self, web_client):
        """验证 provider 缺少必填字段：应返回 400"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"(400|422)"):
            web_client.post(
                "/web/knowledgeBases/models",
                json={"action": "verify"},
                # 故意缺少 provider 和 providerApiKey
            )

    def test_list_provider_models_missing_fields(self, web_client):
        """列出 provider 模型缺少必填字段：应返回 400"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"(400|422)"):
            web_client.post(
                "/web/knowledgeBases/models",
                json={"action": "list-provider-models"},
            )

    def test_list_instance_models_missing_fields(self, web_client):
        """列出 instance 模型缺少必填字段：应返回 400"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"(400|422)"):
            web_client.post(
                "/web/knowledgeBases/models",
                json={"action": "list-instance-models"},
            )

    def test_set_model_status_missing_fields(self, web_client):
        """设置模型状态缺少必填字段：应返回 400"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"(400|422)"):
            web_client.post(
                "/web/knowledgeBases/models",
                json={"action": "set-model-status"},
            )

    def test_add_embedding_provider_missing_fields(self, web_client):
        """添加 provider 缺少必填字段：应返回 400"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"(400|422)"):
            web_client.post(
                "/web/knowledgeBases/models",
                json={"action": "add"},
            )

    def test_delete_embedding_instance_missing_fields(self, web_client):
        """删除 instance 缺少必填字段：应返回 400"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"(400|422)"):
            web_client.post(
                "/web/knowledgeBases/models",
                json={"action": "delete"},
            )

    def test_unknown_embedding_action(self, web_client):
        """未知 action：应返回 400"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"(400|422)"):
            web_client.post(
                "/web/knowledgeBases/models",
                json={"action": "nonexistent-action"},
            )

    def test_embedding_models_unauthorized(self, api_base_url):
        """未登录访问 embedding 模型管理：应返回 401"""
        from tests.api_clients.web_client import WebClient
        bad_client = WebClient(api_base_url)
        try:
            with pytest.raises(httpx.HTTPStatusError, match="401"):
                bad_client.post(
                    "/web/knowledgeBases/models",
                    json={"action": "list"},
                )
        finally:
            bad_client.close()


# ── 知识资源重解析接口测试 ──

class TestKnowledgeResourceReparseAPI:
    """/web/knowledgeBases/:id/resources/:resourceId/reparse 资源重解析接口

    特点：
    - POST /reparse — 触发 RagFlow 重新解析（异步）
    - 可选 body.delete=true 删除旧数据后重新解析
    """

    def test_reparse_resource(self, web_client):
        """触发资源重新解析"""
        result = _get_kb_with_resources(web_client)
        if result is None:
            pytest.skip("没有包含资源的知识库")

        kb_id, resources = result
        resource_id = resources[0]["id"]

        try:
            resp = web_client.post(
                f"/web/knowledgeBases/{kb_id}/resources/{resource_id}/reparse",
                json={},
            )
            data = web_client._unwrap(resp)
            # 触发成功返回 null
            assert data is None or isinstance(data, dict)
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "502" in err_str or "REPARSE_FAILED" in err_str:
                pytest.skip("知识库上游服务不可用，无法触发重解析")
            if "NOT_SYNCED" in err_str:
                pytest.skip("资源未同步到远端，无法重解析")
            raise

    def test_reparse_nonexistent_resource(self, web_client):
        """重解析不存在的资源：应返回 404"""
        kbs = web_client.list_knowledge_bases()
        if len(kbs) == 0:
            pytest.skip("知识库列表为空")
        kb_id = kbs[0]["id"]

        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"(404|400)"):
            web_client.post(
                f"/web/knowledgeBases/{kb_id}/resources/nonexistent-resource-99999/reparse",
                json={},
            )
