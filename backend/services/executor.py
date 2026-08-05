# backend/services/executor.py
"""命令执行器：抽象本地和 SSH 远程命令执行"""
import asyncio
import shutil
from pathlib import Path

import asyncssh


class CommandExecutor:
    """本地命令执行器"""

    async def run(
        self, cmd: list[str], cwd: str | None = None, timeout: int = 600
    ) -> tuple[int, str]:
        """执行命令，返回 (returncode, stdout+stderr)"""
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
            await proc.wait()
            return -1, f"Command timed out after {timeout}s"
        output = stdout.decode("utf-8", errors="replace") if stdout else ""
        return proc.returncode or 0, output

    async def write_file(self, path: str, content: str) -> None:
        """写入文件"""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    async def remove_dir(self, path: str) -> None:
        """删除目录"""
        p = Path(path)
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)

    async def mkdir(self, path: str) -> None:
        """创建目录"""
        Path(path).mkdir(parents=True, exist_ok=True)

    async def close(self) -> None:
        """关闭（本地模式无需操作）"""
        pass


class SSHExecutor:
    """SSH 远程命令执行器"""

    def __init__(self):
        self._conn: asyncssh.SSHClientConnection | None = None

    async def connect(
        self,
        host: str,
        user: str = "root",
        port: int = 22,
        key_path: str = "",
        password: str = "",
    ) -> None:
        """建立 SSH 连接"""
        kwargs: dict = {
            "host": host,
            "port": port,
            "username": user,
            "known_hosts": None,  # 跳过 known_hosts 检查
        }
        if key_path:
            kwargs["client_keys"] = [key_path]
        elif password:
            kwargs["password"] = password

        self._conn = await asyncssh.connect(**kwargs)

    async def run(
        self, cmd: list[str], cwd: str | None = None, timeout: int = 600
    ) -> tuple[int, str]:
        """通过 SSH 执行命令，返回 (returncode, stdout+stderr)"""
        if not self._conn:
            raise RuntimeError("SSH 未连接")

        # 构建命令字符串
        cmd_str = " ".join(f"'{c}'" if " " in c else c for c in cmd)
        if cwd:
            cmd_str = f"cd '{cwd}' && {cmd_str}"

        try:
            result = await asyncio.wait_for(
                self._conn.run(cmd_str, check=False),
                timeout=timeout,
            )
            output = (result.stdout or "") + (result.stderr or "")
            return result.exit_status or 0, output
        except asyncio.TimeoutError:
            return -1, f"SSH command timed out after {timeout}s"

    async def write_file(self, path: str, content: str) -> None:
        """通过 SFTP 写入远程文件"""
        if not self._conn:
            raise RuntimeError("SSH 未连接")

        # 确保目录存在
        dir_path = str(Path(path).parent).replace("\\", "/")
        await self._conn.run(f"mkdir -p '{dir_path}'", check=False)

        # 通过 SFTP 写文件
        async with self._conn.start_sftp_client() as sftp:
            async with sftp.open(path, "w") as f:
                await f.write(content)

    async def remove_dir(self, path: str) -> None:
        """通过 SSH 删除远程目录"""
        if not self._conn:
            raise RuntimeError("SSH 未连接")
        await self._conn.run(f"rm -rf '{path}'", check=False)

    async def mkdir(self, path: str) -> None:
        """通过 SSH 创建远程目录"""
        if not self._conn:
            raise RuntimeError("SSH 未连接")
        await self._conn.run(f"mkdir -p '{path}'", check=False)

    async def close(self) -> None:
        """关闭 SSH 连接"""
        if self._conn:
            self._conn.close()
            self._conn = None


def create_executor(slot) -> CommandExecutor | SSHExecutor:
    """根据 Slot 配置创建对应的执行器

    slot.host == 'localhost' 或 '127.0.0.1' 时本地执行，否则 SSH 远程执行。
    SSHExecutor 需要调用方在使用前 await connect()。
    """
    if not slot.host or slot.host in ("localhost", "127.0.0.1"):
        return CommandExecutor()

    executor = SSHExecutor()
    return executor


async def init_executor(executor: CommandExecutor | SSHExecutor, slot) -> None:
    """初始化执行器（SSH 模式需要建立连接）"""
    if isinstance(executor, SSHExecutor):
        await executor.connect(
            host=slot.host,
            user=slot.ssh_user or "root",
            port=slot.ssh_port or 22,
            key_path=slot.ssh_key_path or "",
            password=slot.ssh_password or "",
        )
