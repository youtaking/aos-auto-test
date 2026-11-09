> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

# Hindsight 模块 API 手工测试用例

## 模块：Hindsight Web API

> 注：Hindsight 是代理服务，大部分端点依赖外部 Hindsight 服务可用性。未启用时大部分接口 skip。

### TC-HINDSIGHT-001：获取 Hindsight 状态（正向）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/hindsight/status`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应包含 `enabled` 字段
  3. 检查 `enabled` 为布尔值
- **预期结果**：返回 `{enabled: true/false}`

---

### TC-HINDSIGHT-002：获取记忆图谱（正向）

- **前置条件**：已登录，Hindsight 已启用
- **请求信息**：
  - 方法：GET
  - URL：`/web/hindsight/graph`
- **步骤**：
  1. 发送 GET 请求
  2. 检查 `nodes` 和 `edges` 均为数组
- **预期结果**：返回 `{nodes: [...], edges: [...]}`

---

### TC-HINDSIGHT-003：获取记忆库统计（正向）

- **前置条件**：已登录，Hindsight 已启用
- **请求信息**：
  - 方法：GET
  - URL：`/web/hindsight/bank-stats`
- **步骤**：
  1. 发送 GET 请求
  2. 检查 `bank_id` 存在
  3. 检查 `total_nodes` 为整数
- **预期结果**：返回 `{bank_id: "...", total_nodes: N, total_links: N, total_documents: N}`

---

### TC-HINDSIGHT-004：列出记忆（正向）

- **前置条件**：已登录，Hindsight 已启用
- **请求信息**：
  - 方法：GET
  - URL：`/web/hindsight/memories`
- **步骤**：
  1. 发送 GET 请求
  2. 检查 `items` 为数组、`total` 为整数
- **预期结果**：返回 `{items: [...], total: N}`

---

### TC-HINDSIGHT-005：创建并删除记忆（正向 CRUD）

- **前置条件**：已登录，Hindsight 已启用
- **请求信息**：
  - 方法：POST（创建）+ DELETE（删除）
  - URL：`/web/hindsight/memories` / `/web/hindsight/memories/{id}`
  - Body（创建）：
    ```json
    {
      "content": "API test memory - safe to delete",
      "type": "observation"
    }
    ```
- **步骤**：
  1. POST 创建记忆
  2. 提取创建响应中的 ID
  3. DELETE 删除该记忆
- **预期结果**：创建成功，删除成功

---

### TC-HINDSIGHT-006：获取记忆详情（正向）

- **前置条件**：已登录，Hindsight 已启用，有记忆数据
- **请求信息**：
  - 方法：GET
  - URL：`/web/hindsight/memories/{memory_id}`
- **步骤**：
  1. 列出记忆取第一个 ID
  2. GET 查详情
  3. 检查返回非空
- **预期结果**：返回记忆详情

---

### TC-HINDSIGHT-007：获取不存在的记忆（异常）

- **前置条件**：已登录，Hindsight 已启用
- **请求信息**：
  - 方法：GET
  - URL：`/web/hindsight/memories/nonexistent-memory-id-99999`
- **步骤**：
  1. 发送 GET 请求
  2. 检查返回 404/400/500 或空响应
- **预期结果**：返回错误或空

---

### TC-HINDSIGHT-008：检索记忆 recall（正向）

- **前置条件**：已登录，Hindsight 已启用
- **请求信息**：
  - 方法：POST
  - URL：`/web/hindsight/recall`
  - Body：`{"query": "test query"}`
- **步骤**：
  1. 发送 POST 请求
  2. 检查返回非空
- **预期结果**：返回检索结果

---

### TC-HINDSIGHT-009：触发反思 reflect（正向）

- **前置条件**：已登录，Hindsight 已启用
- **请求信息**：
  - 方法：POST
  - URL：`/web/hindsight/reflect`
  - Body：`{}`
- **步骤**：
  1. 发送 POST 请求
  2. 检查返回非空
