# backend/services/pipeline_runner.py
"""Pipeline 全流程编排：串联 Slot + Docker + TestRunner"""
import asyncio
import json
import os
import traceback
from datetime import datetime, timedelta

from sqlalchemy import select, update

from backend.db.config import async_session
from backend.db.models import (
    PRPipeline, EnvironmentSlot, TestRun, TestCase,
    CIConfig, AuthConfig, TestCollection,
)
from backend.services import slot_manager, docker_manager
from backend.services.executor import create_executor, init_executor, CommandExecutor, SSHExecutor
from backend import ws as ws_module


async def _get_executor(slot: EnvironmentSlot) -> CommandExecutor | SSHExecutor:
    """根据 Slot 配置创建并初始化执行器"""
    executor = create_executor(slot)
    await init_executor(executor, slot)
    return executor


async def resolve_collection_case_ids(db, collection_ids: list[int]) -> list[int]:
    """解析多个用例集，合并去重，跳过已删除的用例"""
    if not collection_ids:
        return []
    result = await db.execute(
        select(TestCollection).where(TestCollection.id.in_(collection_ids))
    )
    collections = result.scalars().all()
    all_case_ids: set[int] = set()
    for c in collections:
        if c.case_ids:
            all_case_ids.update(c.case_ids)
    if not all_case_ids:
        return []
    # 验证用例是否存在
    valid = await db.execute(
        select(TestCase.id).where(TestCase.id.in_(list(all_case_ids)))
    )
    return [r[0] for r in valid.all()]


async def _broadcast(pipeline_id: int, event: str, data: dict):
    """广播 Pipeline 事件"""
    await ws_module.broadcast_pipeline(pipeline_id, event, data)
    await ws_module.broadcast_global(event, {**data, "pipeline_id": pipeline_id})


async def _resolve_test_cases(
    db,
    config: CIConfig,
    test_config: dict | None,
) -> list[int] | None:
    """根据配置解析要运行的测试用例 ID 列表。返回 None 表示跑全部"""

    # 优先使用 collection_ids
    collection_ids = None
    if test_config and test_config.get("collection_ids"):
        collection_ids = test_config["collection_ids"]
    elif config.collection_ids:
        collection_ids = config.collection_ids

    if collection_ids:
        case_ids = await resolve_collection_case_ids(db, collection_ids)
        return case_ids if case_ids else None

    run_api = False
    run_e2e_p0 = False
    run_e2e_all = False
    custom_ids: list[int] = []

    if test_config:
        run_api = test_config.get("run_api_tests", False)
        run_e2e_p0 = test_config.get("run_e2e_p0", False)
        run_e2e_all = test_config.get("run_e2e_all", False)
        custom_ids = test_config.get("custom_case_ids", [])
    else:
        run_api = bool(config.run_api_tests)
        run_e2e_p0 = bool(config.run_e2e_p0)
        run_e2e_all = bool(config.run_e2e_all)

    # 如果全部关闭，跑全部
    if not run_api and not run_e2e_p0 and not run_e2e_all and not custom_ids:
        return None

    case_ids: list[int] = []

    if run_api:
        result = await db.execute(
            select(TestCase.id).join(
                TestCase.suite
            ).where(
                TestCase.file_path.like("tests/api_suites/%")
            )
        )
        case_ids.extend(r[0] for r in result.all())

    if run_e2e_p0:
        result = await db.execute(
            select(TestCase.id).where(
                TestCase.file_path.like("tests/suites/%"),
                TestCase.tags.contains("p0"),
            )
        )
        case_ids.extend(r[0] for r in result.all())

    if run_e2e_all:
        result = await db.execute(
            select(TestCase.id).where(
                TestCase.file_path.like("tests/suites/%")
            )
        )
        case_ids.extend(r[0] for r in result.all())

    case_ids.extend(custom_ids)
    return list(set(case_ids)) if case_ids else None


