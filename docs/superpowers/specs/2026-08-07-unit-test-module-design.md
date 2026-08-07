# 单元测试模块设计

## 概述

在 autotest 项目中新增独立的单元测试模块，使用 TypeScript + bun:test 框架，针对 FenixAgent 源码编写独立的单元测试。PR 触发 Jenkins Pipeline 时全量运行，结果通过 autotest 前端展示和管理。

## 动机

- autotest 目前只有 API 测试和 UI 测试，缺少对被测应用源码的单元级验证
- PR 回归需要在源码层面尽早发现问题，API/UI 测试只能覆盖端到端场景
- 前端需要统一管理所有类型的测试用例和结果（Unit / API / UI）

## 关键决策

| 项目 | 决策 |
|------|------|
| 测试代码位置 | autotest 项目 `unit_tests/` 目录 |
| 语言和框架 | TypeScript + bun:test（与 FenixAgent 一致） |
| 被测代码来源 | FenixAgent 源码，Jenkins Build 阶段已拉取到 `app/` |
| 与 FenixAgent 自带测试 | 完全独立，不复用其 147 个 `src/__tests__/` 测试 |
| PR 运行策略 | 全量运行所有单元测试 |
| 前端 | 展示用例树 + 查看结果，不在线编辑 |

## 架构

### 整体流程

```
PR 事件触发 Jenkins
  │
  ├─ [1] Clone Repos → app/ (FenixAgent) + autotest/
  ├─ [2] Build Images (Docker 镜像)
  ├─ [3] Build Unit Runner (bun 测试镜像)
  ├─ [4] Resolve Tests (API/UI 用例解析)
  ├─ [5] Write Compose (含 unit-runner 服务)
  ├─ [6] Deploy (postgres + litellm + rcs)
  ├─ [7] Run Unit Tests ← 新增：bun test 全量运行
  ├─ [8] Run API/UI Tests (pytest)
  ├─ [9] Collect Results ← 修改：合并 unit + api/ui 报告
  └─ [10] Cleanup
```

### 目录结构

```
AgentTest/
├── tests/                          # 已有：API + UI (pytest)
│   ├── api_suites/
│   └── suites/
├── unit_tests/                     # 新增：单元测试 (bun:test)
│   ├── package.json
│   ├── tsconfig.json
│   ├── bunfig.toml
│   ├── services/
│   │   ├── phone-number.test.ts
│   │   ├── automation-state.test.ts
│   │   ├── build-info.test.ts
│   │   └── jsonb.test.ts
│   └── errors/
│       └── error-classes.test.ts
├── Dockerfile.unit-runner          # 新增
└── docs/
    └── jenkins-pipeline-script.groovy  # 修改
```

## 单元测试模块详细设计

### package.json

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

不需要安装 FenixAgent 的依赖——测试时通过路径映射直接引用 `app/` 下的源码，bun 会解析其内部的 import。

### tsconfig.json

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ES2022",
    "moduleResolution": "bundler",
    "baseUrl": ".",
    "types": ["bun"],
    "strict": true,
    "paths": {
      "@fenix/*": ["./app/src/*"]
    }
  },
  "include": ["**/*.ts"]
}
```

本地开发时源码放在 `unit_tests/app/src/`；Docker 容器中通过 volume 挂载覆盖该目录。

### bunfig.toml

```toml
[test]
root = "."
```

### Dockerfile.unit-runner

```dockerfile
FROM oven/bun:latest
WORKDIR /app
CMD ["bun", "test", "--reporter=junit", "--reporter-outfile=/app/results/unit-junit.xml"]
```

镜像不需要 COPY 文件——测试代码和 FenixAgent 源码都通过 volume 挂载。

### Docker Compose 中的 unit-runner 服务

```yaml
unit-runner:
  image: unit-runner:latest
  # 单元测试测纯逻辑，不依赖 rcs 服务，无需 depends_on
  volumes:
    - __WORKSPACE__/autotest/unit_tests:/app/tests
    - __WORKSPACE__/app/src:/app/tests/app/src:ro
  working_dir: /app/tests
  command: >
    bun test
    --reporter=junit
    --reporter-outfile=/app/tests/results/unit-junit.xml
```

`/app/tests/app/src` 被 host 上的真实 FenixAgent 源码覆盖（只读），替换本地开发用的源码副本。

### 测试用例引用方式

```typescript
// unit_tests/services/phone-number.test.ts
import { describe, expect, test } from "bun:test";
import {
  normalizeChineseMainlandPhoneNumber,
  buildPhoneTempEmail,
  isEmailIdentifier,
} from "@fenix/services/phone-number";
// @fenix/* 通过 tsconfig paths 解析到 ./app/src/*
// Docker 容器中 app/ 目录被 volume 覆盖为真实 FenixAgent 源码

