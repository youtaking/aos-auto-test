> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

# Channel 模块 API 手工测试用例

## 模块：Channel Web API（/web/channels/langbot/*）

### TC-CHANNEL-001：探测 LangBot 服务（正向）

- **前置条件**：已登录，有访问权限
- **请求信息**：
  - 方法：GET
  - URL：`/web/channels/langbot/status`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 200
  3. 检查响应 `data.reachable` 为布尔值
  4. 检查 `data.version` / `data.edition` / `data.wizardStatus` 字段存在
- **预期结果**：返回 `{success: true, data: {reachable, version, edition, wizardStatus}}`

---

### TC-CHANNEL-002：获取 Bot 列表（正向）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/channels/langbot/bots`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 200
  3. 检查 `data` 为数组
  4. 检查每项含 `name`、`boundRouteCount`、`missingInLangbot`
  5. 检查每项不包含 `config`（写侧凭据不回显）
- **预期结果**：返回 Bot 数组，且不泄露 `config`

---

### TC-CHANNEL-003：获取通道路由列表（正向）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/channels/langbot/routes`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 200
  3. 检查每项含 `id`、`channelId`、`chatType`、`agentConfigId`、`enabled`、`instances`
- **预期结果**：返回路由数组

---

### TC-CHANNEL-004：获取 IM 会话映射（正向）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/channels/langbot/conversations`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应结构为 `{items, total, page, pageSize}`
  3. 检查 `page >= 1`、`pageSize >= 1`、`total >= len(items)`
  4. 检查每条 `sessionId` 已脱敏（含 `***` 或 `rcs_…`）
- **预期结果**：分页结构正确，sessionId 不回显原始 ACP 会话 ID

---

### TC-CHANNEL-005：会话映射分页参数生效（边界）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/channels/langbot/conversations?page=1&pageSize=1`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 200
  3. 检查 `page == 1`、`pageSize == 1`
  4. 检查 `len(items) <= 1`
- **预期结果**：分页参数生效

---

### TC-CHANNEL-006：创建路由缺少必填字段（必填参数缺失）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/channels/langbot/routes`
  - Body：`{}`
- **步骤**：
  1. 发送 POST 请求
  2. 检查响应状态码为 400
  3. 检查 `error.type == "VALIDATION_ERROR"`（或 `error.code == "INVALID_INPUT"`）
  4. 检查错误信息包含 `channelId`
- **预期结果**：400 参数校验错误，提示 channelId 必填

---

### TC-CHANNEL-007：创建路由 chatType 非法枚举（参数边界）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/channels/langbot/routes`
  - Body：
    ```json
    {
      "channelId": "00000000-0000-4000-8000-000000000000",
      "chatType": "invalid-type",
      "agentConfigId": "00000000-0000-4000-8000-000000000000"
    }
    ```
- **步骤**：
  1. 发送 POST 请求
  2. 检查响应状态码为 400
  3. 检查错误信息包含 `chatType`，枚举仅允许 `person` / `group`
- **预期结果**：400 参数校验错误

---

### TC-CHANNEL-008：创建路由使用不存在的通道（异常响应）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/channels/langbot/routes`
  - Body：
    ```json
    {
      "channelId": "00000000-0000-4000-8000-000000000000",
      "chatType": "person",
      "chatId": "pytest-nonexistent",
      "agentConfigId": "00000000-0000-4000-8000-000000000000"
    }
    ```
- **步骤**：
  1. 发送 POST 请求
  2. 检查响应状态码为 404
  3. 检查 `success == false`、`error.code == "NOT_FOUND"`
- **预期结果**：404 通道不存在

---

### TC-CHANNEL-009：读取不存在的 Bot（异常响应）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/channels/langbot/bots/00000000-0000-4000-8000-000000000000`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 404
  3. 检查 `error.code == "NOT_FOUND"`
- **预期结果**：404 未找到

---

### TC-CHANNEL-010：更新不存在的路由（异常响应）

- **前置条件**：已登录
- **请求信息**：
  - 方法：PATCH
  - URL：`/web/channels/langbot/routes/00000000-0000-4000-8000-000000000000`
  - Body：`{"enabled": false}`
- **步骤**：
  1. 发送 PATCH 请求
  2. 检查响应状态码为 404
  3. 检查 `error.code == "NOT_FOUND"`
- **预期结果**：404 路由不存在

---

### TC-CHANNEL-011：删除不存在的路由（异常响应）

- **前置条件**：已登录
- **请求信息**：
  - 方法：DELETE
  - URL：`/web/channels/langbot/routes/00000000-0000-4000-8000-000000000000`
- **步骤**：
  1. 发送 DELETE 请求
  2. 检查响应状态码为 404
  3. 检查 `error.code == "NOT_FOUND"`
- **预期结果**：404 路由不存在

---

### TC-CHANNEL-012：测试发送缺少必填字段（必填参数缺失）

- **前置条件**：已登录，且存在带 `botUuid` 的 Bot
- **请求信息**：
  - 方法：POST
  - URL：`/web/channels/langbot/bots/{botUuid}/send`
  - Body：`{"targetType": "person"}`
- **步骤**：
  1. 先 GET `/web/channels/langbot/bots` 取一个 `botUuid`
  2. 发送 POST 请求（缺 targetId / text）
  3. 检查响应状态码为 400
  4. 检查错误信息包含 `targetId`
- **预期结果**：400 参数校验错误，不触发真实发送

---

### TC-CHANNEL-013：无会话访问 Bot 列表（权限）

- **前置条件**：无有效 session cookie
- **请求信息**：
  - 方法：GET
  - URL：`/web/channels/langbot/bots`
- **步骤**：
  1. 不带 Cookie 发送 GET 请求
  2. 检查响应状态码为 401
- **预期结果**：401 未认证

---

### TC-CHANNEL-014：自建路由生命周期（正向）

- **前置条件**：已登录；环境存在至少一个平台通道和一个 Agent 配置
- **请求信息**：
  - 方法：POST / GET / PATCH / DELETE
  - URL：`/web/channels/langbot/routes`
- **步骤**：
  1. GET `/web/channels/langbot/bots` 取第一个带 `channelId` 的通道
  2. GET `/web/config/agents` 取第一个 Agent 配置 ID
  3. POST 创建路由（chatType=person，chatId=`pytest-route-<uuid>`）
  4. 检查创建响应含 `id`，`enabled == true`
  5. GET 路由列表，确认新路由存在
  6. PATCH `/{id}` 传 `{"enabled": false}`，检查 `enabled == false` 且 chatId/agentConfigId 未变
  7. DELETE `/{id}`，检查 `data.ok == true`
  8. 再次 GET 列表，确认路由已消失
  9. finally 中兜底删除
- **预期结果**：创建→查询→更新→删除全链路成功，测试后无残留

---

### TC-CHANNEL-015：重复创建相同路由（幂等/冲突）

- **前置条件**：已登录；环境存在平台通道和 Agent 配置
- **请求信息**：
  - 方法：POST
  - URL：`/web/channels/langbot/routes`
  - Body：
    ```json
    {
      "channelId": "{通道ID}",
      "chatType": "person",
      "chatId": "pytest-dup-<uuid>",
      "agentConfigId": "{Agent配置ID}"
    }
    ```
- **步骤**：
  1. 首次 POST 创建成功
  2. 用完全相同的 channelId/chatType/chatId 再次 POST
  3. 检查第二次响应状态码为 409
  4. 检查 `error.code == "ROUTE_CONFLICT"`
  5. finally 中删除首次创建的路由
- **预期结果**：409 路由冲突，测试后无残留
