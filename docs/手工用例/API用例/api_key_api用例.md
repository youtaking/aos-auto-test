> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

# API Key 模块 API 手工测试用例

## 模块：API Key Web API

### TC-APIKEY-001：获取 API Key 列表（正向）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/api-keys`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 发送 GET 请求
  2. 检查返回为数组
- **预期结果**：返回 API Key 数组

---

### TC-APIKEY-002：创建并删除 API Key（正向 CRUD）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST（创建）+ GET（验证）+ DELETE（删除）
  - URL：`/web/api-keys`
  - Body（创建）：`{"name": "api-test-web-apikey-001"}`
- **步骤**：
  1. POST 创建 API Key
  2. 检查返回包含 id 和 name
  3. GET 列表验证新 Key 存在
  4. DELETE 删除
  5. GET 列表验证 Key 已消失
- **预期结果**：完整创建→验证→删除正常

---

### TC-APIKEY-003：删除不存在的 API Key（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：DELETE
  - URL：`/web/api-keys/nonexistent-api-key-id-99999`
- **步骤**：
  1. 发送 DELETE 请求
  2. 检查抛出异常
- **预期结果**：抛出异常（404/400/ValueError）

---

### TC-APIKEY-004：DELETE 幂等性

- **前置条件**：已登录
- **请求信息**：
  - 方法：DELETE × 2
  - URL：`/web/api-keys/{key_id}`
- **步骤**：
  1. 创建 API Key
  2. 第一次 DELETE 成功
  3. 第二次 DELETE，检查抛出异常
- **预期结果**：第二次删除抛出异常
