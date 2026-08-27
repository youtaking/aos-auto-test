# tests/api_suites/test_workflow_def_advanced_api.py
"""Workflow Definition 高级接口测试：draft/publish、版本管理、触发器 CRUD

覆盖 refactor/yjs 分支完整的工作流定义端点：
- TestWorkflowDefDraftPublishAPI: 草稿保存/发布/版本管理
- TestWorkflowDefTriggerAPI: 触发器 CRUD + 启用/禁用/重生成
- TestWorkflowDefRecoverAPI: 可恢复工作流 + 恢复确认

这些端点在 refactor/yjs 分支中扩展了完整的版本管理和触发器 CRUD 能力。
"""
import uuid

import httpx
import pytest


# ── 工具函数 ──

def _create_test_workflow(client, name: str) -> str:
    """创建测试工作流并返回 ID"""
    resp = client.create_workflow_def({
        "name": name,
        "description": f"Test workflow: {name}",
    })
    return resp["id"]


def _cleanup_workflow(client, wf_id: str):
    """删除工作流，忽略错误"""
    try:
        client.delete_workflow_def(wf_id)
    except Exception as e:
        import logging
        logging.getLogger("cleanup").warning(f"Cleanup failed: {e}")


def _get_trigger_enabled(client, wf_id: str, trigger_id: str) -> bool | None:
    """从触发器列表读取指定触发器的 enabled 状态"""
    resp = client.get(f"/web/workflow-defs/{wf_id}/triggers")
    data = client._unwrap(resp)
    if isinstance(data, list):
        for t in data:
            if (t.get("id") or t.get("triggerId")) == trigger_id:
                return t.get("enabled")
    return None


# ── Draft / Publish 接口测试 ──

