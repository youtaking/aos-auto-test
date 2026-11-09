> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

# OpenAI Chat 模块 API 手工测试用例

## 模块：OpenAI Chat OpenAPI（/api/v1/chat/completions，API Key 认证）

> 说明：`/api/v1/chat/completions` 是唯一不遵循 `{success, data}` 信封的 v1 接口，错误响应为 OpenAI 原生格式 `{error: {message, type, param, code}}`。

### TC-OPENAICHAT-001：向不存在的 Agent 发送 chat（异常响应，P2）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：POST
  - URL：`/api/v1/chat/completions`
  - Headers：`Authorization: Bearer <API Key>`、`Content-Type: application/json`
  - Body：
    ```json
    {
      "model": "00000000-0000-4000-8000-000000000000",
      "messages": [{"role": "user", "content": "hello"}]
    }
    ```
- **步骤**：
  1. 发送 POST 请求
  2. 检查响应状态码为 404
  3. 检查响应体 `error.message` 为字符串、`error.type` 为字符串
  4. 检查 `error.code` 为 `NOT_FOUND`
- **预期结果**：返回 404，OpenAI 错误信封 `{"error":{"message":"...","type":"...","code":"NOT_FOUND"}}`

---

### TC-OPENAICHAT-002：model 不是 UUID（参数边界，P2）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：POST
  - URL：`/api/v1/chat/completions`
  - Body：
    ```json
    {
      "model": "not-a-uuid",
      "messages": [{"role": "user", "content": "hello"}]
    }
    ```
- **步骤**：
  1. 发送 POST 请求
  2. 检查响应状态码为 400
  3. 检查 `error.code` 为 `VALIDATION_ERROR`
- **预期结果**：返回 400，错误码 `VALIDATION_ERROR`

---

### TC-OPENAICHAT-003：最后一条不是 user 消息（业务规则，P2）

- **前置条件**：已配置 API Key，Agent 列表非空
- **请求信息**：
  - 方法：POST
  - URL：`/api/v1/chat/completions`
  - Body：
    ```json
    {
      "model": "<agentConfigId>",
      "messages": [{"role": "system", "content": "you are a helper"}]
    }
    ```
- **步骤**：
  1. 发送 POST 请求
  2. 检查响应状态码为 400
  3. 检查 `error.code` 为 `VALIDATION_ERROR`
- **预期结果**：返回 400，错误码 `VALIDATION_ERROR`

---

### TC-OPENAICHAT-004：空 messages 数组（必填参数缺失，P2）

- **前置条件**：已配置 API Key，Agent 列表非空
- **请求信息**：
  - 方法：POST
  - URL：`/api/v1/chat/completions`
  - Body：`{"model": "<agentConfigId>", "messages": []}`
- **步骤**：
  1. 发送 POST 请求
  2. 检查响应状态码为 400
  3. 检查 `error.code` 为 `VALIDATION_ERROR`
- **预期结果**：返回 400，错误码 `VALIDATION_ERROR`

---

### TC-OPENAICHAT-005：请求带未声明的顶层字段（strict schema，P2）

- **前置条件**：已配置 API Key，Agent 列表非空
- **请求信息**：
  - 方法：POST
  - URL：`/api/v1/chat/completions`
  - Body：
    ```json
    {
      "model": "<agentConfigId>",
      "messages": [{"role": "user", "content": "ping"}],
      "temperature": 0.7
    }
    ```
- **步骤**：
  1. 发送 POST 请求
  2. 检查响应状态码为 400
  3. 检查 `error.code` 为 `VALIDATION_ERROR`
- **预期结果**：返回 400，错误码 `VALIDATION_ERROR`（schema 为 strict，不接受 temperature）

---

### TC-OPENAICHAT-006：非流式 chat 请求（正向，P0）

- **前置条件**：已配置 API Key，Agent 列表非空，Agent 环境可用
- **请求信息**：
  - 方法：POST
  - URL：`/api/v1/chat/completions`
  - Body：
    ```json
    {
      "model": "<agentConfigId>",
      "messages": [{"role": "user", "content": "ping"}],
      "stream": false
    }
    ```
- **步骤**：
  1. 发送非流式 chat 请求
  2. 校验响应结构：`id/object/created/model/choices`
  3. 检查 `object` 为 `chat.completion`
  4. 检查 `choices` 为数组，元素含 `index/message/finish_reason`
- **预期结果**：返回 200，OpenAI 兼容响应 `{"object":"chat.completion","choices":[...]}`；Agent 环境不可用（404/500/504 或超时）时跳过
