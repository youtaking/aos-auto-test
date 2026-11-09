# 任务：按 FenixAgent main 的新提交同步测试用例

你是本仓库（AgentTest，当前工作目录）的测试维护工程师。
FenixAgent 源码以只读方式挂在 `fenix-source/`。只修改测试用例，使 unit / API / E2E 三套用例与新 main 行为一致。

## 输入

- 变更区间：`{{BASE_SHA}}` .. `{{HEAD_SHA}}`
- 影响面（由 `sync/validate_map.py` 计算）：

```json
{{IMPACT_JSON}}
```

`auto.unit` / `auto.api` / `auto.e2e` 是**允许修改的候选目标**；
`manual_rules` 和 `unmapped` 只做人工关注，不要改。
`rules` 里的 `files` 只是命中文件数（明细已在下面的 diff 里），不要据此再去找文件。

## 已准备好的材料（不要再自行获取）

本轮需要的源码改动和目标文件清单**已全部渲染在下面**。禁止重复执行 `git diff` 取同样的内容，
禁止 `git log` / `git show` / `git blame` 考古提交历史，禁止阅读 `Dockerfile*`、`entrypoint-*`、
`docs/jenkins-*`、`.github/`、`.claude/` 等 CI 配置，禁止浏览与本轮改动无关的源码或测试。

**本轮不使用任何 Skill、不使用任何 MCP / 浏览器工具**：仓库里的技能多为本地交互式流程
（确认目录、`git pull` 被测仓库、Playwright 探查 DOM、实跑环境），在 CI 容器内会卡住或写出白名单外文件。
本提示词已包含全部规则，直接按下面步骤执行。

### 改动概览（git diff --stat {{BASE_SHA}}..{{HEAD_SHA}}）

```
{{DIFF_STAT}}
```

### 命中路径的完整 diff

```diff
{{DIFF}}
```

### 现有目标文件清单（路径 + 行数）

```
{{TARGET_FILES}}
```

### 现有用例提纲（目标文件中已有的用例名）

判断"这个行为有没有测过"直接看这里，不要再用 grep/ls 翻目录。

```
{{TEST_OUTLINE}}
```

## 工作步骤

1. 直接基于上面的 diff 判断行为变化，**不要重新跑 git diff**。
   先用「现有用例提纲」判断哪些行为已覆盖，再决定改哪些文件；不要用 grep/ls 重复翻找。
   若文末「diff 覆盖说明」列出某文件被截断或省略，用 Read 直接读 `fenix-source/<路径>` 的**当前版本**，
   不要重新跑 `git diff`，也不要读覆盖说明之外的文件。
   需要看目标测试文件全文时，用**一次并行的 Read** 把要改的文件全部读完；
   不要串行逐个读，不要读清单之外的文件。
   **命令执行已禁用**（Bash 不可用），只使用 Read / Glob / Grep / Write / Edit。

2. **单测**（`auto.unit` 非空时）：Bun test。纯函数优先内联副本，避免拉起整套依赖。
   每个行为改动点覆盖 5 类场景：正向 / 全部分支 / 边界 / 异常 / 依赖隔离。
   断言必须是具体值（`toEqual({...})`、`toBe(具体值)`），禁止只断言 `toBeDefined()` / `len > 0`。
   测试目标只能引用**当前 main 源码**，不得引用已删除的方法或旧签名。

3. **API**（`auto.api` 非空时）：接口字段 / 路径 / 认证方式有变化时，四类产物一起改，
   只改其中一类视为未完成：
   - `tests/api_clients/`（请求封装）
   - `tests/api_contracts/`（JSON Schema，`additionalProperties: true`）
   - `tests/api_suites/test_<module>_api.py`（用例）
   - `docs/手工用例/API用例/<module>_api用例.md`（手工用例，与自动化一一对应）
   - Web API（`/web/*`）响应是 `{success, data}`，先解包；OpenAPI（`/api/v1/*`）是裸数据。
   - 异常用例必须断言 `status_code` + `error.code`（+ `error.message`），
     禁止 `pytest.raises(Exception)` 或只断言状态码。
   - 写操作（update/delete）必须先自建数据，`try/finally` 清理；禁止改/删已存在的数据。

4. **E2E**（`auto.e2e` 非空时）：选择器必须在 `fenix-source/` 的真实组件源码里有依据
   （`data-slot`、`role`、`aria-label`、可见文案）；禁止凭 `[class*=...]` 猜测。
   `tests/pages/` 与 `tests/suites/` 同步修改。

5. 把 `sync/baseline.json` 的 `main_sha` 更新为 `{{HEAD_SHA}}`。

## 硬约束（违反即整轮作废）

- 只能写：`unit_tests/`、`tests/api_suites/`、`tests/api_clients/`、`tests/api_contracts/`、
  `tests/suites/`、`tests/pages/`、`tests/fixtures/`、`docs/手工用例/`、`sync/baseline.json`。
- 禁止修改 `tsconfig.json` / `bunfig.toml` / `package.json` / `bun.lock` / `Dockerfile*` /
  `entrypoint-*` / `docs/jenkins-*` / `.github/` / `.claude/` / `backend/` / `frontend/` /
  `engine/` / `sync/`（`baseline.json` 除外）/ `fenix-source/`。
- 禁止恒真断言：`assert True`、`x or True`、`len(x) >= 0`、自己和自己比较、`is not None or ...`。
- `skip` 只能放在用例开头做前置检查；执行过程中只能 `assert`，禁止用 skip 掩盖失败。
- 不删除、不修改已有业务数据。
- 不要 commit、不要 push、不要开 MR。
- 不创建计划 / 分析文档，直接改代码。
- 效率：diff 已给出，不要重新获取；只改影响面列出的文件，不要遍历仓库；改动尽量一次写对。
- **不要运行 `bun install` / `bun test` / `pytest`**：依赖安装与静态校验由流水线在本轮之后执行，
  你只负责把文件改对；跑测试只会消耗轮次并让输出挤占上下文。

## 结束

用一段话总结：改了哪些单测 / API / E2E（文件数），以及哪些 `manual_rules` / `unmapped` 需要人工跟进。
