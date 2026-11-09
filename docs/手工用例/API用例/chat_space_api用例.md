# Chat Spaces 模块 API 手工测试用例

> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

## 模块：Chat Spaces Web API

说明：会话分组没有删除分组的端点，为避免遗留数据，本模块只覆盖只读、参数校验与幂等摘除，不创建合法分组。

### TC-CHATSPACE-001：获取实例下的会话分组（正向）

- **前置条件**：已登录；环境下有可用实例（instanceUid）
- **请求信息**：
  - 方法：GET
  - URL：`/web/chat-spaces?instanceUid=<instanceUid>`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 200
  3. 检查 `success` 为 `true`
  4. 检查 `data.spaces` 为数组，元素含 `id`、`name`、`sessionIds`、`instanceUid`
- **预期结果**：返回分组数组，且 `instanceUid` 与请求一致

---

### TC-CHATSPACE-002：查询不存在实例的会话分组（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/chat-spaces?instanceUid=nonexistent-instance-uid-99999`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 404
  3. 检查 `error.code` 为 `not_found`
- **预期结果**：返回 404，提示实例不存在

---

### TC-CHATSPACE-003：创建分组缺少 instanceUid（必填缺失）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/chat-spaces`
  - Body：`{"name": "api-test-space"}`（不传 instanceUid）
- **步骤**：
  1. 发送 POST 请求
  2. 检查响应状态码为 400
  3. 检查 `error.type` 为 `VALIDATION_ERROR`
  4. 检查 `error.message` 包含 `instanceUid`
- **预期结果**：返回 400，且不落库

---

### TC-CHATSPACE-004：创建分组名称为空（边界）

- **前置条件**：已登录；环境下有可用实例
- **请求信息**：
  - 方法：POST
  - URL：`/web/chat-spaces`
  - Body：`{"instanceUid": "<instanceUid>", "name": ""}`
- **步骤**：
  1. 发送 POST 请求
  2. 检查响应状态码为 400
  3. 检查 `error.code` 为 `invalid_name`
  4. 检查 `error.message` 包含 `1-100`
- **预期结果**：返回 400，提示名称长度需为 1-100

---

### TC-CHATSPACE-005：创建分组名称超长（边界）

- **前置条件**：已登录；环境下有可用实例
- **请求信息**：
  - 方法：POST
  - URL：`/web/chat-spaces`
  - Body：`{"instanceUid": "<instanceUid>", "name": "101 个 x 字符"}`
- **步骤**：
  1. 发送 POST 请求
  2. 检查响应状态码为 400
  3. 检查 `error.code` 为 `invalid_name`
- **预期结果**：返回 400，且不落库

---

### TC-CHATSPACE-006：重命名不存在的分组（异常）

- **前置条件**：已登录；环境下有可用实例
- **请求信息**：
  - 方法：PATCH
  - URL：`/web/chat-spaces/nonexistent-space-id-99999?instanceUid=<instanceUid>`
  - Body：`{"name": "renamed-by-api-test"}`
- **步骤**：
  1. 发送 PATCH 请求
  2. 检查响应状态码为 404
  3. 检查 `error.code` 为 `not_found`
- **预期结果**：返回 404

---

### TC-CHATSPACE-007：把会话移入不存在的分组（异常）

- **前置条件**：已登录；环境下有可用实例
- **请求信息**：
  - 方法：PUT
  - URL：`/web/chat-spaces/nonexistent-space-id-99999/sessions/nonexistent-session-id-99999?instanceUid=<instanceUid>`
- **步骤**：
  1. 发送 PUT 请求
  2. 检查响应状态码为 404
  3. 检查 `error.code` 为 `not_found`
- **预期结果**：返回 404

---

### TC-CHATSPACE-008：摘除未归属分组的会话（幂等）

- **前置条件**：已登录；环境下有可用实例
- **请求信息**：
  - 方法：DELETE
  - URL：`/web/chat-spaces/sessions/nonexistent-session-id-99999?instanceUid=<instanceUid>`
- **步骤**：
  1. 发送 DELETE 请求
  2. 检查响应状态码为 200
  3. 检查 `data` 等于 `{"space": null}`
- **预期结果**：幂等成功，会话不被任何分组包含
