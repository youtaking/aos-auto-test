> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

# Control（会话控制）模块 API 手工测试用例

## 模块：Control Web API

> 注：需要活跃 session 才能测试，无可用 session 时大部分用例 skip。

### TC-CONTROL-001：向会话发送事件（正向）

- **前置条件**：已登录，有活跃 session
- **请求信息**：
  - 方法：POST
  - URL：`/web/sessions/{session_id}/events`
  - Body：
    ```json
    {
      "type": "user",
      "content": "auto-test message"
    }
    ```
- **步骤**：
  1. 获取一个活跃 session ID
  2. POST 发送事件
  3. 检查 `status` 为 `ok`
- **预期结果**：返回 `{status: "ok"}`

---

### TC-CONTROL-002：向会话发送控制指令（正向）

- **前置条件**：已登录，有活跃 session
- **请求信息**：
  - 方法：POST
  - URL：`/web/sessions/{session_id}/control`
  - Body：
    ```json
    {
      "type": "control_request",
      "action": "approve"
    }
    ```
- **步骤**：
  1. 获取活跃 session ID
  2. POST 发送控制指令
  3. 检查 `status` 为 `ok`
- **预期结果**：返回 `{status: "ok"}`

---

### TC-CONTROL-003：中断会话（正向）

- **前置条件**：已登录，有活跃 session
- **请求信息**：
  - 方法：POST
  - URL：`/web/sessions/{session_id}/interrupt`
- **步骤**：
  1. 获取活跃 session ID
  2. POST 中断会话
  3. 检查返回 null 或 dict
- **预期结果**：中断成功

---

### TC-CONTROL-004：向不存在的会话发送事件（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/sessions/nonexistent-session-99999/events`
  - Body：`{"type": "user", "content": "test"}`
- **步骤**：
  1. 发送 POST 请求
  2. 检查抛出异常
- **预期结果**：抛出异常（404/403）

---

### TC-CONTROL-005：中断不存在的会话（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/sessions/nonexistent-session-99999/interrupt`
- **步骤**：
  1. 发送 POST 请求
  2. 检查抛出异常
- **预期结果**：抛出异常（404/403）
