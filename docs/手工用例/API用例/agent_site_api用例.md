> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

# Agent Site 模块 API 手工测试用例

## 模块：Agent Site Web API

### TC-AGENTSITE-001：获取 App 列表（正向）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/agent-sites/apps`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 发送 GET 请求
  2. 检查返回为数组
- **预期结果**：返回 App 数组

---

### TC-AGENTSITE-002：获取 App 详情（正向）

- **前置条件**：已登录，App 列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/web/agent-sites/apps/{app_id}`
- **步骤**：
  1. 列表接口取第一个 ID
  2. GET 查详情
  3. 检查 `id` 与请求一致
  4. 检查 `name` 字段存在
- **预期结果**：返回 App 详情

---

### TC-AGENTSITE-003：获取不存在的 App（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/agent-sites/apps/nonexistent-app-id-99999`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 400/404/422
- **预期结果**：返回错误

---

### TC-AGENTSITE-004：创建并删除 App（正向 CRUD）

- **前置条件**：已登录，Agent Site 服务可用
- **请求信息**：
  - 方法：POST（创建）+ GET（验证）+ DELETE（删除）
  - URL：`/web/agent-sites/apps`
  - Body（创建）：`{"name": "test-site-api-auto", "type": "custom"}`
- **步骤**：
  1. 清理同名遗留数据
  2. POST 创建 App
  3. GET 验证创建成功
  4. DELETE 删除
  5. GET 验证 404
- **预期结果**：完整 CRUD 正常。服务不可用时 skip

---

### TC-AGENTSITE-005：通过不存在的 remoteAppId 查询（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/agent-sites/by-remote/nonexistent-remote-id-99999`
- **步骤**：
  1. 发送 GET 请求
  2. 检查返回 404/400
- **预期结果**：返回错误

---

### TC-AGENTSITE-006：轮转不存在的 App Token（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/agent-sites/apps/nonexistent-app-id-99999/rotate-token`
- **步骤**：
  1. 发送 POST 请求
  2. 检查返回 404/400/500
- **预期结果**：返回错误

---

### TC-AGENTSITE-007：部署不存在的 App（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/agent-sites/apps/nonexistent-app-id-99999/deploy`
- **步骤**：
  1. 发送 POST 请求
  2. 检查返回 404/400/500
- **预期结果**：返回错误

---

### TC-AGENTSITE-008：获取 Agent 配置关联的 Sites（正向）

- **前置条件**：已登录，Agent 列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/web/agent-sites/agent-configs/{agent_config_id}/sites`
- **步骤**：
  1. 获取 Agent 列表取第一个 `id`（配置 ID，不能传 name）
  2. GET 获取关联 Sites
  3. 检查返回为数组
- **预期结果**：返回 Sites 数组

---

### TC-AGENTSITE-009：挂载 Site 到不存在的 Agent 配置（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/agent-sites/agent-configs/nonexistent-config-99999/sites/nonexistent-site-99999`
- **步骤**：
  1. 发送 POST 请求
  2. 检查响应状态码为 404
  3. 检查 `error.type` 为 `NOT_FOUND`
  4. 检查 `error.message` 为 `Resource not found`
- **预期结果**：返回 404

---

### TC-AGENTSITE-010：从不存在 Agent 配置卸载 Site（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：DELETE
  - URL：`/web/agent-sites/agent-configs/nonexistent-config-99999/sites/nonexistent-site-99999`
- **步骤**：
  1. 发送 DELETE 请求
  2. 检查响应状态码为 404
  3. 检查 `error.type` 为 `NOT_FOUND`
- **预期结果**：返回 404

---

### TC-AGENTSITE-011：向不存在的 App 上传文件（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：PUT
  - URL：`/web/agent-sites/apps/nonexistent-app-99999/files/index.html`
  - Body：任意字节
- **步骤**：
  1. 发送 PUT 请求
  2. 检查响应状态码为 400
  3. 检查 `error.type` 为 `VALIDATION_ERROR`
  4. 检查 `error.message` 包含 `Invalid UUID`
- **预期结果**：返回 400（app id 非法 UUID）

---

### TC-AGENTSITE-012：向不存在的 App 上传文件包（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/agent-sites/apps/nonexistent-app-99999/files/bundle`
  - Body：任意字节
- **步骤**：
  1. 发送 POST 请求
  2. 检查响应状态码为 400
  3. 检查 `error.type` 为 `VALIDATION_ERROR`
  4. 检查 `error.message` 包含 `Invalid UUID`
- **预期结果**：返回 400
