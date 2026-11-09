> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

# MCP Server 模块 API 手工测试用例

## 模块：MCP Web API

### TC-MCP-001：获取 MCP Server 列表（正向）

- **前置条件**：已登录，有访问权限
- **请求信息**：
  - 方法：GET
  - URL：`/web/config/mcp`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 200
  3. 检查 `data.servers` 字段为数组
- **预期结果**：返回 `{success: true, data: {servers: [...]}}`

---

### TC-MCP-002：获取单个 MCP Server 详情（正向）

- **前置条件**：已登录，MCP 列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/web/config/mcp/{server_id}`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 先调用列表接口获取第一个 Server 的 `id`（或 `name`，客户端会解析成 ID）
  2. 用该 ID 发送 GET 请求
  3. 检查 `data.name` 与请求的 Server 一致
  4. 检查 `data.config` 字段存在
- **预期结果**：返回 MCP Server 详情，包含 id、name、config 字段

---

### TC-MCP-003：创建并删除 MCP Server（正向 CRUD）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST（创建）+ GET（验证）+ DELETE（删除）
  - URL：`/web/config/mcp`
  - Body（创建）：
    ```json
    {
      "name": "api-test-web-mcp-001",
      "config": {
        "type": "remote",
        "url": "https://example.com/mcp"
      }
    }
    ```
- **步骤**：
  1. POST 创建 MCP Server（remote 类型），返回 `{id, name}`
  2. 检查返回 name 与请求一致
  3. GET `/web/config/mcp/{id}` 验证创建成功
  4. DELETE `/web/config/mcp/{id}` 删除
  5. GET 验证资源已消失（404）
- **预期结果**：完整创建→验证→删除生命周期正常

---

### TC-MCP-004：更新 MCP Server（正向）

- **前置条件**：已登录，已创建测试 MCP Server
- **请求信息**：
  - 方法：PATCH
  - URL：`/web/config/mcp/{server_id}`
  - Body：
    ```json
    {
      "config": {
        "type": "remote",
        "url": "https://updated.example.com/mcp"
      }
    }
    ```
- **步骤**：
  1. 创建 MCP Server（url = original），记录返回的 id
  2. 记录原始 name
  3. PATCH 更新 config
  4. GET 验证 config.url 已更新
  5. 验证 name 未被清空
  6. 清理：删除测试 Server
- **预期结果**：url 更新成功，name 保持不变

---

### TC-MCP-005：获取不存在的 MCP Server（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/config/mcp/nonexistent-mcp-name-99999`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 404
- **预期结果**：返回 404 Not Found

---

### TC-MCP-006：启用/禁用 MCP Server（正向）

- **前置条件**：已登录，已创建测试 MCP Server
- **请求信息**：
  - 方法：PATCH
  - URL：`/web/config/mcp/{server_id}`
  - Body（禁用）：`{"enabled": false}`
  - Body（启用）：`{"enabled": true}`
- **步骤**：
  1. 创建 MCP Server，记录返回的 id
  2. PATCH `{"enabled": false}`，检查 `data.enabled == false`
  3. PATCH `{"enabled": true}`，检查 `data.enabled == true`
  4. 清理：删除测试 Server
- **预期结果**：启用/禁用状态切换正常

---

### TC-MCP-007：获取 MCP Server 工具列表（正向）

- **前置条件**：已登录，MCP 列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/web/config/mcp/{server_id}/tools`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 获取 MCP Server 列表，取第一个 Server 的 id
  2. 发送 GET 请求获取工具列表
  3. 检查 `data.name` 与请求一致
  4. 检查 `data.tools` 为数组
- **预期结果**：返回 `{name: "...", tools: [...]}`

---

### TC-MCP-008：创建 MCP Server 使用无效 type（类型错误）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/config/mcp`
  - Body：
    ```json
    {
      "name": "api-test-invalid-type",
      "type": "invalid_type_xyz",
      "url": "https://example.com"
    }
    ```
- **步骤**：
  1. 发送 POST 请求，type 传非法值
  2. 检查响应状态码为 400 或 422
- **预期结果**：返回 400/422 参数校验错误

---

## 模块：MCP OpenAPI（/api/v1/mcp-servers，API Key 认证）

> 说明：响应为 `{success, data}` 信封；错误为 `{success:false, error:{code, message}}`。创建 body：`{name, config: {type: local|remote|streamable-http, ...}, publicReadable?}`（strict）；更新用 PATCH，body 为 `{enabled}` | `{config}` | `{publicReadable}` 三选一。

