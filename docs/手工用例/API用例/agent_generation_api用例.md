> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

# Agent Generation 模块 API 手工测试用例

## 模块：Agent Generation Web API

### TC-AGENTGEN-001：AI 生成 Agent 配置（正向）

- **前置条件**：已登录，服务端已配置生成模型
- **请求信息**：
  - 方法：POST
  - URL：`/web/agent-generation`
  - Headers：`Cookie: session=xxx`
  - Body：`{"prompt": "test assistant"}`
- **步骤**：
  1. 发送 POST 请求
  2. 检查返回 `name` 为字符串
  3. 检查 `systemPrompt` 为字符串
  4. 检查 `skills` 为数组
  5. 503 时 skip（未配置生成模型）
- **预期结果**：返回 `{name: "...", systemPrompt: "...", skills: [...]}`
