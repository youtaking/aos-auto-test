# backend/api/unit_tests.py
"""单元测试管理 API"""
import asyncio
import logging
import re
import shutil
import subprocess
import tempfile
import os
import xml.etree.ElementTree as ET
from pathlib import Path

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from backend.db.config import get_async_session
from backend.db.models import UnitTestCase, UnitTestResult
from backend.schemas.common import ApiResponse

router = APIRouter()

UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent.parent / "unit_tests"


def discover_unit_tests(base_dir: Path) -> list[dict]:
    """扫描 unit_tests/ 目录，提取 describe/test 结构（逐行解析，正确关联 describe → test）"""
    cases = []
    for ts_file in base_dir.rglob("*.test.ts"):
        content = ts_file.read_text(encoding="utf-8")
        relative_path = str(ts_file.relative_to(base_dir))

        # 逐行解析，用缩进/花括号深度追踪当前 describe
        describe_stack: list[str] = []
        brace_depth = 0
        # 记录每个 describe 开始的 brace_depth
        describe_depths: list[int] = []

        for line in content.splitlines():
            stripped = line.strip()

            # 跳过单行注释
            if stripped.startswith("//"):
                continue

            describe_match = re.match(
                r"""describe\s*\(\s*['"](.+?)['"]\s*,""", stripped
            )
            test_match = re.match(
                r"""(?:test|it)\s*\(\s*['"](.+?)['"]\s*,""", stripped
            )

            if describe_match:
                name = describe_match.group(1)
                describe_stack.append(name)
                describe_depths.append(brace_depth)

            if test_match:
                test_name = test_match.group(1)
                describe_name = describe_stack[-1] if describe_stack else "(root)"
                cases.append({
                    "file_path": relative_path,
                    "describe_block": describe_name,
                    "test_name": test_name,
                    "full_name": f"{describe_name} > {test_name}",
                })

            # 跟踪花括号深度
            brace_depth += line.count("{") - line.count("}")

            # 退出 describe 块
            while (
                describe_depths
                and brace_depth <= describe_depths[-1]
            ):
                describe_stack.pop()
                describe_depths.pop()

    return cases


def parse_junit_xml(xml_path: Path) -> list[dict]:
    """解析 bun test 的 junit XML 输出"""
    tree = ET.parse(xml_path)
    results = []
    for testsuite in tree.findall(".//testsuite"):
        for testcase in testsuite.findall("testcase"):
            result = {
                "name": testcase.get("name"),
                "classname": testcase.get("classname"),
                "duration_ms": int(float(testcase.get("time", 0)) * 1000),
                "status": "passed",
                "failure_message": None,
            }
            failure = testcase.find("failure")
            if failure is not None:
                result["status"] = "failed"
                result["failure_message"] = failure.get("message", "")
            skipped = testcase.find("skipped")
            if skipped is not None:
                result["status"] = "skipped"
            results.append(result)
    return results


@router.get("/unit-tests", response_model=ApiResponse)
async def list_unit_tests(db: AsyncSession = Depends(get_async_session)):
    """获取所有单元测试用例（按文件 → describe → test 树形结构）"""
    result = await db.execute(
        select(UnitTestCase).order_by(UnitTestCase.file_path, UnitTestCase.id)
    )
    cases = result.scalars().all()

    # 构建树形结构
    tree: dict[str, dict] = {}
    for c in cases:
        if c.file_path not in tree:
            tree[c.file_path] = {"file_path": c.file_path, "describes": {}}
        d = c.describe_block or "(root)"
        if d not in tree[c.file_path]["describes"]:
            tree[c.file_path]["describes"][d] = []
        tree[c.file_path]["describes"][d].append({
            "id": c.id,
            "test_name": c.test_name,
            "full_name": c.full_name,
        })

    data = []
    for file_info in tree.values():
        data.append({
            "file_path": file_info["file_path"],
            "describes": [
                {"name": name, "tests": tests}
                for name, tests in file_info["describes"].items()
            ],
        })
    return ApiResponse(data=data)


