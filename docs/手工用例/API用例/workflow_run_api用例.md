> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

# Workflow Run 模块 API 手工测试用例

## 模块：Workflow Run Web API

### TC-WFRUN-001：获取运行记录列表（正向）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/workflow-runs`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 发送 GET 请求
  2. 检查返回为数组或包含 items 的分页对象
- **预期结果**：返回运行记录列表

---

### TC-WFRUN-002：获取运行详情（正向）

- **前置条件**：已登录，运行记录非空
- **请求信息**：
  - 方法：GET
  - URL：`/web/workflow-runs/{run_id}`
- **步骤**：
  1. 列表取第一个 run_id
  2. GET 查详情
  3. 检查 run_id 与请求一致
- **预期结果**：返回运行详情

---

### TC-WFRUN-003：获取运行事件（正向）

- **前置条件**：已登录，运行记录非空
- **请求信息**：
  - 方法：GET
  - URL：`/web/workflow-runs/{run_id}/events`
- **步骤**：
  1. 列表取第一个 run_id
  2. GET 获取事件列表
  3. 检查返回为数组
- **预期结果**：返回事件数组

---

### TC-WFRUN-004：获取运行审批列表（正向）

- **前置条件**：已登录，运行记录非空
- **请求信息**：
  - 方法：GET
  - URL：`/web/workflow-runs/{run_id}/approvals`
- **步骤**：
  1. 列表取第一个 run_id
  2. GET 获取审批列表
  3. 检查返回为数组
- **预期结果**：返回审批数组

---

### TC-WFRUN-005：获取不存在的运行记录（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/workflow-runs/nonexistent-run-id-99999`
- **步骤**：
  1. 发送 GET 请求
  2. 检查返回 None/空对象或 404/400/500
- **预期结果**：返回空或错误

---

### TC-WFRUN-006：取消不存在的运行（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/workflow-runs/nonexistent-run-id-99999/cancel`
- **步骤**：
  1. 发送 POST 请求
  2. 检查返回 404/500
- **预期结果**：返回错误

---

### TC-WFRUN-007：获取不存在运行的节点输出（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/workflow-runs/nonexistent-run-id-99999/nodes/nonexistent-node-id/output`
- **步骤**：
  1. 发送 GET 请求
  2. 检查返回 404/500
- **预期结果**：返回错误

---

### TC-WFRUN-008：干运行校验无效 YAML（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/workflow-runs/dry`
  - Body：`{"yaml": "invalid: yaml: content: ["}`
- **步骤**：
  1. 发送无效 YAML
  2. 检查返回 `valid=false` 或 `issues` 列表，或 400/500
- **预期结果**：校验失败

---

### TC-WFRUN-009：恢复不存在的运行（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/workflow-runs/nonexistent-run-id-99999/recover`
- **步骤**：
  1. 发送 POST 请求
  2. 检查返回 400/404/500
- **预期结果**：返回错误

---

### TC-WFRUN-010：重新运行不存在的运行（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/workflow-runs/nonexistent-run-id-99999/rerun`
- **步骤**：
  1. 发送 POST 请求
  2. 检查返回 400/404/500
- **预期结果**：返回错误

---

### TC-WFRUN-011：审批缺少 nodeId（必填缺失）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/workflow-runs/nonexistent-run-id-99999/approve`
  - Body：`{}`
- **步骤**：
  1. 发送 POST 请求
  2. 检查响应状态码为 400
  3. 检查 `error.type` 为 `VALIDATION_ERROR`
  4. 检查 `error.message` 包含 `nodeId`
- **预期结果**：返回 400
