# backend/api/ci.py
"""Pipeline + CI 配置 API：供 Jenkins 调用和前端看板使用"""
import asyncio
import secrets
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.db.config import get_async_session, async_session
from backend.db.models import PRPipeline, CIConfig, TestRun, TestResult, TestCollection, TestCase, UnitTestRun, UnitTestResult
from backend.schemas.ci import (
    CreatePipelineRequest, UpdatePipelineStatusRequest,
    PipelineResponse, CIConfigResponse, CIConfigUpdate,
)
from backend.schemas.common import ApiResponse
from backend.api.branches import _validate_branch_name

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
        docker_image=body.docker_image,
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

    run = await db.get(TestRun, pipeline.run_id) if pipeline.run_id else None
    return ApiResponse(data=_pipeline_to_response(pipeline, run))


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

    # 解析摘要（兼容 pytest-json-report 和 pytest-json 两种格式）
    summary = report.get("summary", {})
    total = summary.get("total", summary.get("num_tests", 0))
    passed = summary.get("passed", summary.get("num_passed", 0))
    failed = summary.get("failed", summary.get("num_failed", 0))
    skipped = summary.get("skipped", summary.get("num_skipped", 0))
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

        # 创建 TestResult 记录（逐条测试结果）
        tests = report.get("tests", [])
        if tests:
            # 删除旧的 TestResult（如果是重新上传）
            existing = await db.execute(
                select(TestResult).where(TestResult.run_id == run.id)
            )
            for old in existing.scalars().all():
                await db.delete(old)

            for t in tests:
                nodeid = t.get("nodeid", "")
                outcome = t.get("outcome", "unknown")
                # pytest-json-report: duration 在 call/setup/teardown 子对象中
                dur = t.get("duration", 0) or (
                    t.get("call", {}).get("duration", 0)
                    + t.get("setup", {}).get("duration", 0)
                    + t.get("teardown", {}).get("duration", 0)
                )

                # 解析 nodeid: "tests/api_suites/test_agent_api.py::TestClass::test_name"
                parts = nodeid.split("::")
                case_name = parts[-1] if parts else nodeid
                suite_name = parts[0] if parts else ""

                # 错误信息在 call.longrepr
                error_msg = None
                call_info = t.get("call", {})
                if call_info and call_info.get("longrepr"):
                    error_msg = str(call_info["longrepr"])[:5000]

                result = TestResult(
                    run_id=run.id,
                    case_name=case_name,
                    suite_name=suite_name,
                    status="passed" if outcome == "passed" else "failed" if outcome == "failed" else "skipped",
                    duration_ms=int(dur * 1000),
                    error_message=error_msg,
                )
                db.add(result)

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
                   "collection_ids", "staging_collection_ids",
                   "branch_e2e_collection_ids"]:
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


