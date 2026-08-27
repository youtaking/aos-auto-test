# tests/api_suites/test_system_logs_api.py
"""System Logs API 接口测试：功能验证 + 契约验证

覆盖 System Logs API：
- TestSystemLogsAPI: /api/system/logs（日志文件列表、搜索、下载）

认证方式：System API Key（RCS_SYSTEM_API_KEYS 环境变量）
响应格式：{success: true, data: {...}} 包装

数据安全规则：
- 全部只读接口，不创建/修改/删除数据
"""
import time
import httpx
import pytest
from tests.api_contracts.system_logs_schemas import (
    SYSTEM_LOG_FILES_RESPONSE,
    SYSTEM_LOG_SEARCH_RESPONSE,
)


# ── 工具函数 ──

def _check_system_access(api_client, max_retries=3):
    """检查是否有 System API 访问权限（使用 system_api_key）"""
    if not api_client._system_api_key:
        return False
    for attempt in range(max_retries):
        try:
            api_client.list_system_log_files()
            return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                time.sleep(2 * (attempt + 1))
                continue
            if e.response.status_code in (401, 403, 404):
                return False
            raise
    return False


@pytest.fixture(scope="module")
def _system_access(api_client):
    """模块级 System API 访问检查 fixture"""
    if not _check_system_access(api_client):
        pytest.skip("System API Key 未配置或 /api/system/logs 不可用，跳过测试")


# ── 日志文件列表测试 ──

class TestSystemLogsListAPI:
    """/api/system/logs 日志文件列表接口（System API Key 认证）"""

    def test_list_log_files(self, api_client, _system_access):
        """获取日志文件列表：返回 {files: [...]}"""
        data = api_client.list_system_log_files()
        api_client.validate_schema(data, SYSTEM_LOG_FILES_RESPONSE)
        assert isinstance(data["files"], list)

    def test_list_log_files_file_structure(self, api_client, _system_access):
        """日志文件条目结构：每个文件包含 name、size 字段"""
        data = api_client.list_system_log_files()
        if not data["files"]:
            pytest.skip("日志文件列表为空，无法校验文件结构")
        first_file = data["files"][0]
        assert "name" in first_file
        assert "size" in first_file
        assert isinstance(first_file["name"], str)
        assert isinstance(first_file["size"], int)
        assert first_file["size"] >= 0

    def test_list_log_files_unauthorized(self, api_base_url):
        """无认证访问日志列表：应返回 401"""
        client = httpx.Client(base_url=api_base_url, timeout=10, verify=False)
        try:
            resp = client.get("/api/system/logs")
            assert resp.status_code == 401
        finally:
            client.close()


# ── 日志搜索测试 ──

