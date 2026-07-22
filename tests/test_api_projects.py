# tests/test_api_projects.py
"""项目与套件 API 集成测试"""
import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

# 确保测试使用 SQLite
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_api.db")

from backend.main import app
from backend.db.config import init_db, engine
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


@pytest.mark.asyncio
async def test_health_check(client):
    """健康检查接口正常"""
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_create_project(client):
    """测试创建项目"""
    resp = await client.post("/api/projects", json={
        "name": "FenixAgent",
        "url": "http://localhost:3001",
        "description": "ACP Agent 平台"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["name"] == "FenixAgent"


@pytest.mark.asyncio
async def test_list_projects(client):
    """测试项目列表"""
    resp = await client.get("/api/projects")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert isinstance(data["data"], list)
