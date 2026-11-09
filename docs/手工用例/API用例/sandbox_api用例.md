> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

# Sandbox 模块 API 手工测试用例

## 模块：Sandbox Pool API（System API Key 认证）

> 注：sandbox 端点需要 System API Key（RCS_SYSTEM_API_KEYS），普通 API Key 可能无权访问。

### TC-SANDBOX-001：获取沙盒池列表（正向）

- **前置条件**：已配置 System API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/sandbox-pools`
  - Headers：`Authorization: Bearer {api_key}`
- **步骤**：
  1. 发送 GET 请求
  2. 检查返回为数组或分页结构
  3. 401/403/503 时 skip
- **预期结果**：返回沙盒池列表

---

### TC-SANDBOX-002：获取沙盒池详情（正向）

- **前置条件**：已配置 System API Key，沙盒池列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/sandbox-pools/{pool_id}`
- **步骤**：
  1. 列表接口取第一个 ID
  2. GET 查详情
  3. 检查返回为 dict
- **预期结果**：返回沙盒池详情

---

### TC-SANDBOX-003：获取不存在的沙盒池（异常）

- **前置条件**：已配置 System API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/sandbox-pools/nonexistent-pool-id-99999`
- **步骤**：
  1. 发送 GET 请求
  2. 检查返回 404/400
- **预期结果**：返回错误

---

## 模块：Sandbox Instance API

### TC-SANDBOX-004：获取沙盒实例列表（正向）

- **前置条件**：已配置 System API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/sandbox-instances`
- **步骤**：
  1. 发送 GET 请求
  2. 检查返回为数组或分页结构
- **预期结果**：返回沙盒实例列表

---

### TC-SANDBOX-005：获取沙盒实例详情（正向）

- **前置条件**：已配置 System API Key，实例列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/sandbox-instances/{instance_id}`
- **步骤**：
  1. 列表接口取第一个 ID
  2. GET 查详情
  3. 检查返回为 dict
- **预期结果**：返回沙盒实例详情

---

### TC-SANDBOX-006：获取不存在的沙盒实例（异常）

- **前置条件**：已配置 System API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/sandbox-instances/nonexistent-instance-id-99999`
- **步骤**：
  1. 发送 GET 请求
  2. 检查返回 404/400
- **预期结果**：返回错误
