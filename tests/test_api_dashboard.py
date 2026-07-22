# tests/test_api_dashboard.py
"""看板统计 API 测试"""
import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

# 确保测试使用 SQLite
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_dashboard.db")

from backend.main import app
from backend.db.config import engine
from backend.db.base import Base
from backend.api import dashboard

# 临时注册 dashboard 路由（main.py 可能尚未注册，避免与其他子代理冲突）
_prefix = "/api"
if not any(
    getattr(r, "path", "") == f"{_prefix}/dashboard/summary"
    for r in app.routes
):
    app.include_router(dashboard.router, prefix=_prefix, tags=["dashboard"])


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
async def test_dashboard_summary(client):
    """测试看板总览接口"""
    resp = await client.get("/api/dashboard/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "total_cases" in data["data"]
    assert "pass_rate" in data["data"]
    assert "total_runs" in data["data"]
    assert "latest_run_status" in data["data"]


@pytest.mark.asyncio
async def test_dashboard_trend(client):
    """测试看板趋势接口"""
    resp = await client.get("/api/dashboard/trend")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert isinstance(data["data"], list)


@pytest.mark.asyncio
async def test_dashboard_trend_with_limit(client):
    """测试带 limit 参数的趋势接口"""
    resp = await client.get("/api/dashboard/trend?limit=5")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert isinstance(data["data"], list)
    assert len(data["data"]) <= 5
