> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

# Organization 模块 API 手工测试用例

## 模块：Organization Web API

### TC-ORG-001：获取组织列表（正向）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/organizations`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 发送 GET 请求
  2. 检查返回为数组
- **预期结果**：返回组织数组

---

### TC-ORG-002：获取组织详情（正向）

- **前置条件**：已登录，组织列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/web/organizations/{org_id}`
- **步骤**：
  1. 获取组织列表取第一个 ID
  2. GET 查详情
  3. 检查 `id`、`name`、`slug` 字段存在
- **预期结果**：返回组织详情对象

---

### TC-ORG-003：获取组织成员列表（正向）

- **前置条件**：已登录，组织列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/web/organizations/{org_id}/members`
- **步骤**：
  1. 获取组织列表取第一个 ID
  2. GET 获取成员列表
  3. 检查返回为数组
- **预期结果**：返回成员数组

---

### TC-ORG-004：搜索成员候选项（正向）

- **前置条件**：已登录，组织列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/web/organizations/{org_id}/member-candidates?query=`
- **步骤**：
  1. 获取组织列表取第一个 ID
  2. 发送空关键词搜索
  3. 检查返回为数组
- **预期结果**：返回候选项数组

---

### TC-ORG-005：获取不存在的组织（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/organizations/nonexistent-org-id-99999`
- **步骤**：
  1. 发送 GET 请求
  2. 检查抛出异常
- **预期结果**：抛出异常（404 或其他错误）

---

### TC-ORG-006：组织 CRUD 生命周期（正向）

- **前置条件**：已登录，有管理员权限
- **请求信息**：
  - 方法：POST（创建）+ GET + PUT（更新）+ DELETE
  - URL：`/web/organizations` / `/web/organizations/{id}`
  - Body（创建）：
    ```json
    {
      "name": "api-test-org-crud-001",
      "slug": "api-test-org-crud-001"
    }
    ```
- **步骤**：
  1. POST 创建组织
  2. GET 验证创建成功
  3. PUT 更新 name
  4. GET 验证更新生效
  5. DELETE 删除
  6. GET 验证资源已消失
- **预期结果**：完整 CRUD 正常。若权限不足返回 400/403/409/500 则 skip

---

### TC-ORG-007：创建组织拒绝空白 name/slug（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/organizations`
  - Body：`{"name": "", "slug": "valid-slug"}` / `{"name": " \t ", ...}` / `slug` 同理
- **步骤**：
  1. 逐组提交空白字段
  2. 检查 HTTP 状态与错误信封
- **预期结果**：返回 400，`error.type = VALIDATION_ERROR`，`error.message` 指向 `name` 或 `slug`

---

### TC-ORG-008：创建组织接受合法字段（正向）

- **前置条件**：已登录，可创建组织
- **请求信息**：
  - 方法：POST
  - URL：`/web/organizations`
  - Body：`{"name": "valid-<slug>", "slug": "api-test-org-valid-xxxx", "description": "contract-check"}`
- **步骤**：
  1. 校验请求体符合契约
  2. POST 创建
  3. 校验响应组织结构与 `slug`
  4. DELETE 清理自建组织
- **预期结果**：返回 200，`success: true`，组织 slug 与请求一致

---

### TC-ORG-009：更新组织拒绝顶层/data 内空白字段（异常）

- **前置条件**：已登录，可创建组织（用例自建唯一 slug 的临时组织 A，结束删除；不触碰既有组织）
- **请求信息**：
  - 方法：PUT
  - URL：`/web/organizations/{org_id}`
  - Body：`{"name": ""}` / `{"name": " \t "}` / `{"slug": ""}` / `{"slug": " \t "}` / `{"data": {"name": ""}}` 等
- **步骤**：
  1. POST 创建唯一 slug 的临时组织 A
  2. 对 A 逐组提交空白字段
  3. 检查状态与错误信息
  4. DELETE 清理 A
- **预期结果**：返回 400，`error.type = VALIDATION_ERROR`，`error.message` 指向对应字段；不写入

---

### TC-ORG-010：更新组织拒绝混合字段（异常）

- **前置条件**：已登录，可创建组织（用例自建唯一 slug 的临时组织 A，结束删除；不触碰既有组织）
- **请求信息**：
  - 方法：PUT
  - URL：`/web/organizations/{org_id}`
  - Body：`{"name": "新名称", "data": {}}` / `{"slug": "new-slug", "data": {"metadata": {...}}}` 等
- **步骤**：
  1. POST 创建唯一 slug 的临时组织 A
  2. 对 A 同时提交顶层字段与 `data`
  3. 检查错误信封
  4. DELETE 清理 A
- **预期结果**：返回 400，`error.type = VALIDATION_ERROR`，`error.message` 包含 `data`

---

### TC-ORG-011：更新组织接受单一格式部分更新（正向）

- **前置条件**：已登录，可创建组织（用例自建唯一 slug 的临时组织 A，结束删除；不触碰既有组织）
- **请求信息**：
  - 方法：PUT
  - URL：`/web/organizations/{org_id}`
  - Body：`{"name": "新名称-<唯一后缀>"}` / `{"slug": "api-test-org-upd-<唯一后缀>"}` / `{"data": {"name": "新名称-<唯一后缀>", "slug": "api-test-org-upd-<唯一后缀>"}}` / `{"data": {"metadata": {"description": "说明"}}}`
- **步骤**：
  1. POST 创建唯一 slug 的临时组织 A
  2. 校验请求体符合 `ORGANIZATION_UPDATE_REQUEST` 契约
  3. PUT 更新 A
  4. GET 回读 A，确认对应字段（name/slug/metadata.description）已生效
  5. DELETE 清理 A
- **预期结果**：返回 200，`success: true`，回读可见对应字段变更

---

### TC-ORG-012：创建组织 Slug 冲突（异常）

- **前置条件**：已登录，可创建组织
- **请求信息**：
  - 方法：POST
  - URL：`/web/organizations`
  - Body：`{"name": "<slug>-other", "slug": "<已存在 slug>"}`
- **步骤**：
  1. 自建一个组织 A
  2. 用相同 slug 再创建组织 B
  3. 检查冲突错误；若 B 意外创建成功，一并 DELETE 清理
  4. DELETE 清理组织 A
- **预期结果**：返回 409，`success: false`，`error.code = ORGANIZATION_SLUG_ALREADY_TAKEN`
