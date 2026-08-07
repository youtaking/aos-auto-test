# 单元测试模块 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 autotest 项目中新增独立的 TypeScript + bun:test 单元测试模块，测试 FenixAgent 源码，集成到 Jenkins Pipeline 和前端展示。

**Architecture:** autotest 项目新增 `unit_tests/` 子目录，使用 bun:test 框架通过 `@fenix/*` tsconfig 路径别名引用 FenixAgent 源码。Jenkins Pipeline 新增 Build Unit Runner + Run Unit Tests 阶段。后端新增用例发现 API 和结果存储。前端 Cases 页面新增"单元测试" Tab。

**Tech Stack:** Bun, TypeScript, bun:test, FastAPI, SQLAlchemy, React, Docker

## Global Constraints

- 单元测试代码位于 `unit_tests/` 目录，与 FenixAgent 自带 `src/__tests__/` 完全独立
- 每次 PR 全量运行所有单元测试
- 前端只展示用例树和结果，不支持在线编辑
- 所有文件读写使用 UTF-8 编码
- Python 代码遵循现有 backend 模式：FastAPI + SQLAlchemy async + Pydantic

---

### Task 1: 单元测试基础设施搭建

**Files:**
- Create: `unit_tests/package.json`
- Create: `unit_tests/tsconfig.json`
- Create: `unit_tests/bunfig.toml`
- Create: `unit_tests/services/phone-number.test.ts` (smoke test)
- Create: `unit_tests/app/src/services/phone-number.ts` (FenixAgent 源码副本，本地开发用)

**Interfaces:**
- Produces: `@fenix/*` 路径别名解析到 `../app/src/*`

- [ ] **Step 1: 创建 unit_tests 目录和配置文件**

```bash
mkdir -p unit_tests/services unit_tests/errors
```

`unit_tests/package.json`:
```json
{
  "name": "fenix-unit-tests",
  "private": true,
  "type": "module",
  "devDependencies": {
    "@types/bun": "latest"
  }
}
```

`unit_tests/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ES2022",
    "moduleResolution": "bundler",
    "types": ["bun"],
    "strict": true,
    "paths": {
      "@fenix/*": ["../app/src/*"]
    }
  },
  "include": ["**/*.ts"]
}
```

`unit_tests/bunfig.toml`:
```toml
[test]
root = "."
```

- [ ] **Step 2: 复制 FenixAgent 源码到 unit_tests/app/src/ 用于本地开发**

从 `D:\chxu\AI中台\Code\FenixAgent\src\` 复制以下文件到 `unit_tests/app/src/`：
- `services/phone-number.ts`
- `services/automationState.ts`
- `services/build-info.ts`
- `services/config/jsonb.ts`
- `errors.ts`
- `types/api.ts`（仅 AutomationStateResponse 类型）

- [ ] **Step 3: 创建冒烟测试验证基础设施**

`unit_tests/services/phone-number.test.ts`:
```typescript
import { describe, expect, test } from "bun:test";
import {
  normalizeChineseMainlandPhoneNumber,
  buildPhoneTempEmail,
  isEmailIdentifier,
} from "@fenix/services/phone-number";

