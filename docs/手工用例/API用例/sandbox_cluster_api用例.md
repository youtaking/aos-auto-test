# Sandbox Cluster 模块 API 手工测试用例

> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

说明：创建/更新/删除属于集群管理动作，本模块只覆盖只读查询、不存在资源与必填校验（校验失败不落库）。

## 模块：Sandbox Cluster System API

认证方式：`Authorization: Bearer <System API Key>`；响应为裸数据。

### TC-SANDCLUSTER-001：获取沙盒池列表（正向）

- **前置条件**：配置有效 System API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/sandbox-cluster/pools`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 200
  3. 检查响应为数组
  4. 检查每个元素含字符串 `id`、`name`、`status`
- **预期结果**：返回沙盒池列表

---

### TC-SANDCLUSTER-002：获取沙盒池详情（正向）

- **前置条件**：沙盒池列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/sandbox-cluster/pools/<poolId>`
- **步骤**：
  1. 先调列表接口取首个 `id`
  2. 发送 GET 详情请求
  3. 检查 `id` 与请求一致
  4. 检查 `capacitySandboxes` 为整数
- **预期结果**：返回池详情

---

### TC-SANDCLUSTER-003：获取沙盒服务器列表（正向）

- **前置条件**：配置有效 System API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/sandbox-cluster/servers`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应为数组
  3. 检查每个元素含字符串 `id`、`poolId`、`status`
- **预期结果**：返回服务器列表

---

### TC-SANDCLUSTER-004：获取沙盒服务器详情（正向）

- **前置条件**：服务器列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/sandbox-cluster/servers/<serverId>`
- **步骤**：
  1. 先调列表接口取首个 `id`
  2. 发送 GET 详情请求
  3. 检查 `id` 与请求一致
  4. 检查 `baseUrl` 为字符串
- **预期结果**：返回服务器详情

---

### TC-SANDCLUSTER-005：列出服务器上的沙盒（正向）

- **前置条件**：服务器列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/sandbox-server/servers/<serverId>/sandboxes?page=1&pageSize=10`
- **步骤**：
  1. 先调服务器列表取首个 `id`
  2. 发送 GET 请求
  3. 检查 `items` 为数组
- **预期结果**：返回该服务器上的沙盒列表

---

### TC-SANDCLUSTER-006：获取不存在的沙盒池（异常）

- **前置条件**：配置有效 System API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/sandbox-cluster/pools/nonexistent-pool-id-99999`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 404
  3. 检查 `error.code` 为 `NOT_FOUND`
- **预期结果**：返回 404

---

### TC-SANDCLUSTER-007：获取不存在的沙盒服务器（异常）

- **前置条件**：配置有效 System API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/sandbox-cluster/servers/nonexistent-server-id-99999`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 404
  3. 检查 `error.code` 为 `NOT_FOUND`
- **预期结果**：返回 404

---

### TC-SANDCLUSTER-008：列出不存在服务器的沙盒（异常）

- **前置条件**：配置有效 System API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/sandbox-server/servers/nonexistent-server-id-99999/sandboxes`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 404
  3. 检查 `error.code` 为 `NOT_FOUND`
- **预期结果**：返回 404

---

### TC-SANDCLUSTER-009：创建沙盒池缺少 id（必填缺失）

- **前置条件**：配置有效 System API Key
- **请求信息**：
  - 方法：POST
  - URL：`/api/system/sandbox-cluster/pools`
  - Body：`{}`
- **步骤**：
  1. 发送 POST 请求
  2. 检查响应状态码为 400
  3. 检查 `error.type` 为 `VALIDATION_ERROR`
  4. 检查 `error.message` 包含 `id`
- **预期结果**：返回 400，且不落库

---

### TC-SANDCLUSTER-010：创建沙盒服务器缺少 id（必填缺失）

- **前置条件**：配置有效 System API Key
- **请求信息**：
  - 方法：POST
  - URL：`/api/system/sandbox-cluster/servers`
  - Body：`{}`
- **步骤**：
  1. 发送 POST 请求
  2. 检查响应状态码为 400
  3. 检查 `error.type` 为 `VALIDATION_ERROR`
  4. 检查 `error.message` 包含 `id`
- **预期结果**：返回 400，且不落库
