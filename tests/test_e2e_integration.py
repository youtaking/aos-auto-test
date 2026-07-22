# tests/test_e2e_integration.py
"""端到端集成冒烟测试"""
import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

# 确保测试使用 SQLite
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_e2e.db")

from backend.main import app
from backend.db.config import engine
from backend.db.base import Base


@pytest_asyncio.fixture
async def client():
    """创建测试用 HTTP 客户端（手动建表，ASGI transport 不触发 lifespan）"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    # 清理：删表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_health_check(client):
    """健康检查接口正常"""
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_full_workflow(client):
    """完整流程：创建项目 -> 创建套件 -> 查看看板总览"""
    # 1. 创建项目
    resp = await client.post("/api/projects", json={
        "name": "TestProject", "url": "http://localhost:3001"
    })
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    project_id = resp.json()["data"]["id"]

    # 2. 创建套件
    resp = await client.post(f"/api/projects/{project_id}/suites", json={
        "name": "smoke", "description": "冒烟测试"
    })
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # 3. 查看看板总览
    resp = await client.get("/api/dashboard/summary")
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    assert "total_cases" in resp.json()["data"]
