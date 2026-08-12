# backend/api/branches.py
"""分支管理 API"""
import logging
import platform
import re
import shutil
import subprocess

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.config import get_async_session
from backend.db.models import BranchTracker
from backend.schemas.common import ApiResponse
from backend.schemas.branch import BranchCreate, GenerateRequest
from backend.services.branch_poller import BranchPoller, PROJECT_ROOT, BRANCHES_DIR

router = APIRouter()
logger = logging.getLogger(__name__)

_BRANCH_RE = re.compile(r'^[a-zA-Z0-9._\-/]+$')


def _validate_branch_name(name: str) -> str:
    """校验分支名，拒绝非法字符和 .. 路径段以防止路径穿越和命令注入。"""
    if not _BRANCH_RE.match(name):
        raise HTTPException(status_code=400, detail=f"Invalid branch name: {name}")
    if '..' in name:
        raise HTTPException(status_code=400, detail=f"Invalid branch name: {name}")
    return name


@router.get("/branches", response_model=ApiResponse)
async def list_branches(db: AsyncSession = Depends(get_async_session)):
    """列出所有分支（从数据库 + 文件系统）"""
    result = await db.execute(select(BranchTracker).order_by(BranchTracker.id))
    trackers = result.scalars().all()

    # 也扫描文件系统中的分支目录（可能有手动创建的）
    fs_branches = set()
    if BRANCHES_DIR.exists():
        for d in BRANCHES_DIR.iterdir():
            if d.is_dir():
                fs_branches.add(d.name)

    data = []
    tracked_names = set()
    for t in trackers:
        tracked_names.add(t.branch_name)
        data.append({
            "branch_name": t.branch_name,
            "last_commit_sha": t.last_commit_sha,
            "status": t.status,
            "discovered_at": t.discovered_at.isoformat() if t.discovered_at else None,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
            "has_dir": t.branch_name in fs_branches,
        })

    # 文件系统中有但数据库没有的
    for name in fs_branches - tracked_names:
        data.append({
            "branch_name": name,
            "last_commit_sha": "",
            "status": "manual",
            "discovered_at": None,
            "updated_at": None,
            "has_dir": True,
        })

    # 始终包含 main
    if "main" not in tracked_names and "main" not in fs_branches:
        data.insert(0, {
            "branch_name": "main",
            "last_commit_sha": "",
            "status": "up_to_date",
            "discovered_at": None,
            "updated_at": None,
            "has_dir": False,
        })

    return ApiResponse(data=data)


@router.post("/branches", response_model=ApiResponse)
async def create_branch(
    body: BranchCreate,
    db: AsyncSession = Depends(get_async_session),
):
    """手动创建分支（从 main 复制用例目录）"""
    branch_name = body.branch_name
    branch_dir = BRANCHES_DIR / branch_name

    if branch_dir.exists():
        raise HTTPException(status_code=400, detail=f"分支目录已存在: {branch_name}")

    branch_dir.mkdir(parents=True, exist_ok=True)

    # 复制 API 用例
    api_src = PROJECT_ROOT / "tests" / "api_suites"
    api_dst = branch_dir / "api_suites"
    if api_src.exists():
        shutil.copytree(api_src, api_dst)

    # 复制单元测试用例
    unit_src = PROJECT_ROOT / "unit_tests"
    unit_dst = branch_dir / "unit_tests"
    if unit_src.exists():
        shutil.copytree(unit_src, unit_dst)

    # 入库
    tracker = BranchTracker(branch_name=branch_name, status="up_to_date")
    db.add(tracker)
    await db.commit()

    return ApiResponse(data={
        "branch_name": branch_name,
        "api_suites_copied": api_dst.exists(),
        "unit_tests_copied": unit_dst.exists(),
    })


@router.delete("/branches/{branch_name}", response_model=ApiResponse)
async def delete_branch(
    branch_name: str,
    db: AsyncSession = Depends(get_async_session),
):
    """删除分支目录和追踪记录"""
    _validate_branch_name(branch_name)
    branch_dir = BRANCHES_DIR / branch_name

    deleted_dir = False
    if branch_dir.exists():
        shutil.rmtree(branch_dir)
        deleted_dir = True

    # 删除追踪记录
    result = await db.execute(
        select(BranchTracker).where(BranchTracker.branch_name == branch_name)
    )
    tracker = result.scalars().first()
    if tracker:
        await db.delete(tracker)
        await db.commit()

    return ApiResponse(data={"branch_name": branch_name, "dir_deleted": deleted_dir})


