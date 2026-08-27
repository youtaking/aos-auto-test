# engine/runner.py
"""测试执行引擎：调度 pytest 运行，收集结果"""
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, List


@dataclass
class CaseResult:
    """单条用例运行结果"""
    suite_name: str
    case_name: str
    file_path: str
    function_name: str
    status: str  # passed / failed / skipped / error
    duration_ms: int = 0
    error_message: Optional[str] = None
    stack_trace: Optional[str] = None
    screenshot_path: Optional[str] = None


@dataclass
class RunResult:
    """一次完整运行的结果"""
    started_at: datetime = field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None
    results: List[CaseResult] = field(default_factory=list)
    status: str = "pending"

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.status == "passed")

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.status in ("failed", "error"))

    @property
    def skipped(self) -> int:
        return sum(1 for r in self.results if r.status == "skipped")


class TestRunner:
    """测试运行器：调用 pytest 并解析结果"""

    __test__ = False  # 防止 pytest 误收集此类为测试类

    def __init__(self, test_dir: str = "tests/suites"):
        self.test_dir = test_dir

    def collect_tests(self) -> list[dict]:
        """通过 pytest --collect-only 扫描所有测试用例"""
        result = subprocess.run(
            [sys.executable, "-m", "pytest", self.test_dir, "--collect-only", "-q",
             "--no-header", "-p", "no:cacheprovider"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )

        stdout = result.stdout or ""
        collected = []

        # 兼容 pytest 8.x 树形输出和旧版扁平输出
        current_file = ""
        current_class = ""
        current_class_indent = -1
        for line in stdout.splitlines():
            line_stripped = line.strip()

            # 树形格式：<Module test_login.py>
            if "<Module " in line_stripped:
                module_name = line_stripped.split("<Module ")[-1].rstrip(">").strip()
                current_file = f"tests/suites/{module_name}"
                current_class = ""
                current_class_indent = -1
                continue

            # 树形格式：<Class TestXxx>
            if "<Class " in line_stripped:
                current_class = line_stripped.split("<Class ")[-1].rstrip(">").strip()
                current_class_indent = len(line) - len(line.lstrip())
                continue

            # 树形格式：<Function test_xxx>
            if "<Function " in line_stripped and current_file:
                # 模块级函数与类同级缩进，说明已离开类作用域，须重置类前缀
                if current_class and len(line) - len(line.lstrip()) <= current_class_indent:
                    current_class = ""
                func_name = line_stripped.split("<Function ")[-1].rstrip(">").strip()
                if current_class:
                    func_name = f"{current_class}::{func_name}"
                suite_name = Path(current_file).stem.replace("test_", "")
                collected.append({
                    "suite_name": suite_name,
                    "file_path": current_file,
                    "function_name": func_name,
                })
                continue

            # 旧版扁平格式：tests/suites/test_login.py::test_xxx
            if "::" in line_stripped and line_stripped.startswith(("tests/", ".")):
                parts = line_stripped.split("::")
                if len(parts) >= 2:
                    file_path = parts[0]
                    func_name = parts[-1]
                    suite_name = Path(file_path).stem.replace("test_", "")
                    collected.append({
                        "suite_name": suite_name,
                        "file_path": file_path,
                        "function_name": func_name,
                    })

        return collected

    def collect_tests_api(self, test_dir: str = "tests/api_suites") -> list[dict]:
        """扫描 api_suites 目录的测试用例"""
        return self._collect_from_dir(test_dir)

    def _collect_from_dir(self, test_dir: str) -> list[dict]:
        """从指定目录收集测试用例"""
        result = subprocess.run(
            [sys.executable, "-m", "pytest", test_dir, "--collect-only", "-q",
             "--no-header", "-p", "no:cacheprovider"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )

        stdout = result.stdout or ""
        collected = []
        current_file = ""
        current_class = ""
        current_class_indent = -1

        for line in stdout.splitlines():
            line_stripped = line.strip()

            if "<Module " in line_stripped:
                module_name = line_stripped.split("<Module ")[-1].rstrip(">").strip()
                current_file = f"{test_dir}/{module_name}"
                current_class = ""
                current_class_indent = -1
                continue

            if "<Class " in line_stripped:
                current_class = line_stripped.split("<Class ")[-1].rstrip(">").strip()
                current_class_indent = len(line) - len(line.lstrip())
                continue

            if "<Function " in line_stripped and current_file:
                # 模块级函数与类同级缩进，说明已离开类作用域，须重置类前缀
                if current_class and len(line) - len(line.lstrip()) <= current_class_indent:
                    current_class = ""
                func_name = line_stripped.split("<Function ")[-1].rstrip(">").strip()
                if current_class:
                    func_name = f"{current_class}::{func_name}"
                suite_name = Path(current_file).stem.replace("test_", "")
                collected.append({
                    "suite_name": suite_name,
                    "file_path": current_file,
                    "function_name": func_name,
                })
                continue

            if "::" in line_stripped and line_stripped.startswith(("tests/", ".")):
                parts = line_stripped.split("::")
                if len(parts) >= 2:
                    file_path = parts[0]
                    func_name = parts[-1]
                    suite_name = Path(file_path).stem.replace("test_", "")
                    collected.append({
                        "suite_name": suite_name,
                        "file_path": file_path,
                        "function_name": func_name,
                    })

        return collected

    def run(
        self,
        suite_names: Optional[list[str]] = None,
        report_path: str = "report.json",
    ) -> RunResult:
        """执行 pytest 并生成 JSON 报告"""
        run_result = RunResult(started_at=datetime.utcnow())

        cmd = [
            sys.executable, "-m", "pytest", self.test_dir,
            "-v", "--tb=short",
            f"--json-report", f"--json-report-file={report_path}",
        ]

        if suite_names:
            for name in suite_names:
                cmd.append(f"test_{name}.py")

        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")

        run_result.finished_at = datetime.utcnow()

        report_file = Path(report_path)
        if report_file.exists():
            with open(report_file, "r", encoding="utf-8") as f:
                report_data = json.load(f)

            for test in report_data.get("tests", []):
                nodeid = test.get("nodeid", "")
                parts = nodeid.split("::")
                file_path = parts[0] if parts else ""
                func_name = parts[1] if len(parts) > 1 else ""
                suite_name = Path(file_path).stem.replace("test_", "")

                status_map = {
                    "passed": "passed",
                    "failed": "failed",
                    "skipped": "skipped",
                    "error": "error",
                }
                outcome = test.get("outcome", "error")
                call_info = test.get("call", {})
                duration_ms = int(call_info.get("duration", 0) * 1000)
                longrepr = call_info.get("longrepr", "")

                # teardown 失败时从 teardown 阶段获取错误信息
                if not longrepr:
                    teardown_info = test.get("teardown", {})
                    if teardown_info.get("outcome") == "failed":
                        td_longrepr = teardown_info.get("longrepr", "")
                        if td_longrepr:
                            longrepr = td_longrepr

                run_result.results.append(CaseResult(
                    suite_name=suite_name,
                    case_name=func_name,
                    file_path=file_path,
                    function_name=func_name,
                    status=status_map.get(outcome, "error"),
                    duration_ms=duration_ms,
                    error_message=str(longrepr)[:500] if longrepr else None,
                    stack_trace=str(longrepr) if longrepr else None,
                ))

        run_result.status = "passed" if run_result.failed == 0 else "failed"
        return run_result
