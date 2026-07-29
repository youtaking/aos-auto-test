# MCP 服务器模块 - 人工评审报告

**评审日期**：2026-07-28
**评审人**：人工评审
**测试文件**：`tests/suites/test_mcp.py`

---

## 评审结果汇总

| 类别 | 数量 |
|------|------|
| ✅ 通过 | 23 |
| ⏭️ 跳过 | 1 |
| ❌ 不通过 | 0 |
| 🗑️ 删除 | 0 |
| **合计** | **24** |

---

## 评审过程中的主要修复

### 1. DOM 选择器修正
- `agent-panel-content` → `agent-panel-body`（主内容区选择器错误）
- `get_server_names()` 提取逻辑重写（卡片文本结构：头像字母 → ORG_ID/名称 → 类型）

### 2. 类型选择器修复
- `select_type()` 使用 `filter(has_text=)` 导致同时匹配 Local 和 Remote
- 改为精确文本匹配：`"Local（命令行启动）"` / `"Remote（URL 连接）"`

### 3. Toast 通知检测
- `get_validation_errors()` 重写：支持捕获自动消失的 toast（`<li>` 元素）
- 所有涉及操作反馈的用例增加 toast 轮询抓取

### 4. 测试数据自包含
- 所有用例改为自建测试数据 + 操作后清理
- 新增 `_create_test_server()` 辅助函数
- 使用固定服务器 `langtesttest` 做检测相关测试

### 5. 持久化验证
- 启用/禁用/公开切换后增加刷新页面验证持久化
- 增加错误 toast 检查（防止前端乐观更新掩盖后端错误）

### 6. 类型覆盖
- 启用/禁用/删除/公开 各增加 SSE 类型版本

### 7. API 拦截路径
- 所有 API 拦截器从 `"mcp"` 改为 `"/web/config/mcp"`（内部 API 路径）

### 8. 用例名称修正
- `test_openapi_*` → `test_mcp_api_*`

---

## 系统行为发现

### 检测功能仅支持远程服务器
- 对 Local/Stdio 类型服务器点「检测」返回 400：`Inspect only supports remote MCP servers`
- TC-009 改为验证此错误提示是否正确显示

---

## 各用例评审详情

| 用例 | 名称 | 结论 |
|------|------|------|
| TC-001 | 列表数据加载 | ✅ 通过 |
| TC-002 | 创建 Stdio 服务器 | ✅ 通过 |
| TC-003 | 创建 SSE 服务器 | ✅ 通过 |
| TC-004 | 合法名称校验 | ✅ 通过 |
| TC-005 | 非法名称校验 | ✅ 通过 |
| TC-006 | 命令校验 | ✅ 通过 |
| TC-007 | 启用服务器（Stdio） | ✅ 通过 |
| TC-007b | 启用服务器（SSE） | ✅ 通过（新增） |
| TC-008 | 禁用服务器（Stdio） | ✅ 通过 |
| TC-008b | 禁用服务器（SSE） | ✅ 通过（新增） |
| TC-009 | 本地服务器检测提示不支持 | ✅ 通过（重写） |
| TC-010 | 远程服务器检测 | ✅ 通过 |
| TC-011 | 查看工具列表 | ✅ 通过（改用 langtesttest） |
| TC-012 | 检查服务器状态 | ✅ 通过（改用 langtesttest） |
| TC-013 | 删除 Stdio 服务器 | ✅ 通过 |
| TC-013b | 删除 SSE 服务器 | ✅ 通过（新增） |
| TC-014 | 公开 MCP 可读不可改 | ⏭️ 跳过（需多账号） |
| TC-015 | 公开按钮（Stdio） | ✅ 通过 |
| TC-015b | 公开按钮（SSE） | ✅ 通过（新增） |
| TC-016 | CRUD API 验证 | ✅ 通过 |
| TC-017 | 参数校验 | ✅ 通过 |
| TC-018 | 认证和权限 | ✅ 通过 |
| TC-019 | 工具列表 API 验证 | ✅ 通过 |
| TC-020 | 启用/禁用 API 验证 | ✅ 通过 |

---

## conftest.py 白名单新增

- `Inspect only supports remote` / `检测失败` — MCP 检测本地服务器已知错误
- `SSE error` / `Unable to connect` — MCP 检测远程假 URL 已知错误
- `mcp/actions/inspect` — inspect API 400 响应白名单
- `Failed to load resource` + `400` — 浏览器原生 400 资源加载失败
- `Failed to fetch` + `/web/config/` — SPA 导航切换瞬态错误
- `网络异常` + `ApiError` — API 网络异常
