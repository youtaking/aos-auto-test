> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

# Hooks Webhook 模块 API 手工测试用例

## 模块：Hooks Webhook API

### TC-HOOKS-001：无效 hash 触发 Webhook（异常）

- **前置条件**：无需认证
- **请求信息**：
  - 方法：POST
  - URL：`/hooks/nonexistent-hash-99999`
  - Body：
    ```json
    {"test": "data"}
    ```
- **步骤**：
  1. 用无效 hash 发送 POST 请求
  2. 检查响应状态码
- **预期结果**：源码预期 404 `{error: "..."}` ；当前实际返回 200 + 空 body（应用 Bug）

---

### TC-HOOKS-002：空 hash 触发 Webhook（边界）

- **前置条件**：无需认证
- **请求信息**：
  - 方法：POST
  - URL：`/hooks/`
  - Body：
    ```json
    {"test": "data"}
    ```
- **步骤**：
  1. 用空 hash 发送 POST 请求
  2. 检查响应状态码为 200/400/404/405
- **预期结果**：返回 200/400/404/405

---

### TC-HOOKS-003：超大请求体触发 Webhook（边界）

- **前置条件**：无需认证
- **请求信息**：
  - 方法：POST
  - URL：`/hooks/test-hash`
  - Body：`{"data": "x" * 1048577}`（超过 1MB）
- **步骤**：
  1. 构造超过 1MB 的请求体
  2. 发送 POST 请求
  3. 检查响应状态码为 413（源码预期）或 200
- **预期结果**：源码预期 413 Payload Too Large；当前可能返回 200

---

### TC-HOOKS-004：无请求体触发 Webhook（边界）

- **前置条件**：无需认证
- **请求信息**：
  - 方法：POST
  - URL：`/hooks/nonexistent-hash-99999`
  - Body：空
  - Headers：`Content-Type: application/json`
- **步骤**：
  1. 不携带请求体发送 POST 请求
  2. 检查响应状态码为 200 或 404
- **预期结果**：返回 200/404

---

### TC-HOOKS-005：字符串请求体触发 Webhook（边界）

- **前置条件**：无需认证
- **请求信息**：
  - 方法：POST
  - URL：`/hooks/nonexistent-hash-99999`
  - Body：`plain text body`
  - Headers：`Content-Type: text/plain`
- **步骤**：
  1. 用纯文本请求体发送 POST 请求
  2. 检查响应状态码为 200 或 404
- **预期结果**：返回 200/404

---

### TC-HOOKS-006：带 query 参数触发 Webhook（正向）

- **前置条件**：无需认证
- **请求信息**：
  - 方法：POST
  - URL：`/hooks/nonexistent-hash-99999?key1=value1&key2=value2`
  - Body：
    ```json
    {"test": "data"}
    ```
- **步骤**：
  1. 带 query 参数发送 POST 请求
  2. 检查响应状态码为 200 或 404
- **预期结果**：返回 200/404

---

### TC-HOOKS-007：有效触发器 hash 触发 Webhook（正向）

- **前置条件**：已登录（获取触发器 hash），有可用的工作流触发器
- **请求信息**：
  - 方法：POST
  - URL：`/hooks/{trigger_publicHash}`
  - Body：
    ```json
    {"event": "test", "data": {"key": "value"}}
    ```
- **步骤**：
  1. 通过 Web API 获取工作流定义列表
  2. 获取第一个工作流的触发器列表
  3. 取第一个触发器的 publicHash
  4. 用该 hash 发送 POST 请求
  5. 检查响应状态码为 200
  6. 如有 JSON body，检查 `received` 为 true
- **预期结果**：返回 200，body 为 `{received: true}`（如有 body）
