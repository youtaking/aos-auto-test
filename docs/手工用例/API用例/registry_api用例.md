> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

# Registry 模块 API 手工测试用例

## 模块：Registry Web API

### TC-REGISTRY-001：获取机器列表（正向）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/registry/machines`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 发送 GET 请求
  2. 检查 `items` 为数组
  3. 检查 `total` 存在
- **预期结果**：返回 `{items: [...], total: N}`

---

### TC-REGISTRY-002：获取机器详情（正向）

- **前置条件**：已登录，机器列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/web/registry/machines/{machine_id}`
- **步骤**：
  1. 列表接口取第一个 ID
  2. GET 查详情
  3. 检查 `id` 与请求一致
  4. 检查 `recentEvents` 字段存在
- **预期结果**：返回机器详情，包含 recentEvents

---

### TC-REGISTRY-003：获取机器事件列表（正向）

- **前置条件**：已登录，机器列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/web/registry/machines/{machine_id}/events`
- **步骤**：
  1. 列表接口取第一个 ID
  2. GET 获取事件列表
  3. 检查 `items` 为数组
- **预期结果**：返回 `{items: [...]}`

---

### TC-REGISTRY-004：获取不存在的机器（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/registry/machines/nonexistent-machine-id-99999`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 404
- **预期结果**：返回 404 Not Found

---

### TC-REGISTRY-005：获取机器连接参数（正向）

- **前置条件**：已登录，机器列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/web/registry/machines/{machine_id}/connection-parameters`
- **步骤**：
  1. 列表接口取第一个 ID
  2. 发送 GET 请求
  3. 检查 `data.machineId` 与请求 ID 一致
  4. 检查 `data.agentType` 为非空字符串
  5. 检查 `data.rcsUrl` 以 ws://、wss://、http:// 或 https:// 开头
- **预期结果**：返回 `{machineId, agentType, rcsUrl}`

---

### TC-REGISTRY-006：下载 ACP Runtime 使用非法平台（边界）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/registry/acp-runtime/bogus-platform`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 400
  3. 检查 `error.type` 为 `VALIDATION_ERROR`
  4. 检查 `error.message` 包含 `platform`
- **预期结果**：返回 400，提示平台枚举值

---

### TC-REGISTRY-007：下载 linux-x64 ACP Runtime（正向）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/registry/acp-runtime/linux-x64`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 200
  3. 检查响应体非空
  4. 检查前四字节为 ELF 魔数 `\x7fELF`
- **预期结果**：返回 ELF 二进制

---

### TC-REGISTRY-008：获取 ACP agent 列表（正向）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/acp/agents`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 200
  3. 检查响应为数组
  4. 检查每个元素含字符串 `id`、`status`
- **预期结果**：返回 ACP agent 列表
