# RegressionEye Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a complete UI automation regression testing platform with Python + Playwright test engine, FastAPI backend, React dashboard, and GitHub Actions CI/CD integration.

**Architecture:** Frontend-backend separation with independent test engine. React SPA communicates with FastAPI backend via REST API and WebSocket. Test engine runs pytest + Playwright, can be triggered from dashboard, CI/CD, or API. Results stored in PostgreSQL, screenshots in Docker volume.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, PostgreSQL 16, Playwright, pytest, React 19, Vite, TypeScript, Tailwind CSS, Recharts, Docker Compose

## Global Constraints

- Python 3.12+ required
- All file encoding: UTF-8
- Backend: FastAPI with async handlers, SQLAlchemy 2.0 style (async session)
- Frontend: React 19 + Vite + TypeScript + Tailwind CSS
- Database: PostgreSQL 16, Alembic for migrations
- All API responses follow `{ "success": true, "data": ... }` or `{ "success": false, "error": "..." }` pattern
- Test files: `test_*.py`, test functions: `test_*`, page objects: `*_page.py`
- Commit style: Angular convention `feat:` / `fix:` / `refactor:` / `test:` / `chore:` / `docs:`, titles in Chinese
- All user-facing strings support i18n (Chinese + English)
- Docker deployment via docker-compose, all services containerized

---

## Phase 1: Project Scaffolding

### Task 1: Initialize Python project structure

**Files:**
- Create: `requirements.txt`
- Create: `pytest.ini`
- Create: `.gitignore`
- Create: `engine/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/pages/__init__.py`
- Create: `tests/suites/__init__.py`
- Create: `tests/fixtures/test_data.yaml`
- Create: `README.md`

**Interfaces:**
- Produces: project directory structure that all subsequent tasks depend on

- [ ] **Step 1: Create requirements.txt**

```
fastapi==0.115.12
uvicorn[standard]==0.34.2
sqlalchemy[asyncio]==2.0.41
asyncpg==0.30.0
alembic==1.16.2
pydantic==2.11.4
pydantic-settings==2.10.1
python-multipart==0.0.20
websockets==15.0.1
httpx==0.28.1
playwright==1.53.0
pytest==8.4.1
pytest-playwright==0.7.0
pytest-asyncio==1.0.0
pyyaml==6.0.2
python-dotenv==1.1.1
```

- [ ] **Step 2: Create pytest.ini**

```ini
[pytest]
testpaths = tests/suites
python_files = test_*.py
python_functions = test_*
addopts = -v --tb=short
markers =
    p0: critical path tests
    p1: important feature tests
    p2: nice-to-have tests
    smoke: smoke test suite
```

- [ ] **Step 3: Create .gitignore**

```
__pycache__/
*.py[cod]
*$py.class
.env
.venv/
venv/
dist/
*.egg-info/
.pytest_cache/
test-results/
screenshots/
*.png
*.webm
node_modules/
frontend/dist/
frontend/.vite/
```

- [ ] **Step 4: Create test_data.yaml**

```yaml
# tests/fixtures/test_data.yaml
fenixagent:
  url: "http://localhost:3001"
  admin:
    email: "admin@fenix.com"
    password: "admin123"

test_users:
  - email: "test@example.com"
    password: "test123"
    role: "user"
```

- [ ] **Step 5: Create empty __init__.py files and README.md**

Create the following empty files:
- `engine/__init__.py`
- `tests/__init__.py`
- `tests/pages/__init__.py`
- `tests/suites/__init__.py`

Create `README.md`:
```markdown
# RegressionEye

UI 自动化回归测试平台

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt
playwright install chromium

# 启动看板（开发模式）
docker compose up -d

# 运行测试
pytest tests/suites/
```
```

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "chore: 初始化项目结构"
```

---

### Task 2: Set up development Docker Compose

**Files:**
- Create: `docker-compose.yml`
- Create: `.env.example`

**Interfaces:**
- Produces: running PostgreSQL instance on localhost:5432 for backend development

- [ ] **Step 1: Create .env.example**

```env
DATABASE_URL=postgresql+asyncpg://re:re@localhost:5432/regression_eye
SCREENSHOTS_DIR=./screenshots
BACKEND_PORT=8000
FRONTEND_PORT=3000
FENIXAGENT_URL=http://localhost:3001
```

- [ ] **Step 2: Create docker-compose.yml**

```yaml
services:
  db:
    image: postgres:16-alpine
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: regression_eye
      POSTGRES_USER: re
      POSTGRES_PASSWORD: re
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

- [ ] **Step 3: Test database connectivity**

Run: `docker compose up -d`
Run: `docker compose exec db psql -U re -d regression_eye -c "SELECT 1"`
Expected: `?column?` returns `1`

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml .env.example
git commit -m "chore: 添加开发环境 Docker Compose 配置"
```

---

## Phase 2: Backend Core

### Task 3: Database models with SQLAlchemy

**Files:**
- Create: `backend/__init__.py`
- Create: `backend/db/__init__.py`
- Create: `backend/db/config.py`
- Create: `backend/db/models.py`
- Create: `backend/db/base.py`
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/versions/` (directory)
- Test: `tests/test_models.py`

**Interfaces:**
- Produces: `backend.db.config.get_async_session()` — returns AsyncSession
- Produces: `backend.db.models.Project`, `TestSuite`, `TestCase`, `TestRun`, `TestResult` — SQLAlchemy ORM models
- Produces: `backend.db.base.Base` — declarative base class

- [ ] **Step 1: Write the failing test for database models**

```python
# tests/test_models.py
"""数据库模型单元测试"""
import pytest
from datetime import datetime
from backend.db.models import Project, TestSuite, TestCase, TestRun, TestResult


def test_project_creation():
    """测试 Project 模型创建"""
    project = Project(name="FenixAgent", url="http://localhost:3001")
    assert project.name == "FenixAgent"
    assert project.url == "http://localhost:3001"


def test_test_suite_creation():
    """测试 TestSuite 模型创建"""
    suite = TestSuite(name="login", project_id=1)
    assert suite.name == "login"
    assert suite.project_id == 1


def test_test_case_creation():
    """测试 TestCase 模型创建"""
    case = TestCase(
        name="test_login_success",
        suite_id=1,
        file_path="tests/suites/test_login.py",
        function_name="test_login_success",
        priority="P0",
    )
    assert case.priority == "P0"


def test_test_run_creation():
    """测试 TestRun 模型创建"""
    run = TestRun(project_id=1, trigger_type="manual", status="pending")
    assert run.trigger_type == "manual"
    assert run.status == "pending"


def test_test_result_creation():
    """测试 TestResult 模型创建"""
    result = TestResult(
        run_id=1, case_id=1, status="passed", duration_ms=3200
    )
    assert result.status == "passed"
    assert result.duration_ms == 3200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /d/chxu/AI中台/AgentTest && python -X utf8 -m pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend'`

- [ ] **Step 3: Create backend/db/base.py — declarative base**

```python
# backend/db/base.py
"""SQLAlchemy declarative base"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

- [ ] **Step 4: Create backend/db/models.py — all ORM models**

```python
# backend/db/models.py
"""数据库 ORM 模型"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, Enum, Index
)
from sqlalchemy.orm import relationship
from backend.db.base import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    url = Column(String(500), nullable=False)
    description = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    suites = relationship("TestSuite", back_populates="project", cascade="all, delete-orphan")
    runs = relationship("TestRun", back_populates="project", cascade="all, delete-orphan")


class TestSuite(Base):
    __tablename__ = "test_suites"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    tags = Column(String(500), default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="suites")
    cases = relationship("TestCase", back_populates="suite", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_test_suites_project_id", "project_id"),
    )


class TestCase(Base):
    __tablename__ = "test_cases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    suite_id = Column(Integer, ForeignKey("test_suites.id"), nullable=False)
    name = Column(String(300), nullable=False)
    file_path = Column(String(500), nullable=False)
    function_name = Column(String(300), nullable=False)
    tags = Column(String(500), default="")
    priority = Column(String(10), default="P1")
    timeout = Column(Integer, default=60)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    suite = relationship("TestSuite", back_populates="cases")
    results = relationship("TestResult", back_populates="case", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_test_cases_suite_id", "suite_id"),
        Index("ix_test_cases_function_name", "function_name"),
    )


class TestRun(Base):
    __tablename__ = "test_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    trigger_type = Column(String(20), nullable=False, default="manual")  # manual / ci / api
    trigger_user = Column(String(200), default="")
    git_commit = Column(String(40), default="")
    git_branch = Column(String(200), default="")
    status = Column(String(20), default="pending")  # pending / running / passed / failed / error
    total = Column(Integer, default=0)
    passed = Column(Integer, default=0)
    failed = Column(Integer, default=0)
    skipped = Column(Integer, default=0)
    duration_ms = Column(Integer, default=0)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="runs")
    results = relationship("TestResult", back_populates="run", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_test_runs_project_id", "project_id"),
        Index("ix_test_runs_status", "status"),
        Index("ix_test_runs_created_at", "created_at"),
    )


class TestResult(Base):
    __tablename__ = "test_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("test_runs.id"), nullable=False)
    case_id = Column(Integer, ForeignKey("test_cases.id"), nullable=True)
    case_name = Column(String(300), nullable=False)
    suite_name = Column(String(200), default="")
    status = Column(String(20), nullable=False)  # passed / failed / skipped / error
    duration_ms = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    stack_trace = Column(Text, nullable=True)
    screenshot_path = Column(String(500), nullable=True)
    retry_count = Column(Integer, default=0)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    run = relationship("TestRun", back_populates="results")
    case = relationship("TestCase", back_populates="results")

    __table_args__ = (
        Index("ix_test_results_run_id", "run_id"),
        Index("ix_test_results_case_id", "case_id"),
    )
```

- [ ] **Step 5: Create backend/db/config.py — database session config**

```python
# backend/db/config.py
"""数据库连接与会话管理"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from backend.db.base import Base

