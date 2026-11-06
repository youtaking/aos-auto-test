# tests/api_suites/test_channel_api.py
"""Channel 接口测试：功能验证 + 契约验证

覆盖控制台接口（LangBot 控制面）：
- TestChannelWebAPI: /web/channels/langbot/*（session cookie 认证）

源码：packages/resources/channel/src/server/routes/web/langbot.ts
"""
import uuid

import httpx
import pytest


# ── Schema（对应 langbot.schema.ts，data 部分） ──

_LANGBOT_STATUS = {
    "type": "object",
    "properties": {
        "reachable": {"type": "boolean"},
        "version": {"type": ["string", "null"]},
        "edition": {"type": ["string", "null"]},
        "wizardStatus": {"type": ["string", "null"]},
    },
    "required": ["reachable", "version", "edition", "wizardStatus"],
    "additionalProperties": True,
}

_LANGBOT_BOT = {
    "type": "object",
    "properties": {
        "botUuid": {"type": ["string", "null"]},
        "name": {"type": "string"},
        "adapter": {"type": ["string", "null"]},
        "channelId": {"type": ["string", "null"]},
        "channelName": {"type": ["string", "null"]},
        "status": {"type": ["string", "null"]},
        "boundRouteCount": {"type": "integer", "minimum": 0},
        "missingInLangbot": {"type": "boolean"},
        "createdAt": {"type": ["string", "null"]},
        "updatedAt": {"type": ["string", "null"]},
    },
    "required": ["name", "boundRouteCount", "missingInLangbot"],
    "additionalProperties": True,
}

_LANGBOT_ROUTE = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "channelId": {"type": "string"},
        "chatType": {"type": "string"},
        "chatId": {"type": ["string", "null"]},
        "agentConfigId": {"type": "string"},
        "enabled": {"type": "boolean"},
        "instances": {"type": "array"},
        "createdAt": {"type": "string"},
        "updatedAt": {"type": "string"},
    },
    "required": ["id", "channelId", "chatType", "agentConfigId", "enabled", "instances"],
    "additionalProperties": True,
}

_LANGBOT_CONVERSATION_PAGE = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "channelId": {"type": "string"},
                    "chatType": {"type": "string"},
                    "chatId": {"type": "string"},
                    "agentConfigId": {"type": "string"},
                    "sessionId": {"type": "string"},
                },
                "required": ["id", "channelId", "chatType", "agentConfigId", "sessionId"],
                "additionalProperties": True,
            },
        },
        "total": {"type": "integer", "minimum": 0},
        "page": {"type": "integer", "minimum": 1},
        "pageSize": {"type": "integer", "minimum": 1},
    },
    "required": ["items", "total", "page", "pageSize"],
    "additionalProperties": True,
}

_ERROR_BODY = {
    "type": "object",
    "properties": {
        "success": {"type": "boolean"},
        "error": {
            "type": "object",
            "properties": {"code": {"type": "string"}, "message": {"type": "string"}},
            "required": ["code", "message"],
        },
    },
    "required": ["success", "error"],
    "additionalProperties": True,
}

_FAKE_UUID = "00000000-0000-4000-8000-000000000000"


# ── 工具函数 ──

def _first_agent_config_id(web_client) -> str | None:
    """取当前组织第一个 Agent 配置 ID"""
    data = web_client.list_agents()
    agents = data.get("agents", [])
    return agents[0].get("id") if agents else None


def _first_channel_id(web_client) -> str | None:
    """取第一个带平台通道的 Bot 的 channelId"""
    for bot in web_client.list_langbot_bots():
        if bot.get("channelId"):
            return bot["channelId"]
    return None


def _assert_error(resp: httpx.Response, status: int, code: str):
    """领域错误：{success: false, error: {code, message}}"""
    assert resp.status_code == status, f"期望 {status}，实际 {resp.status_code}: {resp.text[:300]}"
    body = resp.json()
    assert body.get("success") is False, f"失败响应 success 应为 false: {body}"
    assert body.get("error", {}).get("code") == code, f"错误码不符: {body}"


def _assert_validation_error(resp: httpx.Response, field: str):
    """Zod 校验失败：宿主全局处理器返回 {error: {type: VALIDATION_ERROR, message}}"""
    assert resp.status_code == 400, f"期望 400，实际 {resp.status_code}: {resp.text[:300]}"
    body = resp.json()
    err = body.get("error", {})
    assert err.get("type") == "VALIDATION_ERROR" or err.get("code") == "INVALID_INPUT", \
        f"校验错误类型不符: {body}"
    assert field in err.get("message", ""), f"错误信息应包含字段 {field}: {body}"