@router.post("/unit-tests/discover", response_model=ApiResponse)
async def discover_tests(db: AsyncSession = Depends(get_async_session)):
    """扫描 unit_tests/ 目录，解析并同步用例到 DB（保留测试结果）"""
    if not UNIT_TESTS_DIR.exists():
        return ApiResponse(success=False, error=f"目录不存在: {UNIT_TESTS_DIR}")

    discovered = discover_unit_tests(UNIT_TESTS_DIR)

    # 按 full_name 去重
    seen = set()
    unique_discovered = []
    for c in discovered:
        if c["full_name"] not in seen:
            seen.add(c["full_name"])
            unique_discovered.append(c)

    new_count, updated_count, removed_count = await _sync_unit_test_cases(db, unique_discovered)

    return ApiResponse(data={
        "discovered": len(unique_discovered),
        "new": new_count,
        "updated": updated_count,
        "removed": removed_count,
    })


async def _sync_unit_test_cases(db: AsyncSession, discovered: list[dict]) -> tuple[int, int, int]:
    """同步单元测试用例：merge 策略，不删除测试结果。
    返回 (new_count, updated_count, removed_count)
    """
    from sqlalchemy import update

    # 获取现有用例
    result = await db.execute(select(UnitTestCase))
    existing = {c.full_name: c for c in result.scalars().all()}

    discovered_names = set()
    new_count = 0
    updated_count = 0

    for case_data in discovered:
        fn = case_data["full_name"]
        discovered_names.add(fn)

        if fn in existing:
            # 更新已有用例
            c = existing[fn]
            c.file_path = case_data["file_path"]
            c.describe_block = case_data.get("describe_block", "")
            c.test_name = case_data["test_name"]
            updated_count += 1
        else:
            # 新增用例
            db.add(UnitTestCase(**case_data))
            new_count += 1

    # 处理被删除的用例：将关联的 results.test_case_id 置 NULL，然后删除用例
    removed_names = set(existing.keys()) - discovered_names
    removed_count = 0
    for fn in removed_names:
        c = existing[fn]
        # 将关联结果的 test_case_id 置 NULL
        await db.execute(
            update(UnitTestResult)
            .where(UnitTestResult.test_case_id == c.id)
            .values(test_case_id=None)
        )
        await db.delete(c)
        removed_count += 1

    await db.commit()
    return new_count, updated_count, removed_count


@router.post("/unit-tests/runs/start", response_model=ApiResponse)
async def start_unit_test_run(
    body: dict,
    db: AsyncSession = Depends(get_async_session),
):
    """创建一条 running 状态的单元测试记录（Pipeline 开始测试时调用）"""
    from backend.db.models import UnitTestRun

    pipeline_id = body.get("pipeline_id")
    run = UnitTestRun(
        total=0, passed=0, failed=0, skipped=0,
        duration_ms=0,
        status="running",
        trigger_type="pipeline",
        pipeline_id=pipeline_id,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return ApiResponse(data={"run_id": run.id, "status": "running"})


@router.put("/unit-tests/runs/{run_id}/status", response_model=ApiResponse)
async def update_unit_test_run_status(
    run_id: int,
    body: dict,
    db: AsyncSession = Depends(get_async_session),
):
    """更新单元测试运行状态（容器崩溃时调用，标记为 error）"""
    from backend.db.models import UnitTestRun

    run = await db.get(UnitTestRun, run_id)
    if not run:
        return ApiResponse(success=False, error="UnitTestRun not found")

    new_status = body.get("status", "error")
    run.status = new_status
    await db.commit()
    return ApiResponse(data={"run_id": run.id, "status": new_status})


@router.post("/unit-tests/results", response_model=ApiResponse)
async def submit_unit_results(
    body: dict,
    db: AsyncSession = Depends(get_async_session),
):
    """提交单元测试运行结果（接受 junit XML 字符串，Pipeline 调用）"""
    from backend.db.models import UnitTestRun

    pipeline_id = body.get("pipeline_id")
    junit_xml = body.get("junit_xml")
    existing_run_id = body.get("run_id")  # 可选：更新已有的 running 记录

    logger.info(f"[unit-results] pipeline_id={pipeline_id}, run_id={existing_run_id}, "
                f"has_junit_xml={bool(junit_xml)}, has_results={bool(body.get('results'))}")

    results_data = []
    if junit_xml:
        logger.info(f"[unit-results] junit_xml length: {len(junit_xml)} chars")
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".xml", delete=False, encoding="utf-8"
        ) as f:
            f.write(junit_xml)
            tmp_path = f.name
        try:
            results_data = parse_junit_xml(Path(tmp_path))
        finally:
            os.unlink(tmp_path)
        logger.info(f"[unit-results] parsed {len(results_data)} test cases from XML")
    elif body.get("results"):
        # 直接传入结构化结果列表（调试 / 非 Jenkins 场景）
        results_data = body["results"]
        logger.info(f"[unit-results] received {len(results_data)} results directly")

    if not results_data:
        logger.warning(f"[unit-results] no results data, returning saved=0")
        return ApiResponse(data={"saved": 0})

    # 统计
    total = len(results_data)
    passed = sum(1 for r in results_data if r["status"] == "passed")
    failed = sum(1 for r in results_data if r["status"] == "failed")
    skipped = sum(1 for r in results_data if r["status"] == "skipped")
    duration_ms = sum(r.get("duration_ms", 0) for r in results_data)
    final_status = "failed" if failed > 0 else "completed"

    # 更新已有 running 记录 或 创建新记录
    unit_run = None
    if existing_run_id:
        result = await db.execute(
            select(UnitTestRun).where(UnitTestRun.id == int(existing_run_id))
        )
        unit_run = result.scalars().first()
        if unit_run:
            unit_run.total = total
            unit_run.passed = passed
            unit_run.failed = failed
            unit_run.skipped = skipped
            unit_run.duration_ms = duration_ms
            unit_run.status = final_status

    if not unit_run:
        unit_run = UnitTestRun(
            total=total, passed=passed, failed=failed, skipped=skipped,
            duration_ms=duration_ms, status=final_status,
            trigger_type="pipeline", pipeline_id=pipeline_id,
        )
        db.add(unit_run)
    await db.flush()

    # 删除旧的 UnitTestResult（如果是重新上传）
    del_result = await db.execute(
        delete(UnitTestResult).where(UnitTestResult.run_id == unit_run.id)
    )
    if del_result.rowcount:
        logger.info(f"[unit-results] deleted {del_result.rowcount} old results for run_id={unit_run.id}")

    saved = 0
    for r in results_data:
        # 尝试匹配已有用例
        case_result = await db.execute(
            select(UnitTestCase).where(UnitTestCase.test_name == r["name"])
        )
        test_case = case_result.scalars().first()

        db.add(UnitTestResult(
            run_id=unit_run.id,
            pipeline_id=pipeline_id,
            test_case_id=test_case.id if test_case else None,
            name=r["name"],
            classname=r.get("classname", ""),
            status=r["status"],
            duration_ms=r["duration_ms"],
            failure_message=r.get("failure_message"),
        ))
        saved += 1

    await db.commit()
    logger.info(f"[unit-results] saved {saved} results for run_id={unit_run.id}, pipeline_id={pipeline_id}")
    return ApiResponse(data={"saved": saved, "run_id": unit_run.id})


