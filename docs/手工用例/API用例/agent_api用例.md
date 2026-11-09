> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

# Agent 模块 API 手工测试用例

## 模块：Agent Web API

### TC-AGENT-001：获取 Agent 列表（正向）

- **前置条件**：已登录，有访问权限
- **请求信息**：
  - 方法：GET
  - URL：`/web/config/agents`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 200
  3. 检查响应 `success` 为 `true`
  4. 检查 `data.agents` 字段为非空数组
- **预期结果**：返回 `{success: true, data: {agents: [...], default_agent: ...}}`，agents 数组非空

---

### TC-AGENT-002：获取单个 Agent 详情（正向）

- **前置条件**：已登录，Agent 列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/web/config/agents/{agentId}`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 先调用列表接口获取第一个 Agent 的 name，解析出资源 ID
  2. 用该 ID 发送 GET 请求
  3. 检查响应状态码为 200
  4. 检查 `data.name` 与请求的 name 一致
  5. 检查 `data.id` 字段存在
- **预期结果**：返回 Agent 详情对象，包含 name、id 等字段

---

### TC-AGENT-003：创建并删除 Agent（正向 CRUD）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST（创建）+ GET（验证）+ DELETE（删除）
  - URL：`/web/config/agents`
  - Body（创建）：
    ```json
    {
      "name": "api-test-web-agent-001",
      "description": "Web API 测试自动创建的 Agent"
    }
    ```
- **步骤**：
  1. POST 创建 Agent，检查返回 name 与请求一致
  2. GET 验证创建成功
  3. DELETE 删除
  4. GET 验证资源已消失（抛出异常）
- **预期结果**：完整创建→验证→删除生命周期正常

---

### TC-AGENT-004：更新 Agent（正向）

- **前置条件**：已登录，已创建测试 Agent
- **请求信息**：
  - 方法：PATCH
  - URL：`/web/config/agents/{agentId}`
  - Body：`{"data": {"description": "updated by web api test"}}`
- **步骤**：
  1. 创建测试 Agent
  2. 记录原始 name 字段值
  3. PATCH 更新 description
  4. GET 验证 description 已更新
  5. 验证未修改的 name 字段未被清空
  6. 清理：删除测试 Agent
- **预期结果**：description 更新成功，name 保持不变

---

### TC-AGENT-005：获取不存在的 Agent（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/config/agents/nonexistent-agent-id-99999`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 404
- **预期结果**：返回 404 Not Found

---

### TC-AGENT-006：获取 Agent 模板列表（正向）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/config/agents/templates`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 200
  3. 检查 `data.templates` 为数组
- **预期结果**：返回 `{success: true, data: {templates: [...]}}`

---

### TC-AGENT-007：设置默认 Agent（正向）

- **前置条件**：已登录，Agent 列表非空
- **请求信息**：
  - 方法：POST
  - URL：`/web/config/agents/default`
  - Body：`{"name": "{列表中第一个Agent的name}"}`
- **步骤**：
  1. 获取 Agent 列表，取第一个 Agent name
  2. 记录原始 default_agent
  3. POST 设置新的默认 Agent
  4. 检查返回 `data.default_agent` 与设置值一致
  5. 恢复原始默认 Agent
- **预期结果**：默认 Agent 设置成功

---

### TC-AGENT-008：创建 Agent 缺少 name（必填参数缺失）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/config/agents`
  - Body：`{"description": "no name agent"}`
- **步骤**：
  1. 发送 POST 请求（不传 name 字段）
  2. 检查响应状态码为 400 或 422
- **预期结果**：返回 400/422 参数校验错误

---

### TC-AGENT-009：无效 Token 访问 Agent 列表（权限）

- **前置条件**：未登录（无 Cookie）
- **请求信息**：
  - 方法：GET
  - URL：`/web/config/agents`
  - Headers：无 Cookie
- **步骤**：
  1. 不携带 Cookie 发送 GET 请求
  2. 检查响应状态码为 401
- **预期结果**：返回 401 Unauthorized

---

### TC-AGENT-010：创建同名 Agent（重复/幂等）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST × 2
  - URL：`/web/config/agents`
  - Body：`{"name": "api-test-web-agent-dup-001"}`
- **步骤**：
  1. 第一次 POST 创建 Agent
  2. 第二次 POST 同名 Agent
  3. 检查第二次返回 409 或 400
  4. 清理：删除测试 Agent
- **预期结果**：重复创建返回 409 Conflict 或 400 Bad Request

---

## 模块：Agent OpenAPI（/api/v1/agents，API Key 认证）

> 说明：响应为 `{success, data}` 信封；错误为 `{success:false, error:{code, message}}`。更新用 PATCH；创建 body 必填 `name`（1-64 字符）。

### TC-AGENT-011：获取 Agent 列表（OpenAPI 正向）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/v1/agents`
  - Headers：`Authorization: Bearer {api_key}`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 200
  3. 检查 `items` 字段为数组
  4. 检查分页字段 `total`、`page`、`pageSize` 存在
- **预期结果**：返回 `{items: [...], total: N, page: 1, pageSize: 20}` 分页结构

---

### TC-AGENT-012：获取单个 Agent 详情（OpenAPI 正向）

