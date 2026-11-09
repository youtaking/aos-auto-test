# MCP 服务器 — 手工测试用例

> 生成时间：2026-08-18
> 已有自动化：25 条（test_mcp.py）

---

## 交叉对比

| 功能点 | 已有用例 | 覆盖 | 备注 |
|--------|---------|------|------|
| 列表加载 | test_mcp_list_data_loads | ✅ | |
| 创建 Stdio | test_create_stdio_server | ✅ | |
| 创建 SSE | test_create_sse_server | ✅ | |
| 编辑服务器 | test_edit_server | ✅ | |
| 名称校验 | test_valid/invalid_name_format | ✅ | |
| 命令校验 | test_command_validation | ✅ | |
| 启用 Stdio/SSE | test_enable_server/sse | ✅ | |
| 禁用 Stdio/SSE | test_disable_server/sse | ✅ | |
| 本地检测 | test_local_connection | ✅ | |
| 远程测试 | test_remote_url | ✅ | |
| 查看工具 | test_view_tools | ✅ | |
| 检查状态 | test_inspect_server | ✅ | |
| 删除 | test_delete_server/sse | ✅ | |
| 共享只读 | test_public_mcp_readonly | ✅ | |
| 公开按钮 | test_mcp/sse_mcp_make_public | ✅ | |
| API CRUD | test_mcp_api_crud | ✅ | |
| API 校验 | test_mcp_api_validation | ✅ | |
| API 认证 | test_mcp_api_auth | ✅ | |
| API 工具 | test_mcp_api_tools | ✅ | |
| API 切换 | test_mcp_api_toggle | ✅ | |
| 搜索功能 | — | ❌ | |
| 类型筛选 | — | ❌ | |
| 批量操作 | — | ❌ | |
| 创建取消 | — | ❌ | |

---

## 一、正常流程

### NF-01~25: 已有覆盖
> 全部 25 条已有自动化，覆盖 CRUD、启用/禁用、检测、API、公开等。

---

## 二、边界值

### BV-01: 搜索无结果
| 项目 | 内容 |
|------|------|
| **前置条件** | MCP 列表已加载 |
| **操作步骤** | 搜索"zzz_不存在_99999" |
| **预期结果** | 显示空状态 |
| **自动化状态** | ❌ 缺失 |

### BV-02: URL 格式校验
| 项目 | 内容 |
|------|------|
| **前置条件** | 创建 SSE 服务器 |
| **操作步骤** | 输入无效 URL "not-a-url" |
| **预期结果** | 提示 URL 格式错误 |
| **自动化状态** | ❌ 缺失 |

---

## 三、异常处理

### EX-01: 创建取消
| 项目 | 内容 |
|------|------|
| **前置条件** | 创建服务器对话框打开 |
| **操作步骤** | 填写信息后点击取消 |
| **预期结果** | 对话框关闭，列表无新增 |
| **自动化状态** | ❌ 缺失 |

### EX-02: 检测超时处理
| 项目 | 内容 |
|------|------|
| **前置条件** | 有 SSE 服务器 |
| **操作步骤** | 模拟目标服务器不可达 |
| **预期结果** | 显示超时/连接失败提示 |
| **自动化状态** | ❌ 缺失 |

---

## 四~七

> 权限：共享只读已覆盖。数据清理由 delete 用例覆盖。
