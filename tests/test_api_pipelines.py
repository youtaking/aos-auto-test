# tests/test_api_pipelines.py
"""Jenkins Pipeline API 集成测试"""
import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_pipelines.db")

# 标记为无浏览器测试，防止全局 conftest 触发 Playwright 事件循环冲突
pytestmark = pytest.mark.no_browser

from backend.main import app
from backend.db.config import engine
from backend.db.base import Base


@pytest_asyncio.fixture
async def client():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from backend.db.config import async_session
    from backend.db.models import CIConfig
    async with async_session() as db:
        config = CIConfig(auth_token="test-token-123")
        db.add(config)
        await db.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


AUTH_HEADER = {"Authorization": "Bearer test-token-123"}


@pytest.mark.asyncio
async def test_create_pipeline(client):
    """Jenkins 创建 Pipeline 记录"""
    resp = await client.post("/api/pipelines", json={
        "pr_id": 42,
        "pr_title": "feat: add login",
        "commit_sha": "abc12345def",
        "branch": "feature/login",
        "repo_url": "https://github.com/test/repo",
        "author": "dev",
        "target_url": "http://localhost:30001",
        "build_info": {
            "jenkins_url": "http://jenkins:8080/job/PR/1",
            "build_number": 1,
            "docker_image": "pr-env-1:1",
            "rcs_port": 30001,
            "pg_port": 30002,
            "litellm_port": 30003,
        },
    }, headers=AUTH_HEADER)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["id"] > 0
    assert data["data"]["pr_id"] == 42
    assert data["data"]["target_url"] == "http://localhost:30001"
    assert data["data"]["status"] == "building"


@pytest.mark.asyncio
async def test_create_pipeline_unauthorized(client):
    """无 Token 时返回 401"""
    resp = await client.post("/api/pipelines", json={
        "pr_id": 1,
        "commit_sha": "abc",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_update_pipeline_status(client):
    """Jenkins 更新 Pipeline 状态"""
    create_resp = await client.post("/api/pipelines", json={
        "pr_id": 1,
        "commit_sha": "abc123",
    }, headers=AUTH_HEADER)
    pipeline_id = create_resp.json()["data"]["id"]

    resp = await client.put(f"/api/pipelines/{pipeline_id}/status", json={
        "status": "passed",
    }, headers=AUTH_HEADER)
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "passed"


@pytest.mark.asyncio
async def test_submit_results(client):
    """提交测试结果"""
    create_resp = await client.post("/api/pipelines", json={
        "pr_id": 1,
        "commit_sha": "abc123",
    }, headers=AUTH_HEADER)
    pipeline_id = create_resp.json()["data"]["id"]

    report = {
        "created": 1700000000.0,
        "duration": 5.2,
        "summary": {
            "num_tests": 3,
            "num_passed": 2,
            "num_failed": 1,
            "num_skipped": 0,
        },
        "tests": [
            {
                "nodeid": "tests/suites/test_auth.py::test_login",
                "outcome": "passed",
                "duration": 1.5,
            },
            {
                "nodeid": "tests/suites/test_auth.py::test_logout",
                "outcome": "passed",
                "duration": 0.8,
            },
            {
                "nodeid": "tests/api_suites/test_api.py::test_create",
                "outcome": "failed",
                "duration": 2.9,
                "longrepr": "AssertionError: expected 200 got 500",
            },
        ],
    }
    resp = await client.post(
        f"/api/pipelines/{pipeline_id}/results",
        json=report, headers=AUTH_HEADER,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["test_total"] == 3
    assert data["test_passed"] == 2
    assert data["test_failed"] == 1


@pytest.mark.asyncio
async def test_list_pipelines(client):
    """Pipeline 列表查询"""
    await client.post("/api/pipelines", json={
        "pr_id": 1, "commit_sha": "aaa",
    }, headers=AUTH_HEADER)
    await client.post("/api/pipelines", json={
        "pr_id": 2, "commit_sha": "bbb",
    }, headers=AUTH_HEADER)

    resp = await client.get("/api/pipelines")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_get_pipeline(client):
    """Pipeline 详情查询"""
    create_resp = await client.post("/api/pipelines", json={
        "pr_id": 99,
        "commit_sha": "xyz789",
        "target_url": "http://localhost:30010",
        "build_info": {"jenkins_url": "http://jenkins/job/1"},
    }, headers=AUTH_HEADER)
    pipeline_id = create_resp.json()["data"]["id"]

    resp = await client.get(f"/api/pipelines/{pipeline_id}")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["pr_id"] == 99
    assert data["target_url"] == "http://localhost:30010"


@pytest.mark.asyncio
async def test_pipeline_logs_empty(client):
    """Pipeline 日志查询（初始为空）"""
    create_resp = await client.post("/api/pipelines", json={
        "pr_id": 1, "commit_sha": "abc",
    }, headers=AUTH_HEADER)
    pipeline_id = create_resp.json()["data"]["id"]

    resp = await client.get(f"/api/pipelines/{pipeline_id}/logs")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["logs"] == ""
    assert data["pipeline_id"] == pipeline_id
