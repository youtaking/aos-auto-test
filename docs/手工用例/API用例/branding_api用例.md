> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

# Branding / Sidebar / CustomTools 模块 API 手工测试用例

## 模块：Branding Web API

### TC-BRANDING-001：获取品牌配置（正向）

- **前置条件**：无需认证
- **请求信息**：
  - 方法：GET
  - URL：`/web/branding`
- **步骤**：
  1. 发送 GET 请求
  2. 检查 `brandName` 为字符串
- **预期结果**：返回 `{brandName: "...", logoUrl: "..."}`

---

## 模块：Sidebar Config Web API

### TC-SIDEBAR-001：获取侧边栏配置（正向）

- **前置条件**：无需认证
- **请求信息**：
  - 方法：GET
  - URL：`/web/sidebar-config`
- **步骤**：
  1. 发送 GET 请求
  2. 检查返回为非空字典
- **预期结果**：返回侧边栏配置字典

---

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
  3. 如有数据，检查每项包含工具元数据字段
- **预期结果**：返回自定义工具数组

---

## 模块：品牌 Logo 与系统模块

### TC-BRANDING-002：获取品牌 Logo（正向/环境前置）

- **前置条件**：已部署环境
- **请求信息**：
  - 方法：GET
  - URL：`/web/branding/logo`
- **步骤**：
  1. 发送 GET 请求
  2. 若返回 404：检查 `error.code` 为 `NOT_FOUND`，视为未配置 Logo（环境前置，跳过）
  3. 若返回 200：检查 Content-Type 以 `image/` 开头，响应体非空
- **预期结果**：已配置时返回图片字节；未配置时 404

---

### TC-BRANDING-003：获取启用的系统模块（正向）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/system/modules`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 发送 GET 请求
  2. 检查 `data.modules` 为非空数组
  3. 检查 `data.web` 为非空数组
  4. 检查 `modules` 包含 `knowledge`
- **预期结果**：返回部署启用的模块清单
