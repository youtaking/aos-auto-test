> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

# Workflow Custom Tools 模块 API 手工测试用例

## 模块：Workflow Custom Tools Web API

### TC-CUSTOMTOOLS-001：获取自定义工具列表（正向）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/workflow-custom-tools`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 发送 GET 请求
  2. 检查返回为数组
- **预期结果**：返回工具数组

---

### TC-CUSTOMTOOLS-002：自定义工具原始响应验证（正向）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/workflow-custom-tools`
- **步骤**：
  1. 发送 GET 请求
  2. 检查原始响应 `success` 为 `true`
  3. 检查 `data` 为数组
- **预期结果**：返回 `{success: true, data: [...]}`

---

### TC-CUSTOMTOOLS-003：自定义工具元数据 schema（正向）

- **前置条件**：已登录，工具列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/web/workflow-custom-tools`
- **步骤**：
  1. 获取工具列表
  2. 取第一个工具
  3. 检查包含 `name` 字段
- **预期结果**：每个工具至少包含 name 字段