# ── 控制台接口测试 ──

class TestChannelWebAPI:
    """/web/channels/langbot/* 控制台接口测试（session cookie 认证）

    特点：
    - 状态/列表为只读；Bot 与 Route 的写操作只在自建数据上执行
    - 响应统一包装为 {success, data}，错误为 {success: false, error: {code, message}}
    """

    @pytest.mark.p1
    def test_get_langbot_status(self, web_client):
        """探测 LangBot 服务：返回 reachable/version/edition/wizardStatus"""
        resp = web_client.get_langbot_status()
        web_client.validate_schema(resp, _LANGBOT_STATUS)
        assert isinstance(resp["reachable"], bool)

    @pytest.mark.p1
    def test_list_langbot_bots(self, web_client):
        """获取 Bot 列表：数组，每项含 name/adapter/channelId 等安全字段"""
        resp = web_client.list_langbot_bots()
        assert isinstance(resp, list)
        for item in resp:
            web_client.validate_schema(item, _LANGBOT_BOT)
            assert isinstance(item["name"], str)
            # config 属于写侧凭据，不应回显
            assert "config" not in item, f"Bot 列表不应返回 config: {list(item.keys())}"

    @pytest.mark.p1
    def test_list_langbot_routes(self, web_client):
        """获取通道路由列表：数组，每项含 id/channelId/agentConfigId/enabled"""
        resp = web_client.list_langbot_routes()
        assert isinstance(resp, list)
        for item in resp:
            web_client.validate_schema(item, _LANGBOT_ROUTE)

    @pytest.mark.p1
    def test_list_langbot_conversations(self, web_client):
        """获取 IM 会话映射：分页结构 data{items,total,page,pageSize}"""
        resp = web_client.list_langbot_conversations()
        web_client.validate_schema(resp, _LANGBOT_CONVERSATION_PAGE)
        assert resp["page"] >= 1
        assert resp["pageSize"] >= 1
        assert resp["total"] >= len(resp["items"])
        # sessionId 必须脱敏，不能是原始 ACP 会话 ID
        for item in resp["items"]:
            assert "***" in item["sessionId"] or item["sessionId"].startswith("rcs_…"), \
                f"会话 sessionId 未脱敏: {item['sessionId']}"

    @pytest.mark.p2
    def test_list_langbot_conversations_pagination(self, web_client):
        """分页参数生效：pageSize=1 时返回至多 1 条且 page=1"""
        resp = web_client.list_langbot_conversations({"page": 1, "pageSize": 1})
        web_client.validate_schema(resp, _LANGBOT_CONVERSATION_PAGE)
        assert resp["page"] == 1
        assert resp["pageSize"] == 1
        assert len(resp["items"]) <= 1

    @pytest.mark.p2
    def test_create_route_missing_fields(self, web_client):
        """创建路由缺少必填字段 channelId/chatType/agentConfigId — 应 400 VALIDATION_ERROR"""
        resp = web_client.client.post("/web/channels/langbot/routes", json={})
        _assert_validation_error(resp, "channelId")

    @pytest.mark.p2
    def test_create_route_invalid_chat_type(self, web_client):
        """创建路由 chatType 非法枚举 — 应 400"""
        resp = web_client.client.post("/web/channels/langbot/routes", json={
            "channelId": _FAKE_UUID,
            "chatType": "invalid-type",
            "agentConfigId": _FAKE_UUID,
        })
        _assert_validation_error(resp, "chatType")

    @pytest.mark.p2
    def test_create_route_nonexistent_channel(self, web_client):
        """创建路由使用不存在的 channelId — 应 404 NOT_FOUND"""
        resp = web_client.client.post("/web/channels/langbot/routes", json={
            "channelId": _FAKE_UUID,
            "chatType": "person",
            "chatId": "pytest-nonexistent",
            "agentConfigId": _FAKE_UUID,
        })
        _assert_error(resp, 404, "NOT_FOUND")

    @pytest.mark.p2
    def test_get_nonexistent_bot(self, web_client):
        """读取不存在的 Bot — 应 404 NOT_FOUND"""
        resp = web_client.client.get(f"/web/channels/langbot/bots/{_FAKE_UUID}")
        _assert_error(resp, 404, "NOT_FOUND")

    @pytest.mark.p2
    def test_update_nonexistent_route(self, web_client):
        """更新不存在的路由 — 应 404 NOT_FOUND"""
        resp = web_client.client.patch(
            f"/web/channels/langbot/routes/{_FAKE_UUID}",
            json={"enabled": False},
        )
        _assert_error(resp, 404, "NOT_FOUND")

    @pytest.mark.p2
    def test_delete_nonexistent_route(self, web_client):
        """删除不存在的路由 — 应 404 NOT_FOUND"""
        resp = web_client.client.delete(f"/web/channels/langbot/routes/{_FAKE_UUID}")
        _assert_error(resp, 404, "NOT_FOUND")

    @pytest.mark.p2
    def test_send_message_missing_fields(self, web_client):
        """测试发送缺少 targetType/targetId/text — 应 400（不触发真实发送）"""
        bots = web_client.list_langbot_bots()
        bot_uuid = next((b.get("botUuid") for b in bots if b.get("botUuid")), None)
        if not bot_uuid:
            pytest.skip("无可用 Bot，无法测试发送参数校验")

        resp = web_client.client.post(
            f"/web/channels/langbot/bots/{bot_uuid}/send",
            json={"targetType": "person"},
        )
        _assert_validation_error(resp, "targetId")

    @pytest.mark.p0
    def test_list_bots_unauthorized(self, api_base_url):
        """无 session cookie 访问 — 应 401"""
        with httpx.Client(base_url=api_base_url, timeout=30, verify=False) as client:
            resp = client.get("/web/channels/langbot/bots")
        assert resp.status_code == 401, f"未认证访问应 401，实际: {resp.status_code}"

    @pytest.mark.p1
    def test_route_lifecycle(self, web_client):
        """自建路由生命周期：创建 → 查询 → 更新 → 删除"""
        channel_id = _first_channel_id(web_client)
        agent_config_id = _first_agent_config_id(web_client)
        if not channel_id or not agent_config_id:
            pytest.skip("环境缺少平台通道或 Agent 配置，无法测试路由生命周期")

        chat_id = f"pytest-route-{uuid.uuid4()}"
        route_id = None
        try:
            created = web_client.create_langbot_route({
                "channelId": channel_id,
                "chatType": "person",
                "chatId": chat_id,
                "agentConfigId": agent_config_id,
            })
            web_client.validate_schema(created, _LANGBOT_ROUTE)
            route_id = created["id"]
            assert created["chatId"] == chat_id
            assert created["agentConfigId"] == agent_config_id
            assert created["enabled"] is True

            routes = web_client.list_langbot_routes(channel_id)
            assert any(r["id"] == route_id for r in routes), "创建后未出现在路由列表中"

            updated = web_client.update_langbot_route(route_id, {"enabled": False})
            assert updated["enabled"] is False
            # 未修改字段保持原值
            assert updated["chatId"] == chat_id
            assert updated["agentConfigId"] == agent_config_id

            result = web_client.delete_langbot_route(route_id)
            assert result.get("ok") is True
            route_id = None

            routes = web_client.list_langbot_routes(channel_id)
            assert all(r["id"] != created["id"] for r in routes), "删除后路由仍存在"
        finally:
            if route_id:
                try:
                    web_client.delete_langbot_route(route_id)
                except Exception as e:
                    import logging
                    logging.getLogger("cleanup").warning(f"清理路由失败: {e}")

    @pytest.mark.p2
    def test_create_route_duplicate(self, web_client):
        """同一通道 + 相同聊天目标重复创建 — 应 409 ROUTE_CONFLICT"""
        channel_id = _first_channel_id(web_client)
        agent_config_id = _first_agent_config_id(web_client)
        if not channel_id or not agent_config_id:
            pytest.skip("环境缺少平台通道或 Agent 配置，无法测试重复路由")

        chat_id = f"pytest-dup-{uuid.uuid4()}"
        created_ids = []
        try:
            first = web_client.create_langbot_route({
                "channelId": channel_id,
                "chatType": "person",
                "chatId": chat_id,
                "agentConfigId": agent_config_id,
            })
            created_ids.append(first["id"])

            resp = web_client.client.post("/web/channels/langbot/routes", json={
                "channelId": channel_id,
                "chatType": "person",
                "chatId": chat_id,
                "agentConfigId": agent_config_id,
            })
            _assert_error(resp, 409, "ROUTE_CONFLICT")
        finally:
            for rid in created_ids:
                try:
                    web_client.delete_langbot_route(rid)
                except Exception as e:
                    import logging
                    logging.getLogger("cleanup").warning(f"清理路由失败: {e}")
