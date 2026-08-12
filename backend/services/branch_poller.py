# backend/services/branch_poller.py
"""GitHub 分支轮询服务：检测 Fenix 仓库的新分支和更新"""
import fnmatch
import logging
import shutil
from pathlib import Path
from datetime import datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.config import async_session
from backend.db.models import BranchTracker, Setting

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BRANCHES_DIR = PROJECT_ROOT / "branches"


class BranchPoller:
    """轮询 GitHub API 检测 Fenix 仓库分支变化"""

    async def _get_settings(self, db: AsyncSession) -> dict[str, str]:
        """读取分支轮询相关配置"""
        result = await db.execute(select(Setting))
        settings = {s.key: s.value for s in result.scalars().all()}
        return settings

    def _parse_repo(self, repo_url: str) -> tuple[str, str]:
        """从仓库 URL 提取 owner/repo，如 https://github.com/owner/repo → (owner, repo)"""
        parts = repo_url.rstrip("/").split("/")
        return parts[-2], parts[-1]

    def _match_branch(self, name: str, include: str, exclude: str) -> bool:
        """判断分支名是否匹配 include/exclude 规则"""
        include_patterns = [p.strip() for p in include.split(",") if p.strip()]
        exclude_patterns = [p.strip() for p in exclude.split(",") if p.strip()]

        if exclude_patterns and any(fnmatch.fnmatch(name, p) for p in exclude_patterns):
            return False
        if include_patterns and not any(fnmatch.fnmatch(name, p) for p in include_patterns):
            return False
        return True

    async def poll_once(self) -> dict:
        """执行一次轮询，返回结果摘要"""
        async with async_session() as db:
            settings = await self._get_settings(db)

            enabled = settings.get("branch_poll_enabled", "false") == "true"
            if not enabled:
                return {"status": "disabled"}

            repo_url = settings.get("branch_poll_repo", "")
            github_token = settings.get("github_token", "")
            include = settings.get("branch_poll_include", "*")
            exclude = settings.get("branch_poll_exclude", "")

            if not repo_url:
                return {"status": "error", "message": "branch_poll_repo not configured"}

            owner, repo = self._parse_repo(repo_url)

            # 调用 GitHub API
            headers = {"Accept": "application/vnd.github.v3+json"}
            if github_token:
                headers["Authorization"] = f"Bearer {github_token}"

            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        f"https://api.github.com/repos/{owner}/{repo}/branches",
                        headers=headers,
                        params={"per_page": 100},
                        timeout=30,
                    )
                    resp.raise_for_status()
                    remote_branches = resp.json()
            except Exception as e:
                logger.error(f"GitHub API error: {e}")
                return {"status": "error", "message": str(e)}

            # 获取已有追踪记录
            result = await db.execute(select(BranchTracker))
            trackers = {t.branch_name: t for t in result.scalars().all()}

            new_branches = []
            updated_branches = []

            for rb in remote_branches:
                name = rb["name"]
                sha = rb["commit"]["sha"]

                # 跳过 main/master
                if name in ("main", "master"):
                    continue

                if not self._match_branch(name, include, exclude):
                    continue

                if name not in trackers:
                    # 新分支
                    tracker = BranchTracker(
                        branch_name=name,
                        last_commit_sha=sha,
                        status="up_to_date",
                    )
                    db.add(tracker)
                    new_branches.append(name)
                    # 创建分支目录
                    self._create_branch_dirs(name)
                else:
                    tracker = trackers[name]
                    if tracker.last_commit_sha != sha:
                        tracker.last_commit_sha = sha
                        tracker.status = "needs_update"
                        updated_branches.append(name)

            # 检测已删除的分支
            remote_names = {rb["name"] for rb in remote_branches}
            deleted_branches = []
            for name, tracker in trackers.items():
                if name not in remote_names and tracker.status != "deleted":
                    tracker.status = "deleted"
                    deleted_branches.append(name)

            await db.commit()

            return {
                "status": "ok",
                "new": new_branches,
                "updated": updated_branches,
                "deleted": deleted_branches,
                "total_remote": len(remote_branches),
            }

    def _create_branch_dirs(self, branch_name: str):
        """从 main 复制 API 和单元测试用例到分支目录"""
        branch_dir = BRANCHES_DIR / branch_name
        if branch_dir.exists():
            return

        branch_dir.mkdir(parents=True, exist_ok=True)

        # 复制 API 测试用例
        api_suites_src = PROJECT_ROOT / "tests" / "api_suites"
        api_suites_dst = branch_dir / "api_suites"
        if api_suites_src.exists() and not api_suites_dst.exists():
            shutil.copytree(api_suites_src, api_suites_dst)
            logger.info(f"Copied API suites to branches/{branch_name}/api_suites/")

        # 复制单元测试用例
        unit_tests_src = PROJECT_ROOT / "unit_tests"
        unit_tests_dst = branch_dir / "unit_tests"
        if unit_tests_src.exists() and not unit_tests_dst.exists():
            shutil.copytree(unit_tests_src, unit_tests_dst)
            logger.info(f"Copied unit tests to branches/{branch_name}/unit_tests/")
