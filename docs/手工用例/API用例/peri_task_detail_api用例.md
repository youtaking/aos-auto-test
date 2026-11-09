> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

# Peri Task Detail 模块 API 手工测试用例

## 模块：Peri Task Detail Web API

认证方式：session cookie（better-auth 登录）

---

### TC-PERITASK-001：获取 Peri Task 详情（正向）

- **前置条件**：已登录，有有效的 environmentId、sessionId、taskId
- **请求信息**：
  - 方法：GET
  - URL：`/web/agents/<environmentId>/sessions/<sessionId>/peri-tasks/<taskId>/detail`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 200
  3. 检查响应 `success` 为 `true`
  4. 检查 `data.kind` 为 `"preview"` 或 `"unavailable"`
  5. 检查 `data.taskId` 和 `data.taskKind` 存在
- **预期结果**：返回 `{success: true, data: {kind: "preview"|"unavailable", taskId, taskKind, ...}}`

---

### TC-PERITASK-002：获取 preview 类型详情（正向）

- **前置条件**：已登录，有有效的查询参数，任务返回 preview 类型
- **请求信息**：
  - 方法：GET
  - URL：`/web/agents/<environmentId>/sessions/<sessionId>/peri-tasks/<taskId>/detail`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 发送 GET 请求
  2. 检查 `data.kind` 为 `"preview"`
  3. 检查 `data.items` 为数组（最多 1 个元素）
  4. 检查 `data.complete` 为 boolean
  5. 每个 item 包含 `type: "text"` 和 `content`（string）
- **预期结果**：返回预览详情，items 数组非空

---

### TC-PERITASK-003：获取 unavailable 类型详情（正向）

- **前置条件**：已登录，任务返回 unavailable 类型
- **请求信息**：
  - 方法：GET
  - URL：`/web/agents/<environmentId>/sessions/<sessionId>/peri-tasks/<taskId>/detail`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 发送 GET 请求
  2. 检查 `data.kind` 为 `"unavailable"`
  3. 检查 `data.reason` 为 `"not_provided"` 或 `"expired"`
- **预期结果**：返回不可用原因

---

### TC-PERITASK-004：带查询参数获取详情（正向）

- **前置条件**：已登录，有有效的查询参数
- **请求信息**：
  - 方法：GET
  - URL：`/web/agents/<environmentId>/sessions/<sessionId>/peri-tasks/<taskId>/detail?limit=1&byteLimit=500`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 发送带 limit 和 byteLimit 参数的请求
  2. 检查响应状态码为 200
  3. 检查 data 结构正确
- **预期结果**：查询参数生效，返回正确结构

---

### TC-PERITASK-005：查询不存在的 Peri Task（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/agents/nonexistent-env/sessions/nonexistent-session/peri-tasks/nonexistent-task/detail`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 发送使用不存在 ID 的请求
  2. 检查响应状态码为 404
- **预期结果**：返回 404，error.code 为 NOT_FOUND

---

### TC-PERITASK-006：空 environmentId（边界）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/agents//sessions/session-1/peri-tasks/task-1/detail`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 发送 environmentId 为空的请求（产生双斜杠路径）
  2. 检查响应状态码为 302（服务端路径规范化重定向）或 400/404
- **预期结果**：服务端路径规范化返回 302 重定向

---

### TC-PERITASK-007：limit 边界值 0（边界）

- **前置条件**：已登录，有有效的查询参数
- **请求信息**：
  - 方法：GET
  - URL：`/web/agents/<environmentId>/sessions/<sessionId>/peri-tasks/<taskId>/detail?limit=0`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 发送 limit=0 的请求（源码约束 min=1）
  2. 检查响应状态码为 400 或 422
- **预期结果**：返回参数校验错误

---

### TC-PERITASK-008：byteLimit 超限（边界）

- **前置条件**：已登录，有有效的查询参数
- **请求信息**：
  - 方法：GET
  - URL：`/web/agents/<environmentId>/sessions/<sessionId>/peri-tasks/<taskId>/detail?byteLimit=99999`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 发送 byteLimit=99999 的请求（源码约束 max=2000）
  2. 检查响应状态码为 400 或 422
- **预期结果**：返回参数校验错误

---

### TC-PERITASK-009：无认证访问（权限）

- **前置条件**：无
- **请求信息**：
  - 方法：GET
  - URL：`/web/agents/env-1/sessions/sess-1/peri-tasks/task-1/detail`
  - Headers：无 Cookie
- **步骤**：
  1. 不携带认证信息发送请求
  2. 检查响应状态码为 401 或 302（重定向到登录）
- **预期结果**：返回 401 或重定向

---