@router.get("/pipelines/{pipeline_id}/unit-results", response_model=ApiResponse)
async def get_pipeline_unit_results(
    pipeline_id: int,
    db: AsyncSession = Depends(get_async_session),
):
    """获取某次 Pipeline 的单元测试结果"""
    from backend.db.models import UnitTestRun

    # 查找该 pipeline 的 UnitTestRun 记录
    run_result = await db.execute(
        select(UnitTestRun)
        .where(UnitTestRun.pipeline_id == pipeline_id)
        .order_by(UnitTestRun.id.desc())
    )
    unit_run = run_result.scalars().first()

    if not unit_run:
        return ApiResponse(data={
            "status": "not_run",
            "total": 0, "passed": 0, "failed": 0, "skipped": 0,
            "duration_ms": 0, "results": [],
        })

    result = await db.execute(
        select(UnitTestResult).where(UnitTestResult.run_id == unit_run.id)
    )
    results = result.scalars().all()

    return ApiResponse(data={
        "status": unit_run.status or "completed",
        "run_id": unit_run.id,
        "total": unit_run.total or len(results),
        "passed": unit_run.passed,
        "failed": unit_run.failed,
        "skipped": unit_run.skipped,
        "duration_ms": unit_run.duration_ms,
        "started_at": unit_run.started_at.isoformat() if unit_run.started_at else None,
        "results": [
            {
                "id": r.id,
                "test_case_id": r.test_case_id,
                "name": r.name,
                "classname": r.classname,
                "status": r.status,
                "duration_ms": r.duration_ms,
                "failure_message": r.failure_message,
                "ran_at": r.ran_at.isoformat() if r.ran_at else None,
            }
            for r in results
        ],
    })


