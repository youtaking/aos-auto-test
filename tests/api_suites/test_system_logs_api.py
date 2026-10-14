# tests/api_suites/test_system_logs_api.py
"""System Logs API 接口测试：功能验证 + 契约验证

覆盖 System Logs API：
- TestSystemLogsListAPI: /api/system/logs（日志源枚举）
- TestSystemLogsSearchAPI: /api/system/logs/search（日志源检索）
- TestSystemLogsDownloadAPI: /api/system/logs/download（投影导出）

认证方式：System API Key（RCS_SYSTEM_API_KEYS 环境变量）
响应格式：{success: true, data: {...}} 包装

新契约（1b80cdfa 起，安全重设计，源码 packages/resources/observer/src/server/{routes,schemas,services}）：
- 不暴露文件路径/原始文件名，客户端只能传服务端枚举的 sourceId（app-YYYY-MM-DD / error-YYYY-MM-DD）
- 单次检索/导出的源上限 50MB，超过返回 413
- sourceId 形状非法（含文件名/路径）返回 400，形状合法但未枚举到返回 404
- download 返回投影后的 JSON Lines（application/x-ndjson），非底层文件字节

数据安全规则：
- 全部只读接口，不创建/修改/删除数据
"""
import json
import time

import httpx
import pytest

from tests.api_contracts.system_logs_schemas import (
    SYSTEM_LOG_SOURCES_RESPONSE,
    SYSTEM_LOG_SEARCH_RESPONSE,
)

# 服务端单次读取上限（源码 MAX_SOURCE_BYTES = 50 * 1024 * 1024）
MAX_SOURCE_BYTES = 50 * 1024 * 1024

# sourceId 形状：app-YYYY-MM-DD / error-YYYY-MM-DD（@fenix/logger LOG_SOURCE_ID_PATTERN）
SOURCE_ID_PATTERN = r"^(?:app|error)-\d{4}-\d{2}-\d{2}$"


# ── 工具函数 ──

def _check_system_access(api_client, max_retries=3):
    """检查是否有 System API 访问权限（使用 system_api_key）"""
    if not api_client._system_api_key:
        return False
    for attempt in range(max_retries):
        try:
            api_client.list_system_log_sources()
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


@pytest.fixture(scope="module")
def _searchable_source(api_client, _system_access):
    """挑一个体积小于服务端上限（50MB）的日志源；没有则 skip

    app 全量日志当日即可超过 50MB，error 独立文件通常较小，故按体积升序取第一个可用源。
    """
    data = api_client.list_system_log_sources()
    small = sorted(
        (s for s in data["sources"] if s["size"] < MAX_SOURCE_BYTES),
        key=lambda s: s["size"],
    )
    if not small:
        pytest.skip("无小于 50MB 的日志源可检索（全部超过服务端单次读取上限）")
    return small[0]


# ── 日志源枚举测试 ──

class TestSystemLogsListAPI:
    """/api/system/logs 日志源枚举接口（System API Key 认证）"""

    def test_list_log_sources(self, api_client, _system_access):
        """枚举日志源：返回 {sources: [...]}"""
        data = api_client.list_system_log_sources()
        api_client.validate_schema(data, SYSTEM_LOG_SOURCES_RESPONSE)
        assert isinstance(data["sources"], list)

    def test_list_log_sources_structure(self, api_client, _system_access):
        """日志源条目结构：id 形状合法，kind/date/size/modifiedAt 齐全，且不含路径信息"""
        import re
        data = api_client.list_system_log_sources()
        if not data["sources"]:
            pytest.skip("日志源列表为空，无法校验条目结构")
        for src in data["sources"]:
            assert re.match(SOURCE_ID_PATTERN, src["id"]), f"sourceId 形状非法: {src['id']}"
            assert src["kind"] in ("app", "error")
            assert isinstance(src["date"], str)
            assert isinstance(src["size"], int) and src["size"] >= 0
            assert isinstance(src["modifiedAt"], str)
            # 协议不应暴露路径 / 原始文件名
            assert "/" not in src["id"] and "\\" not in src["id"]
            assert not src["id"].endswith(".log")

    def test_list_log_sources_unauthorized(self, api_base_url):
        """无认证访问日志源列表：应返回 401"""
        client = httpx.Client(base_url=api_base_url, timeout=10, verify=False)
        try:
            resp = client.get("/api/system/logs")
            assert resp.status_code == 401
        finally:
            client.close()


# ── 日志检索测试 ──