- **前置条件**：已配置 API Key，Agent 列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/api/v1/agents/{agent_id}`
  - Headers：`Authorization: Bearer {api_key}`
- **步骤**：
  1. 先调用列表接口获取第一个 Agent 的 id
  2. 用该 id 发送 GET 请求
  3. 检查 `id` 与请求一致
- **预期结果**：返回 Agent 详情对象

---

### TC-AGENT-013：创建并删除 Agent（OpenAPI CRUD）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：POST（创建）+ GET（验证）+ DELETE（删除）
  - URL：`/api/v1/agents` / `/api/v1/agents/{id}`
  - Body（创建）：
    ```json
    {
      "name": "api-test-openapi-agent-001",
      "description": "OpenAPI 测试自动创建的 Agent"
    }
    ```
- **步骤**：
  1. POST 创建 Agent
  2. GET 验证创建成功
  3. DELETE 删除
  4. GET 验证资源已消失（404）
- **预期结果**：完整 CRUD 生命周期正常

---

### TC-AGENT-014：更新 Agent（OpenAPI 正向）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：PATCH
  - URL：`/api/v1/agents/{agent_id}`
  - Body：`{"description": "updated by openapi test"}`
- **步骤**：
  1. 创建测试 Agent
  2. PATCH 更新 description
  3. 校验详情结构并检查 description 已更新
  4. GET 验证 description 已更新
  5. 验证未修改的 name 字段保持不变
  6. 清理：删除测试 Agent
- **预期结果**：description 更新成功，name 保持不变

---

### TC-AGENT-015：获取不存在的 Agent（OpenAPI 异常）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/v1/agents/nonexistent-agent-id-99999`
  - Headers：`Authorization: Bearer {api_key}`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 404
  3. 检查 `success` 为 `false`、`error.code` 为 `NOT_FOUND`
- **预期结果**：返回 404 `NOT_FOUND`

---

### TC-AGENT-016：DELETE 幂等性（OpenAPI）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：DELETE × 2
  - URL：`/api/v1/agents/{agent_id}`
- **步骤**：
  1. 创建 Agent
  2. 第一次 DELETE 成功
  3. 第二次 DELETE 同一 Agent
  4. 检查第二次返回 404
- **预期结果**：第二次删除返回 404

---

### TC-AGENT-017：PATCH 部分字段更新（OpenAPI）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：PATCH
  - URL：`/api/v1/agents/{agent_id}`
  - Body：`{"description": "partial update"}`
- **步骤**：
  1. 创建 Agent（含 name + description）
  2. 只更新 description，不传 name
  3. GET 验证 description 已更新
  4. 验证 name 保持原始值
  5. 清理：删除测试 Agent
- **预期结果**：部分更新生效，未传字段不被清空

---

### TC-AGENT-018：分页参数生效（OpenAPI）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/v1/agents?page=1&pageSize=1`
- **步骤**：
  1. 发送带分页参数的 GET 请求
  2. 检查 `page` 为 1
  3. 检查 `pageSize` 为 1
- **预期结果**：分页参数生效，返回指定页和页大小

---

### TC-AGENT-019：获取第 2 页数据（OpenAPI 分页）

- **前置条件**：已配置 API Key，Agent 总数 > 1
- **请求信息**：
  - 方法：GET
  - URL：`/api/v1/agents?page=2&pageSize=1`
- **步骤**：
  1. 获取第 1 页数据
  2. 获取第 2 页数据
  3. 比较两页数据不重复
- **预期结果**：第 2 页数据与第 1 页不同

---

### TC-AGENT-020：超大 pageSize（OpenAPI 分页边界）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/v1/agents?page=1&pageSize=99999`
- **步骤**：
  1. 发送超大 pageSize 的 GET 请求
  2. 检查响应状态码为 400
  3. 检查 `error.code` 为 `VALIDATION_ERROR`
- **预期结果**：返回 400 `VALIDATION_ERROR`（pageSize 上限 100）

---

### TC-AGENT-021：name 含特殊字符（OpenAPI 边界）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：POST
  - URL：`/api/v1/agents`
  - Body：
    ```json
    {
      "name": "api-test-special-chars-<>&\"'",
      "description": "Special characters test"
    }
    ```
- **步骤**：
  1. 创建含特殊字符的 Agent
  2. GET 验证 name 原样保存
  3. 清理：删除测试 Agent
- **预期结果**：特殊字符正确处理，返回的 name 与请求一致

---

### TC-AGENT-022：重启不存在的 Agent（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/config/agents/nonexistent-agent-id-99999/restart`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 用不存在的 Agent ID 发送 POST 请求
  2. 检查响应状态码为 404
  3. 检查 `error.code` 为 `NOT_FOUND`
- **预期结果**：返回 404 Not Found

---

### TC-AGENT-023：查询不存在的会话 Trace（正向/空结果）

- **前置条件**：已登录，环境列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/web/agents/{env_id}/sessions/nonexistent-session-id-99999/traces`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 环境列表取第一个 env_id
  2. 用不存在的 sessionId 查询 Trace
  3. 检查 `traces` 为数组
  4. 检查 `page`、`totalItems` 为整数
- **预期结果**：返回空 Trace 列表，结构完整（非 404）

---

### TC-AGENT-024：获取不存在的 Trace Observation 详情（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/agents/nonexistent-env-99999/sessions/nonexistent-session-99999/traces/nonexistent-trace-99999/observations/nonexistent-obs-99999`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 用全部不存在的路径参数发送 GET 请求
  2. 检查响应状态码为 404
  3. 检查 `success` 为 `false`
  4. 检查 `error.code` 为 `NOT_FOUND`
- **预期结果**：返回 404，且为环境/资源不存在错误

---

### TC-AGENT-025：无效 API Key 访问 OpenAPI（权限场景）

- **前置条件**：已配置有效 API Key（用于外层 fixture 探测）
- **请求信息**：
  - 方法：GET
  - URL：`/api/v1/agents?page=1&pageSize=1`
  - Headers：`Authorization: Bearer rcs_invalid-token-99999`
- **步骤**：
  1. 用无效 API Key 发送 GET 请求
  2. 检查响应状态码为 401
- **预期结果**：返回 401 Unauthorized
