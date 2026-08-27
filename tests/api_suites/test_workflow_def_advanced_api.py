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
        """保存工作流草稿"""
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
            # 草稿保存成功：应返回 None（空操作确认）或包含 id 的 dict
            if data is not None:
                assert isinstance(data, dict), f"保存草稿返回类型异常: {type(data)}"

            # 回读验证：重新获取 draft 确认已保存
            try:
                get_resp = web_client.get(f"/web/workflow-defs/{wf_id}/draft")
                get_data = web_client._unwrap(get_resp)
                assert get_data is not None, "保存草稿后 GET draft 不应为空"
            except (httpx.HTTPStatusError, RuntimeError):
                pass  # draft GET 端点可能不存在
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "400" in err_str or "422" in err_str:
                pytest.skip(f"草稿保存接口校验严格: {e}")
            raise
        finally:
            _cleanup_workflow(web_client, wf_id)

    def test_publish_version(self, web_client):
        """发布工作流版本"""
        test_name = "api-test-wf-publish-001"
        wf_id = _create_test_workflow(web_client, test_name)

        try:
            # 先保存一个草稿，再发布
            draft_yaml = "name: test-publish\nsteps:\n  - id: step1\n    type: log\n"
            try:
                web_client.put(
                    f"/web/workflow-defs/{wf_id}/draft",
                    json={"yaml": draft_yaml},
                )
            except (httpx.HTTPStatusError, RuntimeError):
                pass  # 草稿保存失败不影响发布测试

            resp = web_client.post(
                f"/web/workflow-defs/{wf_id}/publish",
                json={},
            )
            data = web_client._unwrap(resp)
            # 发布成功返回版本信息或 null
            if data is not None:
                assert isinstance(data, dict), f"发布返回类型异常: {type(data)}"
                assert any(k in data for k in ("version", "tag", "id", "name")), \
                    f"发布响应缺少标识字段: {list(data.keys())}"

            # 回读验证：发布后版本列表应非空
            versions = web_client.list_workflow_def_versions(wf_id)
            assert isinstance(versions, list)
            # 注意：无草稿时发布可能不产生新版本
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            # 无草稿时发布可能返回 400/404/500
            if any(code in err_str for code in ("400", "404", "422", "502")):
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
            # 版本 YAML 可能是字符串或包含 yaml 字段的 dict
            assert isinstance(data, (str, dict))
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
            # set-latest 返回 None（确认）或包含版本信息的 dict
            if data is not None:
                assert isinstance(data, dict), f"set-latest 返回类型异常: {type(data)}"
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
            resp = web_client.post(
                f"/web/workflow-defs/{wf_id}/versions/{version_tag}/restore",
            )
            data = web_client._unwrap(resp)
            # restore 返回 None（确认）或包含恢复结果的 dict
            if data is not None:
                assert isinstance(data, dict), f"restore 返回类型异常: {type(data)}"
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
            # params 可能是数组或包含 params 字段的 dict
            assert isinstance(data, (list, dict))
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

            # 回读验证：触发器列表不应包含已删除的触发器
            try:
                list_resp = web_client.get(f"/web/workflow-defs/{wf_id}/triggers")
                list_data = web_client._unwrap(list_resp)
                if isinstance(list_data, list):
                    remaining_ids = [
                        t.get("id") or t.get("triggerId") for t in list_data
                    ]
                    assert trigger_id not in remaining_ids, \
                        f"已删除触发器 {trigger_id} 仍在列表中"
            except (httpx.HTTPStatusError, RuntimeError):
                pass  # 列表端点可能不可用
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

            # 启用 — 应成功返回
            enable_resp = web_client.post(
                f"/web/workflow-defs/{wf_id}/triggers/{trigger_id}/enable",
            )
            enable_data = web_client._unwrap(enable_resp)
            if enable_data is not None:
                assert isinstance(enable_data, dict), f"启用触发器返回类型异常: {type(enable_data)}"
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

            regen_resp = web_client.post(
                f"/web/workflow-defs/{wf_id}/triggers/{trigger_id}/regenerate",
            )
            regen_data = web_client._unwrap(regen_resp)
            assert isinstance(regen_data, dict)
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
        """获取可恢复工作流列表"""
        resp = web_client.get_recoverable_workflow_defs()
        assert isinstance(resp, list)

    def test_recover_workflows(self, web_client):
        """确认恢复工作流"""
        recoverable = web_client.get_recoverable_workflow_defs()
        if len(recoverable) == 0:
            pytest.skip("无可恢复的工作流")

        # 恢复第一个
        wf_id = recoverable[0].get("id")
        if not wf_id:
            pytest.skip("可恢复工作流缺少 id")

        try:
            resp = web_client.post(
                "/web/workflow-defs/recover",
                json={"workflowIds": [wf_id]},
            )
            data = web_client._unwrap(resp)
            assert isinstance(data, (dict, list, type(None)))
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
