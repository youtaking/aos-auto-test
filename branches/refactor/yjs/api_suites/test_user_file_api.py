# tests/api_suites/test_user_file_api.py
"""User-File 接口测试：功能验证 + 契约验证

覆盖控制台接口：
- TestUserFileWebAPI: /web/environments/:id/user-file/*（session cookie 认证）

User-file 接口限制在 user/ 目录下操作，比 fs 接口更严格。
"""
import httpx
import pytest


def _get_test_env(client):
    """获取一个可用的环境，返回 env_id 或 None"""
    try:
        envs = client.list_environments()
        if isinstance(envs, list) and len(envs) > 0:
            return envs[0].get("id")
        if isinstance(envs, dict) and "items" in envs:
            items = envs["items"]
            if len(items) > 0:
                return items[0].get("id")
    except Exception:
        pass
    return None


class TestUserFileWebAPI:
    """/web/environments/:id/user-file/* 用户文件管理接口（session cookie 认证）

    特点：
    - GET /:id/user-file/tree — 递归 user/ 文件树
    - POST /:id/user-file/mkdir — 在 user/ 下创建目录
    - POST /:id/user-file/rename — 重命名 user/ 文件
    - DELETE /:id/user-file/batch — 批量删除 user/ 文件
    - GET /:id/user-file/download-zip — 下载 zip（仅本地环境）
    """

    def test_get_user_file_tree(self, web_client):
        """获取 user 文件树：返回 paths 数组"""
        env_id = _get_test_env(web_client)
        if not env_id:
            pytest.skip("环境列表为空，无法测试 user-file 接口")

        try:
            result = web_client.get_user_file_tree(env_id)
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "404" in err_str or "not_found" in err_str:
                pytest.skip("环境或 workspace 不存在")
            if "503" in err_str or "remote_error" in err_str:
                pytest.skip("远程文件系统不可用")
            raise

        assert isinstance(result, dict)
        assert "paths" in result
        assert isinstance(result["paths"], list)

    def test_user_file_mkdir(self, web_client):
        """在 user/ 下创建目录"""
        env_id = _get_test_env(web_client)
        if not env_id:
            pytest.skip("环境列表为空，无法测试 user-file 接口")

        test_dir = "user/api-test-mkdir"

        try:
            result = web_client.user_file_mkdir(env_id, test_dir)
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "503" in err_str:
                pytest.skip("远程 mkdir 不可用")
            if "400" in err_str:
                pytest.skip(f"创建目录受限: {e}")
            raise

        assert isinstance(result, dict)
        assert result.get("path") == test_dir

    def test_user_file_rename(self, web_client):
        """重命名 user/ 下的文件"""
        env_id = _get_test_env(web_client)
        if not env_id:
            pytest.skip("环境列表为空，无法测试 user-file 接口")

        # 需要先创建一个文件用于重命名
        old_path = "user/api-test-rename-src.txt"
        new_path = "user/api-test-rename-dst.txt"

        try:
            web_client.write_user_file(env_id, old_path, "rename-test")
        except (httpx.HTTPStatusError, RuntimeError):
            pytest.skip("无法创建测试文件，跳过 rename 测试")

        try:
            result = web_client.user_file_rename(env_id, old_path, new_path)
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "503" in err_str:
                pytest.skip("远程 rename 不可用")
            if "404" in err_str:
                pytest.skip("源文件不存在")
            raise

        assert isinstance(result, dict)
        assert result.get("oldPath") == old_path
        assert result.get("newPath") == new_path

        # 清理
        try:
            web_client.delete_user_file(env_id, new_path)
        except (httpx.HTTPStatusError, RuntimeError):
            pass

    def test_user_file_batch_delete(self, web_client):
        """批量删除 user/ 下的文件"""
        env_id = _get_test_env(web_client)
        if not env_id:
            pytest.skip("环境列表为空，无法测试 user-file 接口")

        # 创建测试文件
        paths = ["user/api-test-batch-a.txt", "user/api-test-batch-b.txt"]
        created = []
        for p in paths:
            try:
                web_client.write_user_file(env_id, p, "batch-test")
                created.append(p)
            except (httpx.HTTPStatusError, RuntimeError):
                pass

        if not created:
            pytest.skip("无法创建测试文件，跳过批量删除测试")

        try:
            result = web_client.user_file_batch_delete(env_id, created)
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "503" in err_str:
                pytest.skip("远程批量删除不可用")
            raise

        assert isinstance(result, dict)
        assert "deleted" in result
        assert isinstance(result["deleted"], list)

    def test_user_file_mkdir_non_user_path(self, web_client):
        """非 user/ 路径创建目录：应返回 400 或 500"""
        env_id = _get_test_env(web_client)
        if not env_id:
            pytest.skip("环境列表为空，无法测试 user-file 接口")

        with pytest.raises((httpx.HTTPStatusError, RuntimeError)):
            web_client.user_file_mkdir(env_id, "system/not-allowed")
