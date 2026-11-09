# tests/api_suites/test_workspace_api.py
"""Workspace 接口测试：功能验证 + 契约验证

覆盖对外 OpenAPI：
- TestWorkspaceOpenAPI: /api/v1/environments/:environmentId/workspace/files（API Key 认证）

接口清单：
- GET  /api/v1/environments/:environmentId/workspace/files → 文件树
- GET  /api/v1/environments/:environmentId/workspace/files/download?path=... → 下载单个文件
- POST /api/v1/environments/:environmentId/workspace/files → 上传文件（multipart）
"""
import httpx
import pytest
from tests.api_contracts.openapi_extra_schemas import API_WORKSPACE_FILE_TREE_RESPONSE


class TestWorkspaceOpenAPI:
    """/api/v1/environments/:environmentId/workspace/files 测试（API Key 认证）

    特点：
    - multipart/form-data 上传，表单字段：files（必填）、path（默认 user）、relativePaths（可选 JSON 数组）
    - 上传到 environment 的 workspace 目录，同名冲突不覆盖
    - 响应为 {success, data} 信封，client 已解包为 data
    """

    def _get_first_environment_id(self, web_client):
        """通过 web 接口获取第一个可用环境 ID（只读）"""
        try:
            envs = web_client.list_environments()
            items = envs if isinstance(envs, list) else envs.get("items", [])
            if items:
                return items[0].get("id")
        except Exception as e:
            import logging
            logging.getLogger("cleanup").warning(f"List environments failed: {e}")
        return None

    @pytest.mark.p1
    def test_list_files_existing_environment(self, api_client, web_client, _openapi_access):
        """查询已有工作区文件树：返回 environmentId + paths 数组"""
        env_id = self._get_first_environment_id(web_client)
        if env_id is None:
            pytest.skip("环境列表为空，无法测试工作区文件树")

        resp = api_client.list_workspace_files(env_id)
        api_client.validate_schema(resp, API_WORKSPACE_FILE_TREE_RESPONSE)
        assert resp["environmentId"] == env_id
        assert isinstance(resp["paths"], list)

    @pytest.mark.p2
    def test_list_files_nonexistent_environment(self, api_client, _openapi_access):
        """查询不存在的环境工作区：返回 404 + NOT_FOUND"""

        with pytest.raises(httpx.HTTPStatusError) as caught:
            api_client.list_workspace_files("nonexistent-env-id-99999")
        assert caught.value.response.status_code == 404
        body = caught.value.response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "NOT_FOUND"

    @pytest.mark.p2
    def test_upload_to_nonexistent_environment(self, api_client, _openapi_access):
        """上传到不存在的环境：返回 404"""

        with pytest.raises(httpx.HTTPStatusError) as caught:
            api_client.upload_workspace_files(
                "nonexistent-env-id-99999", [("test.txt", b"hello")]
            )
        assert caught.value.response.status_code == 404
        body = caught.value.response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "NOT_FOUND"

    @pytest.mark.p2
    def test_upload_without_files(self, api_client, web_client, _openapi_access):
        """上传不含 files 字段：返回 400 VALIDATION_ERROR"""
        env_id = self._get_first_environment_id(web_client)
        if env_id is None:
            pytest.skip("环境列表为空，无法测试上传参数校验")

        resp = api_client.client.post(
            f"/api/v1/environments/{env_id}/workspace/files",
            data={"path": "user"},
        )
        assert resp.status_code == 400, f"期望 400，实际 {resp.status_code}: {resp.text[:200]}"
        body = resp.json()
        assert body["success"] is False
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert "files" in body["error"]["message"].lower()

    @pytest.mark.p2
    def test_download_missing_path(self, api_client, _openapi_access):
        """下载缺少 path 查询参数：返回 400 VALIDATION_ERROR"""

        resp = api_client.client.get("/api/v1/environments/fake-env-id/workspace/files/download")
        assert resp.status_code == 400, f"期望 400，实际 {resp.status_code}: {resp.text[:200]}"
        body = resp.json()
        assert body["success"] is False
        assert body["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.p2
    def test_download_nonexistent_file(self, api_client, web_client, _openapi_access):
        """从已有环境下载不存在的文件：返回 404"""
        env_id = self._get_first_environment_id(web_client)
        if env_id is None:
            pytest.skip("环境列表为空，无法测试文件下载")

        with pytest.raises(httpx.HTTPStatusError) as caught:
            api_client.download_workspace_file(env_id, "nonexistent-file-99999.txt")
        assert caught.value.response.status_code == 404
        body = caught.value.response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "NOT_FOUND"

    @pytest.mark.p2
    def test_upload_invalid_path(self, api_client, web_client, _openapi_access):
        """上传使用越界 path（../）：路径校验先于写入，返回 400 VALIDATION_ERROR"""
        env_id = self._get_first_environment_id(web_client)
        if env_id is None:
            pytest.skip("环境列表为空，无法测试上传路径校验")

        with pytest.raises(httpx.HTTPStatusError) as caught:
            api_client.upload_workspace_files(
                env_id, [("test.txt", b"hello")], path="../escape"
            )
        assert caught.value.response.status_code == 400
        body = caught.value.response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "VALIDATION_ERROR"