class TestSystemLogsSearchAPI:
    """/api/system/logs/search 日志搜索接口（System API Key 认证）"""

    def test_search_logs_basic(self, api_client, _system_access):
        """基础搜索：列出文件 → 选一个较小文件 → 搜索"""
        files_data = api_client.list_system_log_files()
        if not files_data["files"]:
            pytest.skip("无日志文件可搜索")
        # 选择较小的文件（< 10MB），避免触发 413 文件大小限制
        small_files = sorted(files_data["files"], key=lambda f: f["size"])
        file_name = small_files[0]["name"]

        data = api_client.search_system_logs({"file": file_name})
        api_client.validate_schema(data, SYSTEM_LOG_SEARCH_RESPONSE)
        assert isinstance(data["entries"], list)
        assert isinstance(data["totalMatches"], int)
        assert data["totalMatches"] >= 0

    def test_search_logs_with_query(self, api_client, _system_access):
        """带关键字搜索：使用 q 参数过滤"""
        files_data = api_client.list_system_log_files()
        if not files_data["files"]:
            pytest.skip("无日志文件可搜索")
        small_files = sorted(files_data["files"], key=lambda f: f["size"])
        file_name = small_files[0]["name"]

        data = api_client.search_system_logs({"file": file_name, "q": "error", "limit": 10})
        api_client.validate_schema(data, SYSTEM_LOG_SEARCH_RESPONSE)
        assert data["totalMatches"] >= 0
        # 限制条数应生效
        assert len(data["entries"]) <= 10

    def test_search_logs_error_only(self, api_client, _system_access):
        """仅搜索错误日志：errorOnly=true"""
        files_data = api_client.list_system_log_files()
        # 找到一个较小的 error log 文件（< 10MB，避免 413）
        error_files = [f for f in files_data["files"] if f.get("isErrorLog") and f["size"] < 10_000_000]
        if not error_files:
            pytest.skip("无足够小的 error log 文件可搜索")
        file_name = error_files[0]["name"]

        data = api_client.search_system_logs({"file": file_name, "errorOnly": "true"})
        api_client.validate_schema(data, SYSTEM_LOG_SEARCH_RESPONSE)

    def test_search_logs_with_limit(self, api_client, _system_access):
        """搜索带 limit 参数：限制返回条数"""
        files_data = api_client.list_system_log_files()
        if not files_data["files"]:
            pytest.skip("无日志文件可搜索")
        small_files = sorted(files_data["files"], key=lambda f: f["size"])
        file_name = small_files[0]["name"]

        data = api_client.search_system_logs({"file": file_name, "limit": 5})
        api_client.validate_schema(data, SYSTEM_LOG_SEARCH_RESPONSE)
        assert len(data["entries"]) <= 5

    def test_search_logs_missing_file_param(self, api_client, _system_access):
        """搜索缺少 file 参数：应返回 400 或 422 + error 信息"""
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            api_client.search_system_logs({"q": "test"})
        assert exc_info.value.response.status_code in (400, 422)
        body = exc_info.value.response.json()
        assert body.get("success") is False or body.get("error") is not None

    def test_search_logs_nonexistent_file(self, api_client, _system_access):
        """搜索不存在的文件：应返回 404 + NOT_FOUND"""
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            api_client.search_system_logs({"file": "nonexistent_log_file_xyz.log"})
        assert exc_info.value.response.status_code == 404
        body = exc_info.value.response.json()
        assert body.get("success") is False or body.get("error") is not None

    def test_search_logs_empty_file_param(self, api_client, _system_access):
        """搜索空文件名：应返回 400 或 422"""
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            api_client.search_system_logs({"file": ""})
        assert exc_info.value.response.status_code in (400, 422)
        body = exc_info.value.response.json()
        assert body.get("success") is False or body.get("error") is not None

    def test_search_logs_invalid_limit(self, api_client, _system_access):
        """搜索超限 limit（>1000）：应返回 400 或 422"""
        files_data = api_client.list_system_log_files()
        if not files_data["files"]:
            pytest.skip("无日志文件可搜索")
        small_files = sorted(files_data["files"], key=lambda f: f["size"])
        file_name = small_files[0]["name"]

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            api_client.search_system_logs({"file": file_name, "limit": 9999})
        assert exc_info.value.response.status_code in (400, 422)
        body = exc_info.value.response.json()
        assert body.get("success") is False or body.get("error") is not None

    def test_search_logs_unauthorized(self, api_base_url):
        """无认证搜索日志：应返回 401"""
        client = httpx.Client(base_url=api_base_url, timeout=10, verify=False)
        try:
            resp = client.get("/api/system/logs/search", params={"file": "test.log"})
            assert resp.status_code == 401
        finally:
            client.close()


# ── 日志下载测试 ──

class TestSystemLogsDownloadAPI:
    """/api/system/logs/download 日志下载接口（System API Key 认证）"""

    def test_download_log_file(self, api_client, _system_access):
        """下载日志文件：返回 text/plain 流"""
        files_data = api_client.list_system_log_files()
        if not files_data["files"]:
            pytest.skip("无日志文件可下载")
        file_name = files_data["files"][0]["name"]

        content = api_client.download_system_log(file_name)
        assert isinstance(content, bytes)
        assert len(content) > 0

    def test_download_nonexistent_file(self, api_client, _system_access):
        """下载不存在的文件：应返回 404 + NOT_FOUND"""
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            api_client.download_system_log("nonexistent_file_xyz.log")
        assert exc_info.value.response.status_code == 404
        body = exc_info.value.response.json()
        assert body.get("error", {}).get("code") in ("NOT_FOUND", None) or body.get("success") is False

    def test_download_missing_file_param(self, api_client, _system_access):
        """下载缺少 file 参数：应返回 400 或 422 + error 信息"""
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            api_client.download_system_log("")
        assert exc_info.value.response.status_code in (400, 422)
        body = exc_info.value.response.json()
        assert body.get("error") is not None or body.get("success") is False

    def test_download_unauthorized(self, api_base_url):
        """无认证下载日志：应返回 401"""
        client = httpx.Client(base_url=api_base_url, timeout=10, verify=False)
        try:
            resp = client.get("/api/system/logs/download", params={"file": "test.log"})
            assert resp.status_code == 401
        finally:
            client.close()
