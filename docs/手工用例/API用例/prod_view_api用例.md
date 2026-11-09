> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

# ProdView 模块 API 手工测试用例

## 模块：ProdView Web API

### TC-PRODVIEW-001：获取 ProdView 列表（正向）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/config/prod-views`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 发送 GET 请求
  2. 检查返回为数组或对象
- **预期结果**：返回 ProdView 列表

---

### TC-PRODVIEW-002：获取 ProdView 详情（正向）

- **前置条件**：已登录，ProdView 列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/web/config/prod-views/{view_id}`
- **步骤**：
  1. 列表接口取第一个 ID
  2. GET 查详情
  3. 检查 `id` 与请求一致
- **预期结果**：返回 ProdView 详情

---

### TC-PRODVIEW-003：获取不存在的 ProdView（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/config/prod-views/nonexistent-prod-view-id-99999`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 404
  3. 检查 `success == false`、`error.type/code == NOT_FOUND`
- **预期结果**：返回 404 Not Found（注意：UUID 格式但已删除的 ID 当前会返回 400，见 BUG-05）

---

### TC-PRODVIEW-004：ProdView CRUD 生命周期（正向）

- **前置条件**：已登录，Agent 列表非空
- **请求信息**：
  - 方法：POST（创建）+ GET + PUT（更新）+ DELETE
  - Body（创建）：
    ```json
    {
      "agentId": "{agentConfigId}",
      "name": "api-test-prod-view-crud",
      "enabled": false,
      "modulesConfig": {}
    }
    ```
- **步骤**：
  1. POST 创建 ProdView
  2. GET 验证创建成功
  3. PUT 更新 enabled = true
  4. GET 验证 enabled 已更新
  5. DELETE 删除
  6. GET 验证 404
- **预期结果**：完整 CRUD 正常
- **已知缺陷**：BUG-05 — 删除后用该 UUID GET 当前返回 `400 {"error":{"type":"VALIDATION_ERROR","message":"success: Invalid input: expected true"}}`，契约应为 404

---

### TC-PRODVIEW-005：DELETE 幂等性

- **前置条件**：已登录，Agent 列表非空
- **请求信息**：
  - 方法：DELETE × 2
  - URL：`/web/config/prod-views/{view_id}`
- **步骤**：
  1. 创建 ProdView
  2. 第一次 DELETE 成功
  3. 第二次 DELETE，检查返回 404
- **预期结果**：第二次删除返回 404