async def start_pipeline(pipeline_id: int, test_config: dict | None = None):
    """后台任务：完整执行 clone → build → deploy → test 流程"""
    async with async_session() as db:
        pipeline = await db.get(PRPipeline, pipeline_id)
        if not pipeline:
            return

        config = await slot_manager.get_ci_config(db)

        allocated_slot_id = None  # 记录初始分配的 slot_id，防止 rerun 并发修改
        executor = None
        try:
            # ── 1. 分配 Slot ──
            slot = await slot_manager.allocate_slot(db)
            if not slot:
                # 无空闲 Slot，入队
                position = await slot_manager.enqueue_pipeline(
                    db, pipeline, config.max_queue_size
                )
                if position < 0:
                    pipeline.status = "error"
                    pipeline.error_message = "并发已满，队列已满"
                    await db.commit()
                    await _broadcast(pipeline_id, "pipeline_error", {
                        "error": "并发已满，队列已满",
                    })
                    return
                await _broadcast(pipeline_id, "pipeline_queued", {
                    "queue_position": position,
                })
                return

            allocated_slot_id = slot.id
            pipeline.slot_id = slot.id
            pipeline.status = "building"
            await db.commit()

            # 根据 Slot 配置创建执行器（本地或 SSH）
            executor = await _get_executor(slot)

            await _broadcast(pipeline_id, "pipeline_start", {
                "pr_id": pipeline.pr_id,
                "status": "building",
                "slot": slot.name,
                "host": slot.host,
            })

            # ── 2. Clone + Build ──
            image_tag = await docker_manager.clone_and_build(pipeline, slot, executor)
            pipeline.docker_image = image_tag
            await db.commit()

            await _broadcast(pipeline_id, "build_progress", {
                "log": f"镜像构建完成: {image_tag}",
            })

            # ── 3. Deploy ──
            pipeline.status = "deploying"
            await db.commit()

            await _broadcast(pipeline_id, "deploy_progress", {
                "status": "deploying",
                "slot": slot.name,
            })

            await docker_manager.deploy(pipeline, slot, executor)

            # ── 4. Health Check ──
            await _broadcast(pipeline_id, "health_check", {
                "status": "waiting_health",
            })

            healthy = await docker_manager.wait_healthy(slot, timeout=120)
            if not healthy:
                pipeline.status = "error"
                pipeline.error_message = "Health check 超时（120s）"
                await db.commit()
                # 销毁失败的部署
                await docker_manager.destroy(pipeline, slot, executor)
                await slot_manager.release_slot(db, slot.id, pipeline.id)
                await _broadcast(pipeline_id, "pipeline_error", {
                    "error": "Health check 超时",
                })
                # 处理队列
                await _process_queue()
                return

            # 使用 slot.host 作为 RCS URL（支持远程服务器）
            host = slot.host if slot.host and slot.host not in ("localhost",) else "127.0.0.1"
            pipeline.rcs_url = f"http://{host}:{slot.rcs_port}"
            await db.commit()

            await _broadcast(pipeline_id, "deploy_progress", {
                "status": "healthy",
                "rcs_url": pipeline.rcs_url,
            })

            # ── 5. 跑测试（本地执行 pytest，指向远程环境 URL）──
            await _run_tests(db, pipeline, slot, config, test_config)

        except Exception as e:
            print(f"[Pipeline #{pipeline_id}] 异常: {e}", flush=True)
            traceback.print_exc()
            pipeline.status = "error"
            err_msg = str(e)
            pipeline.error_message = err_msg[-3000:] if len(err_msg) > 3000 else err_msg
            await db.commit()

            # 释放 Slot（使用初始分配的 slot_id，防止 rerun 并发导致 slot_id 变化）
            if allocated_slot_id:
                slot = await db.get(EnvironmentSlot, allocated_slot_id)
                if slot:
                    try:
                        if not executor:
                            executor = await _get_executor(slot)
                        await docker_manager.destroy(pipeline, slot, executor)
                    except Exception:
                        pass
                await slot_manager.release_slot(db, allocated_slot_id, pipeline.id)

            await _broadcast(pipeline_id, "pipeline_error", {"error": str(e)[:500]})
            await _process_queue()
        finally:
            if executor:
                await executor.close()


