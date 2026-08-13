# backend/api/settings.py
"""系统配置 API — key-value 存储"""
import logging
import os
import platform
import subprocess
import traceback
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.db.config import get_async_session
from backend.db.models import Setting
from backend.schemas.common import ApiResponse

router = APIRouter()
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
JUNCTION_PATH = PROJECT_ROOT / "fenix-source"

# 预定义的配置项及其默认值和描述
DEFAULT_SETTINGS = {
    "fenix_source_path": {
        "default": "",
        "description": "FenixAgent 源码 src 目录路径（用于单元测试模块解析 @fenix/* 导入）",
    },
    "branch_poll_enabled": {
        "default": "false",
        "description": "是否启用 Fenix 分支轮询",
    },
    "branch_poll_interval": {
        "default": "30",
        "description": "分支轮询间隔（分钟）",
    },
    "branch_poll_repo": {
        "default": "https://github.com/HuangPuStar/FenixAgent",
        "description": "Fenix 仓库地址",
    },
    "github_token": {
        "default": "",
        "description": "GitHub Personal Access Token（用于轮询私有仓库）",
    },
}


class SettingUpdate(BaseModel):
    value: str
    description: str | None = None


def _is_junction(path: Path) -> bool:
    """判断路径是否为 Windows 目录联接（Junction）。"""
    try:
        # Python 3.12+
        return os.path.isjunction(path)
    except AttributeError:
        # Python < 3.12：联接不是 symlink，但是 is_dir() 返回 True
        # 通过检查 reparse point 来判断
        if platform.system() != "Windows":
            return False
        if not path.exists() or path.is_symlink():
            return False
        try:
            import ctypes
            FILE_ATTRIBUTE_REPARSE_POINT = 0x400
            attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
            return bool(attrs & FILE_ATTRIBUTE_REPARSE_POINT)
        except Exception:
            return False


def _remove_junction():
    """安全删除已有的联接/symlink/目录。"""
    if JUNCTION_PATH.is_symlink():
        JUNCTION_PATH.unlink()
    elif _is_junction(JUNCTION_PATH):
        os.rmdir(str(JUNCTION_PATH))  # os.rmdir 可以正确删除 junction
    elif JUNCTION_PATH.is_dir():
        import shutil
        shutil.rmtree(JUNCTION_PATH)


def _create_junction(target: str) -> tuple[bool, str]:
    """创建 fenix-source 联接，指向 target 路径。返回 (成功, 消息)。"""
    target_path = Path(target).resolve()
    if not target_path.exists():
        return False, f"目标路径不存在: {target_path}"

    # 删除旧的联接/目录
    if JUNCTION_PATH.is_symlink() or JUNCTION_PATH.exists():
        try:
            _remove_junction()
        except Exception as e:
            return False, f"删除旧的联接失败: {e}"

    # 创建联接
    is_windows = platform.system() == "Windows"
    try:
        if is_windows:
            # mklink /J 创建目录联接（不需要管理员权限）
            subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(JUNCTION_PATH), str(target_path)],
                check=True, capture_output=True,
            )
        else:
            os.symlink(str(target_path), str(JUNCTION_PATH), target_is_directory=True)
    except Exception as e:
        return False, f"创建联接失败: {e}"

    return True, f"fenix-source → {target_path}"


@router.get("/settings", response_model=ApiResponse)
async def list_settings(db: AsyncSession = Depends(get_async_session)):
    """获取所有配置项"""
    result = await db.execute(select(Setting))
    rows = result.scalars().all()
    stored = {r.key: r for r in rows}

    settings = []
    for key, meta in DEFAULT_SETTINGS.items():
        row = stored.get(key)
        settings.append({
            "key": key,
            "value": row.value if row else meta["default"],
            "description": row.description if row and row.description else meta["description"],
        })

    return ApiResponse(data=settings)


@router.get("/settings/{key}", response_model=ApiResponse)
async def get_setting(key: str, db: AsyncSession = Depends(get_async_session)):
    """获取单个配置项"""
    result = await db.execute(select(Setting).where(Setting.key == key))
    row = result.scalar_one_or_none()

    meta = DEFAULT_SETTINGS.get(key, {"default": "", "description": ""})
    return ApiResponse(data={
        "key": key,
        "value": row.value if row else meta["default"],
        "description": row.description if row and row.description else meta["description"],
    })


@router.put("/settings/{key}", response_model=ApiResponse)
async def update_setting(
    key: str, body: SettingUpdate, db: AsyncSession = Depends(get_async_session)
):
    """更新配置项（不存在则创建）。fenix_source_path 会自动创建目录联接。"""
    try:
        result = await db.execute(select(Setting).where(Setting.key == key))
        row = result.scalar_one_or_none()

        if row:
            row.value = body.value
            if body.description is not None:
                row.description = body.description
        else:
            meta = DEFAULT_SETTINGS.get(key, {"description": ""})
            row = Setting(
                key=key,
                value=body.value,
                description=body.description or meta["description"],
            )
            db.add(row)

        await db.commit()
        await db.refresh(row)

        # fenix_source_path 保存时自动创建联接
        junction_msg = None
        if key == "fenix_source_path" and body.value.strip():
            ok, msg = _create_junction(body.value.strip())
            junction_msg = msg
            if not ok:
                return ApiResponse(
                    success=False,
                    error=f"路径已保存到数据库，但创建联接失败: {msg}",
                )

        resp_data = {"key": row.key, "value": row.value}
        if junction_msg:
            resp_data["junction"] = junction_msg
        return ApiResponse(data=resp_data)
    except Exception as e:
        logger.error("update_setting error: %s\n%s", e, traceback.format_exc())
        return ApiResponse(success=False, error=f"服务器内部错误: {e}")
