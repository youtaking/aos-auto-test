# backend/main.py
"""FastAPI 应用入口"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.db.config import init_db, close_db
from backend.api import projects, suites, runs, cases, dashboard
from backend import ws as ws_module


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时建表，关闭时释放连接"""
    await init_db()
    yield
    await close_db()


app = FastAPI(title="AutoTest API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router, prefix="/api", tags=["projects"])
app.include_router(suites.router, prefix="/api", tags=["suites"])
app.include_router(runs.router, prefix="/api", tags=["runs"])
app.include_router(cases.router, prefix="/api", tags=["cases"])
app.include_router(dashboard.router, prefix="/api", tags=["dashboard"])
app.include_router(ws_module.router, tags=["websocket"])


@app.get("/api/health")
async def health():
    return {"success": True, "data": {"status": "ok"}}
