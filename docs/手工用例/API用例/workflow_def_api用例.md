> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

# Workflow Definition 模块 API 手工测试用例

## 模块：Workflow Def Web API

### TC-WFDEF-001：获取工作流定义列表（正向）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/workflow-defs`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 发送 GET 请求
  2. 检查返回为数组
- **预期结果**：返回工作流定义数组

---

### TC-WFDEF-002：获取工作流定义详情（正向）

- **前置条件**：已登录，列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/web/workflow-defs/{wf_id}`
- **步骤**：
  1. 列表取第一个 ID
  2. GET 查详情
  3. 检查 `id`、`name` 字段存在
- **预期结果**：返回工作流定义详情

---

### TC-WFDEF-003：创建并删除工作流定义（正向 CRUD）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST（创建）+ GET + DELETE
  - Body（创建）：
    ```json
    {
      "name": "api-test-wf-def-001",
      "description": "Web API 测试自动创建的工作流"
    }
    ```
- **步骤**：
  1. POST 创建
  2. GET 验证 name 一致
  3. DELETE 删除
  4. GET 验证 404
- **预期结果**：完整 CRUD 正常

---

### TC-WFDEF-004：获取工作流版本列表（正向）

- **前置条件**：已登录，列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/web/workflow-defs/{wf_id}/versions`
- **步骤**：
  1. 列表取第一个 ID
  2. GET 获取版本列表
  3. 检查返回为数组
- **预期结果**：返回版本数组

---

### TC-WFDEF-005：获取工作流触发器列表（正向）

- **前置条件**：已登录，列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/web/workflow-defs/{wf_id}/triggers`
- **步骤**：
  1. 列表取第一个 ID
  2. GET 获取触发器列表
  3. 检查返回为数组
- **预期结果**：返回触发器数组

---

### TC-WFDEF-006：获取可恢复的工作流列表（正向）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/workflow-defs/recoverable`
- **步骤**：
  1. 发送 GET 请求
  2. 检查返回为数组
- **预期结果**：返回可恢复工作流数组

---

### TC-WFDEF-007：获取不存在的工作流定义（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/workflow-defs/nonexistent-wf-id-99999`
- **步骤**：
  1. 发送 GET 请求
  2. 检查返回 404/500
- **预期结果**：返回错误

---

### TC-WFDEF-008：更新工作流元数据（正向）

- **前置条件**：已登录
- **请求信息**：
  - 方法：PUT
  - URL：`/web/workflow-defs/{wf_id}`
  - Body：
    ```json
    {
      "name": "api-test-wf-def-update-001-updated",
      "description": "Updated description by test"
    }
    ```
- **步骤**：
  1. 创建工作流定义
  2. PUT 更新 name 和 description
  3. GET 验证 description 已更新
  4. 验证 id 不变
  5. 清理：删除
- **预期结果**：更新成功，id 不变

---

### TC-WFDEF-009：无效 Token 访问工作流列表（权限）

- **前置条件**：未登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/workflow-defs`
- **步骤**：
  1. 不携带 Cookie 发送 GET 请求
  2. 检查返回 401
- **预期结果**：返回 401 Unauthorized

---

### TC-WFDEF-010：DELETE 幂等性

- **前置条件**：已登录
- **请求信息**：
  - 方法：DELETE × 2
  - URL：`/web/workflow-defs/{wf_id}`
- **步骤**：
  1. 创建工作流定义
  2. 第一次 DELETE 成功
  3. 第二次 DELETE，检查返回 404
- **预期结果**：第二次删除返回 404
