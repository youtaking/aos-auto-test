# sync-reviewer 检查项

审查对象是当前工作副本里未提交的改动（`git status --porcelain` / `git diff`），
以及 `sync/policy.yml`、`sync/coverage-map.yml` 的约束。只读审查，不修改任何文件。

## 必须逐项检查

1. **范围**：`git status --porcelain` 的每个文件都必须在 `sync/policy.yml` 的
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
9. **基线**：`sync/baseline.json` 的 `main_sha` 等于本次 `HEAD_SHA`。

## 输出格式

```
结论：APPROVE 或 REJECT
理由：
  - <逐条列出命中的问题，附文件:行号>
建议：
  - <最小修正方向，不要代替 Maker 改代码>
```

不确定时倾向 REJECT，并说明需要人工看的点。最后一行只输出一个词：`APPROVE` 或 `REJECT`。