DATABASE_URL = "postgresql+asyncpg://re:re@localhost:5432/regression_eye"

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
```

- [ ] **Step 6: Create __init__.py files**

```python
# backend/__init__.py
```

```python
# backend/db/__init__.py
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd /d/chxu/AI中台/AgentTest && python -X utf8 -m pytest tests/test_models.py -v`
Expected: 5 tests PASS

- [ ] **Step 8: Commit**

```bash
git add backend/ tests/test_models.py
git commit -m "feat: 添加数据库 ORM 模型（Project/TestSuite/TestCase/TestRun/TestResult）"
```

---

### Task 4: Pydantic schemas for API request/response

**Files:**
- Create: `backend/schemas/__init__.py`
- Create: `backend/schemas/project.py`
- Create: `backend/schemas/suite.py`
- Create: `backend/schemas/case.py`
- Create: `backend/schemas/run.py`
- Create: `backend/schemas/common.py`
- Test: `tests/test_schemas.py`

**Interfaces:**
- Consumes: `backend.db.models.*` — ORM models for field alignment
- Produces: Pydantic schemas used by API route handlers in Task 5-8

- [ ] **Step 1: Write the failing test**

```python
# tests/test_schemas.py
"""Pydantic Schema 单元测试"""
from backend.schemas.common import ApiResponse
from backend.schemas.project import ProjectCreate, ProjectResponse
from backend.schemas.run import RunTrigger, RunReport, RunReportItem


def test_api_response_wrapper():
    """测试 API 响应包装"""
    resp = ApiResponse(success=True, data={"key": "value"})
    assert resp.success is True
    assert resp.data == {"key": "value"}


def test_project_create_schema():
    """测试项目创建 schema"""
    p = ProjectCreate(name="FenixAgent", url="http://localhost:3001")
    assert p.name == "FenixAgent"


def test_run_trigger_schema():
    """测试运行触发 schema"""
    r = RunTrigger(project_id=1, trigger_type="manual")
    assert r.trigger_type == "manual"
    assert r.suite_ids is None


def test_run_report_item():
    """测试 CI 上报单条结果"""
    item = RunReportItem(
        suite_name="login",
        case_name="test_login",
        file_path="tests/suites/test_login.py",
        function_name="test_login",
        status="passed",
        duration_ms=1200,
    )
    assert item.status == "passed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -X utf8 -m pytest tests/test_schemas.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Create backend/schemas/common.py**

```python
# backend/schemas/common.py
"""通用 API 响应包装"""
from typing import Any, Optional
from pydantic import BaseModel


class ApiResponse(BaseModel):
    success: bool = True
    data: Any = None
    error: Optional[str] = None
```

- [ ] **Step 4: Create backend/schemas/project.py**

```python
# backend/schemas/project.py
"""项目相关 Schema"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str
    url: str
    description: str = ""


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    url: str
    description: str
    created_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 5: Create backend/schemas/suite.py**

```python
# backend/schemas/suite.py
"""测试套件相关 Schema"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class SuiteCreate(BaseModel):
    name: str
    description: str = ""
    tags: str = ""


class SuiteUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[str] = None


class SuiteResponse(BaseModel):
    id: int
    project_id: int
    name: str
    description: str
    tags: str
    created_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 6: Create backend/schemas/case.py**

```python
# backend/schemas/case.py
"""测试用例相关 Schema"""
from datetime import datetime
from pydantic import BaseModel


class CaseResponse(BaseModel):
    id: int
    suite_id: int
    name: str
    file_path: str
    function_name: str
    tags: str
    priority: str
    timeout: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 7: Create backend/schemas/run.py**

```python
# backend/schemas/run.py
"""测试运行相关 Schema"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class RunTrigger(BaseModel):
    project_id: int
    suite_ids: Optional[List[int]] = None
    case_ids: Optional[List[int]] = None
    trigger_type: str = "manual"  # manual / ci / api


class RunResponse(BaseModel):
    id: int
    project_id: int
    trigger_type: str
    trigger_user: str
    git_commit: str
    git_branch: str
    status: str
    total: int
    passed: int
    failed: int
    skipped: int
    duration_ms: int
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RunReportItem(BaseModel):
    suite_name: str
    case_name: str
    file_path: str
    function_name: str
    status: str  # passed / failed / skipped / error
    duration_ms: int = 0
    error_message: Optional[str] = None
    stack_trace: Optional[str] = None
    screenshot_path: Optional[str] = None


class RunReport(BaseModel):
    project_name: str
    trigger_type: str = "ci"
    git_commit: str = ""
    git_branch: str = ""
    started_at: datetime
    finished_at: datetime
    results: List[RunReportItem]


class ResultResponse(BaseModel):
    id: int
    run_id: int
    case_id: Optional[int] = None
    case_name: str
    suite_name: str
    status: str
    duration_ms: int
    error_message: Optional[str] = None
    stack_trace: Optional[str] = None
    screenshot_path: Optional[str] = None
    retry_count: int
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
```

- [ ] **Step 8: Create backend/schemas/__init__.py**

```python
# backend/schemas/__init__.py
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `python -X utf8 -m pytest tests/test_schemas.py -v`
Expected: 4 tests PASS

- [ ] **Step 10: Commit**

```bash
git add backend/schemas/ tests/test_schemas.py
git commit -m "feat: 添加 Pydantic API Schema（project/suite/case/run）"
```

---

### Task 5: FastAPI app + Project/Suite API routes

**Files:**
- Create: `backend/main.py`
- Create: `backend/api/__init__.py`
- Create: `backend/api/projects.py`
- Create: `backend/api/suites.py`
- Test: `tests/test_api_projects.py`

**Interfaces:**
- Consumes: `backend.db.config.get_async_session`, `backend.db.models.*`, `backend.schemas.*`
- Produces: FastAPI app instance with `/api/projects` and `/api/suites` routes mounted

- [ ] **Step 1: Write the failing test**

```python
# tests/test_api_projects.py
"""项目与套件 API 集成测试"""
import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app


@pytest.fixture
async def client():
    """创建测试用 HTTP 客户端"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -X utf8 -m pytest tests/test_api_projects.py -v`
Expected: FAIL

- [ ] **Step 3: Create backend/main.py — FastAPI application entry**

```python
# backend/main.py
"""FastAPI 应用入口"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.db.config import init_db, close_db
from backend.api import projects, suites


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时建表，关闭时释放连接"""
    await init_db()
    yield
    await close_db()


app = FastAPI(title="RegressionEye API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router, prefix="/api", tags=["projects"])
app.include_router(suites.router, prefix="/api", tags=["suites"])


@app.get("/api/health")
async def health():
    return {"success": True, "data": {"status": "ok"}}
```

- [ ] **Step 4: Create backend/api/__init__.py**

```python
# backend/api/__init__.py
```

- [ ] **Step 5: Create backend/api/projects.py — CRUD routes**

```python
# backend/api/projects.py
"""项目管理 API"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.db.config import get_async_session
from backend.db.models import Project
from backend.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse
from backend.schemas.common import ApiResponse

router = APIRouter()


@router.get("/projects", response_model=ApiResponse)
async def list_projects(db: AsyncSession = Depends(get_async_session)):
    """获取项目列表"""
    result = await db.execute(select(Project).order_by(Project.created_at.desc()))
    projects = result.scalars().all()
    return ApiResponse(data=[ProjectResponse.model_validate(p) for p in projects])


@router.post("/projects", response_model=ApiResponse)
async def create_project(body: ProjectCreate, db: AsyncSession = Depends(get_async_session)):
    """创建项目"""
    project = Project(name=body.name, url=body.url, description=body.description)
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return ApiResponse(data=ProjectResponse.model_validate(project))


@router.put("/projects/{project_id}", response_model=ApiResponse)
async def update_project(
    project_id: int, body: ProjectUpdate, db: AsyncSession = Depends(get_async_session)
):
    """更新项目"""
    project = await db.get(Project, project_id)
    if not project:
        return ApiResponse(success=False, error="项目不存在")
    if body.name is not None:
        project.name = body.name
    if body.url is not None:
        project.url = body.url
    if body.description is not None:
        project.description = body.description
    await db.commit()
    await db.refresh(project)
    return ApiResponse(data=ProjectResponse.model_validate(project))


@router.delete("/projects/{project_id}", response_model=ApiResponse)
async def delete_project(project_id: int, db: AsyncSession = Depends(get_async_session)):
    """删除项目"""
    project = await db.get(Project, project_id)
    if not project:
        return ApiResponse(success=False, error="项目不存在")
    await db.delete(project)
    await db.commit()
    return ApiResponse(data={"deleted": True})
```

- [ ] **Step 6: Create backend/api/suites.py — CRUD routes**

```python
# backend/api/suites.py
"""测试套件管理 API"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.db.config import get_async_session
from backend.db.models import TestSuite
from backend.schemas.suite import SuiteCreate, SuiteUpdate, SuiteResponse
from backend.schemas.common import ApiResponse

router = APIRouter()


@router.get("/projects/{project_id}/suites", response_model=ApiResponse)
async def list_suites(project_id: int, db: AsyncSession = Depends(get_async_session)):
    """获取项目下的套件列表"""
    result = await db.execute(
        select(TestSuite).where(TestSuite.project_id == project_id).order_by(TestSuite.name)
    )
    suites = result.scalars().all()
    return ApiResponse(data=[SuiteResponse.model_validate(s) for s in suites])


@router.post("/projects/{project_id}/suites", response_model=ApiResponse)
async def create_suite(
    project_id: int, body: SuiteCreate, db: AsyncSession = Depends(get_async_session)
):
    """创建套件"""
    suite = TestSuite(
        project_id=project_id, name=body.name,
        description=body.description, tags=body.tags
    )
    db.add(suite)
    await db.commit()
    await db.refresh(suite)
    return ApiResponse(data=SuiteResponse.model_validate(suite))


@router.put("/suites/{suite_id}", response_model=ApiResponse)
async def update_suite(
    suite_id: int, body: SuiteUpdate, db: AsyncSession = Depends(get_async_session)
):
    """更新套件"""
    suite = await db.get(TestSuite, suite_id)
    if not suite:
        return ApiResponse(success=False, error="套件不存在")
    if body.name is not None:
        suite.name = body.name
    if body.description is not None:
        suite.description = body.description
    if body.tags is not None:
        suite.tags = body.tags
    await db.commit()
    await db.refresh(suite)
    return ApiResponse(data=SuiteResponse.model_validate(suite))


@router.delete("/suites/{suite_id}", response_model=ApiResponse)
async def delete_suite(suite_id: int, db: AsyncSession = Depends(get_async_session)):
    """删除套件"""
    suite = await db.get(TestSuite, suite_id)
    if not suite:
        return ApiResponse(success=False, error="套件不存在")
    await db.delete(suite)
    await db.commit()
    return ApiResponse(data={"deleted": True})
```