- **预期结果**：返回反思结果

---

### TC-HINDSIGHT-010：列出文档（正向）

- **前置条件**：已登录，Hindsight 已启用
- **请求信息**：
  - 方法：GET
  - URL：`/web/hindsight/documents`
- **步骤**：
  1. 发送 GET 请求
  2. 检查 `items` 为数组、`total` 为整数
- **预期结果**：返回 `{items: [...], total: N}`

---

### TC-HINDSIGHT-011：删除不存在的文档（异常）

- **前置条件**：已登录，Hindsight 已启用
- **请求信息**：
  - 方法：DELETE
  - URL：`/web/hindsight/documents/nonexistent-doc-id-99999`
- **步骤**：
  1. 发送 DELETE 请求
  2. 检查返回 404/400/500
- **预期结果**：返回错误

---

### TC-HINDSIGHT-012：获取文档分块（正向）

- **前置条件**：已登录，Hindsight 已启用，有文档数据
- **请求信息**：
  - 方法：GET
  - URL：`/web/hindsight/documents/{doc_id}/chunks`
- **步骤**：
  1. 列出文档取第一个 ID
  2. GET 获取分块
  3. 检查返回非空
- **预期结果**：返回文档分块数据

---

### TC-HINDSIGHT-013：列中心智模型（正向）

- **前置条件**：已登录，Hindsight 已启用
- **请求信息**：
  - 方法：GET
  - URL：`/web/hindsight/mental-models`
- **步骤**：
  1. 发送 GET 请求
  2. 检查 `items` 为数组
- **预期结果**：返回 `{items: [...]}`

---

### TC-HINDSIGHT-014：获取心智模型详情（正向）

- **前置条件**：已登录，Hindsight 已启用，有心智模型数据
- **请求信息**：
  - 方法：GET
  - URL：`/web/hindsight/mental-models/{model_id}`
- **步骤**：
  1. 列中心智模型取第一个 ID
  2. GET 查详情
  3. 检查返回非空
- **预期结果**：返回心智模型详情

---

### TC-HINDSIGHT-015：删除不存在的心智模型（异常）

- **前置条件**：已登录，Hindsight 已启用
- **请求信息**：
  - 方法：DELETE
  - URL：`/web/hindsight/mental-models/nonexistent-model-id-99999`
- **步骤**：
  1. 发送 DELETE 请求
  2. 检查返回 404/400/500
- **预期结果**：返回错误

---

### TC-HINDSIGHT-016：列出实体（正向）

- **前置条件**：已登录，Hindsight 已启用
- **请求信息**：
  - 方法：GET
  - URL：`/web/hindsight/entities`
- **步骤**：
  1. 发送 GET 请求
  2. 检查 `items` 为数组、`total` 为整数
- **预期结果**：返回 `{items: [...], total: N}`

---

### TC-HINDSIGHT-017：获取实体详情（正向）

- **前置条件**：已登录，Hindsight 已启用，有实体数据
- **请求信息**：
  - 方法：GET
  - URL：`/web/hindsight/entities/{entity_id}`
- **步骤**：
  1. 列出实体取第一个 ID
  2. GET 查详情
  3. 检查返回非空
- **预期结果**：返回实体详情

---

### TC-HINDSIGHT-018：获取不存在的实体（异常）

- **前置条件**：已登录，Hindsight 已启用
- **请求信息**：
  - 方法：GET
  - URL：`/web/hindsight/entities/nonexistent-entity-id-99999`
- **步骤**：
  1. 发送 GET 请求
  2. 检查返回 404/400/500
- **预期结果**：返回错误

---

### TC-HINDSIGHT-019：获取实体关系图谱（正向）

- **前置条件**：已登录，Hindsight 已启用
- **请求信息**：
  - 方法：GET
  - URL：`/web/hindsight/entities/graph`
- **步骤**：
  1. 发送 GET 请求
  2. 检查返回非空
- **预期结果**：返回实体关系图谱数据
