> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

# Instance Connect 模块 API 手工测试用例

## 模块：Instance Connect OpenAPI（/api/v1/agents/:agentId/instances/connect，API Key 认证）

> 说明：响应为 `{success, data}` 信封；错误为 `{success:false, error:{code, message}}`。`instanceId` 可选，传入时必须为 `inst_` 前缀。

### TC-INSTANCECONNECT-001：连接不存在的 Agent（异常响应，P2）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：POST
  - URL：`/api/v1/agents/nonexistent-agent-id-99999/instances/connect`
  - Headers：`Authorization: Bearer <API Key>`
  - Body：`{}`
- **步骤**：
  1. 发送 POST 请求
  2. 检查响应状态码为 404
  3. 检查 `error.code` 为 `NOT_FOUND`
- **预期结果**：返回 404，错误码 `NOT_FOUND`

---

### TC-INSTANCECONNECT-002：instanceId 格式非法（参数边界，P2）

- **前置条件**：已配置 API Key，Agent 列表非空
- **请求信息**：
  - 方法：POST
  - URL：`/api/v1/agents/{agentId}/instances/connect`
  - Body：`{"instanceId": "bad-id"}`
- **步骤**：
  1. 获取 Agent 列表取第一个 ID
  2. 发送 POST 请求
  3. 检查响应状态码为 400
  4. 检查 `error.code` 为 `VALIDATION_ERROR`
- **预期结果**：返回 400，错误码 `VALIDATION_ERROR`（instanceId 必须以 `inst_` 开头）

---

### TC-INSTANCECONNECT-003：连接 Agent 实例（正向，P2）

- **前置条件**：已配置 API Key，Agent 列表非空，Agent 已绑定可用运行环境
- **请求信息**：
  - 方法：POST
  - URL：`/api/v1/agents/{agentId}/instances/connect`
  - Body：`{}`
- **步骤**：
  1. 获取 Agent 列表取第一个 ID
  2. POST 连接实例
  3. 校验响应结构含 `agentConfigId/environmentId/instanceId/status/runtimeGeneration/relay`
  4. 检查 `status` 为 `running`
  5. 检查 `relay.wsUrl` 为字符串
- **预期结果**：返回 200 `{success:true, data:{...}}`；Agent 无机器/环境不可用（404/500/503/超时）时跳过