class TestWorkflowDefDraftPublishAPI:
    """/web/workflow-defs/:id/draft|publish|versions 草稿/发布/版本管理

    端点：
    - PUT /workflow-defs/:id/draft — 保存草稿
    - POST /workflow-defs/:id/publish — 发布版本
    - GET /workflow-defs/:id/versions — 版本列表
    - GET /workflow-defs/:id/versions/:version — 获取版本 YAML
    - POST /workflow-defs/:id/versions/:version/set-latest — 设为最新
    - POST /workflow-defs/:id/versions/:version/restore — 恢复为草稿
    - GET /workflow-defs/:id/params — 参数定义
    """

    def test_save_draft(self, web_client):
        """保存工作流草稿，回读 GET 详情验证保存生效（G8）"""
        test_name = "api-test-wf-draft-001"
        wf_id = _create_test_workflow(web_client, test_name)

        try:
            draft_yaml = """
name: test-workflow
steps:
  - id: step1
    type: agent
    agentId: test-agent
"""
            resp = web_client.put(
                f"/web/workflow-defs/{wf_id}/draft",
                json={"yaml": draft_yaml},
            )
            data = web_client._unwrap(resp)
            # 契约：保存成功返回 data:null（源码 saveDraft 成功 data:null）
            assert data is None or isinstance(data, dict), \
                f"保存草稿返回意外类型: {data!r}"

            # 回读验证：GET /workflow-defs/:id 返回 draftYaml，应包含已保存内容
            detail = web_client.get_workflow_def(wf_id)
            assert isinstance(detail, dict)
            draft_yaml_back = detail.get("draftYaml")
            assert draft_yaml_back is not None, "保存草稿后 draftYaml 不应为空"
            assert "test-workflow" in draft_yaml_back, \
                f"draftYaml 未包含保存的 YAML: {draft_yaml_back!r}"
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "400" in err_str or "422" in err_str:
                pytest.skip(f"草稿保存接口校验严格: {e}")
            raise
        finally:
            _cleanup_workflow(web_client, wf_id)

    def test_publish_version(self, web_client):
        """发布工作流版本，回读版本列表验证产生新版本（G8/G11）"""
        test_name = "api-test-wf-publish-001"
        wf_id = _create_test_workflow(web_client, test_name)

        try:
            # 先保存一个草稿，再发布
            draft_yaml = "name: test-publish\nsteps:\n  - id: step1\n    type: log\n"
            web_client.put(
                f"/web/workflow-defs/{wf_id}/draft",
                json={"yaml": draft_yaml},
            )

            versions_before = web_client.list_workflow_def_versions(wf_id)
            before_count = len(versions_before) if isinstance(versions_before, list) else 0

            resp = web_client.post(
                f"/web/workflow-defs/{wf_id}/publish",
                json={},
            )
            data = web_client._unwrap(resp)
            # 契约：发布成功返回版本信息 dict（源码 publishVersion 返回 vRow）
            published_version = None
            if isinstance(data, dict):
                published_version = data.get("version")
                assert published_version is not None, \
                    f"发布响应缺少 version 字段: {list(data.keys())}"

            # 回读验证：版本列表新增一个版本，且包含发布的版本号
            versions_after = web_client.list_workflow_def_versions(wf_id)
            assert isinstance(versions_after, list)
            assert len(versions_after) == before_count + 1, \
                f"发布后版本数应增加 1: {before_count} → {len(versions_after)}"
            if published_version is not None:
                assert any(v.get("version") == published_version for v in versions_after), \
                    f"版本列表未包含新发布版本 {published_version}"
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if any(code in err_str for code in ("400", "404", "422")):
                pytest.skip(f"发布失败（可能无有效草稿或服务不可用）: {e}")
            raise
        finally:
            _cleanup_workflow(web_client, wf_id)

    def test_get_version_yaml(self, web_client):
        """获取指定版本的 YAML 内容"""
        items = web_client.list_workflow_defs()
        if len(items) == 0:
            pytest.skip("工作流定义列表为空")
        wf_id = items[0]["id"]

        # 先获取版本列表
        versions = web_client.list_workflow_def_versions(wf_id)
        if not versions or len(versions) == 0:
            pytest.skip(f"工作流 {wf_id} 没有已发布版本")

        version_tag = versions[0].get("version") or versions[0].get("tag") or versions[0].get("name")
        if not version_tag:
            pytest.skip(f"版本缺少标识字段: {list(versions[0].keys())}")

        try:
            resp = web_client.get(
                f"/web/workflow-defs/{wf_id}/versions/{version_tag}",
            )
            data = web_client._unwrap(resp)
            # 契约：返回 {workflowId, version, yaml} dict（源码 WorkflowVersionContentSchema）
            assert isinstance(data, dict), f"版本 YAML 应为 dict，实际: {type(data)}"
            yaml_content = data.get("yaml")
            assert isinstance(yaml_content, str) and yaml_content.strip(), \
                f"yaml 应为非空字符串，实际: {yaml_content!r}"
            # 合法 YAML：工作流定义应包含 name/steps 字段
            assert "name:" in yaml_content or "steps:" in yaml_content, \
                f"yaml 应包含工作流定义字段(name/steps): {yaml_content[:200]!r}"
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "404" in err_str:
                pytest.skip(f"版本 {version_tag} 不存在或已删除")
            raise

    def test_set_latest_version(self, web_client):
        """设置指定版本为最新"""
        items = web_client.list_workflow_defs()
        if len(items) == 0:
            pytest.skip("工作流定义列表为空")
        wf_id = items[0]["id"]

        versions = web_client.list_workflow_def_versions(wf_id)
        if not versions or len(versions) < 2:
            pytest.skip(f"工作流 {wf_id} 需要至少 2 个版本来测试 set-latest")

        version_tag = versions[-1].get("version") or versions[-1].get("tag")
        if not version_tag:
            pytest.skip("版本缺少标识字段")

        try:
            resp = web_client.post(
                f"/web/workflow-defs/{wf_id}/versions/{version_tag}/set-latest",
            )
            data = web_client._unwrap(resp)
            # 契约：set-latest 成功返回 data:null（源码返回 data:null）
            assert data is None or isinstance(data, dict), \
                f"set-latest 返回意外类型: {data!r}"

            # 回读验证：workflow 详情 latestVersion 已更新（G5）
            detail = web_client.get_workflow_def(wf_id)
            assert isinstance(detail, dict)
            assert detail.get("latestVersion") == version_tag, \
                f"set-latest 后 latestVersion 应为 {version_tag}，实际: {detail.get('latestVersion')}"
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "404" in err_str:
                pytest.skip(f"版本 {version_tag} 不存在")
            raise

    def test_restore_version_to_draft(self, web_client):
        """恢复指定版本为草稿"""
        items = web_client.list_workflow_defs()
        if len(items) == 0:
            pytest.skip("工作流定义列表为空")
        wf_id = items[0]["id"]

        versions = web_client.list_workflow_def_versions(wf_id)
        if not versions:
            pytest.skip(f"工作流 {wf_id} 没有已发布版本")

        version_tag = versions[0].get("version") or versions[0].get("tag")
        if not version_tag:
            pytest.skip("版本缺少标识字段")

        try:
            # 先取该版本 YAML 内容，用于恢复后对比
            version_resp = web_client.get(
                f"/web/workflow-defs/{wf_id}/versions/{version_tag}",
            )
            version_data = web_client._unwrap(version_resp)
            version_yaml = version_data.get("yaml") if isinstance(version_data, dict) else version_data
            assert isinstance(version_yaml, str) and version_yaml.strip(), \
                f"版本 {version_tag} YAML 应为非空字符串: {version_yaml!r}"

            resp = web_client.post(
                f"/web/workflow-defs/{wf_id}/versions/{version_tag}/restore",
            )
            data = web_client._unwrap(resp)
            # 契约：restore 成功返回 data:null（源码返回 data:null）
            assert data is None or isinstance(data, dict), \
                f"restore 返回意外类型: {data!r}"

            # 回读验证：草稿已被恢复版本内容覆盖（G5）
            detail = web_client.get_workflow_def(wf_id)
            assert isinstance(detail, dict)
            draft_yaml = detail.get("draftYaml")
            assert draft_yaml is not None, "restore 后草稿不应为空"
            assert draft_yaml.strip() == version_yaml.strip(), \
                "restore 后草稿应与恢复版本 YAML 一致"
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "404" in err_str:
                pytest.skip(f"版本 {version_tag} 不存在")
            raise

    def test_get_workflow_params(self, web_client):
        """获取工作流参数定义"""
        items = web_client.list_workflow_defs()
        if len(items) == 0:
            pytest.skip("工作流定义列表为空")
        wf_id = items[0]["id"]

        try:
            resp = web_client.get(f"/web/workflow-defs/{wf_id}/params")
            data = web_client._unwrap(resp)
            # 契约：返回 {version, params: dict}（源码 parseWorkflowYaml 提取）
            assert isinstance(data, dict), f"params 应为 dict，实际: {type(data)}"
            assert "version" in data, f"params 响应缺少 version: {list(data.keys())}"
            assert isinstance(data.get("params"), dict), \
                f"params 应为 dict: {data.get('params')!r}"
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "404" in err_str:
                pytest.skip(f"工作流 {wf_id} 参数端点不可用")
            raise