@router.post("/pipelines/{pipeline_id}/upload-logs", response_model=ApiResponse)
async def upload_pipeline_logs(
    pipeline_id: int,
    body: dict,
    db: AsyncSession = Depends(get_async_session),
    authorization: str = Header(default=""),
):
    """接收 Jenkins 上传的测试执行日志。body: {"logs": "日志内容"}"""
    await _verify_token(authorization)

    pipeline = await db.get(PRPipeline, pipeline_id)
    if not pipeline:
        return ApiResponse(success=False, error="Pipeline 不存在")

    logs_content = body.get("logs", "")
    if not logs_content:
        return ApiResponse(success=False, error="日志内容为空")

    log_dir = Path("run_logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"pipeline_{pipeline_id}.log"
    log_path.write_text(logs_content, encoding="utf-8")

    return ApiResponse(data={"saved": True, "lines": logs_content.count("\n") + 1})


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

            await asyncio.sleep(1)

    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.get("/ci/resolve-tests", response_model=ApiResponse)
async def resolve_tests(
    branch: str = "",
    db: AsyncSession = Depends(get_async_session),
):
    """根据 CI 配置或分支，解析出 pytest node ID 列表"""
    # 如果有 branch 参数，扫描分支目录 + 配置的 E2E 测试集
    if branch and branch != "main":
        _validate_branch_name(branch)
        from engine.runner import TestRunner
        runner = TestRunner()
        # 使用相对路径，避免 Windows 绝对路径污染 pytest node ID
        branch_api_dir = Path("branches") / branch / "api_suites"
        node_ids = []
        if branch_api_dir.exists():
            collected = runner.collect_tests_api(test_dir=str(branch_api_dir.as_posix()))
            node_ids = [f"{c['file_path']}::{c['function_name']}" for c in collected]

        # 加上 CI 配置的 E2E 测试集
        config = await _get_ci_config(db)
        if config.branch_e2e_collection_ids:
            e2e_result = await db.execute(
                select(TestCollection).where(
                    TestCollection.id.in_(config.branch_e2e_collection_ids)
                )
            )
            e2e_collections = e2e_result.scalars().all()
            e2e_case_ids: set[int] = set()
            for c in e2e_collections:
                if c.case_ids:
                    e2e_case_ids.update(c.case_ids)
            if e2e_case_ids:
                e2e_cases = await db.execute(
                    select(TestCase).where(TestCase.id.in_(list(e2e_case_ids)))
                )
                for tc in e2e_cases.scalars().all():
                    node_ids.append(f"{tc.file_path}::{tc.function_name}")

        if not node_ids and not branch_api_dir.exists():
            return ApiResponse(data={"node_ids": [], "warning": f"branch dir not found: {branch_api_dir}"})
        return ApiResponse(data={"node_ids": node_ids})

    # 原有逻辑：从 CI config 的 collection_ids 解析
    config = await _get_ci_config(db)

    if not config.collection_ids:
        return ApiResponse(data={"node_ids": []})

    # 查询用例集，合并所有 case_ids
    result = await db.execute(
        select(TestCollection).where(TestCollection.id.in_(config.collection_ids))
    )
    collections = result.scalars().all()

    all_case_ids: set[int] = set()
    for c in collections:
        if c.case_ids:
            all_case_ids.update(c.case_ids)

    if not all_case_ids:
        return ApiResponse(data={"node_ids": []})

    # 查询 TestCase，生成 pytest node IDs
    cases_result = await db.execute(
        select(TestCase).where(TestCase.id.in_(list(all_case_ids)))
    )
    cases = cases_result.scalars().all()

    node_ids = [f"{c.file_path}::{c.function_name}" for c in cases]
    return ApiResponse(data={"node_ids": node_ids})


@router.get("/ci/staging-resolve-tests", response_model=ApiResponse)
async def staging_resolve_tests(
    branch: str = "",
    db: AsyncSession = Depends(get_async_session),
):
    """根据 CI 配置的 Staging 用例集或分支，解析出 pytest node ID 列表"""
    # 如果有 branch 参数，扫描分支目录
    if branch and branch != "main":
        _validate_branch_name(branch)
        from engine.runner import TestRunner
        runner = TestRunner()
        # 使用相对路径，避免 Windows 绝对路径污染 pytest node ID
        branch_api_dir = Path("branches") / branch / "api_suites"
        if branch_api_dir.exists():
            collected = runner.collect_tests_api(test_dir=str(branch_api_dir.as_posix()))
            node_ids = [f"{c['file_path']}::{c['function_name']}" for c in collected]
            return ApiResponse(data={"node_ids": node_ids})
        else:
            return ApiResponse(data={"node_ids": [], "warning": f"branch dir not found: {branch_api_dir}"})

    # 原有逻辑：从 CI config 的 staging_collection_ids 解析
    config = await _get_ci_config(db)

    if not config.staging_collection_ids:
        return ApiResponse(data={"node_ids": []})

    # 查询用例集，合并所有 case_ids
    result = await db.execute(
        select(TestCollection).where(TestCollection.id.in_(config.staging_collection_ids))
    )
    collections = result.scalars().all()

    all_case_ids: set[int] = set()
    for c in collections:
        if c.case_ids:
            all_case_ids.update(c.case_ids)

    if not all_case_ids:
        return ApiResponse(data={"node_ids": []})

    # 查询 TestCase，生成 pytest node IDs
    cases_result = await db.execute(
        select(TestCase).where(TestCase.id.in_(list(all_case_ids)))
    )
    cases = cases_result.scalars().all()

    node_ids = [f"{c.file_path}::{c.function_name}" for c in cases]
    return ApiResponse(data={"node_ids": node_ids})


@router.get("/ci/resolve-unit-tests", response_model=ApiResponse)
async def resolve_unit_tests(
    branch: str = "",
    db: AsyncSession = Depends(get_async_session),
):
    """解析单元测试文件列表（供 Jenkins pipeline 使用）"""
    from backend.api.unit_tests import UNIT_TESTS_DIR

    PROJECT_ROOT = UNIT_TESTS_DIR.parent  # unit_tests/ 的父目录就是项目根

    if branch and branch != "main":
        _validate_branch_name(branch)
        unit_dir = PROJECT_ROOT / "branches" / branch / "unit_tests"
    else:
        unit_dir = UNIT_TESTS_DIR

    if not unit_dir.exists():
        return ApiResponse(data={"files": [], "warning": f"dir not found: {unit_dir}"})

    files = []
    for ts_file in unit_dir.rglob("*.test.ts"):
        # 路径相对于 PROJECT_ROOT，确保容器内路径正确：
        # main → unit_tests/xxx.test.ts → /app/unit_tests/xxx.test.ts（挂载到 /app/tests）
        # branch → branches/{branch}/unit_tests/xxx.test.ts → /app/branches/{branch}/unit_tests/xxx.test.ts
        relative = ts_file.relative_to(PROJECT_ROOT).as_posix()
        files.append(relative)

    return ApiResponse(data={"files": sorted(files)})


# === 删除 Pipeline 记录 ===

def _is_truly_active(pipeline) -> bool:
    """判断 Pipeline 是否真正在运行（状态为活跃 且 最近1小时内有更新）"""
    if pipeline.status not in ("building", "deploying", "running"):
        return False
    if pipeline.updated_at:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        updated = pipeline.updated_at.replace(tzinfo=timezone.utc) if pipeline.updated_at.tzinfo is None else pipeline.updated_at
        return (now - updated).total_seconds() < 3600
    return False


@router.delete("/pipelines/{pipeline_id}")
async def delete_pipeline(
    pipeline_id: int,
    db: AsyncSession = Depends(get_async_session),
):
    """删除单条 PR Pipeline 记录（级联删除运行记录、测试结果、单元测试结果）"""
    pipeline = await db.get(PRPipeline, pipeline_id)
    if not pipeline:
        return ApiResponse(success=False, error=f"Pipeline #{pipeline_id} 不存在")
    if _is_truly_active(pipeline):
        return ApiResponse(success=False, error="运行中的 Pipeline 不能删除，请先取消")
    # 1. 删除关联的 unit_test_results 和 unit_test_runs
    ut_results = await db.execute(select(UnitTestResult).where(UnitTestResult.pipeline_id == pipeline_id))
    for r in ut_results.scalars().all():
        await db.delete(r)
    ut_runs = await db.execute(select(UnitTestRun).where(UnitTestRun.pipeline_id == pipeline_id))
    for r in ut_runs.scalars().all():
        await db.delete(r)
    # 2. 删除关联的 test_run 及其 test_results
    if pipeline.run_id:
        test_results = await db.execute(select(TestResult).where(TestResult.run_id == pipeline.run_id))
        for r in test_results.scalars().all():
            await db.delete(r)
        run = await db.get(TestRun, pipeline.run_id)
        if run:
            await db.delete(run)
    else:
        # 也可能通过 test_runs.pipeline_id 反向关联
        runs = await db.execute(select(TestRun).where(TestRun.pipeline_id == pipeline_id))
        for run in runs.scalars().all():
            test_results = await db.execute(select(TestResult).where(TestResult.run_id == run.id))
            for r in test_results.scalars().all():
                await db.delete(r)
            await db.delete(run)
    # 3. 删除 pipeline
    await db.delete(pipeline)
    await db.commit()
    return ApiResponse(data={"deleted": pipeline_id})


@router.post("/pipelines/batch-delete")
async def batch_delete_pipelines(
    body: dict,
    db: AsyncSession = Depends(get_async_session),
):
    """批量删除 PR Pipeline 记录"""
    pipeline_ids = body.get("pipeline_ids", [])
    if not pipeline_ids:
        return ApiResponse(success=False, error="未指定要删除的 Pipeline")

    result = await db.execute(select(PRPipeline).where(PRPipeline.id.in_(pipeline_ids)))
    pipelines = result.scalars().all()

    active = [p for p in pipelines if _is_truly_active(p)]
    if active:
        active_ids = [p.id for p in active]
        return ApiResponse(success=False, error=f"运行中的 Pipeline 不能删除: {active_ids}")

    deleted_ids = []
    for pipeline in pipelines:
        # 1. 删除关联的 unit_test_results 和 unit_test_runs
        ut_results = await db.execute(select(UnitTestResult).where(UnitTestResult.pipeline_id == pipeline.id))
        for r in ut_results.scalars().all():
            await db.delete(r)
        ut_runs = await db.execute(select(UnitTestRun).where(UnitTestRun.pipeline_id == pipeline.id))
        for r in ut_runs.scalars().all():
            await db.delete(r)
        # 2. 删除关联的 test_run 及其 test_results
        if pipeline.run_id:
            test_results = await db.execute(select(TestResult).where(TestResult.run_id == pipeline.run_id))
            for r in test_results.scalars().all():
                await db.delete(r)
            run = await db.get(TestRun, pipeline.run_id)
            if run:
                await db.delete(run)
        else:
            runs = await db.execute(select(TestRun).where(TestRun.pipeline_id == pipeline.id))
            for run in runs.scalars().all():
                test_results = await db.execute(select(TestResult).where(TestResult.run_id == run.id))
                for r in test_results.scalars().all():
                    await db.delete(r)
                await db.delete(run)
        # 3. 删除 pipeline
        await db.delete(pipeline)
        deleted_ids.append(pipeline.id)

    await db.commit()
    return ApiResponse(data={"deleted": deleted_ids, "count": len(deleted_ids)})