@router.post("/unit-tests/run", response_model=ApiResponse)
async def run_unit_tests(
    body: dict = None,
    db: AsyncSession = Depends(get_async_session),
):
    """在后端本地运行 bun test，支持按 test_ids 筛选，结果保存到 DB"""
    if not UNIT_TESTS_DIR.exists():
        return ApiResponse(success=False, error=f"目录不存在: {UNIT_TESTS_DIR}")

    test_ids = (body or {}).get("test_ids", [])

    # 根据 test_ids 构造 bun 命令参数
    bun_path = shutil.which("bun")
    if not bun_path:
        return ApiResponse(success=False, error="bun 未安装或不在 PATH 中")
    bun_args = [bun_path, "test"]
    if test_ids:
        result = await db.execute(
            select(UnitTestCase).where(UnitTestCase.id.in_(test_ids))
        )
        cases = result.scalars().all()
        if not cases:
            return ApiResponse(success=False, error="未找到匹配的测试用例")

        # 查询每个文件的测试总数，判断是否全选
        from sqlalchemy import func
        file_counts_result = await db.execute(
            select(UnitTestCase.file_path, func.count(UnitTestCase.id))
            .group_by(UnitTestCase.file_path)
        )
        total_by_file = dict(file_counts_result.all())

        # 按文件分组选中的测试
        selected_by_file: dict[str, list] = {}
        for c in cases:
            selected_by_file.setdefault(c.file_path, []).append(c)

        # 只需运行选中文件；仅对部分选择的文件加 -t 过滤
        files = list(selected_by_file.keys())
        patterns = []
        all_selected = True
        for fp, file_cases in selected_by_file.items():
            if len(file_cases) < total_by_file.get(fp, 0):
                all_selected = False
                for c in file_cases:
                    if c.describe_block and c.describe_block != "(root)":
                        patterns.append(re.escape(f"{c.describe_block} {c.test_name}"))
                    else:
                        patterns.append(re.escape(c.test_name))

        bun_args.extend(files)
        if not all_selected and patterns:
            pattern_str = "|".join(patterns)
            # Windows 命令行长度限制 ~8000 字符，超长则放弃 -t 运行全部
            if len(pattern_str) < 6000:
                bun_args.extend(["-t", pattern_str])

    results_dir = UNIT_TESTS_DIR / "results"
    results_dir.mkdir(exist_ok=True)
    junit_path = results_dir / "unit-junit.xml"

    # 删除旧报告
    if junit_path.exists():
        junit_path.unlink()

    # 运行 bun test（用 to_thread + subprocess.run 避免 Windows SelectorEventLoop 不支持 create_subprocess_exec）
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                subprocess.run,
                bun_args + [
                    "--reporter=junit",
                    f"--reporter-outfile={junit_path}",
                ],
                cwd=str(UNIT_TESTS_DIR),
                capture_output=True,
            ),
            timeout=120,
        )
        stdout, stderr = result.stdout, result.stderr
    except FileNotFoundError:
        return ApiResponse(success=False, error="bun 未安装或不在 PATH 中")
    except asyncio.TimeoutError:
        return ApiResponse(success=False, error="运行超时 (120s)")

    # 解析结果
    tests = []
    total = passed = failed = skipped = 0
    duration_ms = 0

    if junit_path.exists():
        try:
            tree = ET.parse(junit_path)
            for ts in tree.findall(".//testsuite"):
                # 只统计包含 testcase 的叶子节点，避免嵌套 testsuite 重复计数
                cases = ts.findall("testcase")
                if not cases:
                    continue
                for tc in cases:
                    status = "passed"
                    fail_msg = None
                    if tc.find("failure") is not None:
                        status = "failed"
                        fail_msg = tc.find("failure").get("message", "")
                    elif tc.find("skipped") is not None:
                        status = "skipped"

                    total += 1
                    if status == "failed":
                        failed += 1
                    elif status == "skipped":
                        skipped += 1
                    duration_ms += int(float(tc.get("time", 0)) * 1000)

                    tests.append({
                        "name": tc.get("name", ""),
                        "classname": tc.get("classname", ""),
                        "status": status,
                        "duration_ms": int(float(tc.get("time", 0)) * 1000),
                        "failure_message": fail_msg,
                    })
            passed = total - failed - skipped
        except ET.ParseError as e:
            return ApiResponse(success=False, error=f"JUnit XML 解析失败: {e}")
    else:
        # bun test 可能没有生成 junit（比如 bun 不存在但命令没报错）
        stderr_text = stderr.decode("gbk", errors="replace") if stderr else ""
        stdout_text = stdout.decode("gbk", errors="replace") if stdout else ""
        return ApiResponse(
            success=False,
            error=f"未生成测试报告。\nstdout: {stdout_text[:500]}\nstderr: {stderr_text[:500]}",
        )

    # 保存运行记录到 DB
    from backend.db.models import UnitTestRun, UnitTestResult
    unit_run = UnitTestRun(
        total=total, passed=passed, failed=failed, skipped=skipped,
        duration_ms=duration_ms, trigger_type="manual",
    )
    db.add(unit_run)
    await db.flush()  # 获取 unit_run.id

    for t in tests:
        db.add(UnitTestResult(
            run_id=unit_run.id,
            name=t["name"],
            classname=t["classname"],
            status=t["status"],
            duration_ms=t["duration_ms"],
            failure_message=t.get("failure_message"),
        ))
    await db.commit()

    return ApiResponse(data={
        "run_id": unit_run.id,
        "total": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "duration_ms": duration_ms,
        "tests": tests,
        "exit_code": result.returncode,
    })