async def _run_tests(
    db,
    pipeline: PRPipeline,
    slot: EnvironmentSlot,
    config: CIConfig,
    test_config: dict | None,
):
    """对已部署的环境执行测试"""
    case_ids = await _resolve_test_cases(db, config, test_config)

    # 创建 TestRun 记录
    run = TestRun(
        project_id=1,  # 使用默认项目
        trigger_type="ci",
        status="pending",
        git_commit=pipeline.commit_sha,
        git_branch=pipeline.branch,
        pr_id=pipeline.pr_id,
        pipeline_id=pipeline.id,
        started_at=datetime.utcnow(),
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    pipeline.run_id = run.id
    pipeline.status = "running"
    await db.commit()

    # 读取认证配置
    auth_env = {}
    auth_result = await db.execute(select(AuthConfig).where(AuthConfig.is_active == 1))
    auth_config = auth_result.scalar_one_or_none()
    if auth_config:
        auth_env = {
            "FENIX_UI_EMAIL": auth_config.ui_test_email or "",
            "FENIX_UI_PASSWORD": auth_config.ui_test_password or "",
            "FENIX_API_EMAIL": auth_config.api_test_email or "",
            "FENIX_API_PASSWORD": auth_config.api_test_password or "",
            "FENIX_OPEN_API_KEY": auth_config.open_api_key or "",
        }

    await _broadcast(pipeline.id, "test_start", {
        "run_id": run.id,
        "status": "running",
    })

    # 使用自有的测试执行函数，传入 PR 环境的 URL
    await _execute_pipeline_tests(
        run.id, pipeline.id, slot, pipeline.rcs_url,
        auth_env, case_ids,
    )


async def _execute_pipeline_tests(
    run_id: int,
    pipeline_id: int,
    slot: EnvironmentSlot,
    project_url: str,
    auth_env: dict,
    case_ids: list[int] | None,
):
    """执行测试并在完成后更新 Pipeline 状态"""
    import re
    import subprocess
    import sys
    from pathlib import Path

    async with async_session() as db:
        run = await db.get(TestRun, run_id)
        pipeline = await db.get(PRPipeline, pipeline_id)
        if not run or not pipeline:
            return

        run.status = "running"
        run.started_at = datetime.utcnow()
        await db.commit()

        try:
            report_path = f"report_pipeline_{pipeline_id}.json"
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
                    nodeids = [f"{c.file_path}::{c.function_name}" for c in selected_cases]
                    cmd.extend(nodeids)
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

            passed = failed = skipped = 0
            log_path = Path("run_logs") / f"pipeline_{pipeline_id}.log"
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
                        print(f"[Pipeline #{pipeline_id}] {stripped}", flush=True)
                        await _broadcast(pipeline_id, "test_log", {"line": stripped})

                    # 解析测试结果
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
                        await _broadcast(pipeline_id, "test_progress", {
                            "case": func_name,
                            "status": outcome,
                            "passed": passed,
                            "failed": failed,
                            "skipped": skipped,
                        })

            await asyncio.to_thread(proc.wait)

            # 更新最终状态
            finished = datetime.utcnow()
            run.status = "passed" if failed == 0 else "failed"
            run.finished_at = finished
            run.duration_ms = int((finished - run.started_at).total_seconds() * 1000)
            await db.commit()

            pipeline.status = run.status
            config = await slot_manager.get_ci_config(db)
            pipeline.timeout_at = datetime.utcnow() + timedelta(minutes=config.timeout_minutes)
            await db.commit()

            # 保存环境信息快照
            pipeline.environment_info = json.dumps({
                "slot_name": slot.name,
                "rcs_port": slot.rcs_port,
                "postgres_port": slot.postgres_port,
                "litellm_port": slot.litellm_port,
                "docker_image": pipeline.docker_image,
                "rcs_url": pipeline.rcs_url,
            })
            await db.commit()

            await _broadcast(pipeline_id, "pipeline_complete", {
                "status": run.status,
                "total": run.total,
                "passed": run.passed,
                "failed": run.failed,
                "skipped": run.skipped,
                "duration_ms": run.duration_ms,
            })

        except Exception as e:
            print(f"[Pipeline #{pipeline_id}] 测试执行异常: {e}", flush=True)
            run.status = "error"
            run.finished_at = datetime.utcnow()
            pipeline.status = "failed"
            err_msg = str(e)
            pipeline.error_message = err_msg[-3000:] if len(err_msg) > 3000 else err_msg
            try:
                config = await slot_manager.get_ci_config(db)
                pipeline.timeout_at = datetime.utcnow() + timedelta(minutes=config.timeout_minutes)
            except Exception:
                pipeline.timeout_at = datetime.utcnow() + timedelta(minutes=30)
            await db.commit()
            await _broadcast(pipeline_id, "pipeline_complete", {
                "status": "error",
                "error": str(e)[:500],
            })


async def rerun_pipeline(pipeline_id: int, case_ids: list[int] | None = None):
    """重跑测试"""
    async with async_session() as db:
        pipeline = await db.get(PRPipeline, pipeline_id)
        if not pipeline:
            raise ValueError(f"Pipeline #{pipeline_id} 不存在")

        executor = None
        if pipeline.status in ("destroyed", "error"):
            # 需要重建
            config = await slot_manager.get_ci_config(db)
            slot = await slot_manager.allocate_slot(db)
            if not slot:
                position = await slot_manager.enqueue_pipeline(
                    db, pipeline, config.max_queue_size
                )
                if position < 0:
                    raise RuntimeError("并发已满，队列已满")
                pipeline.status = "queued"
                pipeline.queue_position = position
                await db.commit()
                return

            pipeline.slot_id = slot.id
            pipeline.status = "building"
            pipeline.timeout_at = None
            await db.commit()

            executor = await _get_executor(slot)

            await _broadcast(pipeline_id, "pipeline_start", {
                "pr_id": pipeline.pr_id,
                "status": "rebuilding",
                "slot": slot.name,
            })

            try:
                image_tag = await docker_manager.clone_and_build(pipeline, slot, executor)
                pipeline.docker_image = image_tag
                pipeline.status = "deploying"
                await db.commit()

                await docker_manager.deploy(pipeline, slot, executor)
                healthy = await docker_manager.wait_healthy(slot, timeout=120)
                if not healthy:
                    pipeline.status = "error"
                    pipeline.error_message = "重建后 Health check 超时"
                    await db.commit()
                    await docker_manager.destroy(pipeline, slot, executor)
                    await slot_manager.release_slot(db, slot.id, pipeline.id)
                    await _process_queue()
                    return

                host = slot.host if slot.host and slot.host not in ("localhost",) else "127.0.0.1"
                pipeline.rcs_url = f"http://{host}:{slot.rcs_port}"
                await db.commit()
            except Exception:
                await executor.close()
                raise
        else:
            slot = await slot_manager.get_slot_for_pipeline(db, pipeline)
            if not slot:
                raise ValueError(f"Pipeline #{pipeline_id} 关联的 Slot (id={pipeline.slot_id}) 不存在")
            executor = await _get_executor(slot)

        # 暂停超时计时
        pipeline.timeout_at = None
        await db.commit()

        config = await slot_manager.get_ci_config(db)

        # 解析用例
        if case_ids is None:
            case_ids = await _resolve_test_cases(db, config, None)

        try:
            # 跑测试
            await _run_tests(db, pipeline, slot, config, {"custom_case_ids": case_ids} if case_ids else None)
        finally:
            if executor:
                await executor.close()


async def destroy_pipeline(pipeline_id: int):
    """手动销毁 Pipeline 环境"""
    async with async_session() as db:
        pipeline = await db.get(PRPipeline, pipeline_id)
        if not pipeline:
            raise ValueError(f"Pipeline #{pipeline_id} 不存在")

        if pipeline.status == "destroyed":
            return

        slot = await slot_manager.get_slot_for_pipeline(db, pipeline)
        if slot:
            # 保存环境信息快照
            pipeline.environment_info = json.dumps({
                "slot_name": slot.name,
                "host": slot.host,
                "rcs_port": slot.rcs_port,
                "postgres_port": slot.postgres_port,
                "litellm_port": slot.litellm_port,
                "docker_image": pipeline.docker_image,
                "rcs_url": pipeline.rcs_url,
                "destroyed_at": datetime.utcnow().isoformat(),
                "destroyed_reason": "manual",
            })
            executor = await _get_executor(slot)
            try:
                await docker_manager.destroy(pipeline, slot, executor)
            finally:
                await executor.close()
            await slot_manager.release_slot(db, slot.id, pipeline.id)

        pipeline.status = "destroyed"
        pipeline.timeout_at = None
        await db.commit()

        await _broadcast(pipeline_id, "pipeline_timeout", {
            "status": "destroyed",
            "reason": "manual",
        })

        await _process_queue()


async def cancel_pipeline(pipeline_id: int):
    """取消排队中/运行中的 Pipeline"""
    async with async_session() as db:
        pipeline = await db.get(PRPipeline, pipeline_id)
        if not pipeline:
            raise ValueError(f"Pipeline #{pipeline_id} 不存在")

        if pipeline.status == "queued":
            original_queue_pos = pipeline.queue_position  # 保存原始位置，用于后续递减
            pipeline.status = "destroyed"
            pipeline.queue_position = 0
            pipeline.error_message = "用户取消"
            await db.commit()
            # 后续排队位置前移（仅影响被取消的 Pipeline 之后的）
            await db.execute(
                update(PRPipeline)
                .where(
                    PRPipeline.status == "queued",
                    PRPipeline.queue_position > original_queue_pos,
                )
                .values(queue_position=PRPipeline.queue_position - 1)
            )
            await db.commit()
        elif pipeline.status in ("building", "deploying", "running"):
            slot = await slot_manager.get_slot_for_pipeline(db, pipeline)
            if slot:
                pipeline.environment_info = json.dumps({
                    "slot_name": slot.name,
                    "host": slot.host,
                    "rcs_port": slot.rcs_port,
                    "postgres_port": slot.postgres_port,
                    "litellm_port": slot.litellm_port,
                    "docker_image": pipeline.docker_image,
                    "rcs_url": pipeline.rcs_url,
                    "destroyed_at": datetime.utcnow().isoformat(),
                    "destroyed_reason": "cancelled",
                })
                executor = await _get_executor(slot)
                try:
                    await docker_manager.destroy(pipeline, slot, executor)
                finally:
                    await executor.close()
                await slot_manager.release_slot(db, slot.id, pipeline.id)
            pipeline.status = "destroyed"
            pipeline.error_message = "用户取消"
            pipeline.timeout_at = None
            await db.commit()
            await _process_queue()
        else:
            raise ValueError(f"Pipeline 状态 {pipeline.status} 不可取消")

        await _broadcast(pipeline_id, "pipeline_cancelled", {
            "status": "destroyed",
        })


async def handle_pr_update(pr_id: int, new_commit_sha: str):
    """处理同一 PR 的新 commit"""
    async with async_session() as db:
        result = await db.execute(
            select(PRPipeline)
            .where(PRPipeline.pr_id == pr_id)
            .order_by(PRPipeline.created_at.desc())
            .limit(1)
        )
        pipeline = result.scalar_one_or_none()
        if not pipeline:
            return

        if pipeline.commit_sha == new_commit_sha:
            return  # 同一 commit，幂等

        if pipeline.status == "queued":
            # 排队中 → 更新 commit
            pipeline.commit_sha = new_commit_sha
            await db.commit()
        elif pipeline.status in ("building", "deploying", "running", "passed", "failed", "error"):
            # 正在运行或已完成 → 在当前 session 内直接销毁（避免嵌套 session）
            slot = await slot_manager.get_slot_for_pipeline(db, pipeline)
            if slot:
                pipeline.environment_info = json.dumps({
                    "slot_name": slot.name,
                    "host": slot.host,
                    "rcs_port": slot.rcs_port,
                    "postgres_port": slot.postgres_port,
                    "litellm_port": slot.litellm_port,
                    "docker_image": pipeline.docker_image,
                    "rcs_url": pipeline.rcs_url,
                    "destroyed_at": datetime.utcnow().isoformat(),
                    "destroyed_reason": "pr_update",
                })
                executor = await _get_executor(slot)
                try:
                    await docker_manager.destroy(pipeline, slot, executor)
                finally:
                    await executor.close()
                await slot_manager.release_slot(db, slot.id, pipeline.id)

            pipeline.status = "destroyed"
            pipeline.timeout_at = None
            await db.commit()

            await _broadcast(pipeline.id, "pipeline_timeout", {
                "status": "destroyed",
                "reason": "pr_update",
            })
            # 注意：不调用 _process_queue()，新 Pipeline 的启动会自行处理 Slot 分配

            # 创建新 Pipeline
            new_pipeline = PRPipeline(
                pr_id=pipeline.pr_id,
                pr_title=pipeline.pr_title,
                commit_sha=new_commit_sha,
                branch=pipeline.branch,
                repo_url=pipeline.repo_url,
                author=pipeline.author,
            )
            db.add(new_pipeline)
            await db.commit()
            await db.refresh(new_pipeline)

            # 异步启动新 Pipeline
            asyncio.create_task(start_pipeline(new_pipeline.id))


async def _process_queue():
    """检查队列，处理下一个等待的 Pipeline"""
    async with async_session() as db:
        next_pipeline = await slot_manager.dequeue_next(db)
        if next_pipeline:
            asyncio.create_task(start_pipeline(next_pipeline.id))
