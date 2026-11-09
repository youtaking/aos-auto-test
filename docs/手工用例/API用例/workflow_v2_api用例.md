# Workflow V2 模块 API 手工测试用例

> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

## 模块：Workflow V2 Web API

### TC-WFV2-001：列出 V2 工作流（正向）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/workflow-v2/workflows`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 200
  3. 检查 `data.items` 为数组
  4. 检查每个元素含 `id`、`name`
- **预期结果**：返回工作流列表

---

### TC-WFV2-002：列出 V2 运行记录（正向）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/workflow-v2/run-records`
- **步骤**：
  1. 发送 GET 请求
  2. 检查 `data.items`、`data.workflows` 为数组
  3. 检查 `data.scannedWorkflows` 为整数
- **预期结果**：返回运行记录结构完整

---

### TC-WFV2-003：获取组织级应用绑定（正向）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/workflow-v2/org-app`
- **步骤**：
  1. 发送 GET 请求
  2. 检查 `data.appId` 为字符串
  3. 检查 `data.status` 为字符串
- **预期结果**：返回组织应用绑定信息

---

### TC-WFV2-004：获取平台账号状态（正向）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/workflow-v2/platform-account`
- **步骤**：
  1. 发送 GET 请求
  2. 检查 `data.platformUserId` 为字符串
  3. 检查 `data.status` 为字符串
- **预期结果**：返回平台账号状态

---

### TC-WFV2-005：查询不存在工作流的发布记录（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/workflow-v2/workflows/nonexistent-workflow-id-99999/publish-records`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 404
  3. 检查 `error.code` 为 `NOT_FOUND`
- **预期结果**：返回 404

---

### TC-WFV2-006：运行记录 IO 缺少 upstreamWorkflowId（必填缺失）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/workflow-v2/run-records/nonexistent/io`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 400
  3. 检查 `error.type` 为 `VALIDATION_ERROR`
  4. 检查 `error.message` 包含 `upstreamWorkflowId`
- **预期结果**：返回 400

---

### TC-WFV2-007：生成 iframe 代码缺少 workflowId（必填缺失）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/workflow-v2/iframe-code`
  - Body：`{}`
- **步骤**：
  1. 发送 POST 请求
  2. 检查响应状态码为 400
  3. 检查错误信息包含 `workflowId`
- **预期结果**：返回 400，且不落库

---

### TC-WFV2-008：创建工作流缺少 name（必填缺失）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/workflow-v2/workflows`
  - Body：`{}`
- **步骤**：
  1. 发送 POST 请求
  2. 检查响应状态码为 400
  3. 检查 `error.type` 为 `VALIDATION_ERROR`
  4. 检查 `error.message` 包含 `name`
- **预期结果**：返回 400，且不落库

---

### TC-WFV2-009：更新工作流但不提供可改字段（业务规则）

- **前置条件**：已登录
- **请求信息**：
  - 方法：PATCH
  - URL：`/web/workflow-v2/workflows/nonexistent-workflow-id-99999`
  - Body：`{}`
- **步骤**：
  1. 发送 PATCH 请求
  2. 检查响应状态码为 400
  3. 检查 `error.code` 为 `INVALID_REQUEST`
- **预期结果**：返回 400（name/desc/iconUri 至少需要一个）

---

### TC-WFV2-010：删除不存在的工作流（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：DELETE
  - URL：`/web/workflow-v2/workflows/nonexistent-workflow-id-99999`
- **步骤**：
  1. 发送 DELETE 请求
  2. 检查响应状态码为 404
  3. 检查 `error.code` 为 `NOT_FOUND`
- **预期结果**：返回 404

---

### TC-WFV2-011：组织应用重新绑定缺少 appId（必填缺失）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/workflow-v2/org-app/rebind`
  - Body：`{}`
- **步骤**：
  1. 发送 POST 请求
  2. 检查响应状态码为 400
  3. 检查 `error.type` 为 `VALIDATION_ERROR`
  4. 检查 `error.message` 包含 `appId`
- **预期结果**：返回 400，且不改变现有绑定

---

## 模块：Workflow V2 OpenAPI（/api/v1/workflow-v2，API Key 认证）

> 说明：响应为 `{success, data}` 信封；错误为 `{success:false, error:{code, message}}`。该路径下 schema 校验失败返回 **422**；`id` 必须是本地工作流主键 UUID。

### TC-WFV2-012：运行不存在的 V2 工作流（异常，P2）

- **前置条件**：已配置有效 Open API Key
- **请求信息**：
  - 方法：POST
  - URL：`/api/v1/workflow-v2/workflows/nonexistent-workflow-id-99999/run`
  - Headers：`Authorization: Bearer <API Key>`
  - Body：`{}`
- **步骤**：
  1. 发送 POST 请求
  2. 检查响应状态码为 422
  3. 检查 `success` 为 `false`
  4. 检查 `error.code` 为 `VALIDATION_ERROR`，`error.message` 包含 `id`
- **预期结果**：返回 422 `VALIDATION_ERROR`（id 非 UUID 在边界被拒绝），不产生运行记录

---

### TC-WFV2-013：运行合法 UUID 但不存在的 V2 工作流（异常，P2）

- **前置条件**：已配置有效 Open API Key
- **请求信息**：
  - 方法：POST
  - URL：`/api/v1/workflow-v2/workflows/00000000-0000-4000-8000-000000000000/run`
  - Body：`{}`
- **步骤**：
  1. 发送 POST 请求
  2. 检查响应状态码为 404
  3. 检查 `error.code` 为 `WORKFLOW_NOT_FOUND`
- **预期结果**：返回 404 `WORKFLOW_NOT_FOUND`

---

### TC-WFV2-014：parameters 类型非法（类型错误，P2）

- **前置条件**：已配置有效 Open API Key
- **请求信息**：
  - 方法：POST
  - URL：`/api/v1/workflow-v2/workflows/00000000-0000-4000-8000-000000000000/run`
  - Body：`{"parameters": 123}`
- **步骤**：
  1. 发送 POST 请求
  2. 检查响应状态码为 422
  3. 检查 `error.code` 为 `VALIDATION_ERROR`
- **预期结果**：返回 422 `VALIDATION_ERROR`
