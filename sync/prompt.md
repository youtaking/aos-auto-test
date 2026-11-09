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

## 工作步骤

1. 逐个看源码改动（不要凭文件名猜）：
   `git -C fenix-source diff {{BASE_SHA}} {{HEAD_SHA}} -- <file>`

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

## 结束

用一段话总结：改了哪些单测 / API / E2E（文件数），以及哪些 `manual_rules` / `unmapped` 需要人工跟进。
