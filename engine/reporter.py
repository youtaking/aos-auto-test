# engine/reporter.py
"""自定义 pytest Reporter：实时推送测试进度到 AutoTest 后端"""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional
import httpx


class AutoTestReporter:
    """pytest 插件：在每条用例开始/结束时推送状态到后端 API"""

    def __init__(self, run_id: int, backend_url: str = "http://localhost:8111"):
        self.run_id = run_id
        self.backend_url = backend_url
        self._client = httpx.Client(timeout=5.0)
        self._results: list[dict] = []
        self._pending_result: Optional[dict] = None

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
        """用例产生报告时触发（setup/call/teardown 各一次）。
        在 teardown 阶段统一推送最终结果，确保捕获 teardown 阶段的失败
        （如 _page_error_monitor fixture 在 teardown 中检测到的 console/API 错误）。"""
        if report.when == "call":
            # 存储 call 阶段结果，等 teardown 后统一推送
            parts = report.nodeid.split("::")
            file_path = parts[0] if parts else ""
            func_name = parts[1] if len(parts) > 1 else ""
            suite_name = Path(file_path).stem.replace("test_", "")

            status_map = {"passed": "passed", "failed": "failed", "skipped": "skipped"}
            status = status_map.get(report.outcome, "error")

            duration_ms = int(report.duration * 1000)
            longrepr = str(report.longrepr) if report.longrepr else None

            self._pending_result = {
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

        elif report.when == "teardown":
            if self._pending_result:
                # teardown 失败时覆盖 call 阶段的结果
                if report.outcome == "failed" and self._pending_result["status"] != "failed":
                    self._pending_result["status"] = "failed"
                    longrepr = str(report.longrepr) if report.longrepr else None
                    if longrepr:
                        self._pending_result["error_message"] = longrepr[:500]
                        self._pending_result["stack_trace"] = longrepr
                self._results.append(self._pending_result)
                self._push("case_finished", self._pending_result)
                self._pending_result = None
            elif report.outcome == "failed":
                # setup 失败（call 未执行），仍需上报
                parts = report.nodeid.split("::")
                file_path = parts[0] if parts else ""
                func_name = parts[1] if len(parts) > 1 else ""
                suite_name = Path(file_path).stem.replace("test_", "")
                longrepr = str(report.longrepr) if report.longrepr else None
                result = {
                    "suite_name": suite_name,
                    "case_name": func_name,
                    "file_path": file_path,
                    "function_name": func_name,
                    "status": "error",
                    "duration_ms": 0,
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