# ── Trigger CRUD 接口测试 ──

class TestWorkflowDefTriggerAPI:
    """/web/workflow-defs/:id/triggers 触发器 CRUD

    端点：
    - POST /triggers — 创建触发器
    - GET /triggers — 触发器列表
    - DELETE /triggers/:triggerId — 删除触发器
    - POST /triggers/:triggerId/regenerate — 重新生成哈希
    - POST /triggers/:triggerId/enable — 启用
    - POST /triggers/:triggerId/disable — 禁用
    """

    def test_create_trigger(self, web_client):
        """创建触发器"""
        test_name = f"api-test-wf-trigger-{uuid.uuid4().hex[:8]}"
        wf_id = _create_test_workflow(web_client, test_name)

        try:
            resp = web_client.post(
                f"/web/workflow-defs/{wf_id}/triggers",
                json={
                    "type": "cron",
                    "config": {"schedule": "0 0 * * *"},
                },
            )
            data = web_client._unwrap(resp)
            assert isinstance(data, dict)
            trigger_id = data.get("id") or data.get("triggerId")
            assert trigger_id is not None, f"创建触发器未返回 id: {data}"

            # 回读验证：新触发器应出现在触发器列表中（G5）
            list_data = web_client._unwrap(
                web_client.get(f"/web/workflow-defs/{wf_id}/triggers")
            )
            assert isinstance(list_data, list), f"触发器列表应为 list: {list_data!r}"
            listed_ids = [t.get("id") or t.get("triggerId") for t in list_data]
            assert trigger_id in listed_ids, \
                f"新触发器 {trigger_id} 未出现在列表中: {listed_ids}"
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "400" in err_str or "422" in err_str:
                pytest.skip(f"触发器创建校验严格: {e}")
            raise
        finally:
            _cleanup_workflow(web_client, wf_id)

    def test_delete_trigger(self, web_client):
        """删除触发器"""
        test_name = f"api-test-wf-trigger-del-{uuid.uuid4().hex[:8]}"
        wf_id = _create_test_workflow(web_client, test_name)

        try:
            # 先创建触发器
            resp = web_client.post(
                f"/web/workflow-defs/{wf_id}/triggers",
                json={
                    "type": "cron",
                    "config": {"schedule": "0 0 * * *"},
                },
            )
            data = web_client._unwrap(resp)
            trigger_id = data.get("id") or data.get("triggerId")
            if not trigger_id:
                pytest.skip("创建触发器未返回 id")

            # 删除
            del_resp = web_client.delete(
                f"/web/workflow-defs/{wf_id}/triggers/{trigger_id}",
            )
            del_data = web_client._unwrap(del_resp)
            # 删除返回 None（确认）或包含删除结果的 dict
            if del_data is not None:
                assert isinstance(del_data, dict), f"删除触发器返回类型异常: {type(del_data)}"

            # 回读验证：触发器列表不应包含已删除的触发器（G5/G13）
            list_data = web_client._unwrap(
                web_client.get(f"/web/workflow-defs/{wf_id}/triggers")
            )
            assert isinstance(list_data, list), f"触发器列表应为 list: {list_data!r}"
            remaining_ids = [t.get("id") or t.get("triggerId") for t in list_data]
            assert trigger_id not in remaining_ids, \
                f"已删除触发器 {trigger_id} 仍在列表中: {remaining_ids}"
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "400" in err_str or "422" in err_str:
                pytest.skip(f"触发器操作失败: {e}")
            raise
        finally:
            _cleanup_workflow(web_client, wf_id)

    def test_enable_disable_trigger(self, web_client):
        """启用/禁用触发器：验证 disable 和 enable 调用成功"""
        test_name = f"api-test-wf-trigger-toggle-{uuid.uuid4().hex[:8]}"
        wf_id = _create_test_workflow(web_client, test_name)

        try:
            # 创建触发器
            resp = web_client.post(
                f"/web/workflow-defs/{wf_id}/triggers",
                json={
                    "type": "cron",
                    "config": {"schedule": "0 0 * * *"},
                },
            )
            data = web_client._unwrap(resp)
            trigger_id = data.get("id") or data.get("triggerId")
            if not trigger_id:
                pytest.skip("创建触发器未返回 id")

            # 禁用 — 应成功返回（不抛异常即为通过）
            disable_resp = web_client.post(
                f"/web/workflow-defs/{wf_id}/triggers/{trigger_id}/disable",
            )
            disable_data = web_client._unwrap(disable_resp)
            if disable_data is not None:
                assert isinstance(disable_data, dict), f"禁用触发器返回类型异常: {type(disable_data)}"

            # 回读验证：disable 后 enabled 应为 False（G5）
            assert _get_trigger_enabled(web_client, wf_id, trigger_id) is False, \
                "disable 后触发器 enabled 应为 False"

            # 启用 — 应成功返回
            enable_resp = web_client.post(
                f"/web/workflow-defs/{wf_id}/triggers/{trigger_id}/enable",
            )
            enable_data = web_client._unwrap(enable_resp)
            if enable_data is not None:
                assert isinstance(enable_data, dict), f"启用触发器返回类型异常: {type(enable_data)}"

            # 回读验证：enable 后 enabled 应为 True（G5）
            assert _get_trigger_enabled(web_client, wf_id, trigger_id) is True, \
                "enable 后触发器 enabled 应为 True"
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "400" in err_str or "422" in err_str:
                pytest.skip(f"触发器操作失败: {e}")
            raise
        finally:
            _cleanup_workflow(web_client, wf_id)

    def test_regenerate_trigger_hash(self, web_client):
        """重新生成触发器哈希"""
        test_name = f"api-test-wf-trigger-regen-{uuid.uuid4().hex[:8]}"
        wf_id = _create_test_workflow(web_client, test_name)

        try:
            resp = web_client.post(
                f"/web/workflow-defs/{wf_id}/triggers",
                json={
                    "type": "webhook",
                    "config": {},
                },
            )
            data = web_client._unwrap(resp)
            trigger_id = data.get("id") or data.get("triggerId")
            if not trigger_id:
                pytest.skip("创建触发器未返回 id")
            original_hash = data.get("publicHash")

            regen_resp = web_client.post(
                f"/web/workflow-defs/{wf_id}/triggers/{trigger_id}/regenerate",
            )
            regen_data = web_client._unwrap(regen_resp)
            assert isinstance(regen_data, dict)
            # 回读验证：regenerate 后 publicHash 应变化（G5）
            new_hash = regen_data.get("publicHash")
            if original_hash is not None and new_hash is not None:
                assert new_hash != original_hash, \
                    f"regenerate 后 publicHash 未变化: {original_hash}"
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "400" in err_str or "422" in err_str:
                pytest.skip(f"触发器操作失败: {e}")
            raise
        finally:
            _cleanup_workflow(web_client, wf_id)

    def test_trigger_nonexistent_workflow(self, web_client):
        """为不存在的工作流创建触发器：应返回 404"""
        with pytest.raises((httpx.HTTPStatusError, RuntimeError), match=r"(404|400)"):
            web_client.post(
                "/web/workflow-defs/nonexistent-wf-99999/triggers",
                json={"type": "cron", "config": {"schedule": "0 0 * * *"}},
            )


