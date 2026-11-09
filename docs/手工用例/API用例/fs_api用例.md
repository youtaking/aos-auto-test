> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

# FS（文件系统）模块 API 手工测试用例

## 模块：FS Web API

### TC-FS-001：获取 workspace 文件树（正向）

- **前置条件**：已登录，环境列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/web/environments/{env_id}/fs/tree`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 获取可用环境 ID
  2. 发送 GET 请求
  3. 检查响应包含 `paths` 字段
  4. 检查 `paths` 为数组
- **预期结果**：返回 `{paths: [...]}`，paths 为文件路径数组

---

### TC-FS-002：列出 workspace 目录（正向）

- **前置条件**：已登录，环境列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/web/environments/{env_id}/fs`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 获取可用环境 ID
  2. 发送 GET 请求
  3. 检查响应包含 `entries` 字段
  4. 检查 `entries` 为数组
- **预期结果**：返回 `{entries: [...]}`

---

### TC-FS-003：读取 workspace 文件（正向）

- **前置条件**：已登录，workspace 中有文件
- **请求信息**：
  - 方法：GET
  - URL：`/web/environments/{env_id}/fs/{file_path}`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 先获取文件树，找一个有扩展名的文件路径
  2. 发送 GET 请求读取该文件
  3. 检查响应包含 `content` 字段
  4. 检查 `content` 为字符串
- **预期结果**：返回 `{content: "..."}` 文件内容

---

### TC-FS-004：写入并删除 workspace 文件（正向 CRUD）

- **前置条件**：已登录，环境可用
- **请求信息**：
  - 方法：PUT（写入）+ DELETE（删除）
  - URL：`/web/environments/{env_id}/fs/api-test-fs-write.txt`
  - Body（写入）：`"fs-auto-test-content"`
- **步骤**：
  1. PUT 写入测试文件
  2. 检查返回为对象
  3. DELETE 删除测试文件
- **预期结果**：写入成功，清理删除成功

---

### TC-FS-005：创建 workspace 目录（正向）

- **前置条件**：已登录，环境可用
- **请求信息**：
  - 方法：POST
  - URL：`/web/environments/{env_id}/fs/mkdir`
  - Body：`{"path": "api-test-mkdir-dir"}`
- **步骤**：
  1. POST 创建目录
  2. 检查返回 `path` 与请求路径一致
  3. 清理：删除测试目录
- **预期结果**：返回 `{path: "api-test-mkdir-dir"}`

---

### TC-FS-006：重命名 workspace 文件（正向）

- **前置条件**：已登录，已创建测试文件
- **请求信息**：
  - 方法：POST
  - URL：`/web/environments/{env_id}/fs/rename`
  - Body：
    ```json
    {
      "oldPath": "api-test-rename-old.txt",
      "newPath": "api-test-rename-new.txt"
    }
    ```
- **步骤**：
  1. 先创建测试文件（oldPath）
  2. POST 重命名
  3. 检查返回 `oldPath` 和 `newPath` 与请求一致
  4. 清理：删除 newPath 文件
- **预期结果**：返回 `{oldPath: "...", newPath: "..."}`

---

### TC-FS-007：批量删除 workspace 文件（正向）

- **前置条件**：已登录，已创建多个测试文件
- **请求信息**：
  - 方法：DELETE
  - URL：`/web/environments/{env_id}/fs/batch`
  - Body：
    ```json
    {
      "paths": ["api-test-batch-1.txt", "api-test-batch-2.txt"]
    }
    ```
- **步骤**：
  1. 创建两个测试文件
  2. 发送批量 DELETE 请求
  3. 检查返回 `deleted` 为数组
- **预期结果**：返回 `{deleted: [...]}`

---

### TC-FS-008：删除不存在的文件（幂等）

- **前置条件**：已登录，环境可用
- **请求信息**：
  - 方法：DELETE
  - URL：`/web/environments/{env_id}/fs/nonexistent-file-xyz-99999.txt`
- **步骤**：
  1. 发送 DELETE 请求删除不存在的文件
  2. 检查返回 200（幂等删除）或 404
- **预期结果**：幂等删除返回 200 success 或 404 Not Found

---

### TC-FS-009：打包下载缺少 path 参数（必填缺失）

- **前置条件**：已登录，环境可用
- **请求信息**：
  - 方法：GET
  - URL：`/web/environments/{env_id}/fs/download-zip`（不带 path 查询参数）
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 400
  3. 检查 `error.type` 为 `validation_error`
  4. 检查 `error.message` 包含 `path`
- **预期结果**：返回 400，提示 path 查询参数必填

---

### TC-FS-010：打包下载 workspace 目录（正向）

- **前置条件**：已登录，环境文件服务可用
- **请求信息**：
  - 方法：GET
  - URL：`/web/environments/{env_id}/fs/download-zip?path=.`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 200（503 表示文件服务不可用，属环境前置，跳过）
  3. 检查响应为 zip 字节流，前两字节为 `PK`
- **预期结果**：返回非空 zip 文件
