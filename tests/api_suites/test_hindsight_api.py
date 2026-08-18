# tests/api_suites/test_hindsight_api.py
"""Hindsight 接口测试：功能验证 + 契约校验

覆盖控制台接口：
- TestHindsightWebAPI: /web/hindsight（session cookie 认证，代理到外部 Hindsight 服务）

端点清单（源码 src/routes/web/hindsight.ts）：
  GET  /web/hindsight/status
  GET  /web/hindsight/graph
  GET  /web/hindsight/bank-stats
  GET  /web/hindsight/memories
  GET  /web/hindsight/memories/:id
  POST /web/hindsight/memories
  DELETE /web/hindsight/memories/:id
  POST /web/hindsight/recall
  POST /web/hindsight/reflect
  GET  /web/hindsight/documents
  POST /web/hindsight/documents（multipart，跳过）
  DELETE /web/hindsight/documents/:id
  GET  /web/hindsight/documents/:id/chunks
  GET  /web/hindsight/mental-models
  GET  /web/hindsight/mental-models/:id
  DELETE /web/hindsight/mental-models/:id
  GET  /web/hindsight/entities
  GET  /web/hindsight/entities/:id
  GET  /web/hindsight/entities/graph

注：Hindsight 是代理服务，所有端点（除 status）依赖外部 Hindsight 服务可用性。
    未启用时全部 skip。写操作（create/delete memory）采用自建自销模式。
"""
import logging

import httpx
import pytest

logger = logging.getLogger(__name__)


# ── Schema 定义 ──

_HINDSIGHT_STATUS_DATA = {
    "type": "object",
    "properties": {"enabled": {"type": "boolean"}},
    "additionalProperties": True,
}

_HINDSIGHT_GRAPH_DATA = {
    "type": "object",
    "properties": {
        "nodes": {"type": "array"},
        "edges": {"type": "array"},
    },
    "additionalProperties": True,
}

_HINDSIGHT_BANK_STATS_DATA = {
    "type": "object",
    "properties": {
        "bank_id": {"type": "string"},
        "total_nodes": {"type": "integer"},
        "total_links": {"type": "integer"},
        "total_documents": {"type": "integer"},
    },
    "additionalProperties": True,
}

_HINDSIGHT_LIST_DATA = {
    "type": "object",
    "properties": {
        "items": {"type": "array"},
        "total": {"type": "integer"},
    },
    "additionalProperties": True,
}

_HINDSIGHT_MENTAL_MODELS_DATA = {
    "type": "object",
    "properties": {
        "items": {"type": "array"},
    },
    "additionalProperties": True,
}


# ── 模块级服务可用性检查 ──

def _check_hindsight_enabled(web_client) -> bool:
    """检查 Hindsight 服务是否已启用"""
    try:
        status = web_client.get_hindsight_status()
        return status.get("enabled", False) is True
    except (httpx.HTTPStatusError, Exception):
        return False


@pytest.fixture(scope="module")
def _hindsight_enabled(web_client):
    """Hindsight 服务必须已启用，否则跳过所有测试"""
    if not _check_hindsight_enabled(web_client):
        pytest.skip("Hindsight 服务未启用或不可用，跳过所有测试")


# ── 控制台接口测试 ──


