# Plugin Market 模块 API 手工测试用例

> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

说明：发布/下架/恢复属于破坏性管理动作，本模块只覆盖只读列表与不存在包。

## 模块：Plugin Market Web API

### TC-PLUGIN-001：列出插件包（正向）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/config/plugin-market/packages`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 200
  3. 检查 `data.packages` 为数组
  4. 检查 `data.total` 为整数
- **预期结果**：返回插件包列表

---

### TC-PLUGIN-002：获取不存在的插件包（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/config/plugin-market/packages/nonexistent-package-slug-99999`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 404
  3. 检查 `error.code` 为 `NOT_FOUND`
- **预期结果**：返回 404

---

## 模块：Plugin Market System API

认证方式：`Authorization: Bearer <System API Key>`。

### TC-PLUGIN-003：系统接口列出插件包（正向）

- **前置条件**：配置有效 System API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/plugin-market/packages`
- **步骤**：
  1. 发送 GET 请求
  2. 检查 `data.packages` 为数组
  3. 检查 `data.total` 为整数
- **预期结果**：返回插件包列表

---

### TC-PLUGIN-004：系统接口获取不存在的插件包（异常）

- **前置条件**：配置有效 System API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/system/plugin-market/packages/nonexistent-package-slug-99999`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 404
  3. 检查 `error.code` 为 `NOT_FOUND`
- **预期结果**：返回 404
