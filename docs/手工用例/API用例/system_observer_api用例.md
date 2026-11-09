> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

# System Observer 模块 API 手工测试用例

## 模块：System Observer API（/api/system/observer）

认证方式：System API Key（Header: Authorization: Bearer <system-api-key>）

---

### TC-SYSOBS-001：获取 ACP 链接观察树（正向）

- **前置条件**：已配置 System API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/observer/acp-link`
  - Headers：`Authorization: Bearer <system-api-key>`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 200
  3. 检查响应 `success` 为 `true`
  4. 检查 `data.kind` 为 `"acp-link"`
  5. 检查 `data.total` 为整数 ≥ 0
  6. 检查 `data.generatedAt` 为 ISO 8601 格式字符串
- **预期结果**：返回完整的 ACP 链接观察视图

---

### TC-SYSOBS-002：观察树结构校验（正向）

- **前置条件**：已配置 System API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/observer/acp-link`
  - Headers：`Authorization: Bearer <system-api-key>`
- **步骤**：
  1. 发送 GET 请求
  2. 检查 `data.trees` 对象存在
  3. 检查 `data.trees.byEntity` 为数组（machine 树）
  4. 检查 `data.trees.byOrg` 为数组（归属树）
- **预期结果**：trees 包含 byEntity 和 byOrg 两棵子树

---

### TC-SYSOBS-003：一致性汇总校验（正向）

- **前置条件**：已配置 System API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/observer/acp-link`
  - Headers：`Authorization: Bearer <system-api-key>`
- **步骤**：
  1. 发送 GET 请求
  2. 检查 `data.integrity` 对象存在
  3. 检查 `integrity.checked` 为整数 ≥ 0
  4. 检查 `integrity.mismatched` 为整数 ≥ 0
  5. 检查 `integrity.mismatchedItems` 为数组
- **预期结果**：integrity 汇总字段完整

---

### TC-SYSOBS-004：名称字典校验（正向）

- **前置条件**：已配置 System API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/observer/acp-link`
  - Headers：`Authorization: Bearer <system-api-key>`
- **步骤**：
  1. 发送 GET 请求
  2. 检查 `data.names` 为对象
  3. 检查包含 `organizationId`、`userId`、`agentConfigId`、`instanceId`、`machineId` 子对象
- **预期结果**：names 字典包含各角色 id→名称映射

---

### TC-SYSOBS-005：无认证访问 observer（权限）

- **前置条件**：无
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/observer/acp-link`
  - Headers：无 Authorization
- **步骤**：
  1. 不携带认证信息发送请求
  2. 检查响应状态码为 401
- **预期结果**：返回 401 Unauthorized

---
