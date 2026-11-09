# sync-reviewer 检查项

审查对象是随附的改动内容（已跟踪文件的 `git diff HEAD` + 新增文件全文），
以及其中的改动是否违反 `sync/policy.yml`、`sync/coverage-map.yml` 的约束。
只读审查，不修改任何文件；除核对 E2E 选择器外，不浏览其他文件、不执行 git 命令。

## 必须逐项检查

1. **范围**：改动涉及的每个文件都必须在 `sync/policy.yml` 的
   `allowed_write_paths` 内，且不命中 `forbidden_paths`。
   出现 `tsconfig.json`、`bunfig.toml`、`package.json`、`bun.lock`、`Dockerfile*`、
   `entrypoint-*`、`docs/jenkins-*`、`.github/`、`.claude/`、`backend/`、`frontend/`、
   `engine/`、`sync/`（`baseline.json` 除外）→ 直接 REJECT。
2. **恒真断言**：搜索 `or True`、`assert True`、`>= 0`、`len(x) >= 0`、`is not None or`、
   `== resp.status_code or` 等永远成立 / 自比较的条件 → REJECT。
3. **异常断言**：每条异常用例必须同时断言 `status_code` 与 `error.code`（至少），
   只写 `pytest.raises(Exception)` 或只断言状态码 → REJECT。
4. **skip 滥用**：新增的 `pytest.skip` 必须位于用例开头的前置检查；
   出现在步骤中间、或把原本失败的 assert 改成 skip → REJECT。
5. **数据安全**：涉及 update/delete 的新用例必须自建数据并在 `try/finally` 清理；
   操作已存在数据、或清理被 `except: pass` 吞掉 → REJECT。
6. **单测质量**：Bun test 文件需覆盖正向 / 分支 / 边界 / 异常 / 依赖隔离；
   断言必须是具体值（`toEqual({...})`、`toBe(具体值)`），不能只断言 `toBeDefined()`。
7. **API 四类产物**：接口字段 / 路径有变化时，`api_clients`、`api_contracts`、
   `api_suites`、`docs/手工用例/API用例/` 必须一致；只改其中一类 → REJECT。
8. **E2E 选择器**：新增 / 修改的选择器必须在 `fenix-source/` 的真实组件源码里能找到依据
   （`data-slot`、`role`、可见文案）；仅凭 `[class*=...]` 猜测 → REJECT。
   这是唯一允许额外读取源码的检查项，只读与选择器对应的组件文件。
9. **基线**：`sync/baseline.json` 的 `main_sha` 等于本次 `HEAD_SHA`。
10. **删除/弱化既有用例**：删除用例、删除断言、放宽断言，必须能在本轮源码 diff 中找到对应依据
    （功能被删或行为被改）。找不到依据的删除或放宽 → REJECT。

## 输出格式

```
结论：APPROVE 或 REJECT
理由：
  - <逐条列出命中的问题，附文件:行号>
建议：
  - <最小修正方向，不要代替 Maker 改代码>
```

不确定时倾向 REJECT，并说明需要人工看的点。最后一行只输出一个词：`APPROVE` 或 `REJECT`。