@router.get("/unit-tests/runs", response_model=ApiResponse)
async def list_unit_test_runs(db: AsyncSession = Depends(get_async_session)):
    """获取所有单元测试运行记录"""
    from backend.db.models import UnitTestRun
    result = await db.execute(
        select(UnitTestRun).order_by(UnitTestRun.id.desc())
    )
    runs = result.scalars().all()
    return ApiResponse(data=[
        {
            "id": r.id,
            "total": r.total,
            "passed": r.passed,
            "failed": r.failed,
            "skipped": r.skipped,
            "duration_ms": r.duration_ms,
            "trigger_type": r.trigger_type,
            "started_at": r.started_at.isoformat() if r.started_at else None,
        }
        for r in runs
    ])


@router.get("/unit-tests/runs/{run_id}", response_model=ApiResponse)
async def get_unit_test_run(run_id: int, db: AsyncSession = Depends(get_async_session)):
    """获取某次单元测试运行的详细结果"""
    from backend.db.models import UnitTestRun
    result = await db.execute(
        select(UnitTestRun).where(UnitTestRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        return ApiResponse(success=False, error="运行记录不存在")

    results = await db.execute(
        select(UnitTestResult).where(UnitTestResult.run_id == run_id)
    )
    test_results = results.scalars().all()

    return ApiResponse(data={
        "id": run.id,
        "total": run.total,
        "passed": run.passed,
        "failed": run.failed,
        "skipped": run.skipped,
        "duration_ms": run.duration_ms,
        "trigger_type": run.trigger_type,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "tests": [
            {
                "name": r.name,
                "classname": r.classname,
                "status": r.status,
                "duration_ms": r.duration_ms,
                "failure_message": r.failure_message,
            }
            for r in test_results
        ],
    })


@router.get("/unit-tests/runs/{run_id}/report", response_model=ApiResponse)
async def get_unit_test_report(run_id: int, db: AsyncSession = Depends(get_async_session)):
    """生成单元测试 Markdown 报告"""
    from backend.db.models import UnitTestRun
    result = await db.execute(
        select(UnitTestRun).where(UnitTestRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        return ApiResponse(success=False, error="运行记录不存在")

    results = await db.execute(
        select(UnitTestResult).where(UnitTestResult.run_id == run_id)
            .order_by(UnitTestResult.classname, UnitTestResult.id)
    )
    test_results = results.scalars().all()

    # 生成 Markdown
    status_icon = {"passed": "✅", "failed": "❌", "skipped": "⏭️"}
    lines = [
        f"# 单元测试报告 #{run.id}",
        "",
        f"- **时间**: {run.started_at.strftime('%Y-%m-%d %H:%M:%S') if run.started_at else '-'}",
        f"- **总计**: {run.total} | ✅ {run.passed} | ❌ {run.failed} | ⏭️ {run.skipped}",
        f"- **耗时**: {run.duration_ms}ms",
        "",
    ]

    # 按 classname 分组
    from collections import defaultdict
    grouped = defaultdict(list)
    for r in test_results:
        grouped[r.classname or "(root)"].append(r)

    for classname, items in grouped.items():
        lines.append(f"## {classname}")
        lines.append("")
        lines.append("| 状态 | 测试名 | 耗时 | 错误信息 |")
        lines.append("|------|--------|------|----------|")
        for r in items:
            icon = status_icon.get(r.status, "❓")
            fail_msg = (r.failure_message or "")[:100].replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {icon} | {r.name} | {r.duration_ms}ms | {fail_msg} |")
        lines.append("")

    markdown = "\n".join(lines)
    return ApiResponse(data=markdown)
