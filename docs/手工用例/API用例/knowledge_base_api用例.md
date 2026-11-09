> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

# Knowledge Base OpenAPI 模块手工测试用例

## 模块：Knowledge Base OpenAPI（/api/v1/knowledge-bases，API Key 认证）

> 说明：响应为 `{success, data}` 信封，client 已解包为分页数据。

### TC-KBOPENAPI-001：获取知识库列表（正向，P0）

- **前置条件**：已配置 API Key
- **请求信息**：
  - 方法：GET
  - URL：`/api/v1/knowledge-bases`
  - Headers：`Authorization: Bearer {api_key}`
- **步骤**：
  1. 发送 GET 请求
  2. 校验分页结构 `items/total/page/pageSize`
  3. 检查 `items` 为数组
  4. 如有数据，检查每项为对象且 `id`、`name` 均为字符串
- **预期结果**：返回 200 分页结构 `{items: [...], total, page, pageSize}`
