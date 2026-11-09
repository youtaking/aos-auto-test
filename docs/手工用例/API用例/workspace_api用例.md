> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

# Workspace 模块 API 手工测试用例

## 模块：Workspace OpenAPI（/api/v1/environments/:environmentId/workspace/files，API Key 认证）

> 说明：响应为 `{success, data}` 信封；错误为 `{success:false, error:{code, message}}`。环境归属校验（404）先于文件参数校验（400）。

### TC-WORKSPACE-001：查询已有环境工作区文件树（正向，P1）

- **前置条件**：已配置 API Key，环境中至少有一个 environment
- **请求信息**：
  - 方法：GET
  - URL：`/api/v1/environments/{environmentId}/workspace/files`
  - Headers：`Authorization: Bearer <API Key>`
- **步骤**：
  1. 通过控制台接口获取第一个 environmentId
  2. 发送 GET 请求
  3. 校验响应结构含 `environmentId`、`paths`
  4. 检查 `environmentId` 与请求一致
  5. 检查 `paths` 为数组
- **预期结果**：返回 200 `{success:true, data:{environmentId, paths:[...]}}`

---

### TC-WORKSPACE-002：查询不存在环境的工作区（异常响应，P2）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/v1/environments/nonexistent-env-id-99999/workspace/files`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 404
  3. 检查 `success` 为 `false`
  4. 检查 `error.code` 为 `NOT_FOUND`
- **预期结果**：返回 404，错误码 `NOT_FOUND`

---

### TC-WORKSPACE-003：上传到不存在的环境（异常响应，P2）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：POST
  - URL：`/api/v1/environments/nonexistent-env-id-99999/workspace/files`
  - Body：multipart/form-data，`files=@test.txt`
- **步骤**：
  1. 发送 POST 请求
  2. 检查响应状态码为 404
  3. 检查 `error.code` 为 `NOT_FOUND`
- **预期结果**：返回 404，错误码 `NOT_FOUND`

---

### TC-WORKSPACE-004：上传不含 files 字段（必填参数缺失，P2）

- **前置条件**：已配置 API Key，环境中至少有一个 environment
- **请求信息**：
  - 方法：POST
  - URL：`/api/v1/environments/{environmentId}/workspace/files`
  - Body：multipart/form-data，仅 `path=user`，不带 `files`
- **步骤**：
  1. 发送 POST 请求
  2. 检查响应状态码为 400
  3. 检查 `error.code` 为 `VALIDATION_ERROR`
  4. 检查 `error.message` 包含 `files`
- **预期结果**：返回 400，错误码 `VALIDATION_ERROR`，提示缺少 files

---

### TC-WORKSPACE-005：下载缺少 path 查询参数（必填参数缺失，P2）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/v1/environments/fake-env-id/workspace/files/download`（不带 `path`）
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 400
  3. 检查 `error.code` 为 `VALIDATION_ERROR`
- **预期结果**：返回 400，错误码 `VALIDATION_ERROR`

---

### TC-WORKSPACE-006：下载不存在的文件（异常响应，P2）

- **前置条件**：已配置 API Key，环境中至少有一个 environment
- **请求信息**：
  - 方法：GET
  - URL：`/api/v1/environments/{environmentId}/workspace/files/download?path=nonexistent-file-99999.txt`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 404
  3. 检查 `error.code` 为 `NOT_FOUND`
- **预期结果**：返回 404，错误码 `NOT_FOUND`

---

### TC-WORKSPACE-007：上传使用越界 path（参数边界，P2）

- **前置条件**：已配置 API Key，环境中至少有一个 environment
- **请求信息**：
  - 方法：POST
  - URL：`/api/v1/environments/{environmentId}/workspace/files`
  - Body：multipart/form-data，`files=@test.txt`，`path=../escape`
- **步骤**：
  1. 发送 POST 请求
  2. 检查响应状态码为 400
  3. 检查 `error.code` 为 `VALIDATION_ERROR`
- **预期结果**：返回 400，错误码 `VALIDATION_ERROR`（路径校验先于写入）
