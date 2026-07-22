# backend/db/config.py
"""数据库连接与会话管理"""
import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from backend.db.base import Base

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://re:re@localhost:5432/auto_test",
)

# SQLite 需要额外的连接参数
if DATABASE_URL.startswith("sqlite"):
    engine = create_async_engine(
        DATABASE_URL, echo=False,
        connect_args={"check_same_thread": False},
    )
else:
    engine = create_async_engine(DATABASE_URL, echo=False)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_async_session():
    """获取异步数据库会话（FastAPI 依赖注入用）"""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """创建所有表（仅开发环境使用，生产环境用 Alembic 迁移）"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """关闭数据库引擎"""
    await engine.dispose()
