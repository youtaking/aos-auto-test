# Jenkins PR Pipeline 集成实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 PR Pipeline 的构建/部署职责从 AutoTest 迁移到 Jenkins，AutoTest 专注于测试管理和结果展示。

**Architecture:** Jenkins 作为编排者负责 clone → build → deploy → 触发测试 → 收集结果 → 清理。每个 PR 拥有独立的 docker-compose 容器栈（含 test-runner 容器），天然并发。AutoTest 只提供 Pipeline CRUD API、测试结果存储和看板展示，同时保留手动测试执行能力。

**Tech Stack:** FastAPI + SQLAlchemy (async) + Pydantic v2 + React + Tailwind + Vite

## Global Constraints

- 数据库使用 PostgreSQL（`postgresql+asyncpg://re:re@192.168.10.25:5432/auto_test`），测试用 SQLite（`sqlite+aiosqlite`）
- 所有文件使用 UTF-8 编码
- API 统一返回 `ApiResponse` 格式：`{"success": true/false, "data": ..., "error": ...}`
- Pipeline 状态枚举：`building / deploying / running / passed / failed / error / destroyed`（移除 `queued`）
- 认证使用 `Authorization: Bearer <token>` Header，Token 存在 CIConfig.auth_token
- PRPipeline 新增字段 `target_url`（String 500）、`build_info`（JSON）、`test_report`（JSON）
- EnvironmentSlot 模型保留不删除（避免迁移复杂），但不再使用
- 前端类型定义在 `frontend/src/api/types.ts`，API 客户端在 `frontend/src/api/` 目录

---

### Task 1: PRPipeline 模型新增字段 + Schema 更新

**Files:**
- Modify: `backend/db/models.py:195-224` (PRPipeline model)
- Modify: `backend/schemas/ci.py` (PipelineResponse, remove old schemas, add new ones)

**Interfaces:**
- Consumes: nothing new
- Produces: `PRPipeline.target_url` (str), `PRPipeline.build_info` (dict|None), `PRPipeline.test_report` (dict|None); `PipelineResponse` with `target_url`, `build_info` fields; `CreatePipelineRequest`, `UpdatePipelineStatusRequest` schemas

- [ ] **Step 1: 修改 PRPipeline 模型，添加新字段**

在 `backend/db/models.py` 的 PRPipeline 类中，在 `error_message` 字段后添加三个新字段：

```python
    # Jenkins 集成字段
    target_url = Column(String(500), default="")       # Jenkins 部署后的 PR 环境地址
    build_info = Column(JSON, nullable=True)            # Jenkins 构建信息（job URL、镜像 tag 等）
    test_report = Column(JSON, nullable=True)           # test-runner 提交的完整 pytest JSON 报告
```

`slot_id` 和 `queue_position` 保留但标记为废弃（注释说明），不删除以避免迁移问题。

- [ ] **Step 2: 更新 PipelineResponse Schema**

在 `backend/schemas/ci.py` 中，替换 `PipelineResponse`：

```python
class PipelineResponse(BaseModel):
    """Pipeline 响应"""
    id: int
    pr_id: int
    pr_title: str
    commit_sha: str
    branch: str
    repo_url: str
    author: str
    status: str
    docker_image: str
    target_url: str = ""
    rcs_url: str
    run_id: Optional[int] = None
    build_info: Optional[dict] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    test_total: int = 0
    test_passed: int = 0
    test_failed: int = 0
    test_skipped: int = 0

    model_config = {"from_attributes": True}
```

- [ ] **Step 3: 删除不再需要的 Schema，添加新 Schema**

删除 `TestConfigOverride`、`PRTriggerRequest`、`PRUpdateRequest`、`RerunRequest`。

添加：

```python
class BuildInfo(BaseModel):
    """Jenkins 构建信息"""
    jenkins_url: str = ""
    build_number: int = 0
    docker_image: str = ""
    rcs_port: int = 0
    pg_port: int = 0
    litellm_port: int = 0


class CreatePipelineRequest(BaseModel):
    """Jenkins 创建 Pipeline 记录"""
    pr_id: int
    pr_title: str = ""
    commit_sha: str
    branch: str = ""
    repo_url: str = ""
    author: str = ""
    target_url: str = ""
    build_info: Optional[BuildInfo] = None


class UpdatePipelineStatusRequest(BaseModel):
    """更新 Pipeline 状态"""
    status: str
    error_message: Optional[str] = None
```

