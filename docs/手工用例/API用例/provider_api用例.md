> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

# Provider 模块 API 手工测试用例

## 模块：Provider Web API（/web/config/providers）

### TC-PROVIDER-001：获取 Provider 列表（正向）

- **前置条件**：已登录，有访问权限
- **请求信息**：
  - 方法：GET
  - URL：`/web/config/providers`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 200
  3. 检查 `data.providers` 为数组
  4. 检查每项含 `id`、`name`
- **预期结果**：返回 `{success: true, data: {providers: [...]}}`

---

### TC-PROVIDER-002：获取单个 Provider 详情（正向）

- **前置条件**：已登录，Provider 列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/web/config/providers/{providerId}`
- **步骤**：
  1. 先 GET `/web/config/providers` 取一个可查询的 `id`
  2. 发送 GET 详情请求
  3. 检查响应状态码为 200
  4. 检查 `data.id` 与请求一致，含 `name`
  5. 检查结构符合 Provider 详情契约
- **预期结果**：返回 Provider 详情

---

### TC-PROVIDER-003：获取不存在的 Provider（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/config/providers/nonexistent-provider-name-99999`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 404
- **预期结果**：返回 404 Not Found

---

### TC-PROVIDER-004：Provider CRUD 生命周期（正向）

- **前置条件**：已登录；测试开始前先清理同名残留
- **请求信息**：
  - 方法：POST（创建）+ GET（读取）+ PATCH（更新）+ DELETE（删除）
  - URL：`/web/config/providers`
  - Body（创建）：
    ```json
    {
      "name": "api-test-web-provider-001",
      "displayName": "Test Provider",
      "protocol": "openai",
      "apiKey": "sk-test-key-for-api-testing",
      "baseURL": "https://api.test-provider.example.com"
    }
    ```
  - Body（更新，PATCH `/web/config/providers/{id}`）：
    ```json
    {
      "displayName": "Updated Test Provider",
      "protocol": "openai",
      "baseURL": "https://updated.test-provider.example.com"
    }
    ```
- **步骤**：
  1. POST 创建 Provider，检查返回 `name == api-test-web-provider-001`
  2. GET 读取验证创建成功
  3. PATCH 更新 baseURL，检查返回 `name` 一致
  4. GET 验证 baseURL 已更新、protocol 未被清空
  5. DELETE 删除
  6. GET 验证资源已消失（404）
  7. finally 中兜底删除
- **预期结果**：完整 CRUD 生命周期正常，更新时未修改字段保持不变

---

### TC-PROVIDER-005：删除不存在的 Provider（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：DELETE
  - URL：`/web/config/providers/nonexistent-provider-to-delete-99999`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 发送 DELETE 请求
  2. 检查响应状态码为 404
- **预期结果**：返回 404 Not Found

---

### TC-PROVIDER-006：POST 同名 Provider 两次（重复冲突）

- **前置条件**：已登录；测试开始前先清理同名残留
- **请求信息**：
  - 方法：POST × 2
  - URL：`/web/config/providers`
  - Body（第一次）：
    ```json
    {
      "name": "api-test-web-provider-dup",
      "displayName": "Provider Dup V1",
      "protocol": "openai",
      "apiKey": "sk-test-key-v1",
      "baseURL": "https://v1.example.com"
    }
    ```
  - Body（第二次）：同名，baseURL 改为 `https://v2.example.com`
- **步骤**：
  1. 第一次 POST 创建成功
  2. 第二次 POST 同名配置
  3. 检查第二次响应状态码为 409
  4. GET 验证原有记录未被覆盖（baseURL 仍为 v1）
  5. finally 中删除
- **预期结果**：第二次创建 409 冲突，不产生隐式覆盖

---

### TC-PROVIDER-007：Provider DELETE 幂等性

- **前置条件**：已登录；测试开始前先清理同名残留
- **请求信息**：
  - 方法：POST + DELETE × 2
  - URL：`/web/config/providers`
- **步骤**：
  1. POST 创建 Provider `test-idempotent-delete-provider`
  2. 第一次 DELETE 成功
  3. 第二次 DELETE 同一 Provider
  4. 检查第二次 DELETE 返回 404
- **预期结果**：第二次删除返回 404，证明幂等性

---

## 模块：Provider Model（/web/config/providers/:providerId/models）

### TC-PROVIDER-008：为 Provider 添加模型（正向）

- **前置条件**：已登录；测试自建 Provider
- **请求信息**：
  - 方法：POST
  - URL：`/web/config/providers/{providerId}/models`
  - Body：
    ```json
    {
      "modelId": "test-model-add-001",
      "name": "Test Model Add"
    }
    ```
- **步骤**：
  1. POST 创建测试 Provider
  2. 发送 POST 添加模型
  3. 检查返回 `modelId` 与请求一致
  4. GET Provider 详情，检查 models 中同时含该行 `id` 与 `modelId`
  5. 清理：删除测试 Provider
- **预期结果**：模型添加成功，出现在 Provider 的 models 列表中

---

### TC-PROVIDER-009：更新 Provider 下的模型（正向）

- **前置条件**：已登录；测试自建 Provider
- **请求信息**：
  - 方法：POST（添加）+ PATCH（更新）
  - URL：`/web/config/providers/{providerId}/models/{modelRowId}`
  - Body（更新）：
    ```json
    {
      "name": "Updated Model Name"
    }
    ```
- **步骤**：
  1. 创建测试 Provider 并添加模型 `test-model-update-001`
  2. 按 modelId 解析出模型行 ID（GET 详情中匹配 `id` 或 `modelId`）
  3. PATCH 更新模型名称
  4. 回读详情，检查目标模型 `name == "Updated Model Name"`
  5. 清理：删除测试 Provider
- **预期结果**：模型更新成功

---

### TC-PROVIDER-010：删除 Provider 下的模型（正向）

- **前置条件**：已登录；测试自建 Provider
- **请求信息**：
  - 方法：POST（添加）+ DELETE（删除）
  - URL：`/web/config/providers/{providerId}/models/{modelRowId}`
- **步骤**：
  1. 创建测试 Provider 并添加模型 `test-model-delete-001`
  2. DELETE 删除该模型
  3. 回读详情，检查 models 中不再含该 `id`/`modelId`
  4. 清理：删除测试 Provider
- **预期结果**：模型删除成功

---

### TC-PROVIDER-011：获取 Provider 模型列表（从上游拉取）

- **前置条件**：已登录；存在当前用户可管理的 Provider（`access.actions` 含 `update`）
- **请求信息**：
  - 方法：POST
  - URL：`/web/config/providers/{providerId}/fetch-models`
  - Body：`{}`
- **步骤**：
  1. GET 列表，筛选 `access.actions` 含 `update` 的 Provider（只读系统网关会 403）
  2. 发送 POST fetch-models
  3. 检查响应为数组或对象，且模型项含 `id`/`modelId`/`name` 之一
  4. 上游不可用（502/503/504）时跳过
- **预期结果**：返回上游模型列表

---

### TC-PROVIDER-012：获取不存在 Provider 的模型列表（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/config/providers/nonexistent-provider-99999/fetch-models`
  - Body：`{}`
- **步骤**：
  1. 发送 POST 请求
  2. 检查响应状态码为 404（或 400）
- **预期结果**：返回未找到错误
