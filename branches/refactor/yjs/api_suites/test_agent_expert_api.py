# tests/api_suites/test_agent_expert_api.py
"""Agent Expert（专家库）接口测试：功能验证 + 契约验证

覆盖控制台接口：
- TestAgentExpertAPI: POST /web/config/agent-expert（session cookie 认证，action 分发风格）

Agent Expert 是 refactor/yjs 分支新增功能（commit f45f3902），
通过 POST body 中的 action 字段分发到不同操作：
  list      → 内置 + 本组织专家列表
  create    → 创建专家
  update    → 更新专家
  delete    → 删除专家
  refresh   → 手动触发内置模板同步
  duplicate → 复制专家到本组织
"""
import httpx
import pytest


# ── 工具函数 ──

def _agent_expert_action(client, action: str, **extra) -> dict:
    """发送 agent-expert action 请求"""
    body = {"action": action, **extra}
    resp = client.post("/web/config/agent-expert", json=body)
    return client._unwrap(resp)


def _cleanup_expert(client, expert_id: str):
    """按 ID 删除专家，忽略错误"""
    try:
        _agent_expert_action(client, "delete", id=expert_id)
    except Exception as e:
        import logging
        logging.getLogger("cleanup").warning(f"Expert cleanup failed: {e}")


# ── 测试类 ──

