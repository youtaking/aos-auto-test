# engine/reporter.py
"""自定义 pytest Reporter：实时推送测试进度到 RegressionEye 后端"""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional
import httpx


class RegressionEyeReporter:
    """pytest 插件：在每条用例开始/结束时推送状态到后端 API"""

    def __init__(self, run_id: int, backend_url: str = "http://localhost:8000"):
        self.run_id = run_id
        self.backend_url = backend_url
        self._client = httpx.Client(timeout=5.0)
        self._results: list[dict] = []

    def pytest_runtest_logstart(self, nodeid: str, location: tuple):
        """用例开始执行时触发"""
        parts = nodeid.split("::")
        func_name = parts[1] if len(parts) > 1 else nodeid
        self._push("case_started", {
            "case_name": func_name,
            "status": "running",
            "started_at": datetime.utcnow().isoformat(),
        })

    def pytest_runtest_logreport(self, report):
        """用例产生报告时触发（setup/call/teardown 各一次）"""
        if report.when != "call":
            return

        parts = report.nodeid.split("::")
        file_path = parts[0] if parts else ""
        func_name = parts[1] if len(parts) > 1 else ""
        suite_name = Path(file_path).stem.replace("test_", "")

        status_map = {"passed": "passed", "failed": "failed", "skipped": "skipped"}
        status = status_map.get(report.outcome, "error")

        duration_ms = int(report.duration * 1000)
        longrepr = str(report.longrepr) if report.longrepr else None

        result = {
            "suite_name": suite_name,
            "case_name": func_name,
            "file_path": file_path,
            "function_name": func_name,
            "status": status,
            "duration_ms": duration_ms,
            "error_message": longrepr[:500] if longrepr else None,
            "stack_trace": longrepr,
            "screenshot_path": None,
        }
        self._results.append(result)
        self._push("case_finished", result)

    def pytest_sessionfinish(self, session, exitstatus):
        """整个测试会话结束时触发"""
        self._push("run_finished", {
            "status": "passed" if exitstatus == 0 else "failed",
            "total": len(self._results),
            "passed": sum(1 for r in self._results if r["status"] == "passed"),
            "failed": sum(1 for r in self._results if r["status"] in ("failed", "error")),
            "skipped": sum(1 for r in self._results if r["status"] == "skipped"),
        })
        self._client.close()

    def _push(self, event: str, data: dict):
        """推送事件到后端"""
        try:
            self._client.post(
                f"{self.backend_url}/api/runs/{self.run_id}/events",
                json={"event": event, "data": data},
            )
        except Exception:
            pass