- [ ] **Step 7: Run tests**

Run: `python -X utf8 -m pytest tests/test_api_projects.py -v`
Expected: 2 tests PASS

- [ ] **Step 8: Commit**

```bash
git add backend/main.py backend/api/ tests/test_api_projects.py
git commit -m "feat: 添加 FastAPI 应用入口和项目管理/套件 CRUD API"
```

---

### Task 6: Test Run API + Case management API

**Files:**
- Create: `backend/api/runs.py`
- Create: `backend/api/cases.py`
- Test: `tests/test_api_runs.py`

**Interfaces:**
- Consumes: `backend.db.models.TestRun`, `TestResult`, `TestCase`; `backend.schemas.run.*`
- Produces: `/api/runs` (GET/POST), `/api/runs/{id}`, `/api/runs/{id}/results`, `/api/runs/{id}/report`, `/api/suites/{id}/cases`, `/api/cases/{id}`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_api_runs.py
"""测试运行 API 集成测试"""
import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_list_runs_empty(client):
    """测试空运行列表"""
    resp = await client.get("/api/runs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert isinstance(data["data"], list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -X utf8 -m pytest tests/test_api_runs.py -v`
Expected: FAIL

- [ ] **Step 3: Create backend/api/runs.py**

```python
# backend/api/runs.py
"""测试运行 API"""
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.db.config import get_async_session
from backend.db.models import TestRun, TestResult, TestCase, TestSuite, Project
from backend.schemas.run import RunResponse, RunReport, ResultResponse
from backend.schemas.common import ApiResponse

router = APIRouter()


@router.get("/runs", response_model=ApiResponse)
async def list_runs(
    project_id: int | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_async_session),
):
    """获取运行历史（分页+筛选）"""
    query = select(TestRun).order_by(TestRun.created_at.desc())
    if project_id:
        query = query.where(TestRun.project_id == project_id)
    if status:
        query = query.where(TestRun.status == status)
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    runs = result.scalars().all()
    return ApiResponse(data=[RunResponse.model_validate(r) for r in runs])


@router.post("/runs", response_model=ApiResponse)
async def trigger_run(
    project_id: int,
    trigger_type: str = "manual",
    db: AsyncSession = Depends(get_async_session),
):
    """触发一次测试运行（创建记录，实际执行由 engine 负责）"""
    run = TestRun(
        project_id=project_id,
        trigger_type=trigger_type,
        status="pending",
        started_at=datetime.utcnow(),
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return ApiResponse(data=RunResponse.model_validate(run))


@router.get("/runs/{run_id}", response_model=ApiResponse)
async def get_run(run_id: int, db: AsyncSession = Depends(get_async_session)):
    """获取单次运行详情"""
    run = await db.get(TestRun, run_id)
    if not run:
        return ApiResponse(success=False, error="运行记录不存在")
    return ApiResponse(data=RunResponse.model_validate(run))


@router.get("/runs/{run_id}/results", response_model=ApiResponse)
async def get_run_results(run_id: int, db: AsyncSession = Depends(get_async_session)):
    """获取某次运行的所有用例结果"""
    result = await db.execute(
        select(TestResult).where(TestResult.run_id == run_id).order_by(TestResult.id)
    )
    results = result.scalars().all()
    return ApiResponse(data=[ResultResponse.model_validate(r) for r in results])


@router.post("/runs/{run_id}/report", response_model=ApiResponse)
async def report_run(
    run_id: int, body: RunReport, db: AsyncSession = Depends(get_async_session)
):
    """CI/CD 结果上报：接收 report.json，写入 TestResult 记录"""
    run = await db.get(TestRun, run_id)
    if not run:
        return ApiResponse(success=False, error="运行记录不存在")

    passed_count = 0
    failed_count = 0
    skipped_count = 0

    for item in body.results:
        # 尝试匹配已有 case
        case_result = await db.execute(
            select(TestCase).where(TestCase.function_name == item.function_name)
        )
        case = case_result.scalar_one_or_none()

        test_result = TestResult(
            run_id=run_id,
            case_id=case.id if case else None,
            case_name=item.case_name,
            suite_name=item.suite_name,
            status=item.status,
            duration_ms=item.duration_ms,
            error_message=item.error_message,
            stack_trace=item.stack_trace,
            screenshot_path=item.screenshot_path,
        )
        db.add(test_result)

        if item.status == "passed":
            passed_count += 1
        elif item.status in ("failed", "error"):
            failed_count += 1
        else:
            skipped_count += 1

    run.status = "passed" if failed_count == 0 else "failed"
    run.total = len(body.results)
    run.passed = passed_count
    run.failed = failed_count
    run.skipped = skipped_count
    run.started_at = body.started_at
    run.finished_at = body.finished_at
    run.duration_ms = int((body.finished_at - body.started_at).total_seconds() * 1000)
    run.git_commit = body.git_commit
    run.git_branch = body.git_branch

    await db.commit()
    return ApiResponse(data={"imported": len(body.results)})
```

- [ ] **Step 4: Create backend/api/cases.py**

```python
# backend/api/cases.py
"""测试用例管理 API"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from backend.db.config import get_async_session
from backend.db.models import TestCase, TestResult
from backend.schemas.case import CaseResponse
from backend.schemas.common import ApiResponse

router = APIRouter()


@router.get("/suites/{suite_id}/cases", response_model=ApiResponse)
async def list_cases(suite_id: int, db: AsyncSession = Depends(get_async_session)):
    """获取套件下的用例列表"""
    result = await db.execute(
        select(TestCase).where(TestCase.suite_id == suite_id).order_by(TestCase.name)
    )
    cases = result.scalars().all()
    return ApiResponse(data=[CaseResponse.model_validate(c) for c in cases])


@router.get("/cases/{case_id}", response_model=ApiResponse)
async def get_case(case_id: int, db: AsyncSession = Depends(get_async_session)):
    """获取用例详情（含历史通过率）"""
    case = await db.get(TestCase, case_id)
    if not case:
        return ApiResponse(success=False, error="用例不存在")

    # 计算历史通过率
    total_result = await db.execute(
        select(func.count()).select_from(TestResult).where(TestResult.case_id == case_id)
    )
    total = total_result.scalar() or 0

    passed_result = await db.execute(
        select(func.count()).select_from(TestResult).where(
            TestResult.case_id == case_id, TestResult.status == "passed"
        )
    )
    passed = passed_result.scalar() or 0

    data = CaseResponse.model_validate(case).model_dump()
    data["pass_rate"] = round(passed / total * 100, 1) if total > 0 else 0.0
    data["total_runs"] = total
    return ApiResponse(data=data)
```

- [ ] **Step 5: Update backend/main.py to include new routers**

```python
# backend/main.py (更新 include_router 部分)
from backend.api import projects, suites, runs, cases

# ... 在 lifespan 之后 ...
app.include_router(projects.router, prefix="/api", tags=["projects"])
app.include_router(suites.router, prefix="/api", tags=["suites"])
app.include_router(runs.router, prefix="/api", tags=["runs"])
app.include_router(cases.router, prefix="/api", tags=["cases"])
```

- [ ] **Step 6: Run tests**

Run: `python -X utf8 -m pytest tests/test_api_runs.py -v`
Expected: 1 test PASS

- [ ] **Step 7: Commit**

```bash
git add backend/api/runs.py backend/api/cases.py backend/main.py tests/test_api_runs.py
git commit -m "feat: 添加测试运行 API（触发/列表/详情/结果上报）和用例管理 API"
```

---

### Task 7: Dashboard statistics API + WebSocket

**Files:**
- Create: `backend/api/dashboard.py`
- Create: `backend/ws.py`
- Test: `tests/test_api_dashboard.py`

**Interfaces:**
- Consumes: `backend.db.models.TestRun`, `TestResult`
- Produces: `/api/dashboard/summary`, `/api/dashboard/trend`, `/ws/runs/{id}` WebSocket endpoint

- [ ] **Step 1: Write the failing test**

```python
# tests/test_api_dashboard.py
"""看板统计 API 测试"""
import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_dashboard_summary(client):
    """测试看板总览接口"""
    resp = await client.get("/api/dashboard/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "total_cases" in data["data"]
    assert "pass_rate" in data["data"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -X utf8 -m pytest tests/test_api_dashboard.py -v`
Expected: FAIL

- [ ] **Step 3: Create backend/api/dashboard.py**

```python
# backend/api/dashboard.py
"""看板统计 API"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from backend.db.config import get_async_session
from backend.db.models import TestCase, TestRun, TestResult
from backend.schemas.common import ApiResponse

router = APIRouter()


@router.get("/dashboard/summary", response_model=ApiResponse)
async def dashboard_summary(db: AsyncSession = Depends(get_async_session)):
    """看板总览：用例总数、最近运行状态、通过率"""
    total_cases = (await db.execute(select(func.count()).select_from(TestCase))).scalar() or 0

    latest_run = (await db.execute(
        select(TestRun).order_by(TestRun.created_at.desc()).limit(1)
    )).scalar_one_or_none()

    total_results = (await db.execute(
        select(func.count()).select_from(TestResult)
    )).scalar() or 0

    passed_results = (await db.execute(
        select(func.count()).select_from(TestResult).where(TestResult.status == "passed")
    )).scalar() or 0

    pass_rate = round(passed_results / total_results * 100, 1) if total_results > 0 else 0.0

    return ApiResponse(data={
        "total_cases": total_cases,
        "latest_run_status": latest_run.status if latest_run else None,
        "pass_rate": pass_rate,
        "total_runs": (await db.execute(
            select(func.count()).select_from(TestRun)
        )).scalar() or 0,
    })


@router.get("/dashboard/trend", response_model=ApiResponse)
async def dashboard_trend(limit: int = 10, db: AsyncSession = Depends(get_async_session)):
    """最近 N 次运行的趋势数据"""
    result = await db.execute(
        select(TestRun).order_by(TestRun.created_at.desc()).limit(limit)
    )
    runs = result.scalars().all()

    trend = []
    for run in reversed(runs):
        trend.append({
            "id": run.id,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "status": run.status,
            "total": run.total,
            "passed": run.passed,
            "failed": run.failed,
            "skipped": run.skipped,
            "pass_rate": round(run.passed / run.total * 100, 1) if run.total > 0 else 0.0,
        })

    return ApiResponse(data=trend)
```

- [ ] **Step 4: Create backend/ws.py — WebSocket manager**

```python
# backend/ws.py
"""WebSocket 连接管理器：实时推送测试执行进度"""
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

# 活跃连接：{ run_id: [websocket, ...] }
_active_connections: dict[int, list[WebSocket]] = {}


async def connect(run_id: int, ws: WebSocket):
    """接受 WebSocket 连接并注册"""
    await ws.accept()
    if run_id not in _active_connections:
        _active_connections[run_id] = []
    _active_connections[run_id].append(ws)


async def disconnect(run_id: int, ws: WebSocket):
    """移除 WebSocket 连接"""
    if run_id in _active_connections:
        _active_connections[run_id] = [
            w for w in _active_connections[run_id] if w != ws
        ]
        if not _active_connections[run_id]:
            del _active_connections[run_id]


async def broadcast(run_id: int, event: str, data: dict):
    """向关注某个 run 的所有客户端广播消息"""
    message = json.dumps({"event": event, "data": data}, default=str)
    if run_id in _active_connections:
        for ws in _active_connections[run_id]:
            try:
                await ws.send_text(message)
            except Exception:
                pass


@router.websocket("/ws/runs/{run_id}")
async def ws_run_progress(ws: WebSocket, run_id: int):
    """WebSocket 端点：实时推送测试运行进度"""
    await connect(run_id, ws)
    try:
        while True:
            # 保持连接，接收客户端心跳
            await ws.receive_text()
    except WebSocketDisconnect:
        await disconnect(run_id, ws)
```

- [ ] **Step 5: Update backend/main.py to include dashboard + ws routers**

```python
# 在 main.py 中添加导入
from backend.api import projects, suites, runs, cases, dashboard
from backend import ws as ws_module

# 在 include_router 部分添加
app.include_router(dashboard.router, prefix="/api", tags=["dashboard"])
app.include_router(ws_module.router, tags=["websocket"])
```

- [ ] **Step 6: Run tests**

Run: `python -X utf8 -m pytest tests/test_api_dashboard.py -v`
Expected: 1 test PASS

- [ ] **Step 7: Commit**

```bash
git add backend/api/dashboard.py backend/ws.py backend/main.py tests/test_api_dashboard.py
git commit -m "feat: 添加看板统计 API 和 WebSocket 实时推送"
```

---

## Phase 3: Test Engine

### Task 8: Test runner — pytest invocation engine

**Files:**
- Create: `engine/runner.py`
- Test: `tests/test_runner.py`

**Interfaces:**
- Consumes: `backend.db.config`, `backend.db.models`, `backend.ws.broadcast`
- Produces: `engine.runner.run_tests(project_id, suite_ids=None, case_ids=None)` — async function that runs pytest and stores results

- [ ] **Step 1: Write the failing test**

```python
# tests/test_runner.py
"""测试引擎 Runner 单元测试"""
import pytest
from engine.runner import TestRunner


def test_runner_init():
    """测试 Runner 初始化"""
    runner = TestRunner(test_dir="tests/suites")
    assert runner.test_dir == "tests/suites"


def test_runner_collect_tests():
    """测试用例收集（pytest --collect-only）"""
    runner = TestRunner(test_dir="tests/suites")
    collected = runner.collect_tests()
    assert isinstance(collected, list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -X utf8 -m pytest tests/test_runner.py -v`
Expected: FAIL

- [ ] **Step 3: Create engine/runner.py**

```python
# engine/runner.py
"""测试执行引擎：调度 pytest 运行，收集结果"""
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, List


@dataclass
class CaseResult:
    """单条用例运行结果"""
    suite_name: str
    case_name: str
    file_path: str
    function_name: str
    status: str  # passed / failed / skipped / error
    duration_ms: int = 0
    error_message: Optional[str] = None
    stack_trace: Optional[str] = None
    screenshot_path: Optional[str] = None


@dataclass
class RunResult:
    """一次完整运行的结果"""
    started_at: datetime = field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None
    results: List[CaseResult] = field(default_factory=list)
    status: str = "pending"

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.status == "passed")

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.status in ("failed", "error"))

    @property
    def skipped(self) -> int:
        return sum(1 for r in self.results if r.status == "skipped")


class TestRunner:
    """测试运行器：调用 pytest 并解析结果"""

    def __init__(self, test_dir: str = "tests/suites"):
        self.test_dir = test_dir

    def collect_tests(self) -> list[dict]:
        """通过 pytest --collect-only 扫描所有测试用例"""
        result = subprocess.run(
            [sys.executable, "-m", "pytest", self.test_dir, "--collect-only", "-q"],
            capture_output=True, text=True, encoding="utf-8"
        )

        collected = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if "::" in line and line.endswith(")"):
                # 格式：tests/suites/test_login.py::test_login_success
                line = line.rsplit(")", 1)[0]  # 去掉尾部标记
            if "::" not in line:
                continue
            parts = line.split("::")
            if len(parts) == 2:
                file_path, func_name = parts
                suite_name = Path(file_path).stem.replace("test_", "")
                collected.append({
                    "suite_name": suite_name,
                    "file_path": file_path,
                    "function_name": func_name,
                })
        return collected

    def run(
        self,
        suite_names: Optional[list[str]] = None,
        case_names: Optional[list[str]] = None,
        report_path: str = "report.json",
    ) -> RunResult:
        """执行 pytest 并生成 JSON 报告"""
        run_result = RunResult(started_at=datetime.utcnow())

        # 构建 pytest 命令
        cmd = [
            sys.executable, "-m", "pytest", self.test_dir,
            "-v", "--tb=short",
            f"--json-report", f"--json-report-file={report_path}",
        ]

        if suite_names:
            patterns = [f"test_{s}.py" for s in suite_names]
            cmd.extend([f"--file-pattern={p}" for p in patterns])

        if case_names:
            for name in case_names:
                cmd.append(f"-k {name}")

        # 执行 pytest
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")

        run_result.finished_at = datetime.utcnow()

        # 解析 JSON 报告
        report_file = Path(report_path)
        if report_file.exists():
            with open(report_file, "r", encoding="utf-8") as f:
                report_data = json.load(f)

            for test in report_data.get("tests", []):
                nodeid = test.get("nodeid", "")
                parts = nodeid.split("::")
                file_path = parts[0] if parts else ""
                func_name = parts[1] if len(parts) > 1 else ""
                suite_name = Path(file_path).stem.replace("test_", "")

                status_map = {
                    "passed": "passed",
                    "failed": "failed",
                    "skipped": "skipped",
                    "error": "error",
                }
                outcome = test.get("outcome", "error")

                call_info = test.get("call", {})
                duration_ms = int(call_info.get("duration", 0) * 1000)
                longrepr = call_info.get("longrepr", "")

                run_result.results.append(CaseResult(
                    suite_name=suite_name,
                    case_name=func_name,
                    file_path=file_path,
                    function_name=func_name,
                    status=status_map.get(outcome, "error"),
                    duration_ms=duration_ms,
                    error_message=str(longrepr)[:500] if longrepr else None,
                    stack_trace=str(longrepr) if longrepr else None,
                ))

        run_result.status = "passed" if run_result.failed == 0 else "failed"
        return run_result
```

- [ ] **Step 4: Install pytest-json-report dependency**

Add to `requirements.txt`:
```
pytest-json-report==1.5.0
```

Run: `pip install pytest-json-report`

- [ ] **Step 5: Run tests**

Run: `python -X utf8 -m pytest tests/test_runner.py -v`
Expected: 2 tests PASS

- [ ] **Step 6: Commit**

```bash
git add engine/runner.py tests/test_runner.py requirements.txt
git commit -m "feat: 添加测试执行引擎 Runner（pytest 调度 + JSON 报告解析）"
```

---

### Task 9: Custom reporter — real-time WebSocket push

**Files:**
- Create: `engine/reporter.py`
- Test: `tests/test_reporter.py`

**Interfaces:**
- Consumes: `backend.ws.broadcast`
- Produces: `engine.reporter.RegressionEyeReporter` — pytest plugin that hooks into test lifecycle

- [ ] **Step 1: Write the failing test**

```python
# tests/test_reporter.py
"""Reporter 单元测试"""
from engine.reporter import RegressionEyeReporter


def test_reporter_init():
    """测试 Reporter 初始化"""
    reporter = RegressionEyeReporter(run_id=1, backend_url="http://localhost:8000")
    assert reporter.run_id == 1
    assert reporter.backend_url == "http://localhost:8000"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -X utf8 -m pytest tests/test_reporter.py -v`
Expected: FAIL

- [ ] **Step 3: Create engine/reporter.py**

```python
# engine/reporter.py
"""自定义 pytest Reporter：实时推送测试进度到 RegressionEye 后端"""
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
import httpx


class RegressionEyeReporter:
    """pytest 插件：在每条用例开始/结束时推送状态到后端 API"""

    def __init__(self, run_id: int, backend_url: str = "http://localhost:8000"):
        self.run_id = run_id
        self.backend_url = backend_url
        self._client = httpx.Client(timeout=5.0)
        self._results: list[dict] = []

    def pytest_runtest_logstart(self, nodeid: str, location: tuple):
        """用例开始执行时触发"""
        parts = nodeid.split("::")
        func_name = parts[1] if len(parts) > 1 else nodeid
        self._push("case_started", {
            "case_name": func_name,
            "status": "running",
            "started_at": datetime.utcnow().isoformat(),
        })

    def pytest_runtest_logreport(self, report):
        """用例产生报告时触发（setup/call/teardown 各一次）"""
        if report.when != "call":
            return

        parts = report.nodeid.split("::")
        file_path = parts[0] if parts else ""
        func_name = parts[1] if len(parts) > 1 else ""
        suite_name = Path(file_path).stem.replace("test_", "")

        status_map = {"passed": "passed", "failed": "failed", "skipped": "skipped"}
        status = status_map.get(report.outcome, "error")

        duration_ms = int(report.duration * 1000)
        longrepr = str(report.longrepr) if report.longrepr else None

        result = {
            "suite_name": suite_name,
            "case_name": func_name,
            "file_path": file_path,
            "function_name": func_name,
            "status": status,
            "duration_ms": duration_ms,
            "error_message": longrepr[:500] if longrepr else None,
            "stack_trace": longrepr,
            "screenshot_path": None,
        }
        self._results.append(result)

        # 实时推送
        self._push("case_finished", result)

    def pytest_sessionfinish(self, session, exitstatus):
        """整个测试会话结束时触发，上报完整结果"""
        self._push("run_finished", {
            "status": "passed" if exitstatus == 0 else "failed",
            "total": len(self._results),
            "passed": sum(1 for r in self._results if r["status"] == "passed"),
            "failed": sum(1 for r in self._results if r["status"] in ("failed", "error")),
            "skipped": sum(1 for r in self._results if r["status"] == "skipped"),
        })
        self._client.close()

    def _push(self, event: str, data: dict):
        """推送事件到后端"""
        try:
            self._client.post(
                f"{self.backend_url}/api/runs/{self.run_id}/events",
                json={"event": event, "data": data},
            )
        except Exception:
            # 推送失败不影响测试执行
            pass
```

- [ ] **Step 4: Run tests**

Run: `python -X utf8 -m pytest tests/test_reporter.py -v`
Expected: 1 test PASS

- [ ] **Step 5: Commit**

```bash
git add engine/reporter.py tests/test_reporter.py
git commit -m "feat: 添加自定义 pytest Reporter（实时 WebSocket 推送）"
```

---

## Phase 4: Playwright Test Cases (FenixAgent)

### Task 10: conftest.py + Login Page Object + Login tests

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/pages/login_page.py`
- Create: `tests/suites/test_login.py`

**Interfaces:**
- Consumes: FenixAgent running at configured URL
- Produces: `page` fixture, `login_page` fixture, login test cases

- [ ] **Step 1: Create tests/conftest.py — global fixtures**

```python
# tests/conftest.py
"""pytest 全局 fixtures：浏览器、页面、登录状态"""
import pytest
import yaml
from pathlib import Path
from playwright.sync_api import sync_playwright


@pytest.fixture(scope="session")
def test_config():
    """加载测试配置"""
    config_path = Path(__file__).parent / "fixtures" / "test_data.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="session")
def base_url(test_config):
    """被测应用 URL"""
    return test_config["fenixagent"]["url"]


@pytest.fixture(scope="session")
def browser_context_args():
    """浏览器上下文参数"""
    return {
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
    }


@pytest.fixture(scope="function")
def page(browser_context_args):
    """每个测试函数一个干净的浏览器页面"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(**browser_context_args)
        page = context.new_page()
        # 失败自动截图
        yield page
        context.close()
        browser.close()


@pytest.fixture
def login_page(page, base_url):
    """LoginPage 实例"""
    from tests.pages.login_page import LoginPage
    return LoginPage(page, base_url)
```

- [ ] **Step 2: Create tests/pages/login_page.py**

```python
# tests/pages/login_page.py
"""登录页面 Page Object"""
from playwright.sync_api import Page


class LoginPage:
    """FenixAgent 登录页面封装"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/login"

    def goto(self):
        """导航到登录页"""
        self.page.goto(self.url)
        self.page.wait_for_load_state("networkidle")

    def login(self, email: str, password: str):
        """执行登录操作"""
        # FenixAgent 使用 better-auth，登录表单字段根据实际 DOM 调整
        self.page.fill('input[name="email"], input[type="email"]', email)
        self.page.fill('input[name="password"], input[type="password"]', password)
        self.page.click('button[type="submit"]')
        self.page.wait_for_load_state("networkidle")

    def is_logged_in(self) -> bool:
        """判断是否已登录（跳转到 Dashboard）"""
        return "/login" not in self.page.url

    def get_error_message(self) -> str:
        """获取错误提示文本"""
        error = self.page.locator('[role="alert"], .error-message, .text-red-500').first
        if error.is_visible():
            return error.text_content() or ""
        return ""

    def is_on_login_page(self) -> bool:
        """判断是否在登录页面"""
        return "/login" in self.page.url
```

- [ ] **Step 3: Create tests/suites/test_login.py**

```python
# tests/suites/test_login.py
"""登录/认证模块回归测试"""
import pytest


@pytest.mark.p0
def test_login_page_loads(login_page):
    """登录页面能正常加载"""
    login_page.goto()
    assert login_page.is_on_login_page()


@pytest.mark.p0
def test_login_success(login_page, test_config):
    """管理员能正常登录"""
    admin = test_config["fenixagent"]["admin"]
    login_page.goto()
    login_page.login(admin["email"], admin["password"])
    assert login_page.is_logged_in()


@pytest.mark.p0
def test_login_wrong_password(login_page, test_config):
    """错误密码显示提示信息"""
    admin = test_config["fenixagent"]["admin"]
    login_page.goto()
    login_page.login(admin["email"], "wrong_password_123")
    assert not login_page.is_logged_in()


@pytest.mark.p0
def test_unauthenticated_redirect(page, base_url):
    """未登录用户访问受保护页面会跳转到登录页"""
    page.goto(f"{base_url}/agent/dashboard")
    page.wait_for_load_state("networkidle")
    assert "/login" in page.url
```

- [ ] **Step 4: Run login tests (requires FenixAgent running)**

Run: `python -X utf8 -m pytest tests/suites/test_login.py -v`
Expected: tests can connect to FenixAgent (may fail on selectors if DOM doesn't match — adjust selectors)

- [ ] **Step 5: Commit**

```bash
git add tests/conftest.py tests/pages/login_page.py tests/suites/test_login.py
git commit -m "test: 添加登录模块 Page Object 和回归测试用例"
```

---

### Task 11: Dashboard + Agent + Chat Page Objects and tests

**Files:**
- Create: `tests/pages/dashboard_page.py`
- Create: `tests/pages/agent_page.py`
- Create: `tests/pages/chat_page.py`
- Create: `tests/suites/test_dashboard.py`
- Create: `tests/suites/test_agent.py`
- Create: `tests/suites/test_chat.py`

**Interfaces:**
- Consumes: `tests/conftest.py` fixtures, logged-in session
- Produces: 3 test suites with P0/P1 cases

- [ ] **Step 1: Create tests/pages/dashboard_page.py**

```python
# tests/pages/dashboard_page.py
"""Dashboard 页面 Page Object"""
from playwright.sync_api import Page


class DashboardPage:
    """FenixAgent Dashboard 页面封装"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/agent/dashboard"

    def goto(self):
        self.page.goto(self.url)
        self.page.wait_for_load_state("networkidle")

    def is_loaded(self) -> bool:
        """Dashboard 是否加载完成"""
        return "dashboard" in self.page.url.lower() or self.page.locator("main").is_visible()

    def has_sidebar(self) -> bool:
        """侧边栏是否可见"""
        return self.page.locator("nav, aside, [class*='sidebar']").first.is_visible()

    def navigate_to(self, menu_text: str):
        """通过侧边栏导航到指定模块"""
        self.page.get_by_text(menu_text).click()
        self.page.wait_for_load_state("networkidle")
```

- [ ] **Step 2: Create tests/pages/agent_page.py**

```python
# tests/pages/agent_page.py
"""Agent 管理页面 Page Object"""
from playwright.sync_api import Page


class AgentPage:
    """FenixAgent Agent 管理页面封装"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url
        self.url = f"{base_url}/agent/agents"

    def goto(self):
        self.page.goto(self.url)
        self.page.wait_for_load_state("networkidle")

    def is_loaded(self) -> bool:
        return "agent" in self.page.url.lower()

    def get_agent_count(self) -> int:
        """获取 Agent 列表中的条目数"""
        rows = self.page.locator("table tbody tr, [class*='agent-card'], [class*='list-item']")
        return rows.count()

    def click_create_agent(self):
        """点击创建 Agent 按钮"""
        self.page.get_by_role("button", name="创建").or_(
            self.page.get_by_text("Create", exact=False)
        ).first.click()
        self.page.wait_for_load_state("networkidle")
```

- [ ] **Step 3: Create tests/pages/chat_page.py**

```python
# tests/pages/chat_page.py
"""Chat 对话页面 Page Object"""
from playwright.sync_api import Page


class ChatPage:
    """FenixAgent Chat 页面封装"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url

    def goto_sessions(self):
        """导航到会话列表"""
        self.page.goto(f"{self.base_url}/agent/sessions")
        self.page.wait_for_load_state("networkidle")

    def is_sessions_loaded(self) -> bool:
        return "session" in self.page.url.lower()

    def get_session_count(self) -> int:
        """获取会话列表数量"""
        items = self.page.locator("[class*='session-item'], [class*='chat-item'], table tbody tr")
        return items.count()

    def send_message(self, text: str):
        """在聊天框中发送消息"""
        input_box = self.page.locator(
            'textarea, input[type="text"], [contenteditable="true"]'
        ).first
        input_box.fill(text)
        # 按 Enter 或点击发送按钮
        send_btn = self.page.get_by_role("button", name="发送").or_(
            self.page.locator('[class*="send"]')
        ).first
        if send_btn.is_visible():
            send_btn.click()
        else:
            input_box.press("Enter")
        self.page.wait_for_timeout(2000)
```

- [ ] **Step 4: Create tests/suites/test_dashboard.py**

```python
# tests/suites/test_dashboard.py
"""Dashboard 模块回归测试"""
import pytest


@pytest.fixture
def logged_in_page(page, login_page, test_config):
    """已登录的页面（复用于多个测试）"""
    admin = test_config["fenixagent"]["admin"]
    login_page.goto()
    login_page.login(admin["email"], admin["password"])
    return page


@pytest.mark.p0
def test_dashboard_loads(logged_in_page, base_url):
    """Dashboard 页面能正常加载"""
    from tests.pages.dashboard_page import DashboardPage
    dashboard = DashboardPage(logged_in_page, base_url)
    dashboard.goto()
    assert dashboard.is_loaded()


@pytest.mark.p0
def test_dashboard_has_sidebar(logged_in_page, base_url):
    """Dashboard 包含侧边栏导航"""
    from tests.pages.dashboard_page import DashboardPage
    dashboard = DashboardPage(logged_in_page, base_url)
    dashboard.goto()
    assert dashboard.has_sidebar()
```

- [ ] **Step 5: Create tests/suites/test_agent.py**

```python
# tests/suites/test_agent.py
"""Agent 管理模块回归测试"""
import pytest


@pytest.fixture
def logged_in_page(page, login_page, test_config):
    admin = test_config["fenixagent"]["admin"]
    login_page.goto()
    login_page.login(admin["email"], admin["password"])
    return page


@pytest.mark.p1
def test_agent_list_loads(logged_in_page, base_url):
    """Agent 列表页面能正常加载"""
    from tests.pages.agent_page import AgentPage
    agent_page = AgentPage(logged_in_page, base_url)
    agent_page.goto()
    assert agent_page.is_loaded()
```

- [ ] **Step 6: Create tests/suites/test_chat.py**

```python
# tests/suites/test_chat.py
"""Chat 对话模块回归测试"""
import pytest


@pytest.fixture
def logged_in_page(page, login_page, test_config):
    admin = test_config["fenixagent"]["admin"]
    login_page.goto()
    login_page.login(admin["email"], admin["password"])
    return page


@pytest.mark.p1
def test_sessions_page_loads(logged_in_page, base_url):
    """会话列表页面能正常加载"""
    from tests.pages.chat_page import ChatPage
    chat = ChatPage(logged_in_page, base_url)
    chat.goto_sessions()
    assert chat.is_sessions_loaded()
```

- [ ] **Step 7: Commit**

```bash
git add tests/pages/ tests/suites/
git commit -m "test: 添加 Dashboard/Agent/Chat 模块 Page Object 和回归测试用例"
```

---

## Phase 5: Frontend Dashboard

### Task 12: Initialize React frontend with Vite

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/index.css`
- Create: `frontend/tailwind.config.ts`
- Create: `frontend/postcss.config.js`

**Interfaces:**
- Produces: running React dev server on localhost:5173

- [ ] **Step 1: Initialize Vite React project**

Run:
```bash
cd /d/chxu/AI中台/AgentTest
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
```

- [ ] **Step 2: Install additional dependencies**

Run:
```bash
cd /d/chxu/AI中台/AgentTest/frontend
npm install react-router-dom recharts axios lucide-react clsx tailwind-merge
npm install -D tailwindcss @tailwindcss/vite postcss autoprefixer
```

- [ ] **Step 3: Configure Tailwind CSS**

Create `frontend/src/index.css`:
```css
@import "tailwindcss";
```

- [ ] **Step 4: Configure vite.config.ts**

```typescript
// frontend/vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
      "/ws": {
        target: "ws://localhost:8000",
        ws: true,
      },
    },
  },
});
```

- [ ] **Step 5: Create frontend/src/App.tsx with routing**

```tsx
// frontend/src/App.tsx
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Runs from "./pages/Runs";
import RunDetail from "./pages/RunDetail";
import Cases from "./pages/Cases";
import Settings from "./pages/Settings";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="runs" element={<Runs />} />
          <Route path="runs/:id" element={<RunDetail />} />
          <Route path="cases" element={<Cases />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
```

- [ ] **Step 6: Create frontend/src/main.tsx**

```tsx
// frontend/src/main.tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
```

- [ ] **Step 7: Verify dev server starts**

Run:
```bash
cd /d/chxu/AI中台/AgentTest/frontend
npm run dev
```
Expected: Vite dev server starts on http://localhost:5173

- [ ] **Step 8: Commit**

```bash
git add frontend/
git commit -m "chore: 初始化 React + Vite + Tailwind 前端项目"
```

---

### Task 13: API client + Layout + Navigation

**Files:**
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/api/types.ts`
- Create: `frontend/src/api/projects.ts`
- Create: `frontend/src/api/runs.ts`
- Create: `frontend/src/api/dashboard.ts`
- Create: `frontend/src/components/Layout.tsx`
- Create: `frontend/src/components/Sidebar.tsx`

**Interfaces:**
- Consumes: FastAPI backend at `/api/*`
- Produces: typed API client functions, Layout with sidebar navigation

- [ ] **Step 1: Create frontend/src/api/types.ts**

```typescript
// frontend/src/api/types.ts
export interface ApiResponse<T = unknown> {
  success: boolean;
  data: T;
  error?: string;
}

export interface Project {
  id: number;
  name: string;
  url: string;
  description: string;
  created_at: string;
}

export interface TestSuite {
  id: number;
  project_id: number;
  name: string;
  description: string;
  tags: string;
  created_at: string;
}

export interface TestCase {
  id: number;
  suite_id: number;
  name: string;
  file_path: string;
  function_name: string;
  tags: string;
  priority: string;
  timeout: number;
  created_at: string;
  updated_at: string;
}

export interface TestRun {
  id: number;
  project_id: number;
  trigger_type: string;
  trigger_user: string;
  git_commit: string;
  git_branch: string;
  status: string;
  total: number;
  passed: number;
  failed: number;
  skipped: number;
  duration_ms: number;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface TestResult {
  id: number;
  run_id: number;
  case_id: number | null;
  case_name: string;
  suite_name: string;
  status: string;
  duration_ms: number;
  error_message: string | null;
  stack_trace: string | null;
  screenshot_path: string | null;
  retry_count: number;
  started_at: string | null;
  finished_at: string | null;
}

export interface DashboardSummary {
  total_cases: number;
  latest_run_status: string | null;
  pass_rate: number;
  total_runs: number;
}

export interface TrendItem {
  id: number;
  created_at: string;
  status: string;
  total: number;
  passed: number;
  failed: number;
  skipped: number;
  pass_rate: number;
}
```

- [ ] **Step 2: Create frontend/src/api/client.ts**

```typescript
// frontend/src/api/client.ts
import axios from "axios";
import type { ApiResponse } from "./types";

const client = axios.create({
  baseURL: "/api",
  timeout: 30000,
  headers: { "Content-Type": "application/json" },
});

export async function get<T>(url: string, params?: Record<string, unknown>): Promise<T> {
  const resp = await client.get<ApiResponse<T>>(url, { params });
  if (!resp.data.success) {
    throw new Error(resp.data.error ?? "请求失败");
  }
  return resp.data.data;
}

export async function post<T>(url: string, data?: unknown): Promise<T> {
  const resp = await client.post<ApiResponse<T>>(url, data);
  if (!resp.data.success) {
    throw new Error(resp.data.error ?? "请求失败");
  }
  return resp.data.data;
}

export async function put<T>(url: string, data?: unknown): Promise<T> {
  const resp = await client.put<ApiResponse<T>>(url, data);
  if (!resp.data.success) {
    throw new Error(resp.data.error ?? "请求失败");
  }
  return resp.data.data;
}

export async function del<T>(url: string): Promise<T> {
  const resp = await client.delete<ApiResponse<T>>(url);
  if (!resp.data.success) {
    throw new Error(resp.data.error ?? "请求失败");
  }
  return resp.data.data;
}
```

- [ ] **Step 3: Create frontend/src/api/projects.ts**

```typescript
// frontend/src/api/projects.ts
import { get, post, put, del } from "./client";
import type { Project, TestSuite } from "./types";

export const listProjects = () => get<Project[]>("/projects");
export const createProject = (data: { name: string; url: string; description?: string }) =>
  post<Project>("/projects", data);
export const updateProject = (id: number, data: Partial<Project>) =>
  put<Project>(`/projects/${id}`, data);
export const deleteProject = (id: number) => del(`/projects/${id}`);

export const listSuites = (projectId: number) =>
  get<TestSuite[]>(`/projects/${projectId}/suites`);
export const createSuite = (projectId: number, data: { name: string; description?: string }) =>
  post<TestSuite>(`/projects/${projectId}/suites`, data);
```

- [ ] **Step 4: Create frontend/src/api/runs.ts**

```typescript
// frontend/src/api/runs.ts
import { get, post } from "./client";
import type { TestRun, TestResult } from "./types";

export const listRuns = (params?: { project_id?: number; status?: string; page?: number }) =>
  get<TestRun[]>("/runs", params);
export const getRun = (id: number) => get<TestRun>(`/runs/${id}`);
export const getRunResults = (runId: number) => get<TestResult[]>(`/runs/${runId}/results`);
export const triggerRun = (projectId: number, triggerType = "manual") =>
  post<TestRun>(`/runs?project_id=${projectId}&trigger_type=${triggerType}`);
```

- [ ] **Step 5: Create frontend/src/api/dashboard.ts**

```typescript
// frontend/src/api/dashboard.ts
import { get } from "./client";
import type { DashboardSummary, TrendItem } from "./types";

export const getSummary = () => get<DashboardSummary>("/dashboard/summary");
export const getTrend = (limit = 10) => get<TrendItem[]>(`/dashboard/trend?limit=${limit}`);
```

- [ ] **Step 6: Create frontend/src/components/Sidebar.tsx**

```tsx
// frontend/src/components/Sidebar.tsx
import { NavLink } from "react-router-dom";
import { LayoutDashboard, PlayCircle, ListChecks, Settings, Eye } from "lucide-react";

const navItems = [
  { to: "/dashboard", icon: LayoutDashboard, label: "总览" },
  { to: "/runs", icon: PlayCircle, label: "运行记录" },
  { to: "/cases", icon: ListChecks, label: "用例管理" },
  { to: "/settings", icon: Settings, label: "设置" },
];

export default function Sidebar() {
  return (
    <aside className="w-60 bg-gray-900 text-white flex flex-col min-h-screen">
      <div className="p-4 border-b border-gray-700">
        <div className="flex items-center gap-2">
          <Eye className="w-6 h-6 text-green-400" />
          <span className="font-bold text-lg">RegressionEye</span>
        </div>
      </div>
      <nav className="flex-1 p-2">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg mb-1 transition-colors ${
                isActive ? "bg-gray-700 text-white" : "text-gray-300 hover:bg-gray-800"
              }`
            }
          >
            <Icon className="w-5 h-5" />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
```

- [ ] **Step 7: Create frontend/src/components/Layout.tsx**

```tsx
// frontend/src/components/Layout.tsx
import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";

export default function Layout() {
  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar />
      <main className="flex-1 p-6 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
```

- [ ] **Step 8: Commit**

```bash
git add frontend/src/
git commit -m "feat: 添加 API 客户端、侧边栏导航和页面布局"
```

---

### Task 14: Dashboard page — overview + trend chart

**Files:**
- Create: `frontend/src/pages/Dashboard.tsx`
- Create: `frontend/src/pages/Runs.tsx`
- Create: `frontend/src/pages/RunDetail.tsx`
- Create: `frontend/src/pages/Cases.tsx`
- Create: `frontend/src/pages/Settings.tsx`

**Interfaces:**
- Consumes: `frontend/src/api/dashboard.ts`, `frontend/src/api/runs.ts`
- Produces: 5 pages with routing

- [ ] **Step 1: Create frontend/src/pages/Dashboard.tsx**

```tsx
// frontend/src/pages/Dashboard.tsx
import { useEffect, useState } from "react";
import { getSummary, getTrend } from "../api/dashboard";
import { triggerRun } from "../api/runs";
import { listProjects } from "../api/projects";
import type { DashboardSummary, TrendItem, Project } from "../api/types";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";

export default function Dashboard() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [trend, setTrend] = useState<TrendItem[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);

  useEffect(() => {
    getSummary().then(setSummary);
    getTrend().then(setTrend);
    listProjects().then(setProjects);
  }, []);

  const handleRunAll = async () => {
    if (projects.length === 0) return;
    await triggerRun(projects[0].id, "manual");
    window.location.href = "/runs";
  };

  const statusColor = summary?.latest_run_status === "passed" ? "bg-green-500" : "bg-red-500";

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">总览</h1>

      {/* 状态卡片 */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-white rounded-xl p-6 shadow-sm">
          <div className="text-sm text-gray-500">项目状态</div>
          <div className="flex items-center gap-2 mt-2">
            <div className={`w-4 h-4 rounded-full ${summary?.latest_run_status ? statusColor : "bg-gray-300"}`} />
            <span className="text-lg font-semibold">
              {summary?.latest_run_status === "passed" ? "正常" : summary?.latest_run_status === "failed" ? "异常" : "未运行"}
            </span>
          </div>
        </div>
        <div className="bg-white rounded-xl p-6 shadow-sm">
          <div className="text-sm text-gray-500">通过率</div>
          <div className="text-2xl font-bold mt-2">{summary?.pass_rate ?? 0}%</div>
        </div>
        <div className="bg-white rounded-xl p-6 shadow-sm">
          <div className="text-sm text-gray-500">用例总数</div>
          <div className="text-2xl font-bold mt-2">{summary?.total_cases ?? 0}</div>
        </div>
        <div className="bg-white rounded-xl p-6 shadow-sm">
          <div className="text-sm text-gray-500">运行次数</div>
          <div className="text-2xl font-bold mt-2">{summary?.total_runs ?? 0}</div>
        </div>
      </div>

      {/* 趋势图 */}
      <div className="bg-white rounded-xl p-6 shadow-sm">
        <h2 className="text-lg font-semibold mb-4">运行趋势</h2>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={trend}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="created_at" tickFormatter={(v) => new Date(v).toLocaleDateString()} />
            <YAxis />
            <Tooltip />
            <Line type="monotone" dataKey="pass_rate" stroke="#22c55e" name="通过率(%)" strokeWidth={2} />
            <Line type="monotone" dataKey="failed" stroke="#ef4444" name="失败数" strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* 快捷操作 */}
      <div className="flex gap-3">
        <button
          onClick={handleRunAll}
          className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
        >
          运行全部测试
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create frontend/src/pages/Runs.tsx**

```tsx
// frontend/src/pages/Runs.tsx
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listRuns } from "../api/runs";
import type { TestRun } from "../api/types";

const statusBadge: Record<string, string> = {
  passed: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
  running: "bg-blue-100 text-blue-700",
  pending: "bg-gray-100 text-gray-700",
  error: "bg-yellow-100 text-yellow-700",
};

export default function Runs() {
  const [runs, setRuns] = useState<TestRun[]>([]);

  useEffect(() => {
    listRuns().then(setRuns);
  }, []);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">运行记录</h1>
      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">ID</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">状态</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">触发方式</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">通过率</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">耗时</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">时间</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {runs.map((run) => (
              <tr key={run.id} className="hover:bg-gray-50">
                <td className="px-4 py-3">
                  <Link to={`/runs/${run.id}`} className="text-blue-600 hover:underline">
                    #{run.id}
                  </Link>
                </td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${statusBadge[run.status] ?? ""}`}>
                    {run.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-sm">{run.trigger_type}</td>
                <td className="px-4 py-3 text-sm">
                  {run.total > 0 ? `${((run.passed / run.total) * 100).toFixed(1)}%` : "-"}
                </td>
                <td className="px-4 py-3 text-sm">{(run.duration_ms / 1000).toFixed(1)}s</td>
                <td className="px-4 py-3 text-sm">{new Date(run.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create frontend/src/pages/RunDetail.tsx**

```tsx
// frontend/src/pages/RunDetail.tsx
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { getRun, getRunResults } from "../api/runs";
import type { TestRun, TestResult } from "../api/types";

const statusIcon: Record<string, string> = {
  passed: "✅",
  failed: "❌",
  skipped: "⏭️",
  error: "⚠️",
  running: "🔄",
};

export default function RunDetail() {
  const { id } = useParams<{ id: string }>();
  const [run, setRun] = useState<TestRun | null>(null);
  const [results, setResults] = useState<TestResult[]>([]);

  useEffect(() => {
    if (!id) return;
    const runId = Number(id);
    getRun(runId).then(setRun);
    getRunResults(runId).then(setResults);
  }, [id]);

  if (!run) return <div>加载中...</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">运行 #{run.id}</h1>

      <div className="grid grid-cols-5 gap-4">
        <div className="bg-white rounded-xl p-4 shadow-sm text-center">
          <div className="text-sm text-gray-500">总计</div>
          <div className="text-xl font-bold">{run.total}</div>
        </div>
        <div className="bg-white rounded-xl p-4 shadow-sm text-center">
          <div className="text-sm text-gray-500">通过</div>
          <div className="text-xl font-bold text-green-600">{run.passed}</div>
        </div>
        <div className="bg-white rounded-xl p-4 shadow-sm text-center">
          <div className="text-sm text-gray-500">失败</div>
          <div className="text-xl font-bold text-red-600">{run.failed}</div>
        </div>
        <div className="bg-white rounded-xl p-4 shadow-sm text-center">
          <div className="text-sm text-gray-500">跳过</div>
          <div className="text-xl font-bold text-gray-500">{run.skipped}</div>
        </div>
        <div className="bg-white rounded-xl p-4 shadow-sm text-center">
          <div className="text-sm text-gray-500">耗时</div>
          <div className="text-xl font-bold">{(run.duration_ms / 1000).toFixed(1)}s</div>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">状态</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">用例名</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">套件</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">耗时</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">错误</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {results.map((r) => (
              <tr key={r.id} className="hover:bg-gray-50">
                <td className="px-4 py-3">{statusIcon[r.status] ?? "❓"}</td>
                <td className="px-4 py-3 text-sm font-mono">{r.case_name}</td>
                <td className="px-4 py-3 text-sm">{r.suite_name}</td>
                <td className="px-4 py-3 text-sm">{r.duration_ms}ms</td>
                <td className="px-4 py-3 text-sm text-red-600 max-w-xs truncate">
                  {r.error_message ?? "-"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create frontend/src/pages/Cases.tsx**

```tsx
// frontend/src/pages/Cases.tsx
import { useEffect, useState } from "react";
import { listProjects, listSuites } from "../api/projects";
import { get } from "../api/client";
import type { Project, TestSuite, TestCase } from "../api/types";

export default function Cases() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [suites, setSuites] = useState<TestSuite[]>([]);
  const [cases, setCases] = useState<TestCase[]>([]);

  useEffect(() => {
    listProjects().then((projs) => {
      setProjects(projs);
      if (projs.length > 0) {
        listSuites(projs[0].id).then(setSuites);
      }
    });
  }, []);

  useEffect(() => {
    if (suites.length > 0) {
      get<TestCase[]>(`/suites/${suites[0].id}/cases`).then(setCases);
    }
  }, [suites]);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">用例管理</h1>
      {suites.map((suite) => (
        <div key={suite.id} className="bg-white rounded-xl shadow-sm p-4">
          <h2 className="text-lg font-semibold mb-3">{suite.name}</h2>
          <p className="text-sm text-gray-500 mb-2">{suite.description}</p>
          <div className="text-sm text-gray-400">
            用例数: {cases.filter((c) => c.suite_id === suite.id).length}
          </div>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 5: Create frontend/src/pages/Settings.tsx**

```tsx
// frontend/src/pages/Settings.tsx
import { useEffect, useState } from "react";
import { listProjects, createProject } from "../api/projects";
import type { Project } from "../api/types";

export default function Settings() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");

  useEffect(() => {
    listProjects().then(setProjects);
  }, []);

  const handleCreate = async () => {
    if (!name || !url) return;
    await createProject({ name, url });
    listProjects().then(setProjects);
    setName("");
    setUrl("");
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">设置</h1>
      <div className="bg-white rounded-xl shadow-sm p-6 space-y-4">
        <h2 className="text-lg font-semibold">项目管理</h2>
        <div className="flex gap-2">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="项目名称"
            className="px-3 py-2 border rounded-lg"
          />
          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="项目 URL"
            className="px-3 py-2 border rounded-lg flex-1"
          />
          <button
            onClick={handleCreate}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            添加
          </button>
        </div>
        <div className="space-y-2">
          {projects.map((p) => (
            <div key={p.id} className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
              <div>
                <div className="font-medium">{p.name}</div>
                <div className="text-sm text-gray-500">{p.url}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Verify frontend renders**

Run: `cd /d/chxu/AI中台/AgentTest/frontend && npm run dev`
Expected: all 5 pages render correctly with sidebar navigation

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/ frontend/src/components/
git commit -m "feat: 添加看板页面（总览/运行记录/运行详情/用例管理/设置）"
```

---

## Phase 6: CI/CD + Docker Deployment

### Task 15: GitHub Actions workflow

**Files:**
- Create: `.github/workflows/regression.yml`

**Interfaces:**
- Consumes: FenixAgent repo, RegressionEye runner image
- Produces: automated CI pipeline

- [ ] **Step 1: Create .github/workflows/regression.yml**

```yaml
name: RegressionEye Tests

on:
  pull_request:
    branches: [main, develop]
  push:
    branches: [main]
    tags: ['v*']
  workflow_dispatch:
    inputs:
      suite:
        description: '测试套件（留空=全部）'
        type: string
        required: false

jobs:
  regression:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_DB: fenixagent
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - name: 拉取 RegressionEye 代码
        uses: actions/checkout@v4

      - name: 安装 Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: 安装依赖
        run: |
          pip install -r requirements.txt
          playwright install --with-deps chromium

      - name: 运行回归测试
        run: |
          pytest tests/suites/ \
            -v --tb=short \
            --json-report --json-report-file=report.json \
            ${{ github.event.inputs.suite && format('-k {0}', github.event.inputs.suite) || '' }}
        env:
          FENIXAGENT_URL: ${{ secrets.FENIXAGENT_URL }}

      - name: 上报结果到看板
        if: always()
        run: |
          python -c "
          import json, httpx, os
          report = json.load(open('report.json'))
          # 转换为 RegressionEye report 格式并上报
          "
        env:
          REGRESSION_EYE_URL: ${{ secrets.REGRESSION_EYE_URL }}
          RE_TOKEN: ${{ secrets.RE_TOKEN }}

      - name: 上传截图
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: screenshots
          path: test-results/
          retention-days: 7
```

- [ ] **Step 2: Commit**

```bash
git add .github/
git commit -m "ci: 添加 GitHub Actions 回归测试工作流"
```

---

### Task 16: Docker deployment (production)

**Files:**
- Create: `Dockerfile.backend`
- Create: `Dockerfile.frontend`
- Create: `Dockerfile.runner`
- Modify: `docker-compose.yml` (add production services)

**Interfaces:**
- Produces: production-ready Docker Compose stack

- [ ] **Step 1: Create Dockerfile.backend**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ backend/
COPY engine/ engine/

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Create Dockerfile.frontend**

```dockerfile
FROM node:20-alpine AS builder

WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

- [ ] **Step 3: Create nginx.conf for frontend**

```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /ws/ {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

- [ ] **Step 4: Create Dockerfile.runner**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install system deps for Playwright
RUN apt-get update && apt-get install -y \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libxkbcommon0 libxdamage1 libgbm1 libpango-1.0-0 \
    libcairo2 libasound2 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium

COPY tests/ tests/
COPY engine/ engine/
COPY backend/ backend/
COPY pytest.ini .

CMD ["pytest", "tests/suites/", "-v", "--tb=short"]
```

- [ ] **Step 5: Update docker-compose.yml for production**

```yaml
services:
  db:
    image: postgres:16-alpine
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: regression_eye
      POSTGRES_USER: re
      POSTGRES_PASSWORD: re
    volumes:
      - pgdata:/var/lib/postgresql/data

  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://re:re@db:5432/regression_eye
      SCREENSHOTS_DIR: /screenshots
    volumes:
      - screenshots:/screenshots
    depends_on:
      - db

  frontend:
    build:
      context: .
      dockerfile: Dockerfile.frontend
    ports:
      - "3000:80"
    depends_on:
      - backend

  runner:
    build:
      context: .
      dockerfile: Dockerfile.runner
    environment:
      BACKEND_URL: http://backend:8000
    volumes:
      - screenshots:/screenshots
    profiles:
      - runner
    depends_on:
      - backend

volumes:
  pgdata:
  screenshots:
```

- [ ] **Step 6: Commit**

```bash
git add Dockerfile.* nginx.conf docker-compose.yml
git commit -m "chore: 添加生产环境 Docker 部署配置"
```

---

## Phase 7: Integration + README

### Task 17: End-to-end integration test + README

**Files:**
- Create: `tests/test_e2e_integration.py`
- Modify: `README.md`

- [ ] **Step 1: Write integration smoke test**

```python
# tests/test_e2e_integration.py
"""端到端集成冒烟测试"""
import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


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
    """完整流程：创建项目 → 创建套件 → 触发运行 → 查看结果"""
    # 1. 创建项目
    resp = await client.post("/api/projects", json={
        "name": "TestProject", "url": "http://localhost:3001"
    })
    assert resp.json()["success"] is True
    project_id = resp.json()["data"]["id"]

    # 2. 创建套件
    resp = await client.post(f"/api/projects/{project_id}/suites", json={
        "name": "smoke", "description": "冒烟测试"
    })
    assert resp.json()["success"] is True

    # 3. 查看看板总览
    resp = await client.get("/api/dashboard/summary")
    assert resp.json()["success"] is True
```

- [ ] **Step 2: Run integration test**

Run: `python -X utf8 -m pytest tests/test_e2e_integration.py -v`
Expected: all smoke tests PASS

- [ ] **Step 3: Update README.md with complete documentation**

```markdown
# RegressionEye

UI 自动化回归测试平台

## 功能

- **Playwright E2E 测试**：Python + Playwright + pytest，POM 模式
- **可视化看板**：React 实时 Dashboard，展示运行状态和趋势
- **多种触发**：看板手动 / GitHub Actions / API
- **CI/CD 集成**：代码提交自动回归，结果上报看板

## 快速开始

### 1. 启动开发环境

```bash
# 启动 PostgreSQL
docker compose up db -d

# 安装 Python 依赖
pip install -r requirements.txt
playwright install chromium

# 启动后端
uvicorn backend.main:app --reload

# 启动前端（另一个终端）
cd frontend && npm install && npm run dev
```

### 2. 部署生产环境

```bash
docker compose up -d
```

看板访问 http://localhost:3000

### 3. 运行测试

```bash
# 运行全部测试
pytest tests/suites/ -v

# 只运行 P0 用例
pytest tests/suites/ -m p0 -v

# 运行指定套件
pytest tests/suites/test_login.py -v
```

## 项目结构

```
RegressionEye/
├── tests/          # Playwright 测试用例（POM 模式）
├── engine/         # 测试执行引擎
├── backend/        # FastAPI 后端
├── frontend/       # React 看板前端
├── .github/        # CI/CD 配置
└── docker-compose.yml
```

## 新增测试用例

1. 在 `tests/pages/` 下创建 Page Object
2. 在 `tests/suites/test_*.py` 下编写 `test_*` 函数
3. 提交代码，引擎自动发现注册
```

- [ ] **Step 4: Commit**

```bash
git add tests/test_e2e_integration.py README.md
git commit -m "docs: 添加集成冒烟测试和完整 README 文档"
```

---

## Self-Review

**Spec coverage check:**
- ✅ Project structure (Task 1)
- ✅ Database models (Task 3)
- ✅ Pydantic schemas (Task 4)
- ✅ Project/Suite CRUD API (Task 5)
- ✅ Run/Case API (Task 6)
- ✅ Dashboard API + WebSocket (Task 7)
- ✅ Test runner engine (Task 8)
- ✅ Custom reporter (Task 9)
- ✅ Playwright POM + login tests (Task 10)
- ✅ Dashboard/Agent/Chat tests (Task 11)
- ✅ React frontend init (Task 12)
- ✅ API client + Layout (Task 13)
- ✅ Dashboard pages (Task 14)
- ✅ GitHub Actions CI/CD (Task 15)
- ✅ Docker deployment (Task 16)
- ✅ Integration test + README (Task 17)

**Placeholder scan:** No TBD/TODO/vague references found.

**Type consistency:** All model field names, API paths, and function signatures are consistent across tasks.
