# backend/api/slots.py
"""Slot 管理 API"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from backend.db.config import get_async_session
from backend.db.models import EnvironmentSlot, PRPipeline
from backend.schemas.slot import SlotResponse, SlotUpdate
from backend.schemas.common import ApiResponse

router = APIRouter()

_DEFAULT_SLOT_IDS = [1, 2, 3]


def _slot_to_response(s, pipeline=None):
    return SlotResponse(
        id=s.id, name=s.name,
        rcs_port=s.rcs_port,
        postgres_port=s.postgres_port,
        litellm_port=s.litellm_port,
        status=s.status,
        host=s.host,
        ssh_user=s.ssh_user,
        ssh_port=s.ssh_port,
        ssh_key_path=s.ssh_key_path,
        work_dir=s.work_dir,
        pipeline_id=pipeline.id if pipeline else None,
        pipeline_pr_id=pipeline.pr_id if pipeline else None,
        pipeline_status=pipeline.status if pipeline else None,
        created_at=s.created_at,
        updated_at=s.updated_at,
    ).model_dump()


@router.get("/slots", response_model=ApiResponse)
async def list_slots(db: AsyncSession = Depends(get_async_session)):
    """获取 Slot 列表及状态"""
    result = await db.execute(select(EnvironmentSlot).order_by(EnvironmentSlot.id))
    slots = result.scalars().all()

    items = []
    for s in slots:
        pipeline = None
        if s.status == "occupied":
            pr = await db.execute(
                select(PRPipeline)
                .where(PRPipeline.slot_id == s.id, PRPipeline.status != "destroyed")
                .order_by(PRPipeline.created_at.desc())
                .limit(1)
            )
            pipeline = pr.scalar_one_or_none()
        items.append(_slot_to_response(s, pipeline))

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

    for field in [
        "name", "rcs_port", "postgres_port", "litellm_port", "status",
        "host", "ssh_user", "ssh_port", "ssh_key_path", "ssh_password", "work_dir",
    ]:
        value = getattr(body, field, None)
        if value is not None:
            setattr(slot, field, value)

    await db.commit()
    await db.refresh(slot)
    return ApiResponse(data=_slot_to_response(slot))


@router.post("/slots", response_model=ApiResponse)
async def create_slot(
    body: SlotUpdate,
    db: AsyncSession = Depends(get_async_session),
):
    """新增 Slot（仅当默认 3 个 Slot 全部启用时允许）"""
    # 检查默认 3 个 Slot 是否全部启用
    result = await db.execute(
        select(EnvironmentSlot).where(EnvironmentSlot.id.in_(_DEFAULT_SLOT_IDS))
    )
    defaults = result.scalars().all()
    disabled = [s.name for s in defaults if s.status == "maintenance"]
    if disabled:
        return ApiResponse(
            success=False,
            error=f"请先启用默认 Slot：{', '.join(disabled)}，才能添加新 Slot",
        )

    # 自动计算端口（取现有最大端口 +1）
    max_ports = await db.execute(
        select(
            func.max(EnvironmentSlot.rcs_port),
            func.max(EnvironmentSlot.postgres_port),
            func.max(EnvironmentSlot.litellm_port),
        )
    )
    row = max_ports.one()
    next_rcs = (row[0] or 3100) + 1
    next_pg = (row[1] or 5500) + 1
    next_llm = (row[2] or 4100) + 1

    # 计算 Slot 编号
    count_result = await db.execute(select(func.count()).select_from(EnvironmentSlot))
    next_num = (count_result.scalar() or 0) + 1

    slot = EnvironmentSlot(
        name=body.name or f"Slot {next_num}",
        rcs_port=body.rcs_port or next_rcs,
        postgres_port=body.postgres_port or next_pg,
        litellm_port=body.litellm_port or next_llm,
        host=body.host or "localhost",
        ssh_user=body.ssh_user or "root",
        ssh_port=body.ssh_port or 22,
        ssh_key_path=body.ssh_key_path or "",
        ssh_password=body.ssh_password or "",
        work_dir=body.work_dir or "/tmp/pr-environments",
    )
    db.add(slot)
    await db.commit()
    await db.refresh(slot)
    return ApiResponse(data=_slot_to_response(slot))


@router.delete("/slots/{slot_id}", response_model=ApiResponse)
async def delete_slot(
    slot_id: int,
    db: AsyncSession = Depends(get_async_session),
):
    """删除 Slot（默认 3 个不可删，占用中的不可删）"""
    if slot_id in _DEFAULT_SLOT_IDS:
        return ApiResponse(success=False, error="默认 Slot 不可删除，可以停用")

    slot = await db.get(EnvironmentSlot, slot_id)
    if not slot:
        return ApiResponse(success=False, error="Slot 不存在")
    if slot.status == "occupied":
        return ApiResponse(success=False, error="Slot 正在使用中，无法删除")

    await db.delete(slot)
    await db.commit()
    return ApiResponse(data={"id": slot_id})
