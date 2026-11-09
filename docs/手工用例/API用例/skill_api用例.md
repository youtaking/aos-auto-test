> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

# Skill 模块 API 手工测试用例

## 模块：Skill Web API

### TC-SKILL-001：获取 Skill 列表（正向）

- **前置条件**：已登录，有访问权限
- **请求信息**：
  - 方法：GET
  - URL：`/web/config/skills`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 200
  3. 检查 `data.skills` 字段为数组
- **预期结果**：返回 `{success: true, data: {skills: [...]}}`

---

### TC-SKILL-002：获取单个 Skill 详情（正向）

- **前置条件**：已登录，Skill 列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/web/config/skills/{skillId}`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 先调用列表接口获取第一个 Skill 的 name，解析出资源 ID
  2. 用该 ID 发送 GET 请求
  3. 检查 `data.name` 与请求的 name 一致
  4. 检查 `data.content` 或 `data.description` 存在
- **预期结果**：返回 Skill 详情对象

---

### TC-SKILL-003：创建并删除 Skill（正向 CRUD）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST（创建）+ GET（验证）+ DELETE（删除）
  - URL：`/web/config/skills` / `/web/config/skills/{skillId}`
  - Body（创建）：
    ```json
    {
      "name": "api-test-web-skill-001",
      "data": {
        "description": "Web API 测试自动创建的 Skill",
        "content": "# Test Skill\nThis is a test skill."
      }
    }
    ```
- **步骤**：
  1. POST 创建 Skill
  2. 检查返回 name 与请求一致
  3. GET 验证创建成功
  4. DELETE 删除
  5. GET 验证资源已消失
- **预期结果**：完整创建→验证→删除生命周期正常

---

### TC-SKILL-004：更新 Skill（正向）

- **前置条件**：已登录，已创建测试 Skill
- **请求信息**：
  - 方法：PATCH
  - URL：`/web/config/skills/{skillId}`
  - Body：
    ```json
    {
      "data": {
        "description": "updated by web api test",
        "content": "# Updated Content"
      }
    }
    ```
- **步骤**：
  1. 创建测试 Skill
  2. PATCH 更新 description 和 content
  3. GET 验证 description 已更新
  4. 验证 name 未被清空
  5. 清理：删除测试 Skill
- **预期结果**：更新成功，name 保持不变

---

### TC-SKILL-005：获取不存在的 Skill（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/config/skills/nonexistent-skill-id-99999`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 404
- **预期结果**：返回 404 Not Found

---

### TC-SKILL-006：DELETE 幂等性

- **前置条件**：已登录
- **请求信息**：
  - 方法：DELETE × 2
  - URL：`/web/config/skills/{skillId}`
- **步骤**：
  1. 创建 Skill
  2. 第一次 DELETE 成功
  3. 第二次 DELETE，检查返回 404
- **预期结果**：第二次删除返回 404

---

## 模块：Skill OpenAPI（/api/v1/skills，API Key 认证）

> 说明：响应为 `{success, data}` 信封；删除返回 `data: null`。创建/覆盖走 multipart/form-data：`manifest`（JSON 字符串，`[{skillName, relativePath}]`）+ `files`（≥1）+ `overwrite`（"true"/"false"）；manifest 与 files 必须一一对应且包含 `relativePath == "SKILL.md"`。重复导入未指定 overwrite → 409 ALREADY_EXISTS；overwrite=true → 200 覆盖。

### TC-SKILL-007：获取 Skill 列表（正向，P0）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/v1/skills`
  - Headers：`Authorization: Bearer <API Key>`
- **步骤**：
  1. 发送 GET 请求
  2. 校验分页结构 `items/total/page/pageSize`
  3. 检查 `items` 为数组
- **预期结果**：返回 200 分页结构

---

### TC-SKILL-008：获取单个 Skill 详情（正向，P0）

