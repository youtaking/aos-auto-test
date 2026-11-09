> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

# Task V2 模块 API 手工测试用例

## 模块：Task V2 Web API

### TC-TASK-001：获取任务列表（正向）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/tasks/v2`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 发送 GET 请求
  2. 检查 `items` 为数组
  3. 检查分页字段 `total`、`page`、`pageSize` 存在
- **预期结果**：返回 `{items: [...], total: N, page: N, pageSize: N}`

---

### TC-TASK-002：获取任务详情（正向）

- **前置条件**：已登录，任务列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/web/tasks/v2/{task_id}`
- **步骤**：
  1. 列表接口取第一个 ID
  2. GET 查详情
  3. 检查 `id` 与请求一致
- **预期结果**：返回任务详情对象

---

### TC-TASK-003：获取不存在的任务（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/tasks/v2/nonexistent-task-id-99999`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 404
- **预期结果**：返回 404 Not Found

---

### TC-TASK-004：获取任务日志（正向）

- **前置条件**：已登录，任务列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/web/tasks/v2/{task_id}/logs`
- **步骤**：
  1. 列表接口取第一个 ID
  2. GET 获取日志
  3. 检查返回为 dict
  4. 如有 `entries` 或 `logs` 字段，检查为数组
- **预期结果**：返回日志对象

---

### TC-TASK-005：切换任务启用状态（正向）

- **前置条件**：已登录，任务列表非空
- **请求信息**：
  - 方法：POST
  - URL：`/web/tasks/v2/{task_id}/toggle`
- **步骤**：
  1. 记录任务当前 enabled 状态
  2. POST 切换
  3. GET 验证 enabled 已变化
- **预期结果**：enabled 状态翻转

---

### TC-TASK-006：手动触发任务（正向）

- **前置条件**：已登录，任务列表非空
- **请求信息**：
  - 方法：POST
  - URL：`/web/tasks/v2/{task_id}/trigger`
- **步骤**：
  1. POST 触发任务
  2. 检查返回包含 `status`/`id`/`run_id` 之一
- **预期结果**：返回触发状态信息

---

### TC-TASK-007：清空任务日志（正向）

- **前置条件**：已登录，任务列表非空
- **请求信息**：
  - 方法：DELETE
  - URL：`/web/tasks/v2/{task_id}/logs`
- **步骤**：
  1. DELETE 清空日志
  2. GET 验证日志为空（entries 或 logs 为空数组）
- **预期结果**：日志被清空