describe("phone-number", () => {
  test("归一化带 +86 前缀的手机号", () => {
    expect(normalizeChineseMainlandPhoneNumber("+86 188-2648-0215")).toBe("18826480215");
  });

  test("归一化带 86 前缀的 13 位手机号", () => {
    expect(normalizeChineseMainlandPhoneNumber("8618826480215")).toBe("18826480215");
  });

  test("归一化纯 11 位手机号", () => {
    expect(normalizeChineseMainlandPhoneNumber("18826480215")).toBe("18826480215");
  });

  test("拒绝 12 位非法手机号", () => {
    expect(() => normalizeChineseMainlandPhoneNumber("188264802150")).toThrow("手机号格式不正确");
  });

  test("拒绝非 1 开头的手机号", () => {
    expect(() => normalizeChineseMainlandPhoneNumber("28826480215")).toThrow("手机号格式不正确");
  });

  test("生成临时邮箱", () => {
    expect(buildPhoneTempEmail("18826480215")).toBe("18826480215@fenix.com");
  });

  test("判断邮箱标识符 - 包含 @", () => {
    expect(isEmailIdentifier("user@example.com")).toBe(true);
  });

  test("判断邮箱标识符 - 手机号", () => {
    expect(isEmailIdentifier("18826480215")).toBe(false);
  });
});
```

- [ ] **Step 4: 安装依赖并运行测试**

```bash
cd unit_tests && bun install && bun test
```
Expected: 所有测试通过

- [ ] **Step 5: Commit**

```bash
git add unit_tests/
git commit -m "feat: add unit test infrastructure with phone-number tests"
```

---

### Task 2: 编写全部单元测试用例

**Files:**
- Create: `unit_tests/services/automation-state.test.ts`
- Create: `unit_tests/services/build-info.test.ts`
- Create: `unit_tests/services/jsonb.test.ts`
- Create: `unit_tests/errors/error-classes.test.ts`

**Interfaces:**
- Consumes: `@fenix/services/automationState`, `@fenix/services/build-info`, `@fenix/services/config/jsonb`, `@fenix/errors`
- Produces: 完整的单元测试套件

- [ ] **Step 1: automation-state.test.ts**

```typescript
import { describe, expect, test } from "bun:test";
import {
  getAutomationStateSnapshot,
  getAutomationStateEventPayload,
  automationStatesEqual,
} from "@fenix/services/automationState";
import type { AutomationStateResponse } from "@fenix/types/api";

describe("getAutomationStateSnapshot", () => {
  test("metadata 无 automation_state 时返回 undefined", () => {
    expect(getAutomationStateSnapshot({})).toBeUndefined();
    expect(getAutomationStateSnapshot(null)).toBeUndefined();
    expect(getAutomationStateSnapshot(undefined)).toBeUndefined();
  });

  test("automation_state 为 null 时返回 disabled", () => {
    const result = getAutomationStateSnapshot({ automation_state: null });
    expect(result).toEqual({ enabled: false, phase: null, next_tick_at: null, sleep_until: null });
  });

  test("enabled 为 true 时正确归一化", () => {
    const result = getAutomationStateSnapshot({ automation_state: { enabled: true } });
    expect(result?.enabled).toBe(true);
  });

  test("enabled 非 true 值归一化为 false", () => {
    const result = getAutomationStateSnapshot({ automation_state: { enabled: "yes" } });
    expect(result?.enabled).toBe(false);
  });

  test("接受 phase: standby", () => {
    const result = getAutomationStateSnapshot({ automation_state: { enabled: true, phase: "standby" } });
    expect(result?.phase).toBe("standby");
  });

  test("接受 phase: sleeping", () => {
    const result = getAutomationStateSnapshot({ automation_state: { enabled: true, phase: "sleeping" } });
    expect(result?.phase).toBe("sleeping");
  });

  test("拒绝非法 phase 值", () => {
    for (const phase of ["running", "idle", "active", "", null]) {
      const result = getAutomationStateSnapshot({ automation_state: { enabled: true, phase } });
      expect(result?.phase).toBeNull();
    }
  });

  test("归一化 next_tick_at 为 number", () => {
    const result = getAutomationStateSnapshot({ automation_state: { enabled: true, next_tick_at: 12345 } });
    expect(result?.next_tick_at).toBe(12345);
  });

  test("归一化非 number 的 next_tick_at 为 null", () => {
    const result = getAutomationStateSnapshot({ automation_state: { enabled: true, next_tick_at: "soon" } });
    expect(result?.next_tick_at).toBeNull();
  });

  test("完整有效状态归一化", () => {
    const result = getAutomationStateSnapshot({
      automation_state: { enabled: true, phase: "sleeping", next_tick_at: 100, sleep_until: 200 },
    });
    expect(result).toEqual({ enabled: true, phase: "sleeping", next_tick_at: 100, sleep_until: 200 });
  });
});

