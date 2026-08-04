# backend/services/timeout_checker.py
"""超时自动销毁后台任务"""
import asyncio
import json
import traceback
from datetime import datetime

from sqlalchemy import select

from backend.db.config import async_session
from backend.db.models import PRPipeline, EnvironmentSlot
from backend.services import slot_manager, docker_manager
from backend import ws as ws_module

_CHECK_INTERVAL = 300  # 5 分钟
_task: asyncio.Task | None = None


async def check_and_destroy_expired():
    """检查已过期的 Pipeline，自动销毁"""
    async with async_session() as db:
        now = datetime.utcnow()
        result = await db.execute(
            select(PRPipeline).where(
                PRPipeline.status.in_(["passed", "failed"]),
                PRPipeline.timeout_at.isnot(None),
                PRPipeline.timeout_at <= now,
            )
        )
        expired = result.scalars().all()

        for pipeline in expired:
            try:
                slot = await db.get(EnvironmentSlot, pipeline.slot_id) if pipeline.slot_id else None
                if slot:
                    pipeline.environment_info = json.dumps({
                        "slot_name": slot.name,
                        "rcs_port": slot.rcs_port,
                        "postgres_port": slot.postgres_port,
                        "litellm_port": slot.litellm_port,
                        "docker_image": pipeline.docker_image,
                        "rcs_url": pipeline.rcs_url,
                        "destroyed_at": now.isoformat(),
                        "destroyed_reason": "timeout",
                    })
                    await docker_manager.destroy(pipeline, slot)
                    await slot_manager.release_slot(db, pipeline.slot_id, pipeline.id)

                pipeline.status = "destroyed"
                pipeline.timeout_at = None
                await db.commit()

                await ws_module.broadcast_pipeline(pipeline.id, "pipeline_timeout", {
                    "status": "destroyed",
                    "reason": "timeout",
                })
                await ws_module.broadcast_global("pipeline_timeout", {
                    "pipeline_id": pipeline.id,
                    "status": "destroyed",
                    "reason": "timeout",
                })
                print(f"[TimeoutChecker] Pipeline #{pipeline.id} 超时销毁完成", flush=True)
            except Exception as e:
                print(f"[TimeoutChecker] Pipeline #{pipeline.id} 销毁失败: {e}", flush=True)
                traceback.print_exc()

        # 处理队列
        if expired:
            next_pipeline = await slot_manager.dequeue_next(db)
            if next_pipeline:
                from backend.services.pipeline_runner import start_pipeline
                asyncio.create_task(start_pipeline(next_pipeline.id))


async def _loop():
    """后台循环"""
    while True:
        try:
            await check_and_destroy_expired()
        except Exception as e:
            print(f"[TimeoutChecker] 检查异常: {e}", flush=True)
            traceback.print_exc()
        await asyncio.sleep(_CHECK_INTERVAL)


def start_timeout_checker():
    """启动超时检查后台任务"""
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(_loop())
        print("[TimeoutChecker] 已启动，检查间隔 5 分钟", flush=True)


def stop_timeout_checker():
    """停止超时检查后台任务"""
    global _task
    if _task and not _task.done():
        _task.cancel()
        _task = None
        print("[TimeoutChecker] 已停止", flush=True)
