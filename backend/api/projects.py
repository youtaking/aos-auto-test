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