describe("getAutomationStateEventPayload", () => {
  test("无 metadata 时返回 disabled 默认值", () => {
    const result = getAutomationStateEventPayload({});
    expect(result).toEqual({ enabled: false, phase: null, next_tick_at: null, sleep_until: null });
  });

  test("null metadata 返回 disabled 默认值", () => {
    const result = getAutomationStateEventPayload(null);
    expect(result).toEqual({ enabled: false, phase: null, next_tick_at: null, sleep_until: null });
  });

  test("有 automation_state 时返回归一化值", () => {
    const result = getAutomationStateEventPayload({
      automation_state: { enabled: true, phase: "standby", next_tick_at: 50, sleep_until: 60 },
    });
    expect(result).toEqual({ enabled: true, phase: "standby", next_tick_at: 50, sleep_until: 60 });
  });

  test("每次调用返回新对象", () => {
    const a = getAutomationStateEventPayload({});
    const b = getAutomationStateEventPayload({});
    expect(a).toEqual(b);
    expect(a).not.toBe(b);
  });
});

describe("automationStatesEqual", () => {
  const base: AutomationStateResponse = {
    enabled: true, phase: "standby", next_tick_at: 100, sleep_until: 200,
  };

  test("相同状态返回 true", () => {
    expect(automationStatesEqual(base, { ...base })).toBe(true);
  });

  test("enabled 不同返回 false", () => {
    expect(automationStatesEqual(base, { ...base, enabled: false })).toBe(false);
  });

  test("phase 不同返回 false", () => {
    expect(automationStatesEqual(base, { ...base, phase: "sleeping" })).toBe(false);
  });

  test("next_tick_at 不同返回 false", () => {
    expect(automationStatesEqual(base, { ...base, next_tick_at: 999 })).toBe(false);
  });

  test("sleep_until 不同返回 false", () => {
    expect(automationStatesEqual(base, { ...base, sleep_until: 999 })).toBe(false);
  });

  test("两个 disabled 默认值相等", () => {
    const disabled: AutomationStateResponse = { enabled: false, phase: null, next_tick_at: null, sleep_until: null };
    expect(automationStatesEqual(disabled, { ...disabled })).toBe(true);
  });
});
```

- [ ] **Step 2: build-info.test.ts**

```typescript
import { describe, expect, test } from "bun:test";
import { buildHealthInfo, buildInfo, resolveCommitId } from "@fenix/services/build-info";

describe("resolveCommitId", () => {
  test("无注入且无 git 时返回 unknown", () => {
    expect(resolveCommitId(undefined, () => undefined)).toBe("unknown");
  });

  test("构建注入值优先于 git", () => {
    expect(resolveCommitId("built-commit", () => "working-tree-commit")).toBe("built-commit");
  });

  test("无注入时使用 git 回调", () => {
    expect(resolveCommitId(undefined, () => "startup-commit")).toBe("startup-commit");
  });

  test("空白注入值被忽略", () => {
    expect(resolveCommitId("  ", () => "fallback")).toBe("fallback");
  });

  test("unknown 注入值被忽略", () => {
    expect(resolveCommitId("unknown", () => "fallback")).toBe("fallback");
  });
});

describe("buildHealthInfo", () => {
  test("包含 status ok 和 startedAt", () => {
    const startedAt = "2026-07-31T10:20:30.123Z";
    const result = buildHealthInfo(startedAt);
    expect(result.status).toBe("ok");
    expect(result.startedAt).toBe(startedAt);
    expect(result.commitId).toBe(buildInfo.commitId);
  });
});
```

- [ ] **Step 3: jsonb.test.ts**

```typescript
import { describe, expect, test } from "bun:test";
import { parseJsonb, parseJsonbOr } from "@fenix/services/config/jsonb";

