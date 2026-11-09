> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

# Sandbox Pool Config 模块 API 手工测试用例

## 模块：Sandbox Pool Config Web API

### TC-SANDBOXPOOL-001：获取 sandbox pool 可选项（正向）

- **前置条件**：已登录，Sandbox 服务已启用
- **请求信息**：
  - 方法：GET
  - URL：`/web/config/sandbox-pools`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 发送 GET 请求
  2. 检查 `enabled` 为布尔值
  3. 检查 `pools` 为数组
  4. 如 enabled=true 且 pools 非空，检查每项有 id 和 name
- **预期结果**：返回 `{enabled: bool, pools: [{id, name}, ...]}`

---

### TC-SANDBOXPOOL-002：验证 sandbox pool 响应结构完整性（正向）

- **前置条件**：已登录，Sandbox 服务已启用
- **请求信息**：
  - 方法：GET
  - URL：`/web/config/sandbox-pools`
- **步骤**：
  1. 发送 GET 请求
  2. Schema 校验 enabled + pools 结构
- **预期结果**：通过 Schema 校验

---

### TC-SANDBOXPOOL-003：未登录访问 sandbox pool 配置（权限）

- **前置条件**：未登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/config/sandbox-pools`
- **步骤**：
  1. 不携带 Cookie 发送 GET 请求
  2. 检查返回 401
- **预期结果**：返回 401 Unauthorized
