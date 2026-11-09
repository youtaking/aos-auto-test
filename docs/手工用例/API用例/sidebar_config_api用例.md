> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

# Sidebar Config 模块 API 手工测试用例

## 模块：Sidebar Config Web API

### TC-SIDEBAR-001：获取侧边栏配置（正向）

- **前置条件**：无需认证
- **请求信息**：
  - 方法：GET
  - URL：`/web/sidebar-config`
- **步骤**：
  1. 发送 GET 请求
  2. 检查返回为 dict/list/None
- **预期结果**：返回侧边栏配置数据

---

### TC-SIDEBAR-002：侧边栏配置原始响应验证（正向）

- **前置条件**：无需认证
- **请求信息**：
  - 方法：GET
  - URL：`/web/sidebar-config`
- **步骤**：
  1. 发送 GET 请求
  2. 检查原始响应 `success` 为 `true`
  3. 检查 `data` 字段存在
- **预期结果**：返回 `{success: true, data: {...}}`