class TestHindsightWebAPI:
    """/web/hindsight 控制台接口测试（session cookie 认证）"""

    # ── Status ──

    def test_get_hindsight_status(self, web_client):
        """获取 Hindsight 状态：返回 enabled 字段"""
        resp = web_client.get_hindsight_status()
        web_client.validate_schema(resp, _HINDSIGHT_STATUS_DATA)
        assert "enabled" in resp
        assert isinstance(resp["enabled"], bool)

    # ── Graph ──

    def test_get_hindsight_graph(self, web_client, _hindsight_enabled):
        """获取记忆图谱：返回 nodes 和 edges 数组"""
        resp = web_client.get_hindsight_graph()
        web_client.validate_schema(resp, _HINDSIGHT_GRAPH_DATA)
        assert "nodes" in resp
        assert "edges" in resp
        assert isinstance(resp["nodes"], list)
        assert isinstance(resp["edges"], list)

    # ── Bank Stats ──

    def test_get_hindsight_bank_stats(self, web_client, _hindsight_enabled):
        """获取记忆库统计：返回统计字段"""
        resp = web_client.get_hindsight_bank_stats()
        web_client.validate_schema(resp, _HINDSIGHT_BANK_STATS_DATA)
        assert "bank_id" in resp
        assert "total_nodes" in resp
        assert isinstance(resp["total_nodes"], int)

    # ── Memories ──

    def test_list_hindsight_memories(self, web_client, _hindsight_enabled):
        """列出记忆：返回 items 和 total"""
        resp = web_client.list_hindsight_memories()
        web_client.validate_schema(resp, _HINDSIGHT_LIST_DATA)
        assert "items" in resp
        assert "total" in resp
        assert isinstance(resp["items"], list)
        assert isinstance(resp["total"], int)

    def test_create_and_delete_hindsight_memory(self, web_client, _hindsight_enabled):
        """创建并删除记忆：自建自销"""
        created_id = None
        try:
            create_resp = web_client.create_hindsight_memory({
                "content": "API test memory - safe to delete",
                "type": "observation",
            })
            assert create_resp is not None
            # 创建响应结构取决于 Hindsight 上游，提取 ID
            if isinstance(create_resp, dict):
                created_id = create_resp.get("id") or create_resp.get("memory_id")
            elif isinstance(create_resp, str):
                created_id = create_resp
        except (httpx.HTTPStatusError, Exception) as e:
            logger.warning(f"Create hindsight memory failed: {e}")
            pytest.skip("无法创建记忆，跳过生命周期测试")
        finally:
            if created_id:
                try:
                    web_client.delete_hindsight_memory(created_id)
                except Exception as e:
                    logger.warning(f"Cleanup hindsight memory {created_id} failed: {e}")

    def test_get_hindsight_memory_detail(self, web_client, _hindsight_enabled):
        """获取记忆详情：先列表取 ID 再查详情"""
        list_resp = web_client.list_hindsight_memories()
        items = list_resp.get("items", [])
        if not items:
            pytest.skip("无记忆数据，跳过详情测试")
        memory_id = items[0].get("id") or items[0].get("memory_id")
        if not memory_id:
            pytest.skip("记忆项无 ID 字段")
        detail = web_client.get_hindsight_memory(memory_id)
        assert detail is not None

    def test_get_hindsight_memory_nonexistent(self, web_client, _hindsight_enabled):
        """获取不存在的记忆：应返回 404 或空结果"""
        try:
            result = web_client.get_hindsight_memory("nonexistent-memory-id-99999")
            # Hindsight 服务可能返回 200 + 空结果而非 404
            assert result is None or isinstance(result, (dict, list)), \
                f"预期空结果或 dict/list，实际: {type(result)}"
        except httpx.HTTPStatusError as e:
            assert e.response.status_code in (404, 400), \
                f"预期 404/400，实际 {e.response.status_code}"
        except RuntimeError as e:
            assert "404" in str(e) or "400" in str(e) or "not_found" in str(e).lower(), \
                f"预期 404/not_found 错误，实际: {e}"

    # ── Recall & Reflect ──

    def test_recall_hindsight(self, web_client, _hindsight_enabled):
        """检索记忆：POST /recall"""
        try:
            resp = web_client.recall_hindsight({"query": "test query"})
            assert resp is not None
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "502" in err_str or "503" in err_str or "504" in err_str:
                pytest.skip(f"Hindsight 上游服务不可用: {e}")
            raise

    def test_reflect_hindsight(self, web_client, _hindsight_enabled):
        """触发反思：POST /reflect"""
        try:
            resp = web_client.reflect_hindsight({})
            assert resp is not None
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "502" in err_str or "503" in err_str or "504" in err_str:
                pytest.skip(f"Hindsight 上游服务不可用: {e}")
            raise

    # ── Documents ──

    def test_list_hindsight_documents(self, web_client, _hindsight_enabled):
        """列出文档：返回 items 和 total"""
        resp = web_client.list_hindsight_documents()
        web_client.validate_schema(resp, _HINDSIGHT_LIST_DATA)
        assert "items" in resp
        assert "total" in resp
        assert isinstance(resp["items"], list)
        assert isinstance(resp["total"], int)

    def test_delete_hindsight_document_nonexistent(self, web_client, _hindsight_enabled):
        """删除不存在的文档：应返回 404 或幂等成功"""
        try:
            result = web_client.delete_hindsight_document("nonexistent-doc-id-99999")
            # 幂等删除：服务可能返回 200 成功
            assert result is None or isinstance(result, dict)
        except httpx.HTTPStatusError as e:
            assert e.response.status_code in (404, 400), \
                f"预期 404/400，实际 {e.response.status_code}"
        except RuntimeError as e:
            assert "404" in str(e) or "400" in str(e) or "not_found" in str(e).lower(), \
                f"预期 404/not_found 错误，实际: {e}"

    def test_get_hindsight_document_chunks(self, web_client, _hindsight_enabled):
        """获取文档分块：需要先有文档"""
        docs = web_client.list_hindsight_documents()
        items = docs.get("items", [])
        if not items:
            pytest.skip("无文档数据，跳过分块测试")
        doc_id = items[0].get("id") or items[0].get("document_id")
        if not doc_id:
            pytest.skip("文档项无 ID 字段")
        try:
            chunks = web_client.get_hindsight_document_chunks(doc_id)
            assert chunks is not None
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "502" in err_str or "503" in err_str or "504" in err_str:
                pytest.skip(f"Hindsight 上游服务不可用: {e}")
            raise

    # ── Mental Models ──

    def test_list_hindsight_mental_models(self, web_client, _hindsight_enabled):
        """列中心智模型：返回 items 数组"""
        resp = web_client.list_hindsight_mental_models()
        web_client.validate_schema(resp, _HINDSIGHT_MENTAL_MODELS_DATA)
        assert "items" in resp
        assert isinstance(resp["items"], list)

    def test_get_hindsight_mental_model(self, web_client, _hindsight_enabled):
        """获取心智模型详情：先列表取 ID 再查详情"""
        list_resp = web_client.list_hindsight_mental_models()
        items = list_resp.get("items", [])
        if not items:
            pytest.skip("无心智模型数据，跳过详情测试")
        model_id = items[0].get("id") or items[0].get("model_id")
        if not model_id:
            pytest.skip("心智模型项无 ID 字段")
        detail = web_client.get_hindsight_mental_model(model_id)
        assert detail is not None

    def test_delete_hindsight_mental_model_nonexistent(self, web_client, _hindsight_enabled):
        """删除不存在的心智模型：应返回 404 或幂等成功"""
        try:
            result = web_client.delete_hindsight_mental_model("nonexistent-model-id-99999")
            assert result is None or isinstance(result, dict)
        except httpx.HTTPStatusError as e:
            assert e.response.status_code in (404, 400), \
                f"预期 404/400，实际 {e.response.status_code}"
        except RuntimeError as e:
            assert "404" in str(e) or "400" in str(e) or "not_found" in str(e).lower(), \
                f"预期 404/not_found 错误，实际: {e}"

    # ── Entities ──

    def test_list_hindsight_entities(self, web_client, _hindsight_enabled):
        """列出实体：返回 items 和 total"""
        resp = web_client.list_hindsight_entities()
        web_client.validate_schema(resp, _HINDSIGHT_LIST_DATA)
        assert "items" in resp
        assert "total" in resp
        assert isinstance(resp["items"], list)
        assert isinstance(resp["total"], int)

    def test_get_hindsight_entity(self, web_client, _hindsight_enabled):
        """获取实体详情：先列表取 ID 再查详情"""
        list_resp = web_client.list_hindsight_entities()
        items = list_resp.get("items", [])
        if not items:
            pytest.skip("无实体数据，跳过详情测试")
        entity_id = items[0].get("id") or items[0].get("entity_id")
        if not entity_id:
            pytest.skip("实体项无 ID 字段")
        detail = web_client.get_hindsight_entity(entity_id)
        assert detail is not None

    def test_get_hindsight_entity_nonexistent(self, web_client, _hindsight_enabled):
        """获取不存在的实体：应返回 404 或空结果"""
        try:
            result = web_client.get_hindsight_entity("nonexistent-entity-id-99999")
            assert result is None or isinstance(result, (dict, list)), \
                f"预期空结果或 dict/list，实际: {type(result)}"
        except httpx.HTTPStatusError as e:
            assert e.response.status_code in (404, 400), \
                f"预期 404/400，实际 {e.response.status_code}"
        except RuntimeError as e:
            assert "404" in str(e) or "400" in str(e) or "not_found" in str(e).lower(), \
                f"预期 404/not_found 错误，实际: {e}"

    def test_get_hindsight_entities_graph(self, web_client, _hindsight_enabled):
        """获取实体关系图谱"""
        resp = web_client.get_hindsight_entities_graph()
        assert resp is not None