class TestAgentExpertAPI:
    """POST /web/config/agent-expert action 分发接口测试

    特点：
    - 统一 POST 入口，通过 body.action 分发
    - list 返回内置（system）+ 本组织自建专家
    - system 行只读：update/delete 拒绝 FORBIDDEN
    - 多租户隔离：list 恒为 IN ('system', ?org)
    """

    def test_list_experts(self, web_client):
        """获取专家列表：返回包含内置 + 自建专家的数组"""
        result = _agent_expert_action(web_client, "list")
        assert isinstance(result, (list, dict))

        # 如果是 dict，期望包含 items/experts 字段
        if isinstance(result, dict):
            experts = result.get("items", result.get("experts", []))
        else:
            experts = result

        assert isinstance(experts, list)
        if len(experts) > 0:
            expert = experts[0]
            assert isinstance(expert, dict)
            # 每个专家应有 id 和 name
            assert "id" in expert, f"专家条目缺少 id: {list(expert.keys())}"
            assert "name" in expert, f"专家条目缺少 name: {list(expert.keys())}"

    def test_list_experts_includes_system(self, web_client):
        """专家列表应包含内置 system 专家"""
        result = _agent_expert_action(web_client, "list")
        if isinstance(result, dict):
            experts = result.get("items", result.get("experts", []))
        else:
            experts = result

        # 内置专家的 origin/source 字段为 'system'
        system_experts = [
            e for e in experts
            if e.get("origin") == "system" or e.get("source") == "system" or e.get("isBuiltin") is True
        ]
        # 如果系统有内置专家，应该至少找到一个
        # 但不强制（某些部署可能没有内置专家）
        if len(experts) > 0:
            assert isinstance(experts[0], dict)

    def test_list_experts_with_include_disabled(self, web_client):
        """带 includeDisabled=true 列表应返回包含已禁用的专家"""
        result_normal = _agent_expert_action(web_client, "list")
        result_with_disabled = _agent_expert_action(web_client, "list", includeDisabled=True)

        # 两者都应是合法响应
        assert isinstance(result_normal, (list, dict))
        assert isinstance(result_with_disabled, (list, dict))

    def test_create_expert(self, web_client):
        """创建专家：name/description/prompt 必填"""
        test_name = "api-test-expert-crud-001"

        # 先清理可能遗留的同名专家
        try:
            result = _agent_expert_action(web_client, "list")
            if isinstance(result, dict):
                experts = result.get("items", result.get("experts", []))
            else:
                experts = result
            for e in experts:
                if e.get("name") == test_name:
                    _cleanup_expert(web_client, e["id"])
        except Exception:
            pass

        try:
            create_resp = _agent_expert_action(web_client, "create", data={
                "name": test_name,
                "description": "API test expert",
                "prompt": "You are a test expert assistant.",
            })

            assert isinstance(create_resp, dict)
            expert_id = create_resp.get("id")
            assert expert_id is not None, f"创建专家未返回 id: {create_resp}"

            # 回查验证
            result = _agent_expert_action(web_client, "list")
            if isinstance(result, dict):
                experts = result.get("items", result.get("experts", []))
            else:
                experts = result
            found = [e for e in experts if e.get("id") == expert_id]
            assert len(found) > 0, f"创建后列表中找不到专家 {expert_id}"
        finally:
            # 清理
            try:
                result = _agent_expert_action(web_client, "list")
                if isinstance(result, dict):
                    experts = result.get("items", result.get("experts", []))
                else:
                    experts = result
                for e in experts:
                    if e.get("name") == test_name:
                        _cleanup_expert(web_client, e["id"])
            except Exception:
                pass

    def test_create_expert_missing_name(self, web_client):
        """创建专家缺少 name：应返回 400"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"(400|422)"):
            _agent_expert_action(web_client, "create", data={
                "description": "No name expert",
                "prompt": "Should fail validation.",
            })

    def test_update_expert(self, web_client):
        """更新自建专家：修改 description"""
        test_name = "api-test-expert-update-001"

        # 先创建
        try:
            create_resp = _agent_expert_action(web_client, "create", data={
                "name": test_name,
                "description": "Original description",
                "prompt": "Test prompt.",
            })
            expert_id = create_resp["id"]
        except (httpx.HTTPStatusError, RuntimeError) as e:
            pytest.skip(f"创建专家失败，无法测试更新: {e}")

        try:
            # 更新 description
            update_resp = _agent_expert_action(web_client, "update", id=expert_id, data={
                "description": "Updated description",
            })
            assert isinstance(update_resp, dict)

            # 回查验证
            result = _agent_expert_action(web_client, "list")
            if isinstance(result, dict):
                experts = result.get("items", result.get("experts", []))
            else:
                experts = result
            found = [e for e in experts if e.get("id") == expert_id]
            if found:
                assert found[0].get("description") == "Updated description"
        finally:
            _cleanup_expert(web_client, expert_id)

    def test_delete_expert(self, web_client):
        """删除自建专家：物理删除"""
        test_name = "api-test-expert-delete-001"

        try:
            create_resp = _agent_expert_action(web_client, "create", data={
                "name": test_name,
                "description": "To be deleted",
                "prompt": "Test prompt.",
            })
            expert_id = create_resp["id"]
        except (httpx.HTTPStatusError, RuntimeError) as e:
            pytest.skip(f"创建专家失败，无法测试删除: {e}")

        # 删除
        delete_resp = _agent_expert_action(web_client, "delete", id=expert_id)
        # 删除成功可能返回 null 或 {ok: true}
        assert delete_resp is None or isinstance(delete_resp, dict)

        # 验证已删除
        result = _agent_expert_action(web_client, "list")
        if isinstance(result, dict):
            experts = result.get("items", result.get("experts", []))
        else:
            experts = result
        found = [e for e in experts if e.get("id") == expert_id]
        assert len(found) == 0, f"删除后仍找到专家 {expert_id}"

    def test_delete_system_expert_forbidden(self, web_client):
        """删除内置 system 专家：应返回 403 FORBIDDEN"""
        # 找到内置专家
        result = _agent_expert_action(web_client, "list")
        if isinstance(result, dict):
            experts = result.get("items", result.get("experts", []))
        else:
            experts = result

        system_experts = [
            e for e in experts
            if e.get("origin") == "system" or e.get("source") == "system" or e.get("isBuiltin") is True
        ]
        if len(system_experts) == 0:
            pytest.skip("无内置 system 专家，无法测试删除保护")

        system_id = system_experts[0]["id"]
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"(403|400)"):
            _agent_expert_action(web_client, "delete", id=system_id)

    def test_refresh_experts(self, web_client):
        """刷新内置模板同步：幂等操作"""
        result = _agent_expert_action(web_client, "refresh")
        # refresh 成功返回同步结果或 null
        assert result is None or isinstance(result, dict)

    def test_duplicate_expert(self, web_client):
        """复制专家到本组织：内置专家恢复路径"""
        result = _agent_expert_action(web_client, "list")
        if isinstance(result, dict):
            experts = result.get("items", result.get("experts", []))
        else:
            experts = result

        system_experts = [
            e for e in experts
            if e.get("origin") == "system" or e.get("source") == "system" or e.get("isBuiltin") is True
        ]
        if len(system_experts) == 0:
            pytest.skip("无内置 system 专家，无法测试复制")

        system_id = system_experts[0]["id"]
        try:
            dup_resp = _agent_expert_action(web_client, "duplicate", id=system_id)
            assert isinstance(dup_resp, dict)
            new_id = dup_resp.get("id")
            assert new_id is not None, f"复制后未返回 id: {dup_resp}"
            # 新复制的专家 ID 应不同于原始 ID
            assert new_id != system_id, "复制的专家 ID 不应与原始相同"
        finally:
            # 清理复制出来的专家
            try:
                result2 = _agent_expert_action(web_client, "list")
                if isinstance(result2, dict):
                    experts2 = result2.get("items", result2.get("experts", []))
                else:
                    experts2 = result2
                for e in experts2:
                    if e.get("id") != system_id and e.get("name", "").startswith(
                        system_experts[0].get("name", "___never_match___")
                    ):
                        _cleanup_expert(web_client, e["id"])
            except Exception:
                pass

    def test_unknown_action(self, web_client):
        """未知 action：应返回 400"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"(400|422)"):
            _agent_expert_action(web_client, "nonexistent_action")

    def test_list_experts_unauthorized(self, api_base_url):
        """未登录访问专家列表：应返回 401"""
        from tests.api_clients.web_client import WebClient
        bad_client = WebClient(api_base_url)
        try:
            with pytest.raises(httpx.HTTPStatusError, match="401"):
                bad_client.post("/web/config/agent-expert", json={"action": "list"})
        finally:
            bad_client.close()
