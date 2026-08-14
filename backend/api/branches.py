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
from backend.schemas.branch import BranchCreate, BranchAction, GenerateRequest
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
    # 通过检查 api_suites 或 unit_tests 子目录判断是否为有效分支目录
    fs_branches = set()
    if BRANCHES_DIR.exists():
        for d in BRANCHES_DIR.rglob("*"):
            if d.is_dir() and ((d / "api_suites").exists() or (d / "unit_tests").exists()):
                # 用相对路径作为分支名（支持 feature/xxx 嵌套）
                # Windows 路径用反斜杠，统一转为正斜杠
                fs_branches.add(d.relative_to(BRANCHES_DIR).as_posix())

    data = []
    tracked_names = set()
    for t in trackers:
        tracked_names.add(t.branch_name)
        data.append({
            "branch_name": t.branch_name,
            "last_commit_sha": t.last_commit_sha,
            "pr_number": t.pr_number,
            "dev_status": t.dev_status,
            "case_status": t.case_status,
            "discovered_at": t.discovered_at.isoformat() if t.discovered_at else None,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
            "has_dir": t.branch_name in fs_branches,
        })

    # 文件系统中有但数据库没有的
    for name in fs_branches - tracked_names:
        data.append({
            "branch_name": name,
            "last_commit_sha": "",
            "pr_number": None,
            "dev_status": "manual",
            "case_status": "active",
            "discovered_at": None,
            "updated_at": None,
            "has_dir": True,
        })

    # 始终包含 main
    if "main" not in tracked_names and "main" not in fs_branches:
        data.insert(0, {
            "branch_name": "main",
            "last_commit_sha": "",
            "pr_number": None,
            "dev_status": "up_to_date",
            "case_status": "active",
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

    # 检查是否已有追踪记录
    result = await db.execute(
        select(BranchTracker).where(BranchTracker.branch_name == branch_name)
    )
    tracker = result.scalars().first()

    if branch_dir.exists() and tracker and tracker.case_status != "pending":
        raise HTTPException(status_code=400, detail=f"分支已创建: {branch_name}")

    if not branch_dir.exists():
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

    # 入库：轮询可能已创建追踪记录，存在则更新状态
    if tracker:
        tracker.case_status = "active"
    else:
        tracker = BranchTracker(branch_name=branch_name, dev_status="manual", case_status="active")
        db.add(tracker)
    await db.commit()

    return ApiResponse(data={
        "branch_name": branch_name,
        "api_suites_copied": (branch_dir / "api_suites").exists(),
        "unit_tests_copied": (branch_dir / "unit_tests").exists(),
    })


@router.post("/branches/reset", response_model=ApiResponse)
async def reset_branch(
    body: BranchAction,
    db: AsyncSession = Depends(get_async_session),
):
    """重置分支用例：删除分支目录下的用例，从 main 重新复制"""
    branch_name = body.branch_name
    _validate_branch_name(branch_name)

    if branch_name == "main":
        raise HTTPException(status_code=400, detail="不能重置 main 分支")

    branch_dir = BRANCHES_DIR / branch_name
    if not branch_dir.exists():
        raise HTTPException(status_code=404, detail=f"分支目录不存在: {branch_name}")

    # 删除现有用例目录
    api_dst = branch_dir / "api_suites"
    unit_dst = branch_dir / "unit_tests"
    if api_dst.exists():
        shutil.rmtree(api_dst)
    if unit_dst.exists():
        shutil.rmtree(unit_dst)

    # 从 main 重新复制
    api_src = PROJECT_ROOT / "tests" / "api_suites"
    unit_src = PROJECT_ROOT / "unit_tests"
    if api_src.exists():
        shutil.copytree(api_src, api_dst)
    if unit_src.exists():
        shutil.copytree(unit_src, unit_dst)

    # 更新追踪记录状态
    result = await db.execute(
        select(BranchTracker).where(BranchTracker.branch_name == branch_name)
    )
    tracker = result.scalars().first()
    if tracker:
        tracker.case_status = "active"
        await db.commit()

    return ApiResponse(data={
        "branch_name": branch_name,
        "api_suites_copied": api_dst.exists(),
        "unit_tests_copied": unit_dst.exists(),
    })


@router.delete("/branches/delete", response_model=ApiResponse)
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


@router.post("/branches/promote", response_model=ApiResponse)
async def promote_branch(body: BranchAction):
    """提取分支中新增的用例文件到 main"""
    branch_name = body.branch_name
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
            "pr_number": t.pr_number,
            "dev_status": t.dev_status,
            "case_status": t.case_status,
            "discovered_at": t.discovered_at.isoformat() if t.discovered_at else None,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        }
        for t in trackers
    ]
    return ApiResponse(data=data)


@router.get("/branches/cases", response_model=ApiResponse)
async def list_branch_cases(branch_name: str):
    """列出指定分支下的测试用例文件"""
    _validate_branch_name(branch_name)
    branch_dir = BRANCHES_DIR / branch_name
    if not branch_dir.exists():
        raise HTTPException(status_code=404, detail=f"分支目录不存在: {branch_name}")

    api_suites = []
    api_dir = branch_dir / "api_suites"
    if api_dir.exists():
        for f in sorted(api_dir.rglob("*.py")):
            api_suites.append({
                "name": f.name,
                "path": f.relative_to(branch_dir).as_posix(),
                "size": f.stat().st_size,
                "modified": f.stat().st_mtime,
            })

    unit_tests = []
    unit_dir = branch_dir / "unit_tests"
    if unit_dir.exists():
        for f in sorted(unit_dir.rglob("*.test.ts")):
            unit_tests.append({
                "name": f.name,
                "path": f.relative_to(branch_dir).as_posix(),
                "size": f.stat().st_size,
                "modified": f.stat().st_mtime,
            })

    return ApiResponse(data={
        "branch_name": branch_name,
        "api_suites": api_suites,
        "unit_tests": unit_tests,
    })


@router.get("/branches/can-generate", response_model=ApiResponse)
async def can_generate():
    """检测本地是否可以拉起 Claude Code"""
    claude_path = shutil.which("claude")
    return ApiResponse(data={
        "can_generate": claude_path is not None,
        "autotest_dir": str(PROJECT_ROOT) if claude_path else None,
    })


@router.post("/branches/generate", response_model=ApiResponse)
async def launch_generate(body: GenerateRequest):
    """拉起 Claude Code 生成分支用例"""
    branch_name = body.branch_name
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
            f"执行 /api-test-from-branch-code，针对分支 {branch_name} "
            f"生成 API 测试用例，写入 branches/{branch_name}/api_suites/"
        )
    else:
        prompt = (
            f"执行 /unit-test-from-branch-code，针对分支 {branch_name} "
            f"生成单元测试用例，写入 branches/{branch_name}/unit_tests/"
        )

    system = platform.system()
    try:
        if system == "Windows":
            # 写入临时 bat 文件（GBK 编码，cmd.exe 默认用 GBK 读取）
            bat_path = PROJECT_ROOT / "_temp" / f"gen-{branch_name.replace('/', '-')}.bat"
            bat_path.parent.mkdir(parents=True, exist_ok=True)
            bat_path.write_text(
                f'@echo off\n'
                f'title gen-{branch_name.replace("/", "-")}\n'
                f'cd /d "{PROJECT_ROOT}"\n'
                f'claude --dangerously-skip-permissions "{prompt}"\n',
                encoding="gbk",
            )
            subprocess.Popen([
                "wt.exe", "--title", f"gen-{branch_name.replace('/', '-')}",
                "cmd", "/k", str(bat_path),
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