class TestSystemLogsSearchAPI:
    """/api/system/logs/search 日志检索接口（System API Key 认证）"""

    def test_search_logs_basic(self, api_client, _searchable_source):
        """基础检索：用可检索的 sourceId 拉取投影"""
        data = api_client.search_system_logs({"sourceId": _searchable_source["id"]})
        api_client.validate_schema(data, SYSTEM_LOG_SEARCH_RESPONSE)
        assert data["source"]["id"] == _searchable_source["id"]
        assert isinstance(data["entries"], list)
        assert isinstance(data["totalMatches"], int)
        assert data["totalMatches"] >= 0
        assert isinstance(data["truncated"], bool)

    def test_search_logs_with_query(self, api_client, _searchable_source):
        """带关键字检索：q 过滤 + limit 上限生效"""
        data = api_client.search_system_logs(
            {"sourceId": _searchable_source["id"], "q": "error", "limit": 10}
        )
        api_client.validate_schema(data, SYSTEM_LOG_SEARCH_RESPONSE)
        assert data["totalMatches"] >= 0
        assert len(data["entries"]) <= 10

    def test_search_logs_error_only(self, api_client, _searchable_source):
        """仅错误行检索：errorOnly=true"""
        data = api_client.search_system_logs(
            {"sourceId": _searchable_source["id"], "errorOnly": "true"}
        )
        api_client.validate_schema(data, SYSTEM_LOG_SEARCH_RESPONSE)
        assert isinstance(data["entries"], list)

    def test_search_logs_with_limit(self, api_client, _searchable_source):
        """检索带 limit 参数：限制返回条数"""
        data = api_client.search_system_logs(
            {"sourceId": _searchable_source["id"], "limit": 5}
        )
        api_client.validate_schema(data, SYSTEM_LOG_SEARCH_RESPONSE)
        assert len(data["entries"]) <= 5

    def test_search_logs_missing_source_id(self, api_client, _system_access):
        """检索缺少 sourceId 参数：应返回 400 + error 信息"""
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            api_client.search_system_logs({"q": "test"})
        assert exc_info.value.response.status_code == 400
        body = exc_info.value.response.json()
        assert body.get("error") is not None

    def test_search_logs_malformed_source_id(self, api_client, _system_access):
        """检索形状非法的 sourceId（传路径）：应返回 400 VALIDATION_ERROR"""
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            api_client.search_system_logs({"sourceId": "../etc/passwd"})
        assert exc_info.value.response.status_code == 400
        body = exc_info.value.response.json()
        assert body["error"]["code"] == "VALIDATION_ERROR"

    def test_search_logs_nonexistent_source(self, api_client, _system_access):
        """检索形状合法但未枚举到的 sourceId：应返回 404 NOT_FOUND"""
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            api_client.search_system_logs({"sourceId": "app-1999-01-01"})
        assert exc_info.value.response.status_code == 404
        body = exc_info.value.response.json()
        assert body["error"]["code"] == "NOT_FOUND"

    def test_search_logs_empty_source_id(self, api_client, _system_access):
        """检索空 sourceId：应返回 400"""
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            api_client.search_system_logs({"sourceId": ""})
        assert exc_info.value.response.status_code == 400
        body = exc_info.value.response.json()
        assert body.get("error") is not None

    def test_search_logs_invalid_limit(self, api_client, _searchable_source):
        """检索超限 limit（>1000）：应返回 400"""
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            api_client.search_system_logs(
                {"sourceId": _searchable_source["id"], "limit": 9999}
            )
        assert exc_info.value.response.status_code == 400
        body = exc_info.value.response.json()
        assert body.get("error") is not None

    def test_search_logs_extra_large_source_413(self, api_client, _system_access):
        """检索超过 50MB 的日志源：应返回 413 FILE_TOO_LARGE"""
        data = api_client.list_system_log_sources()
        big = [s for s in data["sources"] if s["size"] >= MAX_SOURCE_BYTES]
        if not big:
            pytest.skip("当前无超过 50MB 的日志源，无法验证 413 分支")
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            api_client.search_system_logs({"sourceId": big[0]["id"]})
        assert exc_info.value.response.status_code == 413
        body = exc_info.value.response.json()
        assert body["error"]["code"] == "FILE_TOO_LARGE"

    def test_search_logs_unauthorized(self, api_client, _system_access):
        """无认证检索日志：应返回 401"""
        source_id = api_client.list_system_log_sources()["sources"][0]["id"]
        client = httpx.Client(base_url=api_client.base_url, timeout=10, verify=False)
        try:
            resp = client.get("/api/system/logs/search", params={"sourceId": source_id})
            assert resp.status_code == 401
        finally:
            client.close()


# ── 日志导出测试 ──

class TestSystemLogsDownloadAPI:
    """/api/system/logs/download 日志投影导出接口（System API Key 认证）"""

    def test_download_log_source(self, api_client, _searchable_source):
        """导出日志源：返回 application/x-ndjson，每行为合法 JSON"""
        resp = api_client._system_raw_response(
            "/api/system/logs/download", params={"sourceId": _searchable_source["id"]}
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/x-ndjson")
        assert 'attachment; filename*=' in resp.headers.get("content-disposition", "")
        assert resp.content, "导出内容不应为空"
        # 至少首行可解析为一条投影记录
        first_line = resp.content.decode("utf-8").splitlines()[0]
        entry = json.loads(first_line)
        assert "message" in entry

    def test_download_nonexistent_source(self, api_client, _system_access):
        """导出形状合法但未枚举到的 sourceId：应返回 404 NOT_FOUND"""
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            api_client.download_system_log("app-1999-01-01")
        assert exc_info.value.response.status_code == 404
        body = exc_info.value.response.json()
        assert body["error"]["code"] == "NOT_FOUND"

    def test_download_malformed_source_id(self, api_client, _system_access):
        """导出形状非法的 sourceId：应返回 400 VALIDATION_ERROR"""
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            api_client.download_system_log("../etc/passwd")
        assert exc_info.value.response.status_code == 400
        body = exc_info.value.response.json()
        assert body["error"]["code"] == "VALIDATION_ERROR"

    def test_download_unauthorized(self, api_client, _system_access):
        """无认证导出日志：应返回 401"""
        source_id = api_client.list_system_log_sources()["sources"][0]["id"]
        client = httpx.Client(base_url=api_client.base_url, timeout=10, verify=False)
        try:
            resp = client.get("/api/system/logs/download", params={"sourceId": source_id})
            assert resp.status_code == 401
        finally:
            client.close()
