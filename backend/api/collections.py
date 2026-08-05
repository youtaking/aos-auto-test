# backend/api/collections.py
"""用例集管理 API"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.db.config import get_async_session
from backend.db.models import TestCollection, TestCase
from backend.schemas.collection import CollectionCreate, CollectionUpdate, CollectionResponse
from backend.schemas.common import ApiResponse

router = APIRouter()


@router.get("/collections", response_model=ApiResponse)
async def list_collections(
    project_id: int | None = None,
    db: AsyncSession = Depends(get_async_session),
):
    """获取用例集列表"""
    query = select(TestCollection).order_by(TestCollection.created_at.desc())
    if project_id:
        query = query.where(TestCollection.project_id == project_id)
    result = await db.execute(query)
    collections = result.scalars().all()
    return ApiResponse(data=[CollectionResponse.model_validate(c).model_dump() for c in collections])


@router.post("/collections", response_model=ApiResponse)
async def create_collection(
    body: CollectionCreate,
    db: AsyncSession = Depends(get_async_session),
):
    """创建用例集"""
    if not body.name.strip():
        return ApiResponse(success=False, error="名称不能为空")

    # 验证 case_ids 中存在的 ID
    valid_ids = []
    if body.case_ids:
        result = await db.execute(
            select(TestCase.id).where(TestCase.id.in_(body.case_ids))
        )
        valid_ids = [r[0] for r in result.all()]

    collection = TestCollection(
        project_id=1,  # 默认项目
        name=body.name.strip(),
        description=body.description,
        case_ids=valid_ids,
    )
    db.add(collection)
    await db.commit()
    await db.refresh(collection)
    return ApiResponse(data=CollectionResponse.model_validate(collection).model_dump())


@router.get("/collections/{collection_id}", response_model=ApiResponse)
async def get_collection(
    collection_id: int,
    db: AsyncSession = Depends(get_async_session),
):
    """获取用例集详情（含关联用例信息）"""
    collection = await db.get(TestCollection, collection_id)
    if not collection:
        return ApiResponse(success=False, error="用例集不存在")

    data = CollectionResponse.model_validate(collection).model_dump()

    # 附带关联用例的详细信息
    cases_info = []
    if collection.case_ids:
        result = await db.execute(
            select(TestCase).where(TestCase.id.in_(collection.case_ids))
        )
        cases = result.scalars().all()
        cases_info = [
            {"id": c.id, "name": c.name, "suite_id": c.suite_id,
             "file_path": c.file_path, "function_name": c.function_name,
             "tags": c.tags, "priority": c.priority}
            for c in cases
        ]
    data["cases"] = cases_info
    return ApiResponse(data=data)


@router.put("/collections/{collection_id}", response_model=ApiResponse)
async def update_collection(
    collection_id: int,
    body: CollectionUpdate,
    db: AsyncSession = Depends(get_async_session),
):
    """更新用例集"""
    collection = await db.get(TestCollection, collection_id)
    if not collection:
        return ApiResponse(success=False, error="用例集不存在")

    if body.name is not None:
        collection.name = body.name.strip()
    if body.description is not None:
        collection.description = body.description
    if body.case_ids is not None:
        # 验证 case_ids
        result = await db.execute(
            select(TestCase.id).where(TestCase.id.in_(body.case_ids))
        )
        collection.case_ids = [r[0] for r in result.all()]

    await db.commit()
    await db.refresh(collection)
    return ApiResponse(data=CollectionResponse.model_validate(collection).model_dump())


@router.delete("/collections/{collection_id}", response_model=ApiResponse)
async def delete_collection(
    collection_id: int,
    db: AsyncSession = Depends(get_async_session),
):
    """删除用例集"""
    collection = await db.get(TestCollection, collection_id)
    if not collection:
        return ApiResponse(success=False, error="用例集不存在")

    await db.delete(collection)
    await db.commit()
    return ApiResponse(data={"message": "已删除"})