describe("parseJsonb", () => {
  test("null 输入返回 null", () => {
    expect(parseJsonb(null)).toBeNull();
  });

  test("undefined 输入返回 null", () => {
    expect(parseJsonb(undefined)).toBeNull();
  });

  test("正常对象直接返回", () => {
    const obj = { key: "value" };
    expect(parseJsonb(obj)).toEqual(obj);
  });

  test("正常数组直接返回", () => {
    const arr = [1, 2, 3];
    expect(parseJsonb(arr)).toEqual(arr);
  });

  test("JSON 字符串被解析为对象", () => {
    expect(parseJsonb('{"key":"value"}')).toEqual({ key: "value" });
  });

  test("双重编码字符串被正确解析", () => {
    const doubleEncoded = JSON.stringify(JSON.stringify({ key: "value" }));
    expect(parseJsonb(doubleEncoded)).toEqual({ key: "value" });
  });

  test("无效 JSON 字符串返回 null", () => {
    expect(parseJsonb("not-json")).toBeNull();
  });

  test("无效双重编码返回 null", () => {
    expect(parseJsonb('"not-json-after-parse"')).toBeNull();
  });
});

describe("parseJsonbOr", () => {
  test("解析成功返回解析结果", () => {
    expect(parseJsonbOr('{"a":1}', {})).toEqual({ a: 1 });
  });

  test("解析失败返回 fallback", () => {
    const fallback = { default: true };
    expect(parseJsonbOr("invalid", fallback)).toBe(fallback);
  });

  test("null 输入返回 fallback", () => {
    expect(parseJsonbOr(null, "default")).toBe("default");
  });
});
```

- [ ] **Step 4: error-classes.test.ts**

```typescript
import { describe, expect, test } from "bun:test";
import {
  AppError,
  ValidationError,
  NotFoundError,
  ConflictError,
  ConfigWriteError,
} from "@fenix/errors";

describe("AppError", () => {
  test("默认 statusCode 为 500", () => {
    const err = new AppError("something broke", "INTERNAL_ERROR");
    expect(err.statusCode).toBe(500);
    expect(err.code).toBe("INTERNAL_ERROR");
    expect(err.message).toBe("something broke");
    expect(err.name).toBe("AppError");
  });

  test("可自定义 statusCode", () => {
    const err = new AppError("forbidden", "FORBIDDEN", 403);
    expect(err.statusCode).toBe(403);
  });

  test("是 Error 的实例", () => {
    expect(new AppError("x", "X")).toBeInstanceOf(Error);
  });
});

describe("ValidationError", () => {
  test("statusCode 为 400", () => {
    const err = new ValidationError("field required");
    expect(err.statusCode).toBe(400);
    expect(err.code).toBe("VALIDATION_ERROR");
    expect(err.name).toBe("ValidationError");
  });

  test("是 AppError 的实例", () => {
    expect(new ValidationError("x")).toBeInstanceOf(AppError);
  });
});

describe("NotFoundError", () => {
  test("statusCode 为 404", () => {
    const err = new NotFoundError("not found");
    expect(err.statusCode).toBe(404);
    expect(err.code).toBe("NOT_FOUND");
    expect(err.name).toBe("NotFoundError");
  });
});

describe("ConflictError", () => {
  test("statusCode 为 409", () => {
    const err = new ConflictError("already exists");
    expect(err.statusCode).toBe(409);
    expect(err.code).toBe("ALREADY_EXISTS");
    expect(err.name).toBe("ConflictError");
  });
});

