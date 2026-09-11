# 2026-09-11 本地 API + E2E 全量验证

目标：`http://100.105.9.16:38879`，部署 commit `da5eb543bf17aa0c772eebbf0961e4dc2daac0e8`。
Windows 本地执行，Chromium 有头模式，串行收集 728 条用例。被测应用源码仅供读取，本次未修改。

## 执行结果

首次全量耗时 5033.27 秒（1:23:53）。按 JSON report 的唯一用例统计：625 passed、5 failed、76 skipped、1 error、21 xfailed。
pytest 终端显示 77 skipped，是因为视图配置用例的主体跳过、teardown 又报错；JSON 将该条最终归为 error，避免重复计数。

修复并定向复测后，按每条用例最近一次结果合并：**639 passed、4 failed、64 skipped、21 xfailed，共 728 条**。
这是一次全量加定向复测的汇总，未声称重新执行了第二轮全量，也未将跳过或预期失败算作通过。

## 测试代码修复

| 文件 | 修改及原因 | 定向验证 |
| --- | --- | --- |
| `tests/pages/sidebar_pages.py` | 等待主内容的任务类型筛选组，避免侧栏按钮提前出现导致误判页面已加载 | 侧栏任务 3 passed |
| `tests/pages/tasks_page.py` | 同样修正页面就绪标志；读取筛选项前等待可见 | 搜索、类型筛选、执行历史 3 passed |
| `tests/pages/config_pages.py` | 目录选择超时且 input 文件列表仍为空时重选一次；已选择文件的超时继续抛错 | 技能文件夹上传及冲突处理 2 passed |
| `tests/suites/test_chat_multi_client_sync.py` | 保存对比日志前同时确认 composer 解锁；不再把模型思考期间文本静止当作回复结束，超时明确失败 | 同步全组 5 passed，保留 5 秒同步验收 |
| `tests/api_suites/test_fs_api.py` | 按主实例运行状态选环境；原先固定选第一项，其主实例已停止，文件服务返回 503 | 文件接口全组 8 passed |
| `tests/api_suites/test_control_api.py` | 正向前置条件读取当前 `instanceUid` 并筛选 running；旧字段不存在使测试误跳过 | 2 passed、3 failed，暴露下述应用异常 |

视图配置用例还曾在本地内存压力下出现 `ERR_INSUFFICIENT_RESOURCES` 和动态模块加载失败，独立浏览器复测 1 passed；未屏蔽页面错误或修改断言。
本次没有新增 skip/xfail。`git diff --check` 通过。

## 尚未解决的 4 条失败

1. `TestKnowledgeBaseResourceAPI::test_toggle_knowledge_resource`
   - HTTP 400，`TOGGLE_FAILED`。
   - 上游信息：`RagFlow returned non-JSON response (status=502, content-type=text/html)`。
   - 先前检查还出现 `getaddrinfo ETIMEOUT ragflow`；embedding 模型前置条件不满足，28 条知识库 UI 用例按原 fixture 跳过。
2. `TestControlWebAPI::test_send_session_event`
3. `TestControlWebAPI::test_send_session_control`
4. `TestControlWebAPI::test_interrupt_session`
   - 对运行实例 `inst_27ecdd9c707043a49ac8d86232886264` 的 `/web/sessions/:id/events`、`/control`、`/interrupt` 直接复核，均为 HTTP 200、空响应体、无 Content-Type。
   - 空响应被测试客户端解析为 `{}`，随后严格解包失败。
   - 当前源码 `src/routes/web/control.ts` 约定返回 `{success:true,data:...}`，且明确以持久 `instanceUid` 识别会话。不能把空响应当作成功。

完成全部通过仍需修复被测服务/依赖。遵守被测源码只读限制，以上问题保留失败。
剩余 64 个跳过和 21 个已有 xfail 的逐条结果见汇总 JSON；包含知识库依赖、缺少渠道/站点/工作流版本等数据以及既有接口异常，并不代表这些功能验证通过。

## 本地复现与证据

```powershell
$env:HEADLESS='false'
python -X utf8 -u -m pytest tests/suites tests/api_suites --base-url http://100.105.9.16:38879 --alluredir=_temp/full-api-e2e-20260911/allure --json-report --json-report-file=_temp/full-api-e2e-20260911/report.json --junitxml=_temp/full-api-e2e-20260911/junit.xml
```

结果目录：`D:\chxu\AI中台\AgentTest\_temp\full-api-e2e-20260911`。

- `report.json` / `junit.xml` / `allure/`：首次全量原始报告。
- `verified-summary.json`：按用例合并的最新结果、来源报告、失败详情及跳过原因。
- `tasks-rerun.json`、`tasks-supplement-rerun.json`、`skill-folder-final.json`、`sync-rerun.json`、`views-rerun.json`、`fs-rerun.json`、`control-rerun.json`：定向复测报告。
- `probe-control.log`：三个控制接口的原始状态码和空响应证据，不含认证信息。
- `probe-env-names.log`：主实例状态与文件服务状态的只读检查。

原始运行报告保留在本地；此次验证未执行远端部署。
