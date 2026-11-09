> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

# Instance 模块 API 手工测试用例

## 模块：Instance Web API（/web/instances，session cookie 认证）

### TC-INSTANCE-001：获取实例活跃度（正向，P1）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/instances/activity`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 发送 GET 请求
  2. 校验响应结构（data 可为数组或 `{instances, total}` 对象）
  3. 数组时逐项校验 `id`；对象时检查 `instances` 为数组、`total` 为整数
- **预期结果**：返回 200 实例活跃度数据

---

### TC-INSTANCE-002：跨组织查询实例活跃度 all=true（权限场景，P1）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/instances/activity?all=true`
- **步骤**：
  1. 发送带 `all=true` 的 GET 请求
  2. 检查响应状态码为 403
  3. 检查 `success` 为 `false`
  4. 检查 `error.code` 为 `FORBIDDEN`
- **预期结果**：返回 403，错误码 `FORBIDDEN`（控制台禁止跨组织查询）

---

### TC-INSTANCE-003：从环境启动实例（正向，P0）

- **前置条件**：已登录，有可用环境
- **请求信息**：
  - 方法：POST
  - URL：`/web/instances/from-environment`
  - Headers：`Cookie: session=xxx`
  - Body：`{"environmentId": "{有效环境ID}"}`
- **步骤**：
  1. 调用环境列表获取第一个 env_id
  2. 发送 POST 请求
  3. 校验返回结构，检查 `environmentId` 与请求一致
  4. 清理：DELETE `/web/instances/{instanceUid}`
- **预期结果**：返回 200 实例信息；环境不存在/服务不可用（404/502/503）时跳过

---

### TC-INSTANCE-004：启动实例缺少 environmentId（必填参数缺失，P2）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/instances/from-environment`
  - Body：`{}`
- **步骤**：
  1. 发送缺少 environmentId 的 POST 请求
  2. 检查响应状态码为 400/422（含 validation 提示）
- **预期结果**：返回 400/422 校验错误

---

### TC-INSTANCE-005：启动实例 environmentId 为空字符串（参数边界，P2）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/instances/from-environment`
  - Body：`{"environmentId": ""}`
- **步骤**：
  1. 发送空 environmentId 的 POST 请求
  2. 检查响应状态码为 400/422
- **预期结果**：返回 400/422 校验错误

---

### TC-INSTANCE-006：启动实例 environmentId 不存在（异常响应，P2）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/instances/from-environment`
  - Body：`{"environmentId": "nonexistent-env-99999"}`
- **步骤**：
  1. 发送不存在的环境 ID
  2. 检查响应状态码为 404
- **预期结果**：返回 404 Not Found

---

### TC-INSTANCE-007：删除不存在的实例（异常响应/幂等，P2）

- **前置条件**：已登录
- **请求信息**：
  - 方法：DELETE
  - URL：`/web/instances/nonexistent-instance-99999`
- **步骤**：
  1. 连续两次发送 DELETE 请求
  2. 每次检查响应状态码为 404
  3. 每次检查 `success` 为 `false`、`error.code` 为 `NOT_FOUND`
- **预期结果**：两次均返回 404 `NOT_FOUND`，不产生资源

---

### TC-INSTANCE-008：启动后删除实例（生命周期，P1）

- **前置条件**：已登录，有可用环境
- **请求信息**：
  - 方法：POST → DELETE → DELETE
  - URL：`/web/instances/from-environment` + `/web/instances/{instanceUid}`
- **步骤**：
  1. POST 启动实例，获取 `instanceUid`
  2. DELETE 删除实例，检查返回 null/对象
  3. 再次 DELETE 同一 id，检查状态码 404、`error.code` 为 `NOT_FOUND`
- **预期结果**：启动→删除成功→二次删除返回 404 `NOT_FOUND`

---

### TC-INSTANCE-009：停止不存在的实例（异常响应，P1）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/instances/nonexistent-instance-id-99999/stop`
- **步骤**：
  1. 用不存在的实例 ID 发送 POST 请求
  2. 检查响应状态码为 404
  3. 检查 `error.code` 为 `NOT_FOUND`
- **预期结果**：返回 404 `NOT_FOUND`

---

### TC-INSTANCE-010：重启不存在的实例（异常响应，P1）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/instances/nonexistent-instance-id-99999/restart`
- **步骤**：
  1. 用不存在的实例 ID 发送 POST 请求
  2. 检查响应状态码为 404
  3. 检查 `error.code` 为 `NOT_FOUND`
- **预期结果**：返回 404 `NOT_FOUND`

---

## 模块：Instance OpenAPI（/api/v1/agents/:id/instances 与 /api/v1/instances/:id，API Key 认证）

> 说明：响应为 `{success, data}` 信封；错误为 `{success:false, error:{code, message}}`。

### TC-INSTANCE-011：列出 Agent 现有实例（正向，P1）

- **前置条件**：已配置 API Key，Agent 列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/api/v1/agents/{agentId}/instances`
- **步骤**：
  1. 获取 Agent 列表取第一个 ID
  2. 发送 GET 请求
  3. 校验响应结构 `items/total/page/pageSize`
  4. 检查 `page` 为 1、`items` 为数组
- **预期结果**：返回 200 分页实例列表

---

### TC-INSTANCE-012：列出不存在 Agent 的实例（异常响应，P2）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/v1/agents/nonexistent-agent-id-99999/instances`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 404
  3. 检查 `error.code` 为 `NOT_FOUND`
- **预期结果**：返回 404 `NOT_FOUND`

---

### TC-INSTANCE-013：pageSize 超出上限（参数边界，P2）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/v1/agents/nonexistent-agent-id-99999/instances?pageSize=99999`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 400
  3. 检查 `error.code` 为 `VALIDATION_ERROR`
- **预期结果**：返回 400 `VALIDATION_ERROR`（pageSize 上限 100）

---

### TC-INSTANCE-014：查询不存在的实例详情（异常响应，P2）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/v1/instances/nonexistent-instance-id-99999`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 404
  3. 检查 `error.code` 为 `NOT_FOUND`
- **预期结果**：返回 404 `NOT_FOUND`

---

### TC-INSTANCE-015：停止不存在的实例（异常响应，P2）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：POST
  - URL：`/api/v1/instances/nonexistent-instance-id-99999/stop`
- **步骤**：
  1. 发送 POST 请求
  2. 检查响应状态码为 404
  3. 检查 `error.code` 为 `NOT_FOUND`
- **预期结果**：返回 404 `NOT_FOUND`

---

### TC-INSTANCE-016：重启不存在的实例（异常响应，P2）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：POST
  - URL：`/api/v1/instances/nonexistent-instance-id-99999/restart`
- **步骤**：
  1. 发送 POST 请求
  2. 检查响应状态码为 404
  3. 检查 `error.code` 为 `NOT_FOUND`
- **预期结果**：返回 404 `NOT_FOUND`