describe("ConfigWriteError", () => {
  test("statusCode 为 500", () => {
    const err = new ConfigWriteError("write failed");
    expect(err.statusCode).toBe(500);
    expect(err.code).toBe("CONFIG_WRITE_ERROR");
    expect(err.name).toBe("ConfigWriteError");
  });
});
```

- [ ] **Step 5: 运行全部测试**

```bash
cd unit_tests && bun test
```
Expected: 全部通过

- [ ] **Step 6: Commit**

```bash
git add unit_tests/
git commit -m "feat: add unit tests for automationState, buildInfo, jsonb, error classes"
```

---

### Task 3: Dockerfile.unit-runner

**Files:**
- Create: `Dockerfile.unit-runner`

**Interfaces:**
- Consumes: `unit_tests/` 目录
- Produces: `unit-runner:latest` Docker 镜像

- [ ] **Step 1: 创建 Dockerfile**

```dockerfile
FROM oven/bun:latest
WORKDIR /app
# 测试代码和 FenixAgent 源码通过 volume 挂载
# 启动时创建 @fenix 路径别名所需的符号链接
CMD ["sh", "-c", "ln -sf /app/app /app/tests/app && cd /app/tests && bun test --reporter=junit --reporter-outfile=/app/tests/results/unit-junit.xml"]
```

- [ ] **Step 2: Commit**

```bash
git add Dockerfile.unit-runner
git commit -m "feat: add Dockerfile.unit-runner for bun:test execution"
```

---

### Task 4: 后端数据模型

**Files:**
- Modify: `backend/db/models.py`

**Interfaces:**
- Produces: `UnitTestCase`, `UnitTestResult` ORM 模型

- [ ] **Step 1: 添加 ORM 模型**

在 `backend/db/models.py` 末尾追加：

```python
class UnitTestCase(Base):
    """单元测试用例（从 .test.ts 文件扫描发现）"""
    __tablename__ = "unit_test_cases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_path = Column(String(500), nullable=False)
    describe_block = Column(String(200), default="")
    test_name = Column(String(300), nullable=False)
    full_name = Column(String(500), nullable=False, unique=True)
    discovered_at = Column(DateTime, default=datetime.utcnow)

    results = relationship("UnitTestResult", back_populates="case", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_unit_test_cases_file_path", "file_path"),
    )


class UnitTestResult(Base):
    """单元测试运行结果"""
    __tablename__ = "unit_test_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pipeline_id = Column(Integer, ForeignKey("pr_pipelines.id"), nullable=True)
    test_case_id = Column(Integer, ForeignKey("unit_test_cases.id"), nullable=True)
    status = Column(String(20), nullable=False)  # passed / failed / skipped / error
    duration_ms = Column(Integer, default=0)
    failure_message = Column(Text, nullable=True)
    ran_at = Column(DateTime, default=datetime.utcnow)

    case = relationship("UnitTestCase", back_populates="results")

    __table_args__ = (
        Index("ix_unit_test_results_pipeline_id", "pipeline_id"),
        Index("ix_unit_test_results_test_case_id", "test_case_id"),
    )
```

- [ ] **Step 2: 验证表自动创建**

重启后端，确认 `unit_test_cases` 和 `unit_test_results` 表被自动创建（`init_db()` 中 `create_all`）。

- [ ] **Step 3: Commit**

```bash
git add backend/db/models.py
git commit -m "feat: add UnitTestCase and UnitTestResult models"
```

---

### Task 5: 后端单元测试 API

**Files:**
- Create: `backend/api/unit_tests.py`
- Modify: `backend/main.py` (注册 router)

**Interfaces:**
- Consumes: `UnitTestCase`, `UnitTestResult` 模型
- Produces: API 端点 `/api/unit-tests`, `/api/unit-tests/discover`, `/api/unit-tests/results`, `/api/pipelines/{id}/unit-results`

- [ ] **Step 1: 创建 API 路由**

`backend/api/unit_tests.py`:
```python
"""单元测试管理 API"""
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from backend.db.config import get_async_session
from backend.db.models import UnitTestCase, UnitTestResult, PRPipeline
from backend.schemas.common import ApiResponse

router = APIRouter()

UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent.parent / "unit_tests"


