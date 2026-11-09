> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

# Knowledge Base Web 模块 API 手工测试用例

## 模块：Knowledge Base Web API

### TC-KBWEB-001：获取知识库列表（正向）

- **前置条件**：已登录，知识库服务可用
- **请求信息**：
  - 方法：GET
  - URL：`/web/knowledgeBases`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 发送 GET 请求
  2. 检查返回为数组
- **预期结果**：返回知识库数组

---

### TC-KBWEB-002：获取知识库详情（正向）

- **前置条件**：已登录，知识库列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/web/knowledgeBases/{kb_id}`
- **步骤**：
  1. 列表取第一个 ID
  2. GET 查详情
  3. 检查 `id` 与请求一致
  4. 检查 `name` 字段存在
- **预期结果**：返回知识库详情

---

### TC-KBWEB-003：获取知识库表单选项（正向）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/knowledgeBases/form-options`
- **步骤**：
  1. 发送 GET 请求
  2. 检查返回为非空 dict 或 list
- **预期结果**：返回表单配置选项

---

### TC-KBWEB-004：获取 rerank 模型列表（正向）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/knowledgeBases/rerank-models`
- **步骤**：
  1. 发送 GET 请求
  2. 检查返回为数组或包含 models/items 的对象
- **预期结果**：返回 rerank 模型列表

---

### TC-KBWEB-005：获取不存在的知识库（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/knowledgeBases/nonexistent-kb-id-99999`
- **步骤**：
  1. 发送 GET 请求
  2. 检查返回 404/500
- **预期结果**：返回错误

---

### TC-KBWEB-006：知识库 CRUD 生命周期（正向）

- **前置条件**：已登录，知识库服务可用
- **请求信息**：
  - 方法：POST（创建）+ GET + PUT（更新）+ DELETE
  - Body（创建）：
    ```json
    {
      "name": "api-test-kb-crud-001",
      "slug": "api-test-kb-crud-001",
      "description": "API 测试自动创建的知识库"
    }
    ```
- **步骤**：
  1. POST 创建知识库
  2. GET 验证
  3. PUT 更新 description
  4. GET 验证更新生效、id 不变
  5. DELETE 删除
  6. GET 验证 404
- **预期结果**：完整 CRUD 正常

---

### TC-KBWEB-007：无效 Token 访问知识库列表（权限）

- **前置条件**：未登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/knowledgeBases`
- **步骤**：
  1. 不携带 Cookie 发送 GET 请求
  2. 检查返回 401
- **预期结果**：返回 401 Unauthorized

---

### TC-KBWEB-008：DELETE 幂等性

- **前置条件**：已登录，知识库服务可用
- **请求信息**：
  - 方法：DELETE × 2
  - URL：`/web/knowledgeBases/{kb_id}`
- **步骤**：
  1. 创建知识库
  2. 第一次 DELETE 成功
  3. 第二次 DELETE，检查返回 404
- **预期结果**：第二次删除返回 404

---

### TC-KBWEB-009：获取知识库资源列表（正向）

- **前置条件**：已登录，知识库列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/web/knowledgeBases/{kb_id}/resources`
- **步骤**：
  1. 列表取第一个知识库 ID
  2. GET 获取资源列表
  3. 检查返回为数组或对象
- **预期结果**：返回资源列表

---

### TC-KBWEB-010：搜索知识库（正向）

- **前置条件**：已登录，知识库列表非空
- **请求信息**：
  - 方法：POST
  - URL：`/web/knowledgeBases/{kb_id}/search`
  - Body：`{"query": "test query"}`
- **步骤**：
  1. 发送搜索请求
  2. 检查返回为数组或对象
- **预期结果**：返回搜索结果

---

### TC-KBWEB-011：切换资源启用状态（正向）

- **前置条件**：已登录，有包含资源的知识库
- **请求信息**：
  - 方法：PATCH
  - URL：`/web/knowledgeBases/{kb_id}/resources/{resource_id}/toggle`
- **步骤**：
  1. 找到有资源的知识库
  2. PATCH 切换 enabled 状态
  3. 检查返回为 dict 或 None
- **预期结果**：状态切换成功

---

### TC-KBWEB-012：按 URL 添加资源缺少 url（必填缺失）

- **前置条件**：已登录，知识库列表非空
- **请求信息**：
  - 方法：POST
  - URL：`/web/knowledgeBases/{kb_id}/resources/url`
  - Body：`{}`
- **步骤**：
  1. 列表取第一个知识库 ID
  2. 发送 POST 请求
  3. 检查响应状态码为 400
  4. 检查 `error.type` 为 `VALIDATION_ERROR`
  5. 检查 `error.message` 包含 `url`
- **预期结果**：返回 400，且不落库

---

### TC-KBWEB-013：上传资源缺少 multipart 请求体（必填缺失）

- **前置条件**：已登录，知识库列表非空
- **请求信息**：
  - 方法：POST
  - URL：`/web/knowledgeBases/{kb_id}/resources/upload`（无请求体）
- **步骤**：
  1. 发送 POST 请求
  2. 检查响应状态码为 400
  3. 检查 `error.code` 为 `VALIDATION_ERROR`
  4. 检查 `error.message` 包含 `form data`
- **预期结果**：返回 400，提示无法解析表单数据

---

### TC-KBWEB-014：下载不存在资源的原文件（异常）

- **前置条件**：已登录，知识库列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/web/knowledgeBases/{kb_id}/resources/nonexistent-resource-99999/file`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 404
  3. 检查 `error.type` 为 `NOT_FOUND`
  4. 检查 `error.message` 为 `Resource not found`
- **预期结果**：返回 404

---

### TC-KBWEB-015：下载不存在资源的 PDF 预览（异常）

- **前置条件**：已登录，知识库列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/web/knowledgeBases/{kb_id}/resources/nonexistent-resource-99999/pdf`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 404
  3. 检查 `error.type` 为 `NOT_FOUND`
  4. 检查 `error.message` 为 `Resource not found`
- **预期结果**：返回 404
