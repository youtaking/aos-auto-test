> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

# System Logs 模块 API 手工测试用例

## 模块：System Logs API（/api/system/logs）

认证方式：System API Key（Header: Authorization: Bearer <system-api-key>）

---

### TC-SYSLOG-001：获取日志文件列表（正向）

- **前置条件**：已配置 System API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/logs`
  - Headers：`Authorization: Bearer <system-api-key>`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 200
  3. 检查响应 `success` 为 `true`
  4. 检查 `data.files` 字段为数组
  5. 检查每个文件包含 `name`（string）、`size`（integer ≥ 0）字段
- **预期结果**：返回 `{success: true, data: {files: [{name: "xxx.log", size: 1024, ...}]}}`

---

### TC-SYSLOG-002：日志文件条目结构校验（正向）

- **前置条件**：已配置 System API Key，日志文件列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/logs`
  - Headers：`Authorization: Bearer <system-api-key>`
- **步骤**：
  1. 发送 GET 请求
  2. 取第一个文件条目
  3. 检查包含 `name`（string）、`size`（integer ≥ 0）字段
  4. 检查 `isErrorLog` 为 boolean（如存在）
  5. 检查 `modifiedAt` 为 ISO 8601 日期格式（如存在）
- **预期结果**：文件条目结构完整，字段类型正确

---

### TC-SYSLOG-003：基础搜索日志（正向）

- **前置条件**：已配置 System API Key，日志文件列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/logs/search?file=<文件名>`
  - Headers：`Authorization: Bearer <system-api-key>`
- **步骤**：
  1. 先调用日志文件列表获取第一个文件名
  2. 发送搜索请求
  3. 检查响应状态码为 200
  4. 检查 `data.entries` 为数组
  5. 检查 `data.totalMatches` 为整数 ≥ 0
  6. 检查 `data.file` 包含文件信息
- **预期结果**：返回搜索结果，包含 entries 数组和 totalMatches 计数

---

### TC-SYSLOG-004：带关键字搜索日志（正向）

- **前置条件**：已配置 System API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/logs/search?file=<文件名>&q=error&limit=10`
  - Headers：`Authorization: Bearer <system-api-key>`
- **步骤**：
  1. 发送带关键字和 limit 的搜索请求
  2. 检查响应状态码为 200
  3. 检查返回条目数 ≤ 10
  4. 检查 `totalMatches` ≥ 0
- **预期结果**：搜索结果被 limit 限制在 10 条以内

---

### TC-SYSLOG-005：仅搜索错误日志（正向）

- **前置条件**：已配置 System API Key，存在 error log 文件
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/logs/search?file=<error_log文件名>&errorOnly=true`
  - Headers：`Authorization: Bearer <system-api-key>`
- **步骤**：
  1. 找到 isErrorLog=true 的文件
  2. 发送 errorOnly=true 的搜索请求
  3. 检查响应状态码为 200
  4. 检查 entries 结构正确
- **预期结果**：仅返回错误级别的日志条目

---

### TC-SYSLOG-006：搜索缺少 file 参数（异常）

- **前置条件**：已配置 System API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/logs/search?q=test`（不传 file 参数）
  - Headers：`Authorization: Bearer <system-api-key>`
- **步骤**：
  1. 发送缺少 file 参数的搜索请求
  2. 检查响应状态码为 400 或 422
- **预期结果**：返回 400/422，提示 file 参数必填

---

### TC-SYSLOG-007：搜索不存在的文件（异常）

- **前置条件**：已配置 System API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/logs/search?file=nonexistent_log_file_xyz.log`
  - Headers：`Authorization: Bearer <system-api-key>`
- **步骤**：
  1. 发送搜索不存在文件的请求
  2. 检查响应状态码为 404
  3. 检查 `error.code` 为 `NOT_FOUND`
- **预期结果**：返回 404，提示日志文件不存在

---

### TC-SYSLOG-008：搜索空文件名（边界）

- **前置条件**：已配置 System API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/logs/search?file=`
  - Headers：`Authorization: Bearer <system-api-key>`
- **步骤**：
  1. 发送 file 为空字符串的搜索请求
  2. 检查响应状态码为 400 或 422
- **预期结果**：返回参数校验错误

---

### TC-SYSLOG-009：搜索 limit 超限（边界）

- **前置条件**：已配置 System API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/logs/search?file=<文件名>&limit=9999`（上限 1000）
  - Headers：`Authorization: Bearer <system-api-key>`
- **步骤**：
  1. 发送 limit=9999 的搜索请求
  2. 检查响应状态码为 400 或 422
- **预期结果**：返回参数校验错误，limit 超出最大值

---

### TC-SYSLOG-010：下载日志文件（正向）

- **前置条件**：已配置 System API Key，日志文件列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/logs/download?file=<文件名>`
  - Headers：`Authorization: Bearer <system-api-key>`
- **步骤**：
  1. 获取日志文件列表，取第一个文件名
  2. 发送下载请求
  3. 检查响应状态码为 200
  4. 检查 Content-Type 为 `text/plain`
  5. 检查响应体非空
- **预期结果**：返回日志文件内容（text/plain 流）

---

### TC-SYSLOG-011：下载不存在的文件（异常）

- **前置条件**：已配置 System API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/logs/download?file=nonexistent_file_xyz.log`
  - Headers：`Authorization: Bearer <system-api-key>`
- **步骤**：
  1. 发送下载不存在文件的请求
  2. 检查响应状态码为 404
- **预期结果**：返回 404

---

### TC-SYSLOG-012：下载空文件名（边界）

- **前置条件**：已配置 System API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/logs/download?file=`
  - Headers：`Authorization: Bearer <system-api-key>`
- **步骤**：
  1. 发送 file 为空字符串的下载请求
  2. 检查响应状态码为 400 或 422
- **预期结果**：返回参数校验错误

---

### TC-SYSLOG-013：无认证访问日志列表（权限）

- **前置条件**：无
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/logs`
  - Headers：无 Authorization
- **步骤**：
  1. 不携带认证信息发送请求
  2. 检查响应状态码为 401
- **预期结果**：返回 401 Unauthorized

---

### TC-SYSLOG-014：无认证搜索日志（权限）

- **前置条件**：无
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/logs/search?file=test.log`
  - Headers：无 Authorization
- **步骤**：
  1. 不携带认证信息发送搜索请求
  2. 检查响应状态码为 401
- **预期结果**：返回 401 Unauthorized

---

### TC-SYSLOG-015：无认证下载日志（权限）

- **前置条件**：无
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/logs/download?file=test.log`
  - Headers：无 Authorization
- **步骤**：
  1. 不携带认证信息发送下载请求
  2. 检查响应状态码为 401
- **预期结果**：返回 401 Unauthorized

---
