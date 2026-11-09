> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

# Knowledge Base 高级接口 API 手工测试用例

## 模块：Knowledge Base Chunk API

### TC-KBADV-001：分页获取资源切片列表（正向）

- **前置条件**：已登录，有包含资源的知识库
- **请求信息**：
  - 方法：GET
  - URL：`/web/knowledgeBases/{kb_id}/resources/{resource_id}/chunks?page=1&pageSize=10`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 获取知识库列表，找到有资源的知识库
  2. 获取该知识库的资源列表，取第一个资源 ID
  3. 发送 GET 请求获取切片列表
  4. 检查返回为 dict，包含 `items`（数组）和 `total`（整数）
- **预期结果**：返回分页结构 `{items: [...], total: N, page: 1, pageSize: 10}`

---

### TC-KBADV-002：按关键词搜索切片（正向）

- **前置条件**：已登录，有包含资源的知识库
- **请求信息**：
  - 方法：GET
  - URL：`/web/knowledgeBases/{kb_id}/resources/{resource_id}/chunks?page=1&pageSize=10&keyword=test`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 获取有资源的知识库和资源 ID
  2. 发送 GET 请求，带 keyword 参数
  3. 检查返回为 dict
- **预期结果**：返回过滤后的切片数据

---

### TC-KBADV-003：查询不存在资源的切片（异常）

- **前置条件**：已登录，知识库列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/web/knowledgeBases/{kb_id}/resources/nonexistent-resource-99999/chunks?page=1`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 获取第一个知识库 ID
  2. 用不存在的资源 ID 发送 GET 请求
  3. 检查返回 404 或 400
- **预期结果**：返回错误状态码 404/400

---

### TC-KBADV-004：切换切片启用状态（正向）

- **前置条件**：已登录，有包含切片的资源
- **请求信息**：
  - 方法：PATCH
  - URL：`/web/knowledgeBases/{kb_id}/resources/{resource_id}/chunks/{chunk_id}/enabled`
  - Headers：`Cookie: session=xxx`
  - Body：`{"enabled": false}`
- **步骤**：
  1. 获取有资源的知识库，获取切片列表
  2. 取第一个切片的 ID 和当前 enabled 状态
  3. PATCH 切换 enabled 状态为相反值
  4. 检查返回 dict，包含 `enabled` 或 `available` 字段
  5. 恢复原始 enabled 状态
- **预期结果**：状态切换成功，返回更新后的切片信息

---

## 模块：Knowledge Base Graph API

### TC-KBADV-005：获取知识图谱数据（正向）

- **前置条件**：已登录，知识库列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/web/knowledgeBases/{kb_id}/graph`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 获取第一个知识库 ID
  2. 发送 GET 请求
  3. 检查返回为 dict/list/None
- **预期结果**：返回知识图谱数据（节点和边）或 null

---

### TC-KBADV-006：查询知识图谱生成进度（正向）

- **前置条件**：已登录，知识库列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/web/knowledgeBases/{kb_id}/graph/progress`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 获取第一个知识库 ID
  2. 发送 GET 请求
  3. 检查返回为 dict 或 None
- **预期结果**：返回生成进度信息或 null

---

### TC-KBADV-007：触发知识图谱生成（正向）

- **前置条件**：已登录，有包含资源的知识库
- **请求信息**：
  - 方法：POST
  - URL：`/web/knowledgeBases/{kb_id}/graph/generate`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 获取有资源的知识库 ID
  2. 发送 POST 请求触发图谱生成
  3. 检查返回为 null 或 dict
- **预期结果**：异步触发生成成功，返回 null 或状态信息

---

### TC-KBADV-008：删除知识图谱（正向）

- **前置条件**：已登录，知识库列表非空
- **请求信息**：
  - 方法：DELETE
  - URL：`/web/knowledgeBases/{kb_id}/graph`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 获取第一个知识库 ID
  2. 发送 DELETE 请求
  3. 检查返回为 null 或 dict
- **预期结果**：删除成功，返回 null 或状态信息

---

### TC-KBADV-009：查询不存在知识库的图谱（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/knowledgeBases/nonexistent-kb-99999/graph`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 用不存在的知识库 ID 发送 GET 请求
  2. 检查返回错误（404/502）
- **预期结果**：返回错误状态码

---

## 模块：Knowledge Base Embedding Model API

### TC-KBADV-010：列出已配置的 Embedding Provider 树（正向）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/knowledgeBases/models`
  - Headers：`Cookie: session=xxx`
  - Body：`{"action": "list"}`
- **步骤**：
  1. 发送 POST 请求，action=list
  2. 检查返回为 list 或 dict
