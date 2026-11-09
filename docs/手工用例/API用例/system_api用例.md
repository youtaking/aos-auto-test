> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

# System API 模块手工测试用例

## 模块：System User API

> 注：需要 System API Key（RCS_SYSTEM_API_KEYS）认证。

### TC-SYSTEM-001：获取用户列表（正向）

- **前置条件**：已配置 System API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/users?page=1&pageSize=10`
  - Headers：`Authorization: Bearer {system_api_key}`
- **步骤**：
  1. 发送 GET 请求
  2. 检查 `items` 为数组
  3. 检查 `total` >= 0
- **预期结果**：返回 `{items: [...], total: N, page: 1, pageSize: 10}`

---

### TC-SYSTEM-002：获取用户详情（正向）

- **前置条件**：已配置 System API Key，用户列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/users/{user_id}`
- **步骤**：
  1. 列表接口取第一个 ID
  2. GET 查详情
  3. 检查 `id`、`name`、`email` 字段存在
- **预期结果**：返回用户详情

---

### TC-SYSTEM-003：创建并删除用户（正向 CRUD）

- **前置条件**：已配置 System API Key
- **请求信息**：
  - 方法：POST（创建）+ GET（验证）+ DELETE（删除）
  - Body（创建）：
    ```json
    {
      "email": "sys-test-{random}@test.local",
      "name": "System API Test User",
      "password": "TestPass12345678"
    }
    ```
- **步骤**：
  1. POST 创建用户
  2. 检查 email 和 name 与请求一致
  3. GET 验证创建成功
  4. DELETE 清理
- **预期结果**：完整创建→验证→删除正常

---

### TC-SYSTEM-004：获取不存在的用户（异常）

- **前置条件**：已配置 System API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/users/nonexistent-user-{random}`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 404
- **预期结果**：返回 404 Not Found

---

### TC-SYSTEM-005：重置用户密码（正向）

- **前置条件**：已配置 System API Key
- **请求信息**：
  - 方法：POST
  - URL：`/api/system/users/reset-password`
  - Body：
    ```json
    {
      "userId": "{自建用户ID}",
      "password": "NewPass87654321"
    }
    ```
- **步骤**：
  1. 创建测试用户
  2. POST 重置密码
  3. 检查 `updated` 为 `true`
  4. 清理：删除测试用户
- **预期结果**：返回 `{updated: true}`

---

### TC-SYSTEM-006：获取用户 API Key 列表（正向）

- **前置条件**：已配置 System API Key，用户列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/users/{user_id}/api-keys?page=1&pageSize=10`
- **步骤**：
  1. 列表接口取第一个用户 ID
  2. GET 获取用户 API Key 列表
  3. 检查 `items` 为数组
- **预期结果**：返回 API Key 列表

---

### TC-SYSTEM-007：获取用户所属组织列表（正向）

- **前置条件**：已配置 System API Key，用户列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/users/{user_id}/organizations?page=1&pageSize=10`
- **步骤**：
  1. 列表接口取第一个用户 ID
  2. GET 获取用户组织列表
  3. 检查 `items` 为数组
- **预期结果**：返回组织列表

---

## 模块：System Organization API

### TC-SYSTEM-008：获取组织列表（正向）

- **前置条件**：已配置 System API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/organizations?page=1&pageSize=10`
- **步骤**：
  1. 发送 GET 请求
  2. 检查 `items` 为数组，`total` >= 0
- **预期结果**：返回分页结构

---

### TC-SYSTEM-009：获取组织详情（正向）

- **前置条件**：已配置 System API Key，组织列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/organizations/{org_id}`
- **步骤**：
  1. 列表接口取第一个 ID
  2. GET 查详情
  3. 检查 `id`、`name`、`members` 字段存在
- **预期结果**：返回组织详情，包含 members 数组

---

### TC-SYSTEM-010：创建并删除组织（正向 CRUD）

- **前置条件**：已配置 System API Key
- **请求信息**：
  - 方法：POST（创建）+ GET + DELETE
  - Body（创建）：
    ```json
    {
      "name": "System API Test Org",
      "slug": "sys-test-org-{random}"
    }
    ```
- **步骤**：
  1. POST 创建组织
  2. GET 验证
  3. DELETE 清理
- **预期结果**：完整创建→验证→删除正常

---

### TC-SYSTEM-011：获取不存在的组织（异常）

- **前置条件**：已配置 System API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/organizations/nonexistent-org-{random}`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 404
- **预期结果**：返回 404

---

### TC-SYSTEM-012：添加组织成员（正向）

- **前置条件**：已配置 System API Key
- **请求信息**：
  - 方法：POST
  - URL：`/api/system/organizations/{org_id}/members`
  - Body：
    ```json
    {
      "userId": "{自建用户ID}",
      "role": "member"
    }
    ```
- **步骤**：
  1. 创建测试组织 + 测试用户
  2. POST 添加成员
  3. 检查返回 userId、organizationId、role 一致
  4. GET 组织详情验证成员在列表中
  5. 清理：删除组织和用户
- **预期结果**：成员添加成功，出现在组织 members 列表中

---

## 模块：System API Key API

### TC-SYSTEM-013：创建并删除 API Key（正向 CRUD）

- **前置条件**：已配置 System API Key
- **请求信息**：
  - 方法：POST（创建）+ DELETE
  - Body（创建）：
    ```json
    {
      "userId": "{自建用户ID}",
      "organizationId": "{有效组织ID}",
      "role": "member",
      "name": "system-api-test-key"
    }
    ```
- **步骤**：
  1. 创建测试用户
  2. 获取可用组织 ID
  3. POST 创建 API Key
  4. 检查返回包含 `key` 字段（明文）
  5. DELETE 删除
  6. 检查 `deleted` 为 `true`
  7. 清理：删除测试用户
- **预期结果**：创建返回明文 key，删除成功

---

### TC-SYSTEM-014：删除不存在的 API Key（异常）

- **前置条件**：已配置 System API Key
- **请求信息**：
  - 方法：DELETE
  - URL：`/api/system/api-keys/nonexistent-key-{random}`
- **步骤**：
  1. 发送 DELETE 请求
  2. 检查响应状态码为 404
- **预期结果**：返回 404

---

## 模块：System Channel API

### TC-SYSTEM-015：获取渠道接入总览（正向）

- **前置条件**：已配置 System API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/channels`
  - Headers：`Authorization: Bearer {system_api_key}`
- **步骤**：
  1. 发送 GET 请求
  2. 检查 `status.reachable` 为布尔值
  3. 检查 `organizations` 为数组
  4. 检查每个元素包含 `id`（字符串）、`name`（字符串）、`users`（数组）
- **预期结果**：返回 `{status: {reachable, version, edition, wizardStatus}, organizations: [{id, name, users}]}`
