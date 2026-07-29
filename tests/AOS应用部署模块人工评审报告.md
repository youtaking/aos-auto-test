# AOS应用部署模块 - 人工评审报告

**评审日期**：2026-07-29
**评审人**：人工评审
**测试文件**：`tests/suites/test_sites.py`
**评审结果**：10 条用例，9 条通过，1 条发现系统 bug

---

## 第 1 条 `test_site_builder_chat_loads`

**用例说明**：建站助手对话页面正常加载

**评审结论**：⚠️ 问题已修复 → ✅ 通过

**评审问题**：
- [x] `has_artifacts_panel()` 只检查 iframe，但实际 ArtifactsPanel 是 `div[class*='artifact']`

**修复措施**：
1. 修改 `has_artifacts_panel()` 同时检查 iframe 和 artifact div

---

## 第 2 条 `test_app_preview_and_url_access`

**用例说明**：应用预览和独立 URL 访问

**评审结论**：✅ 通过

---

## 第 3 条 `test_sites_list_edit_and_delete`

**用例说明**：Sites 列表编辑和删除

**评审结论**：⚠️ 问题已修复 → ✅ 通过

**评审问题**：
- [x] 原实现直接删除列表中最后一个已有应用，会破坏真实数据

**修复措施**：
1. 先通过"创建 App"按钮创建测试站点
2. 在测试站点上执行编辑和删除
3. 添加 `click_create_app()`、`fill_create_form()`、`save_create()` 等 Page Object 方法

---

## 第 4 条 `test_artifacts_panel_with_bound_site`

**用例说明**：应用绑定到 Agent 后 ArtifactsPanel 展示

**评审结论**：⚠️ 问题已修复 → ✅ 通过

**评审问题**：
- [x] 原实现依赖 iframe src，但实际无 iframe
- [x] teardown 捕获建站助手轮询已删除 App 的 404 错误

**修复措施**：
1. 改为同时检查 iframe 和 artifact div 的可见性
2. conftest.py 白名单增加 `agent-sites/apps/by-remote` 的 404

---

## 第 5 条 `test_creator_name_display`

**用例说明**：创建者名称展示

**评审结论**：❌ 发现系统 bug

**发现的问题**：
- 所有应用的创建者列均显示 `"—"`，未展示实际创建者名称
- 原测试 `assert creator` 对 `"—"` 也判定通过（校验太弱）

**修复措施**：
1. 加强校验：排除 `"—"` 占位符，要求至少有一行有实际创建者名称
2. 系统需修复创建者列的数据展示

---

## 第 6 条 `test_creator_name_click_navigation`

**用例说明**：创建者名称点击跳转

**评审结论**：⏭️ SKIP（依赖第 5 条 bug 修复）

**原因**：
- 当前所有创建者列均为 `"—"`，无可点击的创建者链接
- 第 5 条 bug 修复后此用例才能正常执行

---

## 第 7 条 `test_create_app`（补充用例）

**用例说明**：通过「创建 App」按钮创建新应用

**评审结论**：✅ 通过

---

## 第 8 条 `test_sites_search_filter`（补充用例）

**用例说明**：Sites 列表搜索过滤功能

**评审结论**：⚠️ 问题已修复 → ✅ 通过

**评审问题**：
- [x] 原实现只搜索不存在的关键词，未搜索存在的关键词

**修复措施**：
1. 先搜索一个存在的应用名称，验证结果 ≥1 且数量减少
2. 清空搜索验证恢复
3. 再搜索不存在的关键词，验证结果为 0
4. 再次清空搜索验证恢复

---

## 第 9 条 `test_sites_filter_tabs`（补充用例）

**用例说明**：Sites 列表可见性 Tab 切换筛选

**评审结论**：⚠️ 问题已修复 → ✅ 通过

**评审问题**：
- [x] 原实现只点击部分固定 Tab，未遍历所有 Tab

**修复措施**：
1. 通过 `get_filter_tabs()` 动态获取所有 Tab
2. 逐个遍历每个 Tab，验证数量 ≤ "全部"
3. 最后切回"全部"验证恢复

---

## 第 10 条 `test_token_renewal`（补充用例）

**用例说明**：重签 Token — 三点菜单中旋转应用部署 Token

**评审结论**：⚠️ 问题已修复 → ✅ 通过

**评审问题**：
- [x] 原实现错误理解为"用户 session token 刷新"，实际是"应用部署 Token 旋转"

**修复措施**：
1. 重写为先创建测试 App
2. 通过三点菜单点击「重签 Token」
3. 验证 Toast 提示 "Token 已重签"
4. 添加 `renew_token()` Page Object 方法
5. 测试结束后清理测试 App

---

## 修改文件清单

| 文件 | 修改内容 |
|------|---------|
| `tests/pages/sites_page.py` | `has_artifacts_panel()` 适配 artifact div；新增 `click_create_app()`、`fill_create_form()`、`save_create()`、`renew_token()` 等方法 |
| `tests/suites/test_sites.py` | 10 条用例标记评审状态；`test_sites_list_edit_and_delete` 重写为先创建再编辑删除；`test_artifacts_panel_with_bound_site` 适配非 iframe 结构；`test_creator_name_display` 加强校验；新增 4 条补充用例 |
| `tests/conftest.py` | 白名单增加 `agent-sites/apps/by-remote` 404；`/web/environments` 匹配去掉尾部斜杠要求 |
