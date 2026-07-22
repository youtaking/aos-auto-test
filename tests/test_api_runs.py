# tests/test_api_runs.py
"""测试运行 API 集成测试"""
import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_api.db")

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


@pytest.mark.asyncio
async def test_list_runs_empty(client):
    """测试空运行列表"""
    resp = await client.get("/api/runs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert isinstance(data["data"], list)
