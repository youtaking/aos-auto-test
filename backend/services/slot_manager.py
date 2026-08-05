# backend/services/slot_manager.py
"""Slot 分配/释放/FIFO 队列管理"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from backend.db.models import EnvironmentSlot, PRPipeline, CIConfig


async def allocate_slot(db: AsyncSession) -> EnvironmentSlot | None:
    """分配一个空闲 Slot，标记为 occupied。返回 Slot 或 None（无空闲）"""
    result = await db.execute(
        select(EnvironmentSlot)
        .where(EnvironmentSlot.status == "available")
        .order_by(EnvironmentSlot.id)
        .limit(1)
    )
    slot = result.scalar_one_or_none()
    if slot:
        slot.status = "occupied"
        await db.commit()
        await db.refresh(slot)
    return slot


async def release_slot(db: AsyncSession, slot_id: int, pipeline_id: int) -> None:
    """释放 Slot，标记为 available。

    即使 Pipeline 已被 rerun 重新绑定到其他 Slot，仍强制释放此 Slot，
    防止 Slot 状态永久卡在 occupied（并发 rerun 场景）。
    """
    slot = await db.get(EnvironmentSlot, slot_id)
    if slot and slot.status == "occupied":
        slot.status = "available"
        await db.commit()


async def enqueue_pipeline(db: AsyncSession, pipeline: PRPipeline, max_queue_size: int) -> int:
    """将 Pipeline 加入队列，返回队列位置（从 1 开始）。超过上限返回 -1"""
    current_count = await get_queue_count(db)
    if current_count >= max_queue_size:
        return -1
    position = current_count + 1
    pipeline.queue_position = position
    pipeline.status = "queued"
    await db.commit()
    await db.refresh(pipeline)
    return position


async def dequeue_next(db: AsyncSession) -> PRPipeline | None:
    """取出队首 Pipeline（queue_position 最小的），将其 queue_position 设为 0"""
    result = await db.execute(
        select(PRPipeline)
        .where(PRPipeline.status == "queued")
        .order_by(PRPipeline.queue_position)
        .limit(1)
    )
    pipeline = result.scalar_one_or_none()
    if pipeline:
        pipeline.queue_position = 0
        # 后续排队的 pipeline 位置前移（同一事务内完成）
        await db.execute(
            update(PRPipeline)
            .where(PRPipeline.status == "queued", PRPipeline.queue_position > 0)
            .values(queue_position=PRPipeline.queue_position - 1)
        )
        await db.commit()
        await db.refresh(pipeline)
    return pipeline


async def get_slot_for_pipeline(db: AsyncSession, pipeline: PRPipeline) -> EnvironmentSlot | None:
    """获取 Pipeline 关联的 Slot"""
    if not pipeline.slot_id:
        return None
    return await db.get(EnvironmentSlot, pipeline.slot_id)


async def get_available_slot_count(db: AsyncSession) -> int:
    """获取空闲 Slot 数量"""
    result = await db.execute(
        select(func.count())
        .select_from(EnvironmentSlot)
        .where(EnvironmentSlot.status == "available")
    )
    return result.scalar() or 0


async def get_queue_count(db: AsyncSession) -> int:
    """获取当前排队中的 Pipeline 数量"""
    result = await db.execute(
        select(func.count())
        .select_from(PRPipeline)
        .where(PRPipeline.status == "queued")
    )
    return result.scalar() or 0


async def get_ci_config(db: AsyncSession) -> CIConfig:
    """获取 CI 全局配置，不存在则创建默认配置"""
    result = await db.execute(select(CIConfig).limit(1))
    config = result.scalar_one_or_none()
    if not config:
        config = CIConfig()
        db.add(config)
        await db.commit()
        await db.refresh(config)
    return config