- **前置条件**：已配置 API Key，Skill 列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/api/v1/skills/{skillId}`
- **步骤**：
  1. 列表接口取第一个 ID
  2. GET 查详情
  3. 校验详情结构
  4. 检查 `id` 与请求一致
- **预期结果**：返回 200 Skill 详情

---

### TC-SKILL-009：创建并删除 Skill（正向 CRUD，P0）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：POST → GET → DELETE → GET
  - URL：`/api/v1/skills` / `/api/v1/skills/{skillId}`
  - Body（multipart）：`manifest=[{"skillName":"api-test-openapi-skill-001","relativePath":"SKILL.md"}]`，`files=@<name>.md`（内容含 frontmatter name/description）
- **步骤**：
  1. POST 导入 Skill
  2. 校验详情结构，检查 name 一致
  3. GET 验证创建成功且含 `content`
  4. DELETE 删除（返回 null）
  5. 再次 GET，检查 404 NOT_FOUND
- **预期结果**：创建 201 → 读取 200 → 删除 200 → 读取 404 `NOT_FOUND`

---

### TC-SKILL-010：更新 Skill（正向，P1）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：PATCH
  - URL：`/api/v1/skills/{skillId}`
  - Body：`{"description": "updated by openapi test"}`
- **步骤**：
  1. 导入 Skill（description=original description）
  2. PATCH 更新 description
  3. 校验详情结构，检查 description 已更新
  4. GET 复查 description 已更新、name 未变
- **预期结果**：更新成功，name 保持不变

---

### TC-SKILL-011：获取不存在的 Skill（异常响应，P2）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/v1/skills/nonexistent-skill-id-99999`
- **步骤**：
  1. 发送 GET 请求
  2. 检查响应状态码为 404
  3. 检查 `error.code` 为 `NOT_FOUND`
- **预期结果**：返回 404 `NOT_FOUND`

---

### TC-SKILL-012：分页第 2 页（正向，P2）

- **前置条件**：已配置 API Key，Skill 总数 > 1
- **请求信息**：
  - 方法：GET
  - URL：`/api/v1/skills?page=2&pageSize=1`
- **步骤**：
  1. 获取第 1 页和第 2 页数据
  2. 校验第 2 页分页结构
  3. 检查 `page` 为 2
  4. 比较两页第一条 id 不重复
- **预期结果**：第 2 页与第 1 页数据不同

---

### TC-SKILL-013：重复导入同名 Skill（重复/幂等，P1）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：POST
  - URL：`/api/v1/skills`
  - Body（multipart）：同 TC-SKILL-009，skillName=`api-test-openapi-skill-dup`，不带 overwrite
- **步骤**：
  1. 首次导入成功
  2. 再次导入同名 Skill
  3. 检查响应状态码为 409
  4. 检查 `error.code` 为 `ALREADY_EXISTS`
- **预期结果**：返回 409 `ALREADY_EXISTS`

---

### TC-SKILL-014：overwrite 覆盖导入（正向，P1）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：POST
  - URL：`/api/v1/skills`
  - Body（multipart）：同 TC-SKILL-009，skillName=`api-test-openapi-skill-overwrite`，`overwrite=true`，第二次内容 description="second version"
- **步骤**：
  1. 首次导入（description="first version"）
  2. 再次导入（overwrite=true，description="second version"）
  3. 校验返回详情，检查 description 为 second version
  4. GET 复查内容已被替换
- **预期结果**：返回 200，内容被覆盖

---

### TC-SKILL-015：导入缺少 manifest（必填参数缺失，P2）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：POST
  - URL：`/api/v1/skills`
  - Body：multipart 仅 `files=@SKILL.md`
- **步骤**：
  1. 发送 POST 请求
  2. 检查响应状态码为 400
  3. 检查 `error.code` 为 `VALIDATION_ERROR`，message 含 `manifest`
- **预期结果**：返回 400 `VALIDATION_ERROR`

---

### TC-SKILL-016：导入缺少 files（必填参数缺失，P2）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：POST
  - URL：`/api/v1/skills`
  - Body：form-data 仅 `manifest=[{"skillName":"api-test-skill-no-files","relativePath":"SKILL.md"}]`
- **步骤**：
  1. 发送 POST 请求
  2. 检查响应状态码为 400
  3. 检查 `error.code` 为 `VALIDATION_ERROR`