### TC-MCP-009：获取 MCP Server 列表（OpenAPI 正向）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/v1/mcp-servers`
  - Headers：`Authorization: Bearer {api_key}`
- **步骤**：
  1. 发送 GET 请求
  2. 检查 `items` 字段为数组
  3. 检查分页字段存在
- **预期结果**：返回分页结构 `{items: [...], total, page, pageSize}`

---

### TC-MCP-010：获取单个 MCP Server 详情（OpenAPI 正向）

- **前置条件**：已配置 API Key，MCP 列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/api/v1/mcp-servers/{server_id}`
  - Headers：`Authorization: Bearer {api_key}`
- **步骤**：
  1. 列表接口取第一个 Server 的 id
  2. 用该 id 发送 GET 请求
  3. 检查 `id` 与请求一致
- **预期结果**：返回 MCP Server 详情

---

### TC-MCP-011：创建并删除 MCP Server（OpenAPI CRUD）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：POST（创建）+ GET（验证）+ DELETE（删除）
  - URL：`/api/v1/mcp-servers` / `/api/v1/mcp-servers/{id}`
  - Body（创建）：
    ```json
    {
      "name": "api-test-openapi-mcp-001",
      "config": {
        "type": "remote",
        "url": "https://example.com/mcp"
      }
    }
    ```
- **步骤**：
  1. POST 创建
  2. GET 验证创建成功
  3. DELETE 删除
  4. GET 验证 404
- **预期结果**：完整 CRUD 生命周期正常

---

### TC-MCP-012：更新 MCP Server（OpenAPI 正向）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：PATCH
  - URL：`/api/v1/mcp-servers/{server_id}`
  - Body：
    ```json
    {
      "config": {
        "type": "remote",
        "url": "https://updated-openapi.example.com/mcp"
      }
    }
    ```
- **步骤**：
  1. 创建 MCP Server
  2. PATCH 更新 url
  3. GET 验证 url 已更新
  4. 验证 name 保持不变
  5. 清理：删除测试 Server
- **预期结果**：url 更新成功，name 保持不变

---

### TC-MCP-013：获取不存在的 MCP Server（OpenAPI 异常）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/v1/mcp-servers/nonexistent-mcp-id-99999`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 404
  3. 检查 `success` 为 `false`、`error.code` 为 `NOT_FOUND`
- **预期结果**：返回 404 `NOT_FOUND`

---

### TC-MCP-014：DELETE 幂等性（OpenAPI）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：DELETE × 2
  - URL：`/api/v1/mcp-servers/{server_id}`
- **步骤**：
  1. 创建 MCP Server
  2. 第一次 DELETE 成功
  3. 第二次 DELETE，检查返回 404
- **预期结果**：第二次删除返回 404

---

### TC-MCP-015：创建同名 MCP Server（重复/幂等）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：POST × 2
  - URL：`/api/v1/mcp-servers`
  - Body：
    ```json
    {
      "name": "api-test-openapi-mcp-dup",
      "config": {
        "type": "remote",
        "url": "https://example.com/mcp"
      }
    }
    ```
- **步骤**：
  1. 第一次 POST 创建
  2. 第二次 POST 同名 Server
  3. 检查第二次返回 409
  4. 检查 `error.code` 为 `ALREADY_EXISTS`
  5. 清理：删除测试 Server
- **预期结果**：重复创建返回 409 `ALREADY_EXISTS`

---

### TC-MCP-016：测试 MCP URL 缺少 url（必填缺失）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/config/mcp/test-url`
  - Body：`{}`
- **步骤**：
  1. 发送 POST 请求
  2. 检查响应状态码为 400
  3. 检查 `error.code` 为 `VALIDATION_ERROR`
  4. 检查 `error.message` 包含 `URL`
- **预期结果**：返回 400

---

### TC-MCP-017：测试不存在的 MCP Server（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/config/mcp/nonexistent-mcp-id-99999/test`
- **步骤**：
  1. 发送 POST 请求
  2. 检查响应状态码为 404
  3. 检查 `error.code` 为 `NOT_FOUND`
- **预期结果**：返回 404

---

### TC-MCP-018：探测不存在的 MCP Server（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/config/mcp/nonexistent-mcp-id-99999/inspect`
- **步骤**：
  1. 发送 POST 请求
  2. 检查响应状态码为 404
  3. 检查 `error.code` 为 `NOT_FOUND`
- **预期结果**：返回 404
