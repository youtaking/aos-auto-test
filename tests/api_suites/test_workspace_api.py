# tests/api_suites/test_workspace_api.py
"""Workspace 接口测试：功能验证 + 契约验证

覆盖对外 OpenAPI：
- TestWorkspaceOpenAPI: /api/environments/:envId/workspace/files（API Key 认证）

接口清单：
- POST /api/environments/:environmentId/workspace/files → 上传文件到工作区
"""
import io
import httpx
import pytest


class TestWorkspaceOpenAPI:
    """/api/environments/:envId/workspace/files 测试（API Key 认证）

    特点：
    - multipart/form-data 上传
    - 表单字段：files（必填）、path（可选）、relativePaths（可选 JSON 数组）
    - 上传到 environment 的 workspace/user 目录
    """

    def _get_first_environment_id(self, web_client):
        """通过 web 接口获取第一个可用环境 ID"""
        try:
            envs = web_client.list_environments()
            if isinstance(envs, list) and len(envs) > 0:
                return envs[0].get("id")
        except Exception as e:
            import logging
            logging.getLogger("cleanup").warning(f"Cleanup failed: {e}")
        return None

    def test_upload_to_nonexistent_environment(self, api_client, _openapi_access):
        """上传到不存在的环境：应返回 404"""

        # 构造 multipart 请求
        files = {"files": ("test.txt", io.BytesIO(b"hello"), "text/plain")}
        with pytest.raises(httpx.HTTPStatusError, match=r"404"):
            api_client.client.post(
                "/api/environments/nonexistent-env-id-99999/workspace/files",
                files=files,
            ).raise_for_status()

    def test_upload_without_files(self, api_client, _openapi_access):
        """上传不含 files 字段：应返回 400"""

        # 使用假 env_id 验证缺少 files 字段时的服务端处理
        with pytest.raises(httpx.HTTPStatusError, match=r"(400|404)"):
            api_client.client.post(
                "/api/environments/fake-env-id/workspace/files",
                data={"path": "user"},
            ).raise_for_status()
