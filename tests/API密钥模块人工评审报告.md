# API密钥模块 - 人工评审报告

**评审日期**：2026-07-28
**评审人**：人工评审
**测试文件**：`tests/suites/test_apikey.py`
**Page Object**：`tests/pages/apikey_page.py`

---

## 评审总览

| 指标 | 数量 |
|------|------|
| 用例总数 | 12 |
| ✅ 通过 | 12 |
| 🗑️ 已删除 | 1 |
| ❌ 不通过 | 0 |

---

## 用例逐条评审

| # | 用例名 | 优先级 | 评审状态 |
|---|--------|--------|---------|
| 1 | test_apikey_001_list_loads | P0 | ✅ |
| 2 | test_apikey_002_create_key | P0 | ✅ |
| 3 | test_apikey_003_name_empty_validation | P1 | ✅ |
| 4 | test_apikey_004_one_time_display | P0 | ✅ |
| 5 | test_apikey_005_list_no_full_key | P0 | ✅ |
| 6 | test_apikey_006_security_warning | P1 | ✅ |
| 7 | test_apikey_006b_copy_button | P1 | ✅（新增）|
| 8 | test_apikey_006c_close_button_bottom | P2 | ✅（新增）|
| 9 | test_apikey_006d_close_button_x | P2 | ✅（新增）|
| 10 | test_apikey_007_delete_key | P1 | ✅ |
| 11 | test_apikey_008_delete_cancel | P2 | ✅ |
| 12 | test_apikey_009_copy_key | P2 | ✅ |
| 13 | test_apikey_010_loading_state | P2 | 🗑️ 已删除 |

---

## 修复记录

### test_apikey_001_list_loads
- **问题**：缺少标题和创建按钮校验
- **修复**：添加 `"API" in body` 标题检查和 `has_create_button()` 按钮检查

### test_apikey_002_create_key
- **问题1**：输入框选择器 `input[type=text]` 不匹配真实 DOM
- **修复**：改为 `input[data-slot='input']`
- **问题2**：创建成功后未关闭密钥展示弹窗，导致后续检查异常
- **修复**：`submit_dialog()` 后添加 `ak.close_dialog()`

### test_apikey_006_security_warning
- **问题1**：安全警告关键词不全（缺少"妥善保存"、"无法再次查看"等）
- **修复**：扩展关键词列表
- **问题2**：输入框选择器仍是 `input[type=text]`
- **修复**：改为 `input[data-slot='input']`

### test_apikey_009_copy_key
- **问题**：输入框选择器 `input[type=text]` 不匹配，导致名称未填写
- **修复**：改为 `input[data-slot='input']`

### Page Object: apikey_page.py
- **问题1**：`is_loaded()` 使用 `div.agent-panel-content` 指向了错误的面板
- **修复**：改为检查吊销按钮数量 `get_by_role("button", name="吊销").count() > 0`
- **问题2**：所有方法使用 `div.agent-panel-content` 定位错误面板
- **修复**：新增 `_body()` 辅助方法返回 `div.agent-panel-body`，全部方法统一使用

### 新增 3 条用例（006b/006c/006d）
- **来源**：用户要求对创建后弹窗的复制按钮、底部关闭按钮、右上角X按钮分别验证
- **实现**：共用 `_create_and_get_key_dialog()` 辅助函数，分别测试三个交互

### 删除 test_apikey_010_loading_state
- **原因**：加载状态属于 UI 体验优化，非功能性验证；且骨架屏捕获依赖网络速度，与 001 列表加载校验点重复

---

## 全局问题

- **DOM 面板定位**：API 密钥页面的内容在 `div.agent-panel-body` 中，而非 `div.agent-panel-content`（后者对应文件/站点面板）
- **输入框选择器**：弹窗中的输入框使用 `input[data-slot='input']`，不带 `type=text` 属性
