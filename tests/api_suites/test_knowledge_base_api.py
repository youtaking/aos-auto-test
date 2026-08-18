# tests/api_suites/test_knowledge_base_api.py
"""Knowledge Base 接口测试：功能验证 + 契约验证

覆盖两套接口：
- TestKnowledgeBaseOpenAPI: /api/knowledge-bases 对外 OpenAPI（API Key 认证）
"""
import pytest
from tests.api_contracts.openapi_extra_schemas import (
    API_KNOWLEDGE_BASE_LIST_RESPONSE,
)


# ── 对外 OpenAPI 测试 ──

class TestKnowledgeBaseOpenAPI:
    """/api/knowledge-bases 对外 OpenAPI 测试（API Key 认证）

    特点：
    - 仅有一个列表端点
    - 列表带分页 {items, total, page, pageSize}
    """

    def test_list_knowledge_bases(self, api_client, _openapi_access):
        """获取知识库列表：返回分页结构"""

        resp = api_client.list_knowledge_bases()
        api_client.validate_schema(resp, API_KNOWLEDGE_BASE_LIST_RESPONSE)
        assert isinstance(resp["items"], list)
        if len(resp["items"]) > 0:
            # 验证元素结构：至少包含 id 和 name
            item = resp["items"][0]
            assert isinstance(item, dict)
            assert "id" in item or "name" in item, f"知识库条目缺少 id/name 字段: {list(item.keys())}"
