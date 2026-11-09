> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

# Model 模块 API 手工测试用例

## 模块：Model Web API

### TC-MODEL-001：获取模型偏好与可用模型列表（正向）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/config/models`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应包含 `available` 或 `current` 字段
- **预期结果**：返回模型偏好设置和可用模型列表

---

### TC-MODEL-002：强制刷新可用模型缓存（正向）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/config/models/refresh`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 发送 POST 请求
  2. 检查返回 `count` 字段为整数
- **预期结果**：返回 `{count: N}`，N 为整数

---

### TC-MODEL-003：无效 Token 访问模型偏好（权限）

- **前置条件**：未登录（无 Cookie）
- **请求信息**：
  - 方法：GET
  - URL：`/web/config/models`
- **步骤**：
  1. 不携带 Cookie 发送 GET 请求
  2. 检查响应状态码为 401
- **预期结果**：返回 401 Unauthorized

---

## 模块：Model OpenAPI（Provider + Model CRUD）

### TC-MODEL-004：获取 Provider 列表（OpenAPI 正向）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/v1/providers`
  - Headers：`Authorization: Bearer {api_key}`
- **步骤**：
  1. 发送 GET 请求
  2. 检查 `items` 为数组
- **预期结果**：返回分页结构 `{items: [...]}`

---

### TC-MODEL-005：获取 Provider 详情（OpenAPI 正向）

- **前置条件**：已配置 API Key，Provider 列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/api/v1/providers/{provider_id}`
- **步骤**：
  1. 列表接口取第一个 Provider ID
  2. GET 查详情
  3. 检查 `id` 与请求一致
- **预期结果**：返回 Provider 详情

---

### TC-MODEL-006：Provider CRUD 生命周期（OpenAPI）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：POST（创建）+ GET + PATCH（更新）+ DELETE
  - URL：`/api/v1/providers` / `/api/v1/providers/{id}`
  - Body（创建）：
    ```json
    {
      "name": "api-test-openapi-provider-001",
      "displayName": "Test Provider",
      "protocol": "openai",
      "apiKey": "sk-test-key-for-api-testing",
      "baseUrl": "https://api.test-provider.example.com"
    }
    ```
- **步骤**：
  1. POST 创建 Provider
  2. GET 验证创建成功
  3. PATCH 更新 baseUrl
  4. GET 验证更新生效、name 未被清空
  5. DELETE 删除
  6. GET 验证 404
- **预期结果**：完整 CRUD 生命周期正常

---

### TC-MODEL-007：获取 Model 列表（OpenAPI 正向）

- **前置条件**：已配置 API Key，Provider 列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/api/v1/providers/{provider_id}/models`
- **步骤**：
  1. 获取 Provider 列表取第一个 ID
  2. 发送 GET 请求
  3. 检查 `items` 为数组
- **预期结果**：返回 Model 列表

---

### TC-MODEL-008：Model CRUD 生命周期（OpenAPI）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：POST（创建 Provider + Model）+ GET + PATCH + DELETE
  - Body（创建 Model）：
    ```json
    {
      "modelId": "test-model-gpt-4",
      "displayName": "Test GPT-4"
    }
    ```
- **步骤**：
  1. 创建 Provider
  2. POST 添加 Model
  3. GET 获取 Model 详情
  4. PATCH 更新 displayName
  5. GET 验证更新生效，modelId 不变
  6. DELETE 删除 Model，验证 404
  7. 删除 Provider
- **预期结果**：Model 完整 CRUD 正常

---

### TC-MODEL-009：获取不存在的 Provider（异常）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/v1/providers/nonexistent-provider-id-99999`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 404
  3. 检查 `success` 为 `false`、`error.code` 为 `NOT_FOUND`
- **预期结果**：返回 404 `NOT_FOUND`

---

### TC-MODEL-010：创建 Model 使用空 modelId（必填参数缺失）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：POST
  - URL：`/api/v1/providers/{provider_id}/models`
  - Body：`{"modelId": "", "displayName": "Invalid Model"}`
- **步骤**：
  1. 发送 POST 请求，modelId 传空字符串
  2. 检查响应状态码为 400
  3. 检查 `error.code` 为 `VALIDATION_ERROR`
- **预期结果**：返回 400 `VALIDATION_ERROR`

---

### TC-MODEL-011：创建 Model 缺少 modelId 字段（必填参数缺失）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：POST
  - URL：`/api/v1/providers/{provider_id}/models`
  - Body：`{"displayName": "No modelId"}`
- **步骤**：
  1. 发送 POST 请求，不传 modelId 字段
  2. 检查响应状态码为 400
  3. 检查 `error.code` 为 `VALIDATION_ERROR`
- **预期结果**：返回 400 `VALIDATION_ERROR`
