> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

# Workflow Execute 模块 API 手工测试用例

## 模块：Workflow OpenAPI（/api/v1/workflows，API Key 认证）

> 说明：响应为 `{success, data}` 信封；错误为 `{success:false, error:{code, message}}`。该路径下 Elysia schema 校验失败返回 **422** VALIDATION_ERROR（而非 400）。body：`{inputs?, mode: sync|async, version?, timeout?}`。

### TC-WORKFLOW-001：执行不存在的 workflow（异常响应，P2）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：POST
  - URL：`/api/v1/workflows/nonexistent-workflow-id-99999/execute`
  - Body：`{"inputs": {}}`
- **步骤**：
  1. 发送 POST 请求
  2. 检查响应状态码为 404
  3. 检查 `success` 为 `false`、`error.code` 为 `NOT_FOUND`
- **预期结果**：返回 404 `NOT_FOUND`

---

### TC-WORKFLOW-002：执行 workflow 带错误 inputs（业务规则，P2）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：POST
  - URL：`/api/v1/workflows/nonexistent-workflow-id-99999/execute`
  - Body：
    ```json
    {
      "inputs": {"invalid_key": "invalid_value"},
      "mode": "sync"
    }
    ```
- **步骤**：
  1. 发送带非法 inputs 的请求
  2. 检查响应状态码为 404
  3. 检查 `error.code` 为 `NOT_FOUND`（资源不存在优先于 inputs 校验）
- **预期结果**：返回 404 `NOT_FOUND`

---

### TC-WORKFLOW-003：执行 workflow 带空 body（参数边界，P2）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：POST
  - URL：`/api/v1/workflows/fake-workflow-id/execute`
  - Body：`{}`（mode/timeout 有默认值）
- **步骤**：
  1. 发送空 body 请求
  2. 检查响应状态码为 404
  3. 检查 `error.code` 为 `NOT_FOUND`
- **预期结果**：返回 404 `NOT_FOUND`

---

### TC-WORKFLOW-004：非法 mode 值（类型错误/枚举异常，P2）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：POST
  - URL：`/api/v1/workflows/fake-workflow-id/execute`
  - Body：`{"mode": "invalid-mode"}`
- **步骤**：
  1. 发送非法 mode 的请求
  2. 检查响应状态码为 422
  3. 检查 `error.code` 为 `VALIDATION_ERROR`
- **预期结果**：返回 422 `VALIDATION_ERROR`

---

### TC-WORKFLOW-005：真实 workflow + 错误 inputs（业务规则，P2）

- **前置条件**：已配置 API Key，工作流定义列表非空
- **请求信息**：
  - 方法：POST
  - URL：`/api/v1/workflows/{real_workflow_id}/execute`
  - Body：
    ```json
    {
      "inputs": {"__invalid_key__": "__invalid_value__"},
      "mode": "sync"
    }
    ```
- **步骤**：
  1. 通过控制台接口获取真实工作流定义 ID
  2. 用非法 inputs 执行
  3. 成功时校验 `runId/status/version` 结构
  4. 异常时只接受 404/422 客户端错误
- **预期结果**：返回 200 执行结果（`status` 为 SUCCESS/FAILED/TIMEOUT），或 404/422
