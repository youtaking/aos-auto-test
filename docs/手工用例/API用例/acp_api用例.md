> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

# ACP 模块 API 手工测试用例

## 模块：ACP Web API

### TC-ACP-001：获取 ACP Agent 列表（正向）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/acp/agents`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 200
  3. 检查返回为数组
  4. 如有数据，检查每项包含 `id`、`status`、`max_sessions`、`created_at`
  5. 检查 `status` 为 `online` 或 `offline`
- **预期结果**：返回 ACP Agent 数组（无 `{success, data}` 包装）

---

### TC-ACP-002：ACP Agent 列表项字段校验（正向）

- **前置条件**：已登录，ACP Agent 列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/acp/agents`
- **步骤**：
  1. 发送 GET 请求
  2. 取第一个 Agent 对象
  3. 检查 `id` 为字符串
  4. 检查 `status` 为 `online` 或 `offline`
  5. 检查 `max_sessions` 为数字
  6. 检查 `created_at` 为数字（秒级时间戳）
  7. 检查 `agent_name` 为字符串或 null
  8. 检查 `last_seen_at` 为数字或 null
- **预期结果**：所有字段类型正确

---

### TC-ACP-003：无认证获取 ACP Agent 列表（权限）

- **前置条件**：未登录
- **请求信息**：
  - 方法：GET
  - URL：`/acp/agents`
  - Headers：无 Cookie
- **步骤**：
  1. 不携带 session cookie 发送 GET 请求
  2. 检查响应状态码为 401/403/302
- **预期结果**：未认证请求被拒绝