describe("phone-number", () => {
  test("归一化带 +86 前缀的手机号", () => {
    expect(normalizeChineseMainlandPhoneNumber("+86 188-2648-0215")).toBe("18826480215");
  });

  test("拒绝非法手机号", () => {
    expect(() => normalizeChineseMainlandPhoneNumber("188264802150")).toThrow("手机号格式不正确");
  });

  test("生成临时邮箱", () => {
    expect(buildPhoneTempEmail("18826480215")).toBe("18826480215@fenix.com");
  });

  test("判断邮箱标识符", () => {
    expect(isEmailIdentifier("user@example.com")).toBe(true);
    expect(isEmailIdentifier("18826480215")).toBe(false);
  });
});
```

### 第一批测试用例

从纯逻辑、无外部依赖的模块开始：

| 模块 | 源文件 | 测试内容 |
|------|--------|---------|
| 手机号 | `app/src/services/phone-number.ts` | 归一化、临时邮箱、邮箱判断 |
| 自动化状态 | `app/src/services/automationState.ts` | 状态快照、事件载荷、相等比较 |
| 构建信息 | `app/src/services/build-info.ts` | commit 解析、健康信息 |
| JSONB | `app/src/services/config/jsonb.ts` | 双重编码兼容、fallback |
| 错误类 | `app/src/errors.ts` | 层级结构、statusCode、code |

## Jenkins Pipeline 变更

### 新增阶段：Build Unit Runner

在 Build Images 之后，构建 unit-runner 镜像：

```groovy
stage('Build Unit Runner') {
    steps {
        sh '''
            docker build -t unit-runner:latest -f autotest/Dockerfile.unit-runner .
        '''
    }
}
```

### 新增阶段：Run Unit Tests

在 Deploy 之后、Run API/UI Tests 之前：

```groovy
stage('Run Unit Tests') {
    steps {
        sh '''
            mkdir -p autotest/unit_tests/results
            docker-compose -p __PROJECT_NAME__ up unit-runner
        '''
    }
}
```

### 修改阶段：Collect Results

合并 unit test 的 junit XML 和 pytest 的 JSON report：

```groovy
stage('Collect Results') {
    steps {
        sh '''
            # 拷贝 unit test 报告
            docker cp __PROJECT_NAME__-unit-runner-1:/app/tests/results/unit-junit.xml unit-junit.xml || true
            # 拷贝 api/ui test 报告
            docker cp __PROJECT_NAME__-test-runner-1:/app/results/report.json report.json || true
            # 解析并汇总
            python3 -c "..." # 合并两种报告，提交给 AutoTest API
        '''
    }
}
```

## 后端变更

### 数据模型

新增两张表：

```sql
-- 单元测试用例（从文件扫描发现）
CREATE TABLE unit_test_cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path VARCHAR(500) NOT NULL,        -- 相对路径，如 services/phone-number.test.ts
    describe_block VARCHAR(200),             -- describe 名称
    test_name VARCHAR(300) NOT NULL,         -- test/it 名称
    full_name VARCHAR(500) NOT NULL UNIQUE,  -- describe > test 完整名
    discovered_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 单元测试运行结果
CREATE TABLE unit_test_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pipeline_id INTEGER REFERENCES pipelines(id),
    test_case_id INTEGER REFERENCES unit_test_cases(id),
    status VARCHAR(20) NOT NULL,             -- passed / failed / skipped / error
    duration_ms REAL,
    failure_message TEXT,
    ran_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/unit-tests` | 获取所有单元测试用例（树形结构） |
| POST | `/api/unit-tests/discover` | 扫描 `unit_tests/` 目录，解析并同步用例到 DB |
| POST | `/api/unit-tests/results` | 提交单元测试运行结果（junit XML 解析） |
| GET | `/api/pipelines/{id}/unit-results` | 获取某次 Pipeline 的单元测试结果 |

### 用例发现逻辑

后端解析 `.test.ts` 文件，提取 `describe()` 和 `test()` / `it()` 结构：

```python
import re
from pathlib import Path

def discover_unit_tests(base_dir: str) -> list[dict]:
    """扫描 unit_tests/ 目录，提取 describe/test 结构"""
    cases = []
    for ts_file in Path(base_dir).rglob("*.test.ts"):
        content = ts_file.read_text(encoding="utf-8")
        relative_path = str(ts_file.relative_to(base_dir))

        # 提取 describe 块
        describes = re.findall(r'describe\(\s*["\'](.+?)["\']', content)
        # 提取 test/it 块
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
```

### JUnit XML 解析

```python
import xml.etree.ElementTree as ET

def parse_junit_xml(xml_path: str) -> list[dict]:
    """解析 bun test 的 junit XML 输出"""
    tree = ET.parse(xml_path)
    results = []
    for testsuite in tree.findall(".//testsuite"):
        for testcase in testsuite.findall("testcase"):
            result = {
                "name": testcase.get("name"),
                "classname": testcase.get("classname"),
                "duration_ms": float(testcase.get("time", 0)) * 1000,
                "status": "passed",
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
```

## 前端变更

### Cases 页面

增加 Tab 切换：

```
Cases 页面
├── Tab: API/UI 测试  （已有）
│   ├── Suite 树
│   └── 勾选运行
└── Tab: 单元测试      （新增）
    ├── 文件树（按 describe/test 组织）
    └── 查看详情（跳转到运行结果）
```

### 单元测试用例树组件

```tsx
// UnitTestTree.tsx
// 按文件 → describe → test 三级展示
// 文件: services/phone-number.test.ts
//   └── describe: phone-number
//         ├── test: 归一化带 +86 前缀的手机号
//         ├── test: 拒绝非法手机号
//         └── test: 生成临时邮箱
```

### 结果展示

Reports / RunDetail 页面中区分三种测试类型：

```
Pipeline #42 结果
├── 单元测试: 15 passed / 0 failed / 0 skipped  (bun:test, 120ms)
├── API 测试: 12 passed / 1 failed              (pytest)
└── UI 测试:  8 passed / 0 skipped              (pytest + playwright)
```

## 验证步骤

1. 本地执行 `cd unit_tests && bun test`，确认测试通过
2. 构建 unit-runner Docker 镜像，通过 volume 挂载运行测试
3. Jenkins Pipeline 中 unit-runner 阶段正常执行并输出 junit XML
4. Collect Results 阶段正确解析并合并两种报告
5. 后端 `/api/unit-tests/discover` 正确扫描并存储用例
6. 前端 Cases 页面"单元测试" Tab 正确展示用例树
7. 前端 Reports 页面正确展示单元测试结果
