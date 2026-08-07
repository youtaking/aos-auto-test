# backend/api/unit_tests.py
"""单元测试管理 API"""
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from backend.db.config import get_async_session
from backend.db.models import UnitTestCase, UnitTestResult
from backend.schemas.common import ApiResponse

router = APIRouter()

UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent.parent / "unit_tests"


def discover_unit_tests(base_dir: Path) -> list[dict]:
    """扫描 unit_tests/ 目录，提取 describe/test 结构"""
    cases = []
    for ts_file in base_dir.rglob("*.test.ts"):
        content = ts_file.read_text(encoding="utf-8")
        relative_path = str(ts_file.relative_to(base_dir))

        # 提取 describe 块和 test/it 块
        describes = re.findall(r'describe\(\s*["\'](.+?)["\']', content)
        tests = re.findall(r'(?:test|it)\(\s*["\'](.+?)["\']', content)

        for describe_name in describes:
            for test_name in tests:
                cases.append({
                    "file_path": relative_path,
                    "describe_block": describe_name,
                    "test_name": test_name,
                    "full_name": f"{describe_name} > {test_name}",
                })
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
    """扫描 unit_tests/ 目录，解析并同步用例到 DB"""
    if not UNIT_TESTS_DIR.exists():
        return ApiResponse(success=False, error=f"目录不存在: {UNIT_TESTS_DIR}")

    discovered = discover_unit_tests(UNIT_TESTS_DIR)

    # 清除旧用例
    await db.execute(delete(UnitTestCase))

    # 插入新用例
    for case_data in discovered:
        db.add(UnitTestCase(**case_data))
    await db.commit()

    return ApiResponse(data={
        "discovered": len(discovered),
        "directory": str(UNIT_TESTS_DIR),
    })


@router.post("/unit-tests/results", response_model=ApiResponse)
async def submit_unit_results(
    body: dict,
    db: AsyncSession = Depends(get_async_session),
):
    """提交单元测试运行结果（接受 junit XML 字符串）"""
    pipeline_id = body.get("pipeline_id")
    junit_xml = body.get("junit_xml")

    results_data = []
    if junit_xml:
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".xml", delete=False, encoding="utf-8"
        ) as f:
            f.write(junit_xml)
            tmp_path = f.name
        try:
            results_data = parse_junit_xml(Path(tmp_path))
        finally:
            os.unlink(tmp_path)

    saved = 0
    for r in results_data:
        # 尝试匹配已有用例
        case_result = await db.execute(
            select(UnitTestCase).where(UnitTestCase.test_name == r["name"])
        )
        test_case = case_result.scalars().first()

        db.add(UnitTestResult(
            pipeline_id=pipeline_id,
            test_case_id=test_case.id if test_case else None,
            status=r["status"],
            duration_ms=r["duration_ms"],
            failure_message=r.get("failure_message"),
        ))
        saved += 1

    await db.commit()
    return ApiResponse(data={"saved": saved})


@router.get("/pipelines/{pipeline_id}/unit-results", response_model=ApiResponse)
async def get_pipeline_unit_results(
    pipeline_id: int,
    db: AsyncSession = Depends(get_async_session),
):
    """获取某次 Pipeline 的单元测试结果"""
    result = await db.execute(
        select(UnitTestResult).where(UnitTestResult.pipeline_id == pipeline_id)
    )
    results = result.scalars().all()

    passed = sum(1 for r in results if r.status == "passed")
    failed = sum(1 for r in results if r.status == "failed")
    skipped = sum(1 for r in results if r.status == "skipped")
    total_duration = sum(r.duration_ms or 0 for r in results)

    return ApiResponse(data={
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "duration_ms": total_duration,
        "results": [
            {
                "id": r.id,
                "test_case_id": r.test_case_id,
                "status": r.status,
                "duration_ms": r.duration_ms,
                "failure_message": r.failure_message,
                "ran_at": r.ran_at.isoformat() if r.ran_at else None,
            }
            for r in results
        ],
    })