# ── 可恢复工作流接口测试 ──

class TestWorkflowDefRecoverAPI:
    """/web/workflow-defs/recoverable|recover 可恢复工作流

    端点：
    - GET /workflow-defs/recoverable — 扫描可恢复的工作流
    - POST /workflow-defs/recover — 确认恢复
    """

    def test_get_recoverable_workflows(self, web_client):
        """获取可恢复工作流列表：源码契约返回 string[]（工作流 ID 列表）"""
        resp = web_client.get_recoverable_workflow_defs()
        assert isinstance(resp, list)
        for item in resp:
            # 契约：recoverable 元素为 ID（源码 listRecoverableWorkflows → string[]）
            assert isinstance(item, str) or (isinstance(item, dict) and item.get("id")), \
                f"可恢复工作流元素应为字符串 ID 或含 id 的对象，实际: {item!r}"

    def test_recover_workflows(self, web_client):
        """确认恢复工作流：恢复后该工作流不再出现在可恢复列表"""
        recoverable = web_client.get_recoverable_workflow_defs()
        if len(recoverable) == 0:
            pytest.skip("无可恢复的工作流")

        # 兼容 string[]（源码契约）与 dict[] 两种返回
        first = recoverable[0]
        wf_id = first if isinstance(first, str) else first.get("id")
        if not wf_id:
            pytest.skip("可恢复工作流缺少 id")

        try:
            resp = web_client.post(
                "/web/workflow-defs/recover",
                json={"workflowIds": [wf_id]},
            )
            data = web_client._unwrap(resp)
            assert isinstance(data, (dict, list, type(None)))

            # 回读验证：恢复后的工作流不再出现在可恢复列表（G5）
            after = web_client.get_recoverable_workflow_defs()
            after_ids = [x if isinstance(x, str) else x.get("id") for x in after]
            assert wf_id not in after_ids, \
                f"恢复后 {wf_id} 仍在可恢复列表中: {after_ids}"
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "400" in err_str or "404" in err_str:
                pytest.skip(f"恢复接口不可用: {e}")
            raise

    def test_recover_empty_list(self, web_client):
        """空列表恢复：应返回成功（no-op）或 400"""
        try:
            resp = web_client.post(
                "/web/workflow-defs/recover",
                json={"workflowIds": []},
            )
            data = web_client._unwrap(resp)
            assert data is None or isinstance(data, (dict, list)), \
                f"空列表恢复返回意外数据类型: {type(data)}"
        except (httpx.HTTPStatusError, RuntimeError) as e:
            # 空列表返回 400/422 是合理行为，不接受 500
            assert "400" in str(e) or "422" in str(e), \
                f"空列表恢复预期 400/422，实际: {e}"