def discover_unit_tests(base_dir: Path) -> list[dict]:
    """扫描 unit_tests/ 目录，提取 describe/test 结构"""
    cases = []
    for ts_file in base_dir.rglob("*.test.ts"):
        content = ts_file.read_text(encoding="utf-8")
        relative_path = str(ts_file.relative_to(base_dir))

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

    tree: dict[str, dict] = {}
    for c in cases:
        if c.file_path not in tree:
            tree[c.file_path] = {"file_path": c.file_path, "describes": {}}
        d = c.describe_block or "(root)"
        if d not in tree[c.file_path]["describes"]:
            tree[c.file_path]["describes"][d] = []
        tree[c.file_path]["describes"][d].append({
            "id": c.id, "test_name": c.test_name, "full_name": c.full_name,
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
    """提交单元测试运行结果"""
    pipeline_id = body.get("pipeline_id")
    junit_xml = body.get("junit_xml")

    results_data = []
    if junit_xml:
        # 从 XML 字符串解析
        import tempfile, os
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False, encoding="utf-8") as f:
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
```

- [ ] **Step 2: 注册 router**

在 `backend/main.py` 中添加：
```python
from backend.api import (
    ..., unit_tests,
)
...
app.include_router(unit_tests.router, prefix="/api", tags=["unit-tests"])
```

- [ ] **Step 3: 在 lifespan 中添加自动发现**

在 `backend/main.py` 的 `lifespan()` 函数中，API/UI 用例发现之后追加：

```python
# 单元测试用例自动发现
try:
    from backend.api.unit_tests import discover_unit_tests, UNIT_TESTS_DIR
    from backend.db.models import UnitTestCase
    from sqlalchemy import delete as sql_delete

    if UNIT_TESTS_DIR.exists():
        discovered = discover_unit_tests(UNIT_TESTS_DIR)
        async with async_session() as db:
            await db.execute(sql_delete(UnitTestCase))
            for case_data in discovered:
                db.add(UnitTestCase(**case_data))
            await db.commit()
        print(f"[AutoDiscover] Unit: discovered {len(discovered)} test cases")
except Exception as e:
    print(f"[AutoDiscover] Unit test discovery failed: {e}")
```

- [ ] **Step 4: Commit**

```bash
git add backend/api/unit_tests.py backend/main.py
git commit -m "feat: add unit test management API with discovery and results"
```

---

### Task 6: 前端类型和 API 客户端

**Files:**
- Modify: `frontend/src/api/types.ts`
- Create: `frontend/src/api/unitTests.ts`

**Interfaces:**
- Produces: TypeScript 类型定义和 API 调用函数

- [ ] **Step 1: 添加类型定义**

在 `frontend/src/api/types.ts` 末尾追加：

```typescript
export interface UnitTestCaseInfo {
  id: number;
  test_name: string;
  full_name: string;
}

export interface UnitTestDescribe {
  name: string;
  tests: UnitTestCaseInfo[];
}

export interface UnitTestFile {
  file_path: string;
  describes: UnitTestDescribe[];
}

export interface UnitTestResult {
  id: number;
  test_case_id: number | null;
  status: string;
  duration_ms: number;
  failure_message: string | null;
  ran_at: string | null;
}

export interface UnitTestSummary {
  total: number;
  passed: number;
  failed: number;
  skipped: number;
  duration_ms: number;
  results: UnitTestResult[];
}
```

- [ ] **Step 2: 创建 API 客户端**

`frontend/src/api/unitTests.ts`:
```typescript
import { get, post } from "./client";
import type { UnitTestFile, UnitTestSummary } from "./types";

export async function listUnitTests(): Promise<UnitTestFile[]> {
  return get<UnitTestFile[]>("/unit-tests");
}

export async function discoverUnitTests(): Promise<{ discovered: number }> {
  return post<{ discovered: number }>("/unit-tests/discover");
}

export async function getPipelineUnitResults(pipelineId: number): Promise<UnitTestSummary> {
  return get<UnitTestSummary>(`/pipelines/${pipelineId}/unit-results`);
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/types.ts frontend/src/api/unitTests.ts
git commit -m "feat: add unit test TypeScript types and API client"
```

---

### Task 7: 前端 Cases 页面单元测试 Tab

**Files:**
- Create: `frontend/src/components/UnitTestTree.tsx`
- Modify: `frontend/src/pages/Cases.tsx`

**Interfaces:**
- Consumes: `listUnitTests()`, `UnitTestFile` 类型
- Produces: Cases 页面的"单元测试" Tab

- [ ] **Step 1: 创建 UnitTestTree 组件**

```tsx
import { useEffect, useState } from "react";
import { ChevronDown, FileCode, TestTube } from "lucide-react";
import { listUnitTests } from "../api/unitTests";
import type { UnitTestFile } from "../api/types";

export default function UnitTestTree() {
  const [files, setFiles] = useState<UnitTestFile[]>([]);
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listUnitTests()
      .then(setFiles)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const toggle = (key: string) => {
    setCollapsed((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  if (loading) return <div className="p-4 text-gray-500">加载中...</div>;
  if (files.length === 0) return <div className="p-4 text-gray-500">暂无单元测试用例</div>;

  const totalTests = files.reduce(
    (sum, f) => sum + f.describes.reduce((s, d) => s + d.tests.length, 0), 0
  );

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 px-1 text-sm text-gray-500">
        <TestTube className="w-4 h-4" />
        {files.length} 个测试文件 / {totalTests} 个测试用例
      </div>

      {files.map((file) => {
        const fileKey = `file-${file.file_path}`;
        const fileCollapsed = !!collapsed[fileKey];
        const fileTestCount = file.describes.reduce((s, d) => s + d.tests.length, 0);

        return (
          <div key={file.file_path} className="bg-white rounded-xl shadow-sm overflow-hidden">
            <div
              className="flex items-center gap-3 p-4 cursor-pointer select-none hover:bg-gray-50"
              onClick={() => toggle(fileKey)}
            >
              <ChevronDown
                className={`w-4 h-4 text-gray-400 transition-transform duration-200 ${
                  fileCollapsed ? "-rotate-90" : ""
                }`}
              />
              <FileCode className="w-4 h-4 text-blue-500" />
              <span className="text-sm font-medium flex-1">{file.file_path}</span>
              <span className="text-xs text-gray-400">{fileTestCount} tests</span>
            </div>

            {!fileCollapsed && (
              <div className="px-4 pb-3 space-y-2">
                {file.describes.map((describe) => {
                  const dKey = `${fileKey}-${describe.name}`;
                  const dCollapsed = !!collapsed[dKey];

                  return (
                    <div key={describe.name} className="pl-4">
                      <div
                        className="flex items-center gap-2 py-1 cursor-pointer select-none"
                        onClick={() => toggle(dKey)}
                      >
                        <ChevronDown
                          className={`w-3 h-3 text-gray-400 transition-transform duration-200 ${
                            dCollapsed ? "-rotate-90" : ""
                          }`}
                        />
                        <span className="text-sm font-semibold text-gray-700">
                          {describe.name}
                        </span>
                        <span className="text-xs text-gray-400">
                          ({describe.tests.length})
                        </span>
                      </div>

                      {!dCollapsed && (
                        <div className="pl-5 space-y-0.5">
                          {describe.tests.map((t) => (
                            <div
                              key={t.id}
                              className="flex items-center gap-2 py-0.5 text-sm text-gray-600"
                            >
                              <TestTube className="w-3 h-3 text-gray-400" />
                              {t.test_name}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: 修改 Cases 页面添加 Tab**

在 `frontend/src/pages/Cases.tsx` 中：

1. 顶部添加状态和导入：
```tsx
import UnitTestTree from "../components/UnitTestTree";

// 组件内部添加状态
const [activeTab, setActiveTab] = useState<"api-ui" | "unit">("api-ui");
```

2. 在页面内容最上方添加 Tab 切换：
```tsx
<div className="flex gap-2 mb-4">
  <button
    onClick={() => setActiveTab("api-ui")}
    className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
      activeTab === "api-ui"
        ? "bg-blue-600 text-white"
        : "bg-gray-100 text-gray-600 hover:bg-gray-200"
    }`}
  >
    API/UI 测试
  </button>
  <button
    onClick={() => setActiveTab("unit")}
    className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
      activeTab === "unit"
        ? "bg-blue-600 text-white"
        : "bg-gray-100 text-gray-600 hover:bg-gray-200"
    }`}
  >
    单元测试
  </button>
</div>

{activeTab === "unit" && <UnitTestTree />}
```

3. 将已有的 API/UI 测试内容包裹在 `{activeTab === "api-ui" && (...)}` 条件中。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/UnitTestTree.tsx frontend/src/pages/Cases.tsx
git commit -m "feat: add unit test tree view tab to Cases page"
```

---

### Task 8: Jenkins Pipeline 集成

**Files:**
- Modify: `docs/jenkins-pipeline-script.groovy`
- Modify: `docs/jenkins-pipeline-build.groovy`
- Modify: `docs/jenkins-debug-tests.groovy`

**Interfaces:**
- Consumes: `Dockerfile.unit-runner`, `unit_tests/` 目录
- Produces: Pipeline 中运行单元测试并收集结果

- [ ] **Step 1: 修改主 Pipeline 脚本**

在 `jenkins-pipeline-script.groovy` 中：

1. Build Image 阶段之后新增 Build Unit Runner 阶段：
```groovy
stage('Build Unit Runner') {
    steps {
        sh '''
            set +x
            echo ""
            echo "============================================================"
            echo "[2b] Build Unit Runner — START"
            echo "============================================================"
            docker build -t unit-runner:latest -f autotest/Dockerfile.unit-runner .
            echo ""
            echo "<<< [2b] Build Unit Runner — DONE"
        '''
    }
}
```

2. Write Compose 的 compose 文件中，test-runner 之前新增 unit-runner 服务：
```yaml
  unit-runner:
    image: unit-runner:latest
    volumes:
      - __WORKSPACE__/autotest/unit_tests:/app/tests
      - __WORKSPACE__/app/src:/app/app/src:ro
    working_dir: /app/tests
    command: 'sh -c "ln -sf /app/app /app/tests/app && mkdir -p /app/tests/results && bun test --reporter=junit --reporter-outfile=/app/tests/results/unit-junit.xml"'
```

3. Run Tests 阶段之前新增 Run Unit Tests 阶段：
```groovy
stage('Run Unit Tests') {
    steps {
        sh '''
            set +x
            echo ""
            echo "============================================================"
            echo "Run Unit Tests — START"
            echo "============================================================"
            echo ">>> Starting unit-runner..."
        '''
        sh "docker-compose -p ${PROJECT_NAME} up unit-runner"
        sh '''
            set +x
            echo ""
            echo "<<< Run Unit Tests — DONE"
        '''
    }
}
```

4. Collect Results 阶段新增 unit test 报告收集：
```groovy
// 在已有的 report.json 收集之前，添加：
echo ">>> Copying unit-junit.xml from unit-runner container..."
docker cp __PROJECT_NAME__-unit-runner-1:/app/tests/results/unit-junit.xml unit-junit.xml || true
```

- [ ] **Step 2: 同步修改 build-only 和 debug 脚本**

对 `jenkins-pipeline-build.groovy` 和 `jenkins-debug-tests.groovy` 做相同的修改。

- [ ] **Step 3: Commit**

```bash
git add docs/
git commit -m "feat: integrate unit tests into Jenkins Pipeline"
```

---

### Task 9: 端到端验证

- [ ] **Step 1: 本地运行全部单元测试**

```bash
cd unit_tests && bun test
```
Expected: 全部通过

- [ ] **Step 2: 构建 Docker 镜像并运行**

```bash
docker build -t unit-runner:latest -f Dockerfile.unit-runner .
```

- [ ] **Step 3: 启动后端验证 API**

```bash
# 启动后端
python -m uvicorn backend.main:app --reload
# 验证用例发现
curl http://localhost:8000/api/unit-tests
curl -X POST http://localhost:8000/api/unit-tests/discover
```

- [ ] **Step 4: 前端验证**

访问 Cases 页面，确认"单元测试" Tab 显示用例树。