@router.post("/branches/{branch_name}/promote", response_model=ApiResponse)
async def promote_branch(branch_name: str):
    """提取分支中新增的用例文件到 main"""
    _validate_branch_name(branch_name)
    branch_dir = BRANCHES_DIR / branch_name
    if not branch_dir.exists():
        raise HTTPException(status_code=404, detail=f"分支目录不存在: {branch_name}")

    new_api_files = []
    new_unit_files = []

    # 对比 API 用例
    branch_api = branch_dir / "api_suites"
    main_api = PROJECT_ROOT / "tests" / "api_suites"
    if branch_api.exists() and main_api.exists():
        for f in branch_api.rglob("*.py"):
            relative = f.relative_to(branch_api)
            main_file = main_api / relative
            if not main_file.exists():
                # 新文件，复制到 main
                main_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, main_file)
                new_api_files.append(str(relative))

    # 对比单元测试用例
    branch_unit = branch_dir / "unit_tests"
    main_unit = PROJECT_ROOT / "unit_tests"
    if branch_unit.exists() and main_unit.exists():
        for f in branch_unit.rglob("*.test.ts"):
            relative = f.relative_to(branch_unit)
            main_file = main_unit / relative
            if not main_file.exists():
                main_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, main_file)
                new_unit_files.append(str(relative))

    return ApiResponse(data={
        "branch_name": branch_name,
        "new_api_files": new_api_files,
        "new_unit_files": new_unit_files,
    })


@router.post("/branches/poll-now", response_model=ApiResponse)
async def poll_now():
    """手动触发一次分支轮询"""
    poller = BranchPoller()
    result = await poller.poll_once()
    return ApiResponse(data=result)


@router.get("/branches/trackers", response_model=ApiResponse)
async def get_trackers(db: AsyncSession = Depends(get_async_session)):
    """获取所有分支追踪记录"""
    result = await db.execute(select(BranchTracker).order_by(BranchTracker.updated_at.desc()))
    trackers = result.scalars().all()
    data = [
        {
            "id": t.id,
            "branch_name": t.branch_name,
            "last_commit_sha": t.last_commit_sha,
            "status": t.status,
            "discovered_at": t.discovered_at.isoformat() if t.discovered_at else None,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        }
        for t in trackers
    ]
    return ApiResponse(data=data)


@router.get("/branches/can-generate", response_model=ApiResponse)
async def can_generate():
    """检测本地是否可以拉起 Claude Code"""
    claude_path = shutil.which("claude")
    return ApiResponse(data={
        "can_generate": claude_path is not None,
        "autotest_dir": str(PROJECT_ROOT) if claude_path else None,
    })


@router.post("/branches/{branch_name}/generate", response_model=ApiResponse)
async def launch_generate(branch_name: str, body: GenerateRequest = GenerateRequest()):
    """拉起 Claude Code 生成分支用例"""
    _validate_branch_name(branch_name)

    claude_path = shutil.which("claude")
    if not claude_path:
        raise HTTPException(
            status_code=400,
            detail="Claude Code 未安装或不在 PATH 中，请在本地终端手动执行",
        )

    test_type = body.test_type

    if test_type == "api":
        prompt = (
            f"执行 /api-test-from-code，针对 Fenix 分支 {branch_name} "
            f"生成 API 测试用例，写入 branches/{branch_name}/api_suites/"
        )
    else:
        prompt = (
            f"执行 /unit-test-from-code，针对 Fenix 分支 {branch_name} "
            f"生成单元测试用例，写入 branches/{branch_name}/unit_tests/"
        )

    system = platform.system()
    try:
        if system == "Windows":
            subprocess.Popen([
                "cmd", "/c", "start", "cmd", "/k",
                "cd", "/d", str(PROJECT_ROOT), "&&", "claude", prompt,
            ])
        elif system == "Darwin":
            subprocess.Popen([
                "osascript", "-e",
                f'tell app "Terminal" to do script "cd {PROJECT_ROOT} && claude {prompt}"',
            ])
        else:
            # Linux
            subprocess.Popen([
                "x-terminal-emulator", "-e",
                f"cd {PROJECT_ROOT} && claude {prompt}",
            ])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动 Claude Code 失败: {e}")

    return ApiResponse(data={"branch_name": branch_name, "test_type": test_type, "launched": True})
