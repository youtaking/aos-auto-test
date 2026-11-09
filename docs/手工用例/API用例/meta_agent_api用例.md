> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

# Meta Agent 模块 API 手工测试用例

## 模块：Meta Agent Web API

### TC-METAAGENT-001：确保 Meta Agent 可用（正向）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/meta-agent/ensure`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 发送 POST 请求
  2. 检查 `environmentId` 为字符串
  3. 检查 `status` 为 `created` 或 `reused`
- **预期结果**：返回 `{environmentId: "...", status: "created"|"reused"}`
