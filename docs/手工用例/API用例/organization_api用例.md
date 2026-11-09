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
