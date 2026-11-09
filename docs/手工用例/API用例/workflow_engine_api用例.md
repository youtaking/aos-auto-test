> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

# Workflow Engine 模块 API 手工测试用例

## 模块：Workflow Engine Web API

> 工作流引擎通过 POST action 分发，body 格式为 `{"action": "xxx", ...}`

### TC-WFENGINE-001：未知 action（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/workflow-engine`
  - Body：`{"action": "unknown_action_xyz"}`
- **步骤**：
  1. 发送 POST 请求
  2. 检查返回 400/422 或错误信息
- **预期结果**：返回错误

---

### TC-WFENGINE-002：dryRun 缺少 yaml（必填参数缺失）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/workflow-engine`
  - Body：`{"action": "dryRun"}`
- **步骤**：
  1. 发送不带 yaml 的 dryRun 请求
  2. 检查返回 400
- **预期结果**：返回 400 错误

---

### TC-WFENGINE-003：run 缺少 yaml 和 workflowId（必填参数缺失）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/workflow-engine`
  - Body：`{"action": "run"}`
- **步骤**：
  1. 发送不带 yaml 的 run 请求
  2. 检查返回 400
- **预期结果**：返回 400 错误

---

### TC-WFENGINE-004：获取不存在的 run 状态（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/workflow-engine`
  - Body：`{"action": "getRunStatus", "runId": "nonexistent-run-99999"}`
- **步骤**：
  1. 发送 POST 请求
  2. 检查返回 404/null/错误
- **预期结果**：返回 404 或 null

---

### TC-WFENGINE-005：获取不存在的 run 事件（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/workflow-engine`
  - Body：`{"action": "getEvents", "runId": "nonexistent-run-99999"}`
- **步骤**：
  1. 发送 POST 请求
  2. 检查返回 404/空列表/错误
- **预期结果**：返回 404 或空列表

---

### TC-WFENGINE-006：获取不存在的 run 审批列表（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/workflow-engine`
  - Body：`{"action": "getPendingApprovals", "runId": "nonexistent-run-99999"}`
- **步骤**：
  1. 发送 POST 请求
  2. 检查返回 404/空列表/错误
- **预期结果**：返回 404 或空列表

---

### TC-WFENGINE-007：dryRun 简单 YAML（正向）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/workflow-engine`
  - Body：
    ```json
    {
      "action": "dryRun",
      "yaml": "version: \"1.0\"\nname: auto-test-dry-run\nsteps:\n  - id: step1\n    type: log\n    params:\n      message: \"hello\""
    }
    ```
- **步骤**：
  1. 发送带简单 YAML 的 dryRun 请求
  2. 检查返回 `valid` 字段
- **预期结果**：返回 `{valid: true/false}`
