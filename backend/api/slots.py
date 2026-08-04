# backend/api/slots.py
"""Slot 管理 API"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.db.config import get_async_session
from backend.db.models import EnvironmentSlot, PRPipeline
from backend.schemas.slot import SlotResponse, SlotUpdate
from backend.schemas.common import ApiResponse

router = APIRouter()


@router.get("/slots", response_model=ApiResponse)
async def list_slots(db: AsyncSession = Depends(get_async_session)):
    """获取 Slot 列表及状态"""
    result = await db.execute(select(EnvironmentSlot).order_by(EnvironmentSlot.id))
    slots = result.scalars().all()

    items = []
    for s in slots:
        # 查找当前关联的 Pipeline
        pipeline = None
        if s.status == "occupied":
            pr = await db.execute(
                select(PRPipeline)
                .where(PRPipeline.slot_id == s.id, PRPipeline.status != "destroyed")
                .order_by(PRPipeline.created_at.desc())
                .limit(1)
            )
            pipeline = pr.scalar_one_or_none()

        items.append(SlotResponse(
            id=s.id, name=s.name,
            rcs_port=s.rcs_port,
            postgres_port=s.postgres_port,
            litellm_port=s.litellm_port,
            status=s.status,
            pipeline_id=pipeline.id if pipeline else None,
            pipeline_pr_id=pipeline.pr_id if pipeline else None,
            pipeline_status=pipeline.status if pipeline else None,
            created_at=s.created_at,
            updated_at=s.updated_at,
        ).model_dump())

    return ApiResponse(data=items)


@router.put("/slots/{slot_id}", response_model=ApiResponse)
async def update_slot(
    slot_id: int,
    body: SlotUpdate,
    db: AsyncSession = Depends(get_async_session),
):
    """修改 Slot 配置"""
    slot = await db.get(EnvironmentSlot, slot_id)
    if not slot:
        return ApiResponse(success=False, error="Slot 不存在")

    for field in ["name", "rcs_port", "postgres_port", "litellm_port", "status"]:
        value = getattr(body, field, None)
        if value is not None:
            setattr(slot, field, value)

    await db.commit()
    await db.refresh(slot)
    return ApiResponse(data=SlotResponse(
        id=slot.id, name=slot.name,
        rcs_port=slot.rcs_port,
        postgres_port=slot.postgres_port,
        litellm_port=slot.litellm_port,
        status=slot.status,
        created_at=slot.created_at,
        updated_at=slot.updated_at,
    ).model_dump())