- **预期结果**：返回 400 `VALIDATION_ERROR`

---

### TC-SKILL-017：manifest 非法 JSON（类型错误，P2）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：POST
  - URL：`/api/v1/skills`
  - Body：`manifest=not-a-json` + `files=@SKILL.md`
- **步骤**：
  1. 发送 POST 请求
  2. 检查响应状态码为 400
  3. 检查 `error.code` 为 `VALIDATION_ERROR`
- **预期结果**：返回 400 `VALIDATION_ERROR`

---

### TC-SKILL-018：PATCH 空 body（业务规则，P2）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：PATCH
  - URL：`/api/v1/skills/nonexistent-skill-id-99999`
  - Body：`{}`
- **步骤**：
  1. 发送 PATCH 请求
  2. 检查响应状态码为 400
  3. 检查 `error.code` 为 `VALIDATION_ERROR`
- **预期结果**：返回 400 `VALIDATION_ERROR`（schema 拒绝空更新）

---

### TC-SKILL-019：DELETE 幂等性（重复/幂等，P2）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：DELETE × 2
  - URL：`/api/v1/skills/{skillId}`
- **步骤**：
  1. 导入 Skill 并获取 id
  2. 第一次 DELETE 成功
  3. 第二次 DELETE，检查状态码 404、`error.code` 为 `NOT_FOUND`
- **预期结果**：第二次删除返回 404 `NOT_FOUND`

---

## 模块：Skill Download API

### TC-SKILL-020：无效 token 下载 Skill（异常）

- **前置条件**：已登录，Skill 列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/skills/{skill_name}/download?token=invalid-token-99999`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 从 Skill 列表获取第一个 skill_name
  2. 用无效 token 发送 GET 请求
  3. 检查响应状态码为 403
- **预期结果**：返回 403 Forbidden

---

### TC-SKILL-021：空 token 下载 Skill（边界）

- **前置条件**：已登录，Skill 列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/skills/{skill_name}/download?token=`
- **步骤**：
  1. 用空 token 发送 GET 请求
  2. 检查响应状态码为 400 或 403
- **预期结果**：返回 400（Zod 校验 min(1)）或 403

---

### TC-SKILL-022：缺少 token 下载 Skill（必填参数缺失）

- **前置条件**：无认证
- **请求信息**：
  - 方法：GET
  - URL：`/skills/test-skill/download`（无 token 参数）
- **步骤**：
  1. 不携带 token 参数发送 GET 请求
  2. 检查响应状态码为 400 或 403
- **预期结果**：返回 400/403 校验错误

---

### TC-SKILL-023：下载不存在的 Skill（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/skills/nonexistent-skill-99999/download?token=some-token`
- **步骤**：
  1. 用不存在的 skill name 发送 GET 请求
  2. 检查响应状态码为 403 或 404
- **预期结果**：token 校验先于 skill 查找，返回 403；或返回 404

---

### TC-SKILL-024：非法 skill name 下载（边界）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/skills/invalid..name/download?token=bad-token`
- **步骤**：
  1. 用非法 name 发送 GET 请求
  2. 检查响应状态码为 400/403/404
- **预期结果**：返回 400（name 校验）/403（token 校验）/404（not found）

---

### TC-SKILL-025：更新可见范围缺少 publicReadable（必填缺失）

- **前置条件**：已登录
- **请求信息**：
  - 方法：PATCH
  - URL：`/web/config/skills/nonexistent-skill/access`
  - Body：`{}`
- **步骤**：
  1. 发送 PATCH 请求
  2. 检查响应状态码为 400
  3. 检查 `error.code` 为 `VALIDATION_ERROR`
  4. 检查 `error.message` 包含 `publicReadable`
- **预期结果**：返回 400，且不落库

---

### TC-SKILL-026：下载 Skill 压缩包（正向）

- **前置条件**：已登录，技能列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/web/config/skills/{skill_id}/download`
- **步骤**：
  1. 列表取第一个技能 ID
  2. 发送 GET 请求
  3. 检查响应状态码为 200
  4. 检查响应体非空，前两字节为 `PK`
- **预期结果**：返回 zip 字节流
