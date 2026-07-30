# tests/api_suites/test_hindsight_api.py
"""Hindsight 接口测试：功能验证 + 契约验证

覆盖控制台接口：
- TestHindsightWebAPI: /web/hindsight（session cookie 认证，代理到外部服务）

注：Hindsight 是代理服务，大多数端点依赖外部 Hindsight 服务可用性。
    仅测试状态端点和基本可达性。
"""
import pytest


# unwrapped schema (data portion after _unwrap)
_WEB_HINDSIGHT_STATUS_DATA = {
    "type": "object",
    "properties": {"enabled": {"type": "boolean"}},
    "additionalProperties": True,
}


# ── 控制台接口测试 ──

class TestHindsightWebAPI:
    """/web/hindsight 控制台接口测试（session cookie 认证）

    特点：
    - GET /hindsight/status 获取启用状态
    - 其余端点代理到外部 Hindsight 服务
    """

    def test_get_hindsight_status(self, web_client):
        """获取 Hindsight 状态：返回 enabled 字段"""
        resp = web_client.get_hindsight_status()
        web_client.validate_schema(resp, _WEB_HINDSIGHT_STATUS_DATA)
        assert "enabled" in resp
        assert isinstance(resp["enabled"], bool)