- [ ] **Step 4: 验证模型可以正常导入**

Run: `python -X utf8 -c "from backend.db.models import PRPipeline; from backend.schemas.ci import CreatePipelineRequest, UpdatePipelineStatusRequest, PipelineResponse; print('OK')"`

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/db/models.py backend/schemas/ci.py
git commit -m "feat: add Jenkins pipeline fields and update schemas"
```

---

### Task 2: 新增 Jenkins 调用的 API 接口

**Files:**
- Modify: `backend/api/ci.py` (rewrite — remove old endpoints, add new ones)
- Create: `tests/test_api_pipelines.py`

**Interfaces:**
- Consumes: `CreatePipelineRequest`, `UpdatePipelineStatusRequest` from `backend/schemas/ci.py`
- Produces: `POST /api/pipelines`, `POST /api/pipelines/{id}/results`, `PUT /api/pipelines/{id}/status`, `GET /api/pipelines`, `GET /api/pipelines/{id}`, `GET /api/ci/config`, `PUT /api/ci/config`, `POST /api/ci/config/regenerate-token`

- [ ] **Step 1: 写 API 测试**

创建 `tests/test_api_pipelines.py`：

```python
# tests/test_api_pipelines.py
"""Jenkins Pipeline API 集成测试"""
import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_pipelines.db")

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
```

- [ ] **Step 2: 运行测试验证失败**

Run: `python -X utf8 -m pytest tests/test_api_pipelines.py -v --no-header -x`

Expected: FAIL — 新的 API 端点尚未实现

- [ ] **Step 3: 重写 backend/api/ci.py**

完整替换 `backend/api/ci.py` 内容为：

```python
# backend/api/ci.py
"""Pipeline + CI 配置 API：供 Jenkins 调用和前端看板使用"""
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.db.config import get_async_session, async_session
from backend.db.models import PRPipeline, CIConfig, TestRun
from backend.schemas.ci import (
    CreatePipelineRequest, UpdatePipelineStatusRequest,
    PipelineResponse, CIConfigResponse, CIConfigUpdate,
)
from backend.schemas.common import ApiResponse

router = APIRouter()


async def _verify_token(authorization: str = Header(default="")):
    """验证 Bearer Token"""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="缺少认证 Token")
    token = authorization[7:]
    async with async_session() as db:
        result = await db.execute(select(CIConfig).limit(1))
        config = result.scalars().first()
        if not config:
            return  # 未配置 Token 时允许访问
        if config.auth_token and config.auth_token != token:
            raise HTTPException(status_code=403, detail="认证 Token 无效")


async def _get_ci_config(db):
    """获取或创建 CIConfig"""
    result = await db.execute(select(CIConfig).limit(1))
    config = result.scalars().first()
    if not config:
        config = CIConfig()
        db.add(config)
        await db.commit()
        await db.refresh(config)
    return config


def _pipeline_to_response(p: PRPipeline, run: TestRun | None = None) -> dict:
    """将 PRPipeline 转为响应 dict"""
    return PipelineResponse(
        id=p.id, pr_id=p.pr_id, pr_title=p.pr_title,
        commit_sha=p.commit_sha, branch=p.branch,
        repo_url=p.repo_url, author=p.author,
        status=p.status, docker_image=p.docker_image,
        target_url=p.target_url or "",
        rcs_url=p.rcs_url,
        run_id=p.run_id,
        build_info=p.build_info,
        error_message=p.error_message,
        created_at=p.created_at, updated_at=p.updated_at,
        test_total=run.total if run else 0,
        test_passed=run.passed if run else 0,
        test_failed=run.failed if run else 0,
        test_skipped=run.skipped if run else 0,
    ).model_dump()


@router.post("/pipelines", response_model=ApiResponse)
async def create_pipeline(
    body: CreatePipelineRequest,
    db: AsyncSession = Depends(get_async_session),
    authorization: str = Header(default=""),
):
    """Jenkins 创建 Pipeline 记录"""
    await _verify_token(authorization)

    pipeline = PRPipeline(
        pr_id=body.pr_id,
        pr_title=body.pr_title,
        commit_sha=body.commit_sha,
        branch=body.branch,
        repo_url=body.repo_url,
        author=body.author,
        status="building",
        target_url=body.target_url,
        build_info=body.build_info.model_dump() if body.build_info else None,
    )
    db.add(pipeline)
    await db.commit()
    await db.refresh(pipeline)

    return ApiResponse(data=_pipeline_to_response(pipeline))


