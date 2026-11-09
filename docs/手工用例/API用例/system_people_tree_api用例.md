> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

# System People Tree 模块 API 手工测试用例

## 模块：System People Tree API（/api/system/people-tree）

认证方式：System API Key（Header: Authorization: Bearer <system-api-key>）

---

### TC-SYSPT-001：获取组织人员层级（正向）

- **前置条件**：已配置 System API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/people-tree`
  - Headers：`Authorization: Bearer <system-api-key>`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 200
  3. 检查响应 `success` 为 `true`
  4. 检查 `data.organizations` 为数组
- **预期结果**：返回 `{success: true, data: {organizations: [...]}}`

---

### TC-SYSPT-002：组织结构校验（正向）

- **前置条件**：已配置 System API Key，组织列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/people-tree`
  - Headers：`Authorization: Bearer <system-api-key>`
- **步骤**：
  1. 发送 GET 请求
  2. 取第一个组织
  3. 检查包含 `id`（string）、`name`（string）、`slug`（string）、`users`（array）字段
- **预期结果**：组织条目结构完整

---

### TC-SYSPT-003：用户结构校验（正向）

- **前置条件**：已配置 System API Key，存在至少一个有用户的组织
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/people-tree`
  - Headers：`Authorization: Bearer <system-api-key>`
- **步骤**：
  1. 发送 GET 请求
  2. 找到至少一个有用户的组织
  3. 取第一个用户
  4. 检查包含 `id`、`name`、`email`、`agents`（array）字段
- **预期结果**：用户条目结构完整

---

### TC-SYSPT-004：智能体结构校验（正向）

- **前置条件**：已配置 System API Key，存在至少一个有 agent 的用户
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/people-tree`
  - Headers：`Authorization: Bearer <system-api-key>`
- **步骤**：
  1. 发送 GET 请求
  2. 找到至少一个有 agent 的用户
  3. 取第一个 agent
  4. 检查包含 `id`（string）、`name`（string）字段
  5. 检查 `description` 为 string 或 null（如存在）
  6. 检查 `machineId` 为 string 或 null（如存在）
- **预期结果**：agent 条目结构完整

---

### TC-SYSPT-005：无认证访问 people-tree（权限）

- **前置条件**：无
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/people-tree`
  - Headers：无 Authorization
- **步骤**：
  1. 不携带认证信息发送请求
  2. 检查响应状态码为 401
- **预期结果**：返回 401 Unauthorized

---
