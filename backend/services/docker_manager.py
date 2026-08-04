# backend/services/docker_manager.py
"""Docker 构建与部署管理"""
import asyncio
import os
import shutil
import subprocess
from pathlib import Path

import httpx

from backend.db.models import PRPipeline, EnvironmentSlot

WORK_DIR = Path("/tmp/pr-environments")


def _project_name(pr_id: int) -> str:
    """Docker Compose 项目名，用于隔离不同 PR 的容器"""
    return f"pr-env-{pr_id}"


def _image_tag(pr_id: int, commit_sha: str) -> str:
    """Docker 镜像 tag"""
    return f"fenix-pr-{pr_id}-{commit_sha[:8]}"


def _pr_dir(pr_id: int) -> Path:
    """PR 代码目录"""
    return WORK_DIR / f"pr-{pr_id}"


async def _run_cmd(cmd: list[str], cwd: str | None = None, timeout: int = 600) -> tuple[int, str]:
    """异步执行命令，返回 (returncode, stdout+stderr)"""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=cwd,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return -1, f"Command timed out after {timeout}s"
    output = stdout.decode("utf-8", errors="replace") if stdout else ""
    return proc.returncode or 0, output


def generate_compose_file(pipeline: PRPipeline, slot: EnvironmentSlot) -> str:
    """生成 docker-compose.yml 内容"""
    tag = _image_tag(pipeline.pr_id, pipeline.commit_sha)
    return f"""services:
  postgres:
    image: postgres:16-alpine
    ports:
      - "{slot.postgres_port}:5432"
    environment:
      POSTGRES_USER: rcs
      POSTGRES_PASSWORD: rcs
      POSTGRES_DB: rcs
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U rcs"]
      interval: 5s
      timeout: 5s
      retries: 5

  litellm:
    image: ghcr.io/berriai/litellm:main-stable
    depends_on:
      postgres:
        condition: service_healthy
    ports:
      - "{slot.litellm_port}:4000"
    environment:
      DATABASE_URL: postgresql://rcs:rcs@postgres:5432/litellm
      LITELLM_MASTER_KEY: sk-litellm-admin-dev-key
      LITELLM_SALT_KEY: sk-litellm-salt-dev-key
      STORE_MODEL_IN_DB: "True"

  rcs:
    image: {tag}
    depends_on:
      postgres:
        condition: service_healthy
    ports:
      - "{slot.rcs_port}:3000"
    environment:
      DATABASE_URL: postgres://rcs:rcs@postgres:5432/rcs
      RCS_HOST: 0.0.0.0
      RCS_PORT: 3000
      RCS_SECRET_LITELLM_ADMIN_KEY: sk-litellm-admin-dev-key
    command: ["sh", "-lc", "bun migrate.js && exec bun --no-install run dist/index.js"]
"""


async def clone_and_build(pipeline: PRPipeline) -> str:
    """Clone PR 代码并 Build Docker 镜像，返回镜像 tag"""
    pr_dir = _pr_dir(pipeline.pr_id)

    # 清理旧目录
    if pr_dir.exists():
        shutil.rmtree(pr_dir, ignore_errors=True)
    pr_dir.mkdir(parents=True, exist_ok=True)

    # git clone
    code, output = await _run_cmd([
        "git", "clone",
        "--depth", "1",
        "--branch", pipeline.branch,
        pipeline.repo_url,
        str(pr_dir),
    ], timeout=300)
    if code != 0:
        raise RuntimeError(f"git clone 失败: {output}")

    # docker build
    tag = _image_tag(pipeline.pr_id, pipeline.commit_sha)
    code, output = await _run_cmd([
        "docker", "build",
        "-t", tag,
        str(pr_dir),
    ], cwd=str(pr_dir), timeout=600)
    if code != 0:
        raise RuntimeError(f"docker build 失败: {output}")

    return tag


async def deploy(pipeline: PRPipeline, slot: EnvironmentSlot) -> None:
    """生成 docker-compose 并启动容器"""
    pr_dir = _pr_dir(pipeline.pr_id)
    compose_path = pr_dir / "docker-compose.yml"

    # 写入 docker-compose.yml
    compose_content = generate_compose_file(pipeline, slot)
    compose_path.write_text(compose_content, encoding="utf-8")

    # docker compose up -d
    project = _project_name(pipeline.pr_id)
    code, output = await _run_cmd([
        "docker", "compose",
        "-p", project,
        "-f", str(compose_path),
        "up", "-d",
    ], timeout=120)
    if code != 0:
        raise RuntimeError(f"docker compose up 失败: {output}")


async def wait_healthy(slot: EnvironmentSlot, timeout: int = 120) -> bool:
    """轮询 RCS health endpoint，返回是否健康"""
    health_url = f"http://127.0.0.1:{slot.rcs_port}/health"
    deadline = asyncio.get_event_loop().time() + timeout
    async with httpx.AsyncClient(timeout=5) as client:
        while asyncio.get_event_loop().time() < deadline:
            try:
                resp = await client.get(health_url)
                if resp.status_code == 200:
                    return True
            except Exception:
                pass
            await asyncio.sleep(5)
    return False


async def destroy(pipeline: PRPipeline, slot: EnvironmentSlot) -> None:
    """销毁 PR 环境：docker compose down -v + 清理代码目录"""
    pr_dir = _pr_dir(pipeline.pr_id)
    project = _project_name(pipeline.pr_id)

    # docker compose down -v
    code, _ = await _run_cmd([
        "docker", "compose",
        "-p", project,
        "down", "-v",
    ], timeout=60)

    # 清理 Docker 镜像
    tag = _image_tag(pipeline.pr_id, pipeline.commit_sha)
    await _run_cmd(["docker", "rmi", "-f", tag], timeout=30)

    # 清理代码目录
    if pr_dir.exists():
        shutil.rmtree(pr_dir, ignore_errors=True)
