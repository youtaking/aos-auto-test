# backend/services/docker_manager.py
"""Docker 构建与部署管理：支持本地和 SSH 远程执行"""
import asyncio
from pathlib import Path

import httpx

from backend.db.models import PRPipeline, EnvironmentSlot
from backend.services.executor import CommandExecutor, SSHExecutor


def _project_name(pr_id: int) -> str:
    """Docker Compose 项目名，用于隔离不同 PR 的容器"""
    return f"pr-env-{pr_id}"


def _image_tag(pr_id: int, commit_sha: str) -> str:
    """Docker 镜像 tag"""
    return f"fenix-pr-{pr_id}-{commit_sha[:8]}"


def _pr_dir(pr_id: int, slot: EnvironmentSlot) -> str:
    """PR 代码目录（基于 slot 的 work_dir）"""
    work_dir = slot.work_dir or "/tmp/pr-environments"
    return f"{work_dir}/pr-{pr_id}"


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


async def clone_and_build(
    pipeline: PRPipeline,
    slot: EnvironmentSlot,
    executor: CommandExecutor | SSHExecutor,
) -> str:
    """Clone PR 代码并 Build Docker 镜像，返回镜像 tag"""
    pr_dir = _pr_dir(pipeline.pr_id, slot)

    # 清理旧目录 + 创建新目录
    await executor.remove_dir(pr_dir)
    await executor.mkdir(pr_dir)

    # git clone
    code, output = await executor.run([
        "git", "clone",
        "--depth", "1",
        "--branch", pipeline.branch,
        pipeline.repo_url,
        pr_dir,
    ], timeout=300)
    if code != 0:
        raise RuntimeError(f"git clone 失败: {output}")

    # docker build
    tag = _image_tag(pipeline.pr_id, pipeline.commit_sha)
    code, output = await executor.run([
        "docker", "build",
        "-t", tag,
        pr_dir,
    ], cwd=pr_dir, timeout=600)
    if code != 0:
        raise RuntimeError(f"docker build 失败: {output}")

    return tag


async def deploy(
    pipeline: PRPipeline,
    slot: EnvironmentSlot,
    executor: CommandExecutor | SSHExecutor,
) -> None:
    """生成 docker-compose 并启动容器"""
    pr_dir = _pr_dir(pipeline.pr_id, slot)
    compose_path = f"{pr_dir}/docker-compose.yml"

    # 写入 docker-compose.yml
    compose_content = generate_compose_file(pipeline, slot)
    await executor.write_file(compose_path, compose_content)

    # docker compose up -d
    project = _project_name(pipeline.pr_id)
    code, output = await executor.run([
        "docker", "compose",
        "-p", project,
        "-f", compose_path,
        "up", "-d",
    ], timeout=120)
    if code != 0:
        raise RuntimeError(f"docker compose up 失败: {output}")


async def wait_healthy(slot: EnvironmentSlot, timeout: int = 120) -> bool:
    """轮询 RCS health endpoint，返回是否健康。
    使用 slot.host 作为目标地址（localhost 时用 127.0.0.1）"""
    host = slot.host if slot.host and slot.host not in ("localhost", "127.0.0.1") else "127.0.0.1"
    health_url = f"http://{host}:{slot.rcs_port}/health"
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    async with httpx.AsyncClient(timeout=5) as client:
        while loop.time() < deadline:
            try:
                resp = await client.get(health_url)
                if resp.status_code == 200:
                    return True
            except (httpx.HTTPError, OSError, ConnectionError):
                pass
            await asyncio.sleep(5)
    return False


async def destroy(
    pipeline: PRPipeline,
    slot: EnvironmentSlot,
    executor: CommandExecutor | SSHExecutor,
) -> None:
    """销毁 PR 环境：docker compose down -v + 清理代码目录"""
    pr_dir = _pr_dir(pipeline.pr_id, slot)
    project = _project_name(pipeline.pr_id)

    # docker compose down -v
    await executor.run([
        "docker", "compose",
        "-p", project,
        "down", "-v",
    ], timeout=60)

    # 清理 Docker 镜像
    tag = _image_tag(pipeline.pr_id, pipeline.commit_sha)
    await executor.run(["docker", "rmi", "-f", tag], timeout=30)

    # 清理代码目录
    await executor.remove_dir(pr_dir)
