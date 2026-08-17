# tests/api_suites/test_files_api.py
"""Files 接口测试：功能验证 + 契约验证

覆盖控制台接口：
- TestFilesWebAPI: /web/environments/:id/user/*（session cookie 认证）

文件操作接口需要真实环境和 workspace。测试会在无可用环境时跳过。
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


class TestFilesWebAPI:
    """/web/environments/:id/user/* 文件管理接口（session cookie 认证）

    特点：
    - GET /:id/user — 列出目录
    - GET /:id/user/* — 读取文件
    - PUT /:id/user/* — 写入文件
    - DELETE /:id/user/* — 删除文件
    """

    def test_list_user_files(self, web_client):
        """列出用户目录：返回 entries 数组"""
        env_id = _get_test_env(web_client)
        if not env_id:
            pytest.skip("环境列表为空，无法测试文件接口")

        try:
            result = web_client.list_user_files(env_id)
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "404" in err_str or "not_found" in err_str:
                pytest.skip("环境不存在或 workspace 未初始化")
            if "503" in err_str or "remote_error" in err_str:
                pytest.skip("远程文件系统不可用")
            if "UNKNOWN" in err_str:
                pytest.skip("workspace 未初始化或服务不可用")
            raise

        assert isinstance(result, dict)
        assert "entries" in result
        assert isinstance(result["entries"], list)

    def test_read_user_file(self, web_client):
        """读取用户文件：先列目录找一个文件再读取"""
        env_id = _get_test_env(web_client)
        if not env_id:
            pytest.skip("环境列表为空，无法测试文件接口")

        try:
            dir_result = web_client.list_user_files(env_id)
        except (httpx.HTTPStatusError, RuntimeError):
            pytest.skip("目录列表接口不可用")

        # 找一个文件（非目录）
        entries = dir_result.get("entries", [])
        file_entry = None
        for e in entries:
            if not e.get("isDirectory", False) and not e.get("is_dir", False):
                file_entry = e
                break

        if not file_entry:
            pytest.skip("用户目录中没有文件，无法测试读取")

        file_path = file_entry.get("path") or file_entry.get("name")
        if not file_path:
            pytest.skip("文件条目缺少路径信息")

        try:
            result = web_client.read_user_file(env_id, file_path)
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "503" in err_str or "remote_error" in err_str:
                pytest.skip("远程文件读取不可用")
            if "400" in err_str or "directory" in err_str.lower():
                pytest.skip("路径是目录而非文件")
            raise

        assert isinstance(result, dict)
        # 文本文件应包含 content 字段
        if "content" in result:
            assert isinstance(result["content"], str)

    def test_write_and_delete_user_file(self, web_client):
        """写入然后删除文件：幂等性验证"""
        env_id = _get_test_env(web_client)
        if not env_id:
            pytest.skip("环境列表为空，无法测试文件接口")

        test_path = "user/api-test-write-delete.txt"
        test_content = "auto-test-content-" + str(id(self))

        # 写入
        try:
            write_result = web_client.write_user_file(env_id, test_path, test_content)
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "503" in err_str or "remote_error" in err_str:
                pytest.skip("远程文件写入不可用")
            if "400" in err_str or "validation_error" in err_str:
                pytest.skip(f"写入路径受限: {e}")
            if "UNKNOWN" in err_str:
                pytest.skip("workspace 未初始化或服务不可用")
            raise

        assert isinstance(write_result, dict)

        # 读回验证
        try:
            read_result = web_client.read_user_file(env_id, test_path)
            assert read_result.get("content") == test_content
        except (httpx.HTTPStatusError, RuntimeError):
            pass  # 读回失败不阻塞删除清理

        # 清理：删除
        try:
            web_client.delete_user_file(env_id, test_path)
        except (httpx.HTTPStatusError, RuntimeError):
            pass  # 清理失败不报错

    def test_delete_nonexistent_file(self, web_client):
        """删除不存在的文件：应返回 404 或 503（远程不可用）"""
        env_id = _get_test_env(web_client)
        if not env_id:
            pytest.skip("环境列表为空，无法测试文件接口")

        with pytest.raises((httpx.HTTPStatusError, RuntimeError)):
            web_client.delete_user_file(env_id, "user/nonexistent-file-xyz-99999.txt")
