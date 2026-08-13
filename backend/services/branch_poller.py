# backend/services/branch_poller.py
"""GitHub PR 轮询服务：检测 Fenix 仓库的 open PR，跟踪分支用例状态"""
import logging
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.config import async_session
from backend.db.models import BranchTracker, Setting

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BRANCHES_DIR = PROJECT_ROOT / "branches"


class BranchPoller:
    """轮询 GitHub Pulls API，检测 Fenix 仓库 open PR 变化"""

    async def _get_settings(self, db: AsyncSession) -> dict[str, str]:
        """读取分支轮询相关配置"""
        result = await db.execute(select(Setting))
        settings = {s.key: s.value for s in result.scalars().all()}
        return settings

    def _parse_repo(self, repo_url: str) -> tuple[str, str]:
        """从仓库 URL 提取 owner/repo"""
        parts = repo_url.rstrip("/").split("/")
        return parts[-2], parts[-1]

    async def poll_once(self) -> dict:
        """执行一次轮询，返回结果摘要"""
        async with async_session() as db:
            settings = await self._get_settings(db)

            enabled = settings.get("branch_poll_enabled", "false") == "true"
            if not enabled:
                return {"status": "disabled"}

            repo_url = settings.get("branch_poll_repo", "")
            github_token = settings.get("github_token", "")

            if not repo_url:
                return {"status": "error", "message": "branch_poll_repo not configured"}

            owner, repo = self._parse_repo(repo_url)

            headers = {"Accept": "application/vnd.github.v3+json"}
            if github_token:
                headers["Authorization"] = f"Bearer {github_token}"

            # 1. 拉取 open PRs
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        f"https://api.github.com/repos/{owner}/{repo}/pulls",
                        headers=headers,
                        params={"state": "open", "base": "main", "per_page": 100},
                        timeout=30,
                    )
                    resp.raise_for_status()
                    open_prs = resp.json()
            except Exception as e:
                logger.error(f"GitHub API error (open PRs): {e}")
                return {"status": "error", "message": str(e)}

            # 构建 open PR 映射: branch_name -> {sha, pr_number}
            open_branches: dict[str, dict] = {}
            for pr in open_prs:
                branch_name = pr["head"]["ref"]
                sha = pr["head"]["sha"]
                pr_number = pr["number"]
                open_branches[branch_name] = {"sha": sha, "pr_number": pr_number}

            # 2. 获取已有追踪记录
            result = await db.execute(select(BranchTracker))
            trackers = {t.branch_name: t for t in result.scalars().all()}

            new_prs = []
            updated_prs = []

            # 3. 处理 open PRs
            for branch_name, info in open_branches.items():
                if branch_name not in trackers:
                    # 新 PR — 只记录，不创建目录
                    tracker = BranchTracker(
                        branch_name=branch_name,
                        last_commit_sha=info["sha"],
                        pr_number=info["pr_number"],
                        dev_status="open",
                        case_status="pending",
                    )
                    db.add(tracker)
                    new_prs.append(branch_name)
                else:
                    tracker = trackers[branch_name]
                    if tracker.last_commit_sha != info["sha"]:
                        tracker.last_commit_sha = info["sha"]
                        tracker.pr_number = info["pr_number"]
                        updated_prs.append(branch_name)

            # 4. 检测从 open 列表消失的 PR（可能合入或关闭）
            disappeared = []
            for name, tracker in trackers.items():
                if tracker.dev_status != "open":
                    continue  # 只关注 open 状态的
                if name in open_branches:
                    continue  # 还在 open 列表中

                # PR 从 open 消失了，查 closed PRs 判断是合入还是关闭
                pr_status = await self._check_closed_pr(
                    owner, repo, name, headers
                )
                if pr_status == "merged":
                    tracker.dev_status = "merged"
                    if tracker.case_status == "active":
                        tracker.case_status = "ready_to_sync"
                else:
                    tracker.dev_status = "closed"
                    if tracker.case_status == "active":
                        tracker.case_status = "disposable"
                disappeared.append(name)

            await db.commit()

            return {
                "status": "ok",
                "new_prs": new_prs,
                "updated": updated_prs,
                "disappeared": disappeared,
                "total_open_prs": len(open_prs),
            }

    async def _check_closed_pr(
        self, owner: str, repo: str, branch_name: str, headers: dict
    ) -> str:
        """查询已关闭的 PR，判断是 merged 还是 closed"""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"https://api.github.com/repos/{owner}/{repo}/pulls",
                    headers=headers,
                    params={
                        "state": "closed",
                        "head": f"{owner}:{branch_name}",
                        "sort": "updated",
                        "direction": "desc",
                        "per_page": 1,
                    },
                    timeout=30,
                )
                resp.raise_for_status()
                closed_prs = resp.json()

                if closed_prs:
                    pr = closed_prs[0]
                    if pr.get("merged_at"):
                        return "merged"
                    return "closed"
        except Exception as e:
            logger.warning(f"Failed to check closed PR for {branch_name}: {e}")

        # 查不到就默认 closed
        return "closed"