@router.put("/pipelines/{pipeline_id}/status", response_model=ApiResponse)
async def update_pipeline_status(
    pipeline_id: int,
    body: UpdatePipelineStatusRequest,
    db: AsyncSession = Depends(get_async_session),
    authorization: str = Header(default=""),
):
    """Jenkins 更新 Pipeline 状态"""
    await _verify_token(authorization)

    pipeline = await db.get(PRPipeline, pipeline_id)
    if not pipeline:
        return ApiResponse(success=False, error="Pipeline 不存在")

    pipeline.status = body.status
    if body.error_message:
        pipeline.error_message = body.error_message
    await db.commit()
    await db.refresh(pipeline)

    return ApiResponse(data=_pipeline_to_response(pipeline))


@router.post("/pipelines/{pipeline_id}/results", response_model=ApiResponse)
async def submit_results(
    pipeline_id: int,
    report: dict,
    db: AsyncSession = Depends(get_async_session),
    authorization: str = Header(default=""),
):
    """接收 test-runner/Jenkins 提交的 pytest JSON 报告"""
    await _verify_token(authorization)

    pipeline = await db.get(PRPipeline, pipeline_id)
    if not pipeline:
        return ApiResponse(success=False, error="Pipeline 不存在")

    # 保存原始报告
    pipeline.test_report = report

    # 解析摘要
    summary = report.get("summary", {})
    total = summary.get("num_tests", 0)
    passed = summary.get("num_passed", 0)
    failed = summary.get("num_failed", 0)
    skipped = summary.get("num_skipped", 0)
    duration = report.get("duration", 0)

    # 创建或更新 TestRun
    if pipeline.run_id:
        run = await db.get(TestRun, pipeline.run_id)
    else:
        run = TestRun(
            project_id=1,
            trigger_type="ci",
            git_commit=pipeline.commit_sha,
            git_branch=pipeline.branch,
            pr_id=pipeline.pr_id,
            pipeline_id=pipeline.id,
            started_at=datetime.utcnow(),
        )
        db.add(run)
        await db.flush()

    if run:
        run.total = total
        run.passed = passed
        run.failed = failed
        run.skipped = skipped
        run.duration_ms = int(duration * 1000)
        run.status = "passed" if failed == 0 else "failed"
        run.finished_at = datetime.utcnow()
        pipeline.run_id = run.id

    await db.commit()
    await db.refresh(pipeline)

    return ApiResponse(data={
        **_pipeline_to_response(pipeline, run),
        "test_total": total,
        "test_passed": passed,
        "test_failed": failed,
        "test_skipped": skipped,
    })


