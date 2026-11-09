# Model Gateway 模块 API 手工测试用例

> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

说明：用量查询要求 `startAt`/`endAt` 为 `YYYY-MM-DD`；上游网关不可达时会返回 400 `MODEL_GATEWAY_ERROR`，因此用例只校验参数契约，不把上游可用性当作前提。

## 模块：Model Gateway Web API

### TC-MGW-001：用量查询缺少 startAt（必填缺失）

- **前置条件**：已登录；存在可用 Provider
- **请求信息**：
  - 方法：GET
  - URL：`/web/model-gateway/<providerId>/usage`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 发送 GET 请求（不带查询参数）
  2. 检查响应状态码为 400
  3. 检查 `error.type` 为 `VALIDATION_ERROR`
  4. 检查 `error.message` 包含 `startAt`
- **预期结果**：返回 400

---

### TC-MGW-002：用量查询缺少 endAt（必填缺失）

- **前置条件**：已登录；存在可用 Provider
- **请求信息**：
  - 方法：GET
  - URL：`/web/model-gateway/<providerId>/usage?startAt=2026-01-01`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 400
  3. 检查 `error.type` 为 `VALIDATION_ERROR`
  4. 检查 `error.message` 包含 `endAt`
- **预期结果**：返回 400

---

### TC-MGW-003：用量查询日期格式非法（边界）

- **前置条件**：已登录；存在可用 Provider
- **请求信息**：
  - 方法：GET
  - URL：`/web/model-gateway/<providerId>/usage?startAt=2026/01/01&endAt=2026/02/01`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 400
  3. 检查 `error.type` 为 `VALIDATION_ERROR`
  4. 检查 `error.message` 包含 `startAt`
- **预期结果**：返回 400，提示日期格式应为 YYYY-MM-DD

---

## 模块：Model Gateway System API

认证方式：`Authorization: Bearer <System API Key>`；响应为裸数据。

### TC-MGW-004：获取模型网关配置（正向）

- **前置条件**：配置有效 System API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/model-gateway/config`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 200
  3. 检查 `provider.id`、`provider.name`、`provider.baseUrl` 为字符串
  4. 检查响应含 `adminUiUrl`
- **预期结果**：返回网关配置

---

### TC-MGW-005：获取模型网关 Key 列表（正向）

- **前置条件**：配置有效 System API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/model-gateway/keys?page=1&pageSize=10`
- **步骤**：
  1. 发送 GET 请求
  2. 检查 `items` 为数组
  3. 检查 `total` 为整数
- **预期结果**：返回分页 Key 列表

---

### TC-MGW-006：获取模型网关预算列表（正向）

- **前置条件**：配置有效 System API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/model-gateway/budgets?page=1&pageSize=10`
- **步骤**：
  1. 发送 GET 请求
  2. 检查 `items` 为数组
  3. 检查 `total` 为整数
- **预期结果**：返回分页预算列表

---

### TC-MGW-007：获取模型同步状态（正向）

- **前置条件**：配置有效 System API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/model-gateway/models/status`
- **步骤**：
  1. 发送 GET 请求
  2. 检查 `status` 为字符串
  3. 检查 `models`、`changes` 为数组
- **预期结果**：返回同步状态

---

### TC-MGW-008：获取计费主体（用户）（正向）

- **前置条件**：配置有效 System API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/model-gateway/subjects/users?page=1&pageSize=10`
- **步骤**：
  1. 发送 GET 请求
  2. 检查 `items` 为数组
- **预期结果**：返回分页用户主体列表

---

### TC-MGW-009：获取计费主体（Agent）（正向）

- **前置条件**：配置有效 System API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/model-gateway/subjects/agents`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应为数组
- **预期结果**：返回 Agent 主体列表

---

### TC-MGW-010：系统用量查询缺少 startAt（必填缺失）

- **前置条件**：配置有效 System API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/model-gateway/usage`
- **步骤**：
  1. 发送 GET 请求（不带查询参数）
  2. 检查响应状态码为 400
  3. 检查 `error.type` 为 `VALIDATION_ERROR`
  4. 检查 `error.message` 包含 `startAt`
- **预期结果**：返回 400
