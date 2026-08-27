# tests/api_suites/test_fs_api.py
"""FS 接口测试：功能验证 + 契约验证

覆盖控制台接口：
- TestFsWebAPI: /web/environments/:id/fs/*（session cookie 认证）

FS 是 workspace 文件系统的完整操作接口，支持 tree/list/read/write/delete/mkdir/rename/batch-delete。
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


class TestFsWebAPI:
    """/web/environments/:id/fs/* 文件系统接口（session cookie 认证）

    特点：
    - GET /:id/fs/tree — 递归文件树
    - GET /:id/fs — 列目录
    - GET /:id/fs/* — 读文件
    - PUT /:id/fs/* — 写文件
    - DELETE /:id/fs/* — 删文件
    - POST /:id/fs/mkdir — 创建目录
    - POST /:id/fs/rename — 重命名
    - DELETE /:id/fs/batch — 批量删除
    """

    def test_get_fs_tree(self, web_client):
        """获取 workspace 文件树：返回 paths 数组"""
        env_id = _get_test_env(web_client)
        if not env_id:
            pytest.skip("环境列表为空，无法测试 FS 接口")

        try:
            result = web_client.get_fs_tree(env_id)
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "404" in err_str or "not_found" in err_str:
                pytest.skip("环境或 workspace 不存在")
            if "503" in err_str or "remote_error" in err_str:
                pytest.skip("远程文件系统不可用")
            if "429" in err_str:
                pytest.skip("限流 429，重试耗尽")
            raise

        assert isinstance(result, dict)
        assert "paths" in result
        assert isinstance(result["paths"], list)

    def test_list_fs_dir(self, web_client):
        """列出 workspace 目录：返回 entries 数组"""
        env_id = _get_test_env(web_client)
        if not env_id:
            pytest.skip("环境列表为空，无法测试 FS 接口")

        try:
            result = web_client.list_fs_dir(env_id)
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "404" in err_str or "not_found" in err_str:
                pytest.skip("环境或 workspace 不存在")
            if "503" in err_str or "remote_error" in err_str:
                pytest.skip("远程文件系统不可用")
            if "429" in err_str:
                pytest.skip("限流 429，重试耗尽")
            raise

        assert isinstance(result, dict)
        assert "entries" in result
        assert isinstance(result["entries"], list)

    def test_read_fs_file(self, web_client):
        """读取 workspace 文件：从 tree 中找一个文件"""
        env_id = _get_test_env(web_client)
        if not env_id:
            pytest.skip("环境列表为空，无法测试 FS 接口")

        try:
            tree = web_client.get_fs_tree(env_id)
        except (httpx.HTTPStatusError, RuntimeError):
            pytest.skip("FS tree 接口不可用")

        paths = tree.get("paths", [])
        # 找一个小文件（排除目录，目录通常以 / 结尾或没有扩展名）
        file_path = None
        for p in paths:
            if "." in p.split("/")[-1]:  # 有扩展名的大概率是文件
                file_path = p
                break

        if not file_path:
            pytest.skip("workspace 中没有文件，无法测试读取")

        try:
            result = web_client.read_fs_file(env_id, file_path)
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "503" in err_str:
                pytest.skip("远程文件读取不可用")
            if "400" in err_str or "directory" in err_str.lower():
                pytest.skip("路径是目录而非文件")
            raise

        assert isinstance(result, dict)
        if "content" in result:
            assert isinstance(result["content"], str)

    def test_write_and_cleanup_fs_file(self, web_client):
        """写入然后删除 workspace 文件"""
        env_id = _get_test_env(web_client)
        if not env_id:
            pytest.skip("环境列表为空，无法测试 FS 接口")

        test_path = "api-test-fs-write.txt"
        test_content = "fs-auto-test-" + str(id(self))

        try:
            result = web_client.write_fs_file(env_id, test_path, test_content)
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "503" in err_str or "remote_error" in err_str:
                pytest.skip("远程文件写入不可用")
            if "400" in err_str:
                pytest.skip(f"写入路径受限: {e}")
            raise

        assert isinstance(result, dict)

        # 回读验证写入内容
        try:
            read_back = web_client.read_fs_file(env_id, test_path)
            assert isinstance(read_back, dict)
            if "content" in read_back:
                assert read_back["content"] == test_content, \
                    f"回读内容不匹配: 期望 {test_content!r}, 实际 {read_back['content']!r}"
        except (httpx.HTTPStatusError, RuntimeError) as e:
            pytest.fail(f"写入后回读验证失败: {e}")

        # 清理
        try:
            web_client.delete_fs_file(env_id, test_path)
        except (httpx.HTTPStatusError, RuntimeError):
            pass

    def test_fs_mkdir(self, web_client):
        """创建 workspace 目录"""
        env_id = _get_test_env(web_client)
        if not env_id:
            pytest.skip("环境列表为空，无法测试 FS 接口")

        test_dir = "api-test-mkdir-dir"

        try:
            result = web_client.fs_mkdir(env_id, test_dir)
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "503" in err_str:
                pytest.skip("远程 mkdir 不可用")
            raise

        assert isinstance(result, dict)
        assert result.get("path") == test_dir

        # 清理
        try:
            web_client.delete_fs_file(env_id, test_dir)
        except (httpx.HTTPStatusError, RuntimeError):
            pass

    def test_fs_rename(self, web_client):
        """重命名 workspace 文件"""
        env_id = _get_test_env(web_client)
        if not env_id:
            pytest.skip("环境列表为空，无法测试 FS 接口")

        old_path = "api-test-rename-old.txt"
        new_path = "api-test-rename-new.txt"

        # 先创建
        try:
            web_client.write_fs_file(env_id, old_path, "rename-test")
        except (httpx.HTTPStatusError, RuntimeError):
            pytest.skip("无法创建测试文件，跳过 rename 测试")

        try:
            result = web_client.fs_rename(env_id, old_path, new_path)
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "503" in err_str:
                pytest.skip("远程 rename 不可用")
            raise

        assert isinstance(result, dict)
        assert result.get("oldPath") == old_path
        assert result.get("newPath") == new_path

        # 清理
        try:
            web_client.delete_fs_file(env_id, new_path)
        except (httpx.HTTPStatusError, RuntimeError):
            pass

    def test_fs_batch_delete(self, web_client):
        """批量删除 workspace 文件"""
        env_id = _get_test_env(web_client)
        if not env_id:
            pytest.skip("环境列表为空，无法测试 FS 接口")

        # 创建两个测试文件
        paths = ["api-test-batch-1.txt", "api-test-batch-2.txt"]
        created = []
        for p in paths:
            try:
                web_client.write_fs_file(env_id, p, "batch-test")
                created.append(p)
            except (httpx.HTTPStatusError, RuntimeError):
                pass

        if not created:
            pytest.skip("无法创建测试文件，跳过批量删除测试")

        try:
            result = web_client.fs_batch_delete(env_id, created)
        except (httpx.HTTPStatusError, RuntimeError) as e:
            err_str = str(e)
            if "503" in err_str:
                pytest.skip("远程批量删除不可用")
            raise

        assert isinstance(result, dict)
        assert "deleted" in result
        assert isinstance(result["deleted"], list)

    def test_delete_nonexistent_fs_file(self, web_client):
        """删除不存在的文件：幂等删除应返回 200 或 404"""
        env_id = _get_test_env(web_client)
        if not env_id:
            pytest.skip("环境列表为空，无法测试 FS 接口")

        try:
            resp = web_client.delete_fs_file(env_id, "nonexistent-file-xyz-99999.txt")
            # 幂等删除：服务端返回 200 success
            assert resp.get("ok") is True or resp.get("success") is True
        except (httpx.HTTPStatusError, RuntimeError) as e:
            # 也可能返回 404（文件不存在）
            assert "404" in str(e) or "503" in str(e), \
                f"预期幂等删除或 404/503，实际: {e}"