@router.get("/pipelines", response_model=ApiResponse)
async def list_pipelines(
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_async_session),
):
    """Pipeline 列表（支持状态筛选和分页）"""
    from sqlalchemy import func

    base_query = select(PRPipeline)
    if status:
        statuses = [s.strip() for s in status.split(",") if s.strip()]
        if len(statuses) > 1:
            base_query = base_query.where(PRPipeline.status.in_(statuses))
        elif statuses:
            base_query = base_query.where(PRPipeline.status == statuses[0])

    count_result = await db.execute(
        select(func.count()).select_from(base_query.subquery())
    )
    total_count = count_result.scalar() or 0

    query = base_query.order_by(PRPipeline.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    pipelines = result.scalars().all()

    items = []
    for p in pipelines:
        run = await db.get(TestRun, p.run_id) if p.run_id else None
        items.append(_pipeline_to_response(p, run))

    return ApiResponse(data={
        "items": items,
        "total": total_count,
        "page": page,
        "page_size": page_size,
    })


@router.get("/pipelines/{pipeline_id}", response_model=ApiResponse)
async def get_pipeline(pipeline_id: int, db: AsyncSession = Depends(get_async_session)):
    """Pipeline 详情"""
    p = await db.get(PRPipeline, pipeline_id)
    if not p:
        return ApiResponse(success=False, error="Pipeline 不存在")

    run = await db.get(TestRun, p.run_id) if p.run_id else None
    return ApiResponse(data=_pipeline_to_response(p, run))


@router.get("/ci/config", response_model=ApiResponse)
async def get_ci_config(db: AsyncSession = Depends(get_async_session)):
    """获取 CI 配置"""
    config = await _get_ci_config(db)
    return ApiResponse(data=CIConfigResponse.model_validate(config).model_dump())


@router.put("/ci/config", response_model=ApiResponse)
async def update_ci_config(
    body: CIConfigUpdate,
    db: AsyncSession = Depends(get_async_session),
):
    """更新 CI 配置"""
    config = await _get_ci_config(db)
    for field in ["timeout_minutes", "max_queue_size", "auth_token",
                   "run_api_tests", "run_e2e_p0", "run_e2e_all",
                   "collection_ids"]:
        value = getattr(body, field, None)
        if value is not None:
            setattr(config, field, value)
    await db.commit()
    await db.refresh(config)
    return ApiResponse(data=CIConfigResponse.model_validate(config).model_dump())


@router.post("/ci/config/regenerate-token", response_model=ApiResponse)
async def regenerate_token(db: AsyncSession = Depends(get_async_session)):
    """重新生成认证 Token"""
    config = await _get_ci_config(db)
    config.auth_token = secrets.token_urlsafe(32)
    await db.commit()
    await db.refresh(config)
    return ApiResponse(data={"token": config.auth_token})
```

- [ ] **Step 4: 运行测试验证通过**

Run: `python -X utf8 -m pytest tests/test_api_pipelines.py -v --no-header`

Expected: 所有测试 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/api/ci.py tests/test_api_pipelines.py
git commit -m "feat: add Jenkins pipeline API (create, status, results)"
```

---

### Task 3: 简化 pipeline_runner.py（保留测试执行能力）

**Files:**
- Modify: `backend/services/pipeline_runner.py` (700 lines -> ~150 lines)

**Interfaces:**
- Consumes: nothing from deleted modules
- Produces: `run_manual_tests(project_id, case_ids, project_url)` for manual trigger from UI; `_execute_tests(run_id, project_url, auth_env, case_ids, pipeline_id)` internal helper

- [ ] **Step 1: 重写 pipeline_runner.py**

完整替换 `backend/services/pipeline_runner.py` 内容为：

```python
# backend/services/pipeline_runner.py
"""Pipeline test execution: used for manual/scheduled triggers.
Jenkins-triggered pipelines submit results via API instead."""
import asyncio
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from backend.db.config import async_session
from backend.db.models import TestRun, TestCase, AuthConfig, PRPipeline
from backend import ws as ws_module


async def _broadcast(pipeline_id: int, event: str, data: dict):
    """Broadcast pipeline event via WebSocket"""
    await ws_module.broadcast_pipeline(pipeline_id, event, data)
    await ws_module.broadcast_global(event, {**data, "pipeline_id": pipeline_id})


async def run_manual_tests(
    project_id: int = 1,
    case_ids: list[int] | None = None,
    project_url: str | None = None,
):
    """Execute tests manually (for manual/scheduled triggers from UI).
    Returns the TestRun ID."""
    async with async_session() as db:
        run = TestRun(
            project_id=project_id,
            trigger_type="manual",
            status="running",
            started_at=datetime.utcnow(),
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)

        auth_env = {}
        auth_result = await db.execute(
            select(AuthConfig).where(AuthConfig.is_active == 1)
        )
        auth_config = auth_result.scalars().first()
        if auth_config:
            auth_env = {
                "FENIX_UI_EMAIL": auth_config.ui_test_email or "",
                "FENIX_UI_PASSWORD": auth_config.ui_test_password or "",
                "FENIX_API_EMAIL": auth_config.api_test_email or "",
                "FENIX_API_PASSWORD": auth_config.api_test_password or "",
                "FENIX_OPEN_API_KEY": auth_config.open_api_key or "",
            }

        await _execute_tests(
            run_id=run.id,
            project_url=project_url or "http://localhost:3000",
            auth_env=auth_env,
            case_ids=case_ids,
            pipeline_id=None,
        )
        return run.id


async def _execute_tests(
    run_id: int,
    project_url: str,
    auth_env: dict,
    case_ids: list[int] | None,
    pipeline_id: int | None = None,
):
    """Execute pytest and store results."""
    async with async_session() as db:
        run = await db.get(TestRun, run_id)
        if not run:
            return

        run.status = "running"
        run.started_at = datetime.utcnow()
        await db.commit()

        passed = failed = skipped = 0

        try:
            report_path = f"report_run_{run_id}.json"
            cmd = [
                sys.executable, "-m", "pytest",
                "tests/suites/", "tests/api_suites/",
                "-v", "--tb=short",
                f"--base-url={project_url}",
                "--json-report", f"--json-report-file={report_path}",
            ]

            if case_ids:
                cases_query = await db.execute(
                    select(TestCase).where(TestCase.id.in_(case_ids))
                )
                selected_cases = cases_query.scalars().all()
                if selected_cases:
                    node_ids = [f"{c.file_path}::{c.function_name}" for c in selected_cases]
                    cmd.extend(node_ids)
                    cmd = [c for c in cmd if c not in ("tests/suites/", "tests/api_suites/")]

            env = {
                **os.environ,
                "HEADLESS": "true",
                "FENIX_URL": project_url,
                "PYTHONUNBUFFERED": "1",
                "FENIX_API_BASE_URL": project_url,
            }
            if auth_env:
                env.update(auth_env)

            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                env=env, cwd=os.getcwd(),
            )

            log_name = f"pipeline_{pipeline_id}" if pipeline_id else f"run_{run_id}"
            log_path = Path("run_logs") / f"{log_name}.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)

            with open(log_path, "w", encoding="utf-8") as log_file:
                while True:
                    raw = await asyncio.to_thread(proc.stdout.readline)
                    if not raw:
                        break
                    line = raw.decode("utf-8", errors="replace")
                    stripped = line.rstrip()
                    if stripped:
                        log_file.write(stripped + "\n")
                        print(f"[Run #{run_id}] {stripped}", flush=True)
                        if pipeline_id:
                            await _broadcast(pipeline_id, "test_log", {"line": stripped})

                    m = re.match(r"^(tests/\S+::\S+)\s+(PASSED|FAILED|SKIPPED|ERROR)", stripped)
                    if m:
                        outcome = m.group(2).lower()
                        func_name = m.group(1).split("::")[-1]
                        if outcome == "passed":
                            passed += 1
                        elif outcome in ("failed", "error"):
                            failed += 1
                        else:
                            skipped += 1
                        run.total = passed + failed + skipped
                        run.passed = passed
                        run.failed = failed
                        run.skipped = skipped
                        await db.commit()
                        if pipeline_id:
                            await _broadcast(pipeline_id, "test_progress", {
                                "case": func_name, "status": outcome,
                                "passed": passed, "failed": failed, "skipped": skipped,
                            })

            await asyncio.to_thread(proc.wait)

            finished = datetime.utcnow()
            run.status = "passed" if failed == 0 else "failed"
            run.finished_at = finished
            run.duration_ms = int((finished - run.started_at).total_seconds() * 1000)
            await db.commit()

            if pipeline_id:
                pipeline = await db.get(PRPipeline, pipeline_id)
                if pipeline:
                    pipeline.status = run.status
                    await db.commit()
                    await _broadcast(pipeline_id, "pipeline_complete", {
                        "status": run.status, "total": run.total,
                        "passed": run.passed, "failed": run.failed, "skipped": run.skipped,
                    })

        except Exception as e:
            print(f"[Run #{run_id}] Test execution error: {e}", flush=True)
            run.status = "error"
            run.finished_at = datetime.utcnow()
            await db.commit()
            if pipeline_id:
                pipeline = await db.get(PRPipeline, pipeline_id)
                if pipeline:
                    pipeline.status = "failed"
                    err_msg = str(e)
                    pipeline.error_message = err_msg[-3000:] if len(err_msg) > 3000 else err_msg
                    await db.commit()
            raise
```

- [ ] **Step 2: 验证模块导入正确**

Run: `python -X utf8 -c "from backend.services.pipeline_runner import run_manual_tests, _execute_tests; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/services/pipeline_runner.py
git commit -m "refactor: simplify pipeline_runner to test execution only"
```

---

### Task 4: 删除废弃模块 + 清理 main.py

**Files:**
- Delete: `backend/services/docker_manager.py`
- Delete: `backend/services/executor.py`
- Delete: `backend/services/slot_manager.py`
- Delete: `backend/services/timeout_checker.py`
- Delete: `backend/schemas/slot.py`
- Delete: `backend/api/slots.py`
- Modify: `backend/main.py` (remove slot init, timeout checker, slots router)

**Interfaces:**
- Consumes: nothing
- Produces: clean main.py without slot/timeout/docker references

- [ ] **Step 1: 删除废弃文件**

```bash
git rm backend/services/docker_manager.py
git rm backend/services/executor.py
git rm backend/services/slot_manager.py
git rm backend/services/timeout_checker.py
git rm backend/schemas/slot.py
git rm backend/api/slots.py
```

- [ ] **Step 2: 重写 main.py**

完整替换 `backend/main.py`：

```python
# backend/main.py
"""FastAPI 应用入口"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.db.config import init_db, close_db
from backend.api import (
    projects, suites, runs, cases, dashboard, api_tests,
    auth_configs, llm_configs, zentao_configs, ai_analysis,
    ci, collections,
)
from backend import ws as ws_module


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时建表 + 自动发现用例，关闭时释放连接"""
    await init_db()
    from backend.db.config import async_session
    from sqlalchemy import select

    try:
        from engine.runner import TestRunner
        from backend.db.models import Project
        from backend.api.cases import sync_test_cases, SUITE_LABELS, API_SUITE_LABELS

        runner = TestRunner()

        async with async_session() as db:
            result = await db.execute(select(Project).where(Project.is_active == 1))
            project = result.scalars().first()
            if not project:
                result = await db.execute(select(Project).limit(1))
                project = result.scalars().first()

            if project:
                ui_collected = runner.collect_tests()
                if ui_collected:
                    ui_stats = await sync_test_cases(db, project, ui_collected, SUITE_LABELS, "ui")
                    print(f"[AutoDiscover] UI: scanned {ui_stats['discovered']}, "
                          f"new {ui_stats['new_cases']}, cleaned {ui_stats['removed_cases']}")

                api_collected = runner.collect_tests_api()
                if api_collected:
                    api_stats = await sync_test_cases(db, project, api_collected, API_SUITE_LABELS, "api")
                    print(f"[AutoDiscover] API: scanned {api_stats['discovered']}, "
                          f"new {api_stats['new_cases']}, cleaned {api_stats['removed_cases']}")

    except Exception as e:
        print(f"[AutoDiscover] 用例同步失败: {e}")

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
app.include_router(api_tests.router, prefix="/api", tags=["api-tests"])
app.include_router(auth_configs.router, prefix="/api", tags=["auth-configs"])
app.include_router(llm_configs.router, prefix="/api", tags=["llm-configs"])
app.include_router(zentao_configs.router, prefix="/api", tags=["zentao-configs"])
app.include_router(ai_analysis.router, prefix="/api", tags=["ai-analysis"])
app.include_router(ci.router, prefix="/api", tags=["ci-pipelines"])
app.include_router(collections.router, prefix="/api", tags=["collections"])
app.include_router(ws_module.router, tags=["websocket"])


@app.get("/api/health")
async def health():
    return {"success": True, "data": {"status": "ok"}}
```

- [ ] **Step 3: 验证后端能正常启动**

Run: `python -X utf8 -c "from backend.main import app; print('OK')"`

Expected: `OK`

- [ ] **Step 4: 运行已有测试确认不回归**

Run: `python -X utf8 -m pytest tests/test_api_projects.py tests/test_api_pipelines.py -v --no-header`

Expected: 所有测试 PASS

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: remove deprecated modules (docker, slot, executor, timeout) and clean main.py"
```

---

### Task 5: Dockerfile.runner + requirements-test.txt

**Files:**
- Create: `Dockerfile.runner`
- Create: `requirements-test.txt`

**Interfaces:**
- Produces: Docker image definition for test-runner container

- [ ] **Step 1: 创建 requirements-test.txt**

在项目根目录创建 `requirements-test.txt`：

```
pytest==8.3.4
pytest-base-url==2.1.0
pytest-playwright==0.7.0
pytest-json-report==1.5.0
httpx==0.28.1
```

- [ ] **Step 2: 创建 Dockerfile.runner**

在项目根目录创建 `Dockerfile.runner`：

```dockerfile
FROM mcr.microsoft.com/playwright/python:v1.50.0-noble

WORKDIR /app

COPY requirements-test.txt .
RUN pip install --no-cache-dir -r requirements-test.txt

RUN mkdir -p /app/results

CMD ["echo", "test-runner ready"]
```

- [ ] **Step 3: 验证文件存在**

Run: `ls Dockerfile.runner requirements-test.txt`

Expected: 两个文件都存在

- [ ] **Step 4: Commit**

```bash
git add Dockerfile.runner requirements-test.txt
git commit -m "feat: add test-runner Dockerfile and requirements"
```

---

### Task 6: 前端清理（移除 Slot UI，增加 Jenkins 链接）

**Files:**
- Modify: `frontend/src/api/types.ts` (update Pipeline type, remove EnvironmentSlot)
- Modify: `frontend/src/api/pipelines.ts` (remove rerun/destroy/cancel)
- Delete: `frontend/src/api/slots.ts`
- Delete: `frontend/src/components/SlotCard.tsx`
- Modify: `frontend/src/components/CIConfigModal.tsx` (remove Slot section)
- Modify: `frontend/src/pages/PRPipeline.tsx` (remove Slot UI, remove action buttons)
- Modify: `frontend/src/components/PipelineDetail.tsx` (remove action buttons, add Jenkins link + target_url)

**Interfaces:**
- Consumes: `Pipeline` type from `frontend/src/api/types.ts`
- Produces: Updated frontend components without Slot references, with Jenkins links

- [ ] **Step 1: 更新前端类型**

在 `frontend/src/api/types.ts` 中，替换 `Pipeline` 接口为：

```typescript
export interface Pipeline {
  id: number;
  pr_id: number;
  pr_title: string;
  commit_sha: string;
  branch: string;
  repo_url: string;
  author: string;
  status: string;
  docker_image: string;
  target_url: string;
  rcs_url: string;
  run_id: number | null;
  build_info: Record<string, unknown> | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  test_total: number;
  test_passed: number;
  test_failed: number;
  test_skipped: number;
}
```

删除 `EnvironmentSlot` 接口（整个 interface 定义）。

- [ ] **Step 2: 简化 Pipeline API 客户端**

替换 `frontend/src/api/pipelines.ts` 为：

```typescript
import { get } from "./client";
import type { Pipeline } from "./types";

interface PipelineListResult {
  items: Pipeline[];
  total: number;
  page: number;
  page_size: number;
}

export const listPipelines = (params?: { status?: string; page?: number; page_size?: number }) =>
  get<PipelineListResult>("/pipelines", params);

export const getPipeline = (id: number) => get<Pipeline>(`/pipelines/${id}`);
```

- [ ] **Step 3: 删除 Slot 相关文件**

```bash
git rm frontend/src/api/slots.ts
git rm frontend/src/components/SlotCard.tsx
```

- [ ] **Step 4: 重写 CIConfigModal**

替换 `frontend/src/components/CIConfigModal.tsx`，移除所有 Slot 相关代码（Slot 配置区域、Slot import、Slot 状态管理、Slot 保存逻辑）。只保留：超时时间、队列上限、Token 管理、用例集选择。

关键变化：
- 移除 `import { listSlots, updateSlot, createSlot, deleteSlot }` 行
- 移除 `EnvironmentSlot` 类型导入
- 移除 `slots` state 和 `listSlots()` 调用
- 移除 `DEFAULT_SLOT_IDS` 常量
- 移除整个 "Slot 配置" section
- `handleSave` 中只调用 `updateCIConfig`，不再循环更新 Slot

- [ ] **Step 5: 更新 PRPipeline.tsx**

在 `frontend/src/pages/PRPipeline.tsx` 中：
- 移除 `listSlots`, `SlotCard`, `EnvironmentSlot`, `rerunPipeline`, `destroyPipeline`, `cancelPipeline` 的 import
- 移除 `slots` state
- 从 `load()` 中移除 `listSlots()` 调用
- 删除 Slot 状态栏（grid 区域）
- 删除 `handleRerun`, `handleDestroy`, `handleCancel` 函数
- 表格去掉 "Slot" 列，Slot 单元格改为显示 "-"
- PipelineDetail 移除 `onRerun` 和 `onDestroy` props

- [ ] **Step 6: 更新 PipelineDetail.tsx**

在 `frontend/src/components/PipelineDetail.tsx` 中：
- 移除 `onRerun`, `onDestroy` 从 Props 接口
- "基本信息" tab 中：Slot 行替换为 target_url（带链接），添加 Jenkins 链接行（从 build_info 取）
- 删除底部所有操作按钮（重跑、销毁、重建、取消排队），只保留 "运行详情" 链接

新增的展示元素：

```tsx
{pipeline.target_url && (
  <div>
    <span className="text-gray-500">Target URL:</span>{" "}
    <a href={pipeline.target_url} target="_blank" rel="noopener noreferrer"
       className="text-blue-600 hover:underline">{pipeline.target_url}</a>
  </div>
)}
{pipeline.build_info && (pipeline.build_info as any).jenkins_url && (
  <div>
    <span className="text-gray-500">Jenkins:</span>{" "}
    <a href={(pipeline.build_info as any).jenkins_url} target="_blank"
       rel="noopener noreferrer" className="text-blue-600 hover:underline">
      Build #{(pipeline.build_info as any).build_number || "?"}
    </a>
  </div>
)}
```

- [ ] **Step 7: 验证前端构建通过**

Run: `cd frontend && npx tsc --noEmit`

Expected: 无 TypeScript 编译错误

- [ ] **Step 8: Commit**

```bash
git add frontend/
git commit -m "feat: update frontend for Jenkins integration (remove Slot UI, add Jenkins links)"
```

---

### Task 7: 添加 Pipeline 日志 API（SSE）

**Files:**
- Modify: `backend/api/ci.py` (add log streaming endpoint)

**Interfaces:**
- Consumes: Pipeline model, log files from `run_logs/` directory
- Produces: `GET /api/pipelines/{id}/logs?follow=true|false`

- [ ] **Step 1: 添加日志流端点**

在 `backend/api/ci.py` 末尾（`regenerate_token` 路由之后）添加：

```python
import asyncio as _asyncio
from fastapi.responses import StreamingResponse


@router.get("/pipelines/{pipeline_id}/logs")
async def get_pipeline_logs(
    pipeline_id: int,
    follow: bool = False,
    db: AsyncSession = Depends(get_async_session),
):
    """获取 Pipeline 测试日志。follow=true 时返回 SSE 流。"""
    pipeline = await db.get(PRPipeline, pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline 不存在")

    log_path = Path("run_logs") / f"pipeline_{pipeline_id}.log"

    if not follow:
        lines = ""
        if log_path.exists():
            lines = log_path.read_text(encoding="utf-8")
        return ApiResponse(data={"logs": lines, "pipeline_id": pipeline_id})

    async def generate_sse():
        last_size = 0
        while True:
            if log_path.exists():
                current_size = log_path.stat().st_size
                if current_size > last_size:
                    with open(log_path, "r", encoding="utf-8") as f:
                        f.seek(last_size)
                        new_content = f.read()
                    for line in new_content.splitlines():
                        yield f"data: {line}\n\n"
                    last_size = current_size

                # 检查 Pipeline 是否已结束
                async with async_session() as check_db:
                    p = await check_db.get(PRPipeline, pipeline_id)
                    if p and p.status in ("passed", "failed", "error", "destroyed"):
                        yield "data: [END]\n\n"
                        break

            await _asyncio.sleep(1)

    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
```

- [ ] **Step 2: 添加日志 API 测试**

在 `tests/test_api_pipelines.py` 末尾追加：

```python
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
```

- [ ] **Step 3: 运行测试**

Run: `python -X utf8 -m pytest tests/test_api_pipelines.py -v --no-header`

Expected: 所有测试 PASS

- [ ] **Step 4: Commit**

```bash
git add backend/api/ci.py tests/test_api_pipelines.py
git commit -m "feat: add pipeline log API with SSE streaming"
```

---

### Task 8: 数据库迁移脚本

**Files:**
- Create: `docs/migrations/002_jenkins_pipeline_fields.sql`

- [ ] **Step 1: 创建迁移文件**

创建 `docs/migrations/002_jenkins_pipeline_fields.sql`：

```sql
-- Migration: Add Jenkins pipeline fields
-- Target: pr_pipelines table

ALTER TABLE pr_pipelines ADD COLUMN target_url VARCHAR(500) DEFAULT '';
ALTER TABLE pr_pipelines ADD COLUMN build_info JSON;
ALTER TABLE pr_pipelines ADD COLUMN test_report JSON;
```

- [ ] **Step 2: Commit**

```bash
git add docs/migrations/002_jenkins_pipeline_fields.sql
git commit -m "docs: add database migration for Jenkins pipeline fields"
```