- **预期结果**：返回 embedding provider 树结构

---

### TC-KBADV-011：列出可用的 Embedding Factory（正向）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/knowledgeBases/models`
  - Headers：`Cookie: session=xxx`
  - Body：`{"action": "list-factories"}`
- **步骤**：
  1. 发送 POST 请求，action=list-factories
  2. 检查返回为 list 或 dict
- **预期结果**：返回可用的 embedding factory 列表

---

### TC-KBADV-012：验证 Provider 缺少必填字段（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/knowledgeBases/models`
  - Headers：`Cookie: session=xxx`
  - Body：`{"action": "verify"}`
- **步骤**：
  1. 发送 POST 请求，action=verify，不传 provider 和 providerApiKey
  2. 检查返回 400 或 422
- **预期结果**：返回 400/422 参数校验错误

---

### TC-KBADV-013：列出 Provider 模型缺少必填字段（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/knowledgeBases/models`
  - Headers：`Cookie: session=xxx`
  - Body：`{"action": "list-provider-models"}`
- **步骤**：
  1. 发送 POST 请求，action=list-provider-models，不传必填字段
  2. 检查返回 400 或 422
- **预期结果**：返回 400/422 参数校验错误

---

### TC-KBADV-014：列出 Instance 模型缺少必填字段（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/knowledgeBases/models`
  - Headers：`Cookie: session=xxx`
  - Body：`{"action": "list-instance-models"}`
- **步骤**：
  1. 发送 POST 请求，action=list-instance-models，不传必填字段
  2. 检查返回 400 或 422
- **预期结果**：返回 400/422 参数校验错误

---

### TC-KBADV-015：设置模型状态缺少必填字段（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/knowledgeBases/models`
  - Headers：`Cookie: session=xxx`
  - Body：`{"action": "set-model-status"}`
- **步骤**：
  1. 发送 POST 请求，action=set-model-status，不传必填字段
  2. 检查返回 400 或 422
- **预期结果**：返回 400/422 参数校验错误

---

### TC-KBADV-016：添加 Provider 缺少必填字段（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/knowledgeBases/models`
  - Headers：`Cookie: session=xxx`
  - Body：`{"action": "add"}`
- **步骤**：
  1. 发送 POST 请求，action=add，不传 provider 配置字段
  2. 检查返回 400 或 422
- **预期结果**：返回 400/422 参数校验错误

---

### TC-KBADV-017：删除 Instance 缺少必填字段（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/knowledgeBases/models`
  - Headers：`Cookie: session=xxx`
  - Body：`{"action": "delete"}`
- **步骤**：
  1. 发送 POST 请求，action=delete，不传 instance ID 等必填字段
  2. 检查返回 400 或 422
- **预期结果**：返回 400/422 参数校验错误

---

### TC-KBADV-018：未知 Embedding Action（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/knowledgeBases/models`
  - Headers：`Cookie: session=xxx`
  - Body：`{"action": "nonexistent-action"}`
- **步骤**：
  1. 发送 POST 请求，action=nonexistent-action
  2. 检查返回 400 或 422
- **预期结果**：返回 400/422，未知的 action 类型

---

### TC-KBADV-019：未登录访问 Embedding 模型管理（权限）

- **前置条件**：未登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/knowledgeBases/models`
  - Body：`{"action": "list"}`
- **步骤**：
  1. 不携带 Cookie 发送 POST 请求
  2. 检查返回 401
- **预期结果**：返回 401 Unauthorized

---

## 模块：Knowledge Base Resource Reparse API

### TC-KBADV-020：触发资源重新解析（正向）

- **前置条件**：已登录，有包含资源的知识库
- **请求信息**：
  - 方法：POST
  - URL：`/web/knowledgeBases/{kb_id}/resources/{resource_id}/reparse`
  - Headers：`Cookie: session=xxx`
  - Body：`{}`
- **步骤**：
  1. 获取有资源的知识库和资源 ID
  2. 发送 POST 请求触发重解析
  3. 检查返回为 null 或 dict
- **预期结果**：异步触发重解析成功

---

### TC-KBADV-021：重解析不存在的资源（异常）

- **前置条件**：已登录，知识库列表非空
- **请求信息**：
  - 方法：POST
  - URL：`/web/knowledgeBases/{kb_id}/resources/nonexistent-resource-99999/reparse`
  - Headers：`Cookie: session=xxx`
  - Body：`{}`
- **步骤**：
  1. 获取第一个知识库 ID
  2. 用不存在的资源 ID 发送 POST 请求
  3. 检查返回 404 或 400
- **预期结果**：返回 404/400 错误
