> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

# Workflow SSE 模块 API 手工测试用例

## 模块：Workflow SSE Web API

### TC-WFSSE-001：连接 SSE 流（正向）

- **前置条件**：已登录，工作流定义列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/web/workflow/{workflow_id}/events`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 获取工作流定义列表取第一个 ID
  2. 使用 stream 方式连接 SSE
  3. 检查 Content-Type 包含 `text/event-stream`
  4. 读取一行数据后关闭连接
- **预期结果**：返回 200，Content-Type 为 `text/event-stream`

---

### TC-WFSSE-002：连接不存在的工作流 SSE（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/workflow/nonexistent-wf-99999/events`
- **步骤**：
  1. 发送 GET 请求
  2. 检查返回 404/500
- **预期结果**：返回错误

---

### TC-WFSSE-003：带 fromSeqNum 连接 SSE（断线重连）

- **前置条件**：已登录，工作流定义列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/web/workflow/{workflow_id}/events?fromSeqNum=0`
- **步骤**：
  1. 带 `fromSeqNum=0` 连接 SSE
  2. 检查返回 200
  3. 读取 keepalive 后关闭
- **预期结果**：连接正常，支持断线重连
