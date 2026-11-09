> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

# Environment 模块 API 手工测试用例

## 模块：Environment Web API

### TC-ENV-001：获取环境列表（正向）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/environments`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 发送 GET 请求
  2. 检查返回为数组
- **预期结果**：返回环境数组

---

### TC-ENV-002：获取环境详情（正向）

- **前置条件**：已登录，环境列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/web/environments/{env_id}`
- **步骤**：
  1. 获取环境列表取第一个 ID
  2. GET 查详情
  3. 检查 `id` 与请求一致
  4. 检查 `name` 字段存在
- **预期结果**：返回环境详情对象

---

### TC-ENV-003：环境 CRUD 生命周期（正向）

- **前置条件**：已登录，有可用 Agent 配置
- **请求信息**：
  - 方法：POST（创建）+ GET + PUT（更新）+ DELETE
  - URL：`/web/environments` / `/web/environments/{id}`
  - Body（创建）：
    ```json
    {
      "name": "api-test-web-env-001",
      "description": "API test environment",
      "agentConfigId": "{有效的agentConfigId}",
      "autoStart": false
    }
    ```
- **步骤**：
  1. POST 创建环境
  2. GET 验证创建成功
  3. PUT 更新 description
  4. GET 验证更新生效、name 不变
  5. DELETE 删除
  6. GET 验证 404
- **预期结果**：完整 CRUD 正常

---

### TC-ENV-004：创建环境缺少 agentConfigId（必填参数缺失）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/environments`
  - Body：`{"name": "api-test-env-invalid"}`（不传 agentConfigId）
- **步骤**：
  1. 发送 POST 请求
  2. 检查响应状态码为 400 或 422
- **预期结果**：返回 400/422 参数校验错误

---

### TC-ENV-005：创建环境使用无效 agentConfigId（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/environments`
  - Body：
    ```json
    {
      "name": "api-test-env-bad-agent",
      "agentConfigId": "nonexistent-agent-id-99999"
    }
    ```
- **步骤**：
  1. 发送 POST 请求
  2. 检查响应状态码为 400/404/422/500
- **预期结果**：返回错误状态码

---

### TC-ENV-006：获取不存在的环境（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/environments/nonexistent-env-id-99999`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 404
- **预期结果**：返回 404 Not Found

---

### TC-ENV-007：获取环境实例列表（正向）

- **前置条件**：已登录，环境列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/web/environments/{env_id}/instances`
- **步骤**：
  1. 获取环境列表取第一个 ID
  2. GET 获取实例列表
  3. 检查返回为数组或包含 instances 字段的对象
- **预期结果**：返回实例列表

---

### TC-ENV-008：创建空 name 环境（参数边界）

- **前置条件**：已登录，有可用 Agent 配置
- **请求信息**：
  - 方法：POST
  - URL：`/web/environments`
  - Body：
    ```json
    {
      "name": "",
      "description": "Empty name test",
      "agentConfigId": "{有效的agentConfigId}"
    }
    ```
- **步骤**：
  1. 发送 POST 请求，name 传空字符串
  2. 检查响应状态码为 400 或 422
- **预期结果**：返回 400/422 参数校验错误

---

### TC-ENV-009：DELETE 幂等性

- **前置条件**：已登录，有可用 Agent 配置
- **请求信息**：
  - 方法：DELETE × 2
  - URL：`/web/environments/{env_id}`
- **步骤**：
  1. 创建环境
  2. 第一次 DELETE 成功
  3. 第二次 DELETE，检查返回 404
- **预期结果**：第二次删除返回 404
