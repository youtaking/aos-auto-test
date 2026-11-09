> ⚠️ 本文件由 api-test-from-code 自动生成，请勿手动编辑。每次运行会整体重新生成，手动添加的内容会丢失。

# Workflow Definition 高级接口 API 手工测试用例

## 模块：Workflow Def Draft/Publish API

### TC-WFDEFADV-001：保存工作流草稿（正向）

- **前置条件**：已登录
- **请求信息**：
  - 方法：PUT
  - URL：`/web/workflow-defs/{wf_id}/draft`
  - Headers：`Cookie: session=xxx`
  - Body：
    ```json
    {
      "yaml": "name: test-workflow\nsteps:\n  - id: step1\n    type: agent\n    agentId: test-agent\n"
    }
    ```
- **步骤**：
  1. POST 创建测试工作流定义
  2. PUT 保存草稿 YAML
  3. 检查返回为 null 或 dict
  4. DELETE 清理测试工作流
- **预期结果**：草稿保存成功

---

### TC-WFDEFADV-002：发布工作流版本（正向）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/workflow-defs/{wf_id}/publish`
  - Headers：`Cookie: session=xxx`
  - Body：`{}`
- **步骤**：
  1. POST 创建测试工作流定义
  2. POST 发布版本
  3. 检查返回为 null 或 dict（版本信息）
  4. DELETE 清理测试工作流
- **预期结果**：版本发布成功，返回版本信息或 null

---

### TC-WFDEFADV-003：获取指定版本 YAML 内容（正向）

- **前置条件**：已登录，有已发布版本的工作流定义
- **请求信息**：
  - 方法：GET
  - URL：`/web/workflow-defs/{wf_id}/versions/{version_tag}`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 获取工作流定义列表，取第一个 ID
  2. 获取该工作流的版本列表
  3. 取第一个版本标识
  4. GET 获取版本 YAML 内容
  5. 检查返回为 string 或 dict
- **预期结果**：返回版本 YAML 内容

---

### TC-WFDEFADV-004：设置指定版本为最新（正向）

- **前置条件**：已登录，有至少 2 个已发布版本的工作流定义
- **请求信息**：
  - 方法：POST
  - URL：`/web/workflow-defs/{wf_id}/versions/{version_tag}/set-latest`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 获取工作流定义列表，取第一个 ID
  2. 获取版本列表（至少 2 个版本）
  3. 取最后一个版本标识
  4. POST 设置该版本为最新
  5. 检查返回为 null 或 dict
- **预期结果**：版本设置成功

---

### TC-WFDEFADV-005：恢复指定版本为草稿（正向）

- **前置条件**：已登录，有已发布版本的工作流定义
- **请求信息**：
  - 方法：POST
  - URL：`/web/workflow-defs/{wf_id}/versions/{version_tag}/restore`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 获取工作流定义列表，取第一个 ID
  2. 获取版本列表
  3. 取第一个版本标识
  4. POST 恢复为草稿
  5. 检查返回为 null 或 dict
- **预期结果**：版本恢复为草稿成功

---

### TC-WFDEFADV-006：获取工作流参数定义（正向）

- **前置条件**：已登录，工作流定义列表非空
- **请求信息**：
  - 方法：GET
  - URL：`/web/workflow-defs/{wf_id}/params`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 获取工作流定义列表，取第一个 ID
  2. GET 获取参数定义
  3. 检查返回为 list 或 dict
- **预期结果**：返回参数定义列表

---

## 模块：Workflow Def Trigger API

### TC-WFDEFADV-007：创建触发器（正向）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/workflow-defs/{wf_id}/triggers`
  - Headers：`Cookie: session=xxx`
  - Body：
    ```json
    {
      "type": "cron",
      "config": {"schedule": "0 0 * * *"}
    }
    ```
- **步骤**：
  1. POST 创建测试工作流定义
  2. POST 创建 cron 触发器
  3. 检查返回 dict，包含 `id` 或 `triggerId` 字段
  4. DELETE 清理测试工作流
- **预期结果**：触发器创建成功，返回包含 ID 的触发器信息

---

### TC-WFDEFADV-008：删除触发器（正向）

- **前置条件**：已登录，已有创建的触发器
- **请求信息**：
  - 方法：DELETE
  - URL：`/web/workflow-defs/{wf_id}/triggers/{trigger_id}`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. POST 创建测试工作流定义
  2. POST 创建触发器，获取 trigger_id
  3. DELETE 删除触发器
  4. 检查返回为 null 或 dict
  5. DELETE 清理测试工作流
- **预期结果**：触发器删除成功

---

### TC-WFDEFADV-009：启用/禁用触发器（正向）

- **前置条件**：已登录，已有创建的触发器
- **请求信息**：
  - 方法：POST
  - URL（禁用）：`/web/workflow-defs/{wf_id}/triggers/{trigger_id}/disable`
  - URL（启用）：`/web/workflow-defs/{wf_id}/triggers/{trigger_id}/enable`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. POST 创建测试工作流定义
  2. POST 创建触发器，获取 trigger_id
  3. POST 禁用触发器
  4. POST 启用触发器
  5. DELETE 清理测试工作流
- **预期结果**：触发器禁用和启用均成功

---

### TC-WFDEFADV-010：重新生成触发器哈希（正向）

- **前置条件**：已登录，已有创建的 webhook 触发器
- **请求信息**：
  - 方法：POST
  - URL：`/web/workflow-defs/{wf_id}/triggers/{trigger_id}/regenerate`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. POST 创建测试工作流定义
  2. POST 创建 webhook 触发器，获取 trigger_id
  3. POST 重新生成哈希
  4. 检查返回 dict
  5. DELETE 清理测试工作流
- **预期结果**：触发器哈希重新生成成功

---

### TC-WFDEFADV-011：为不存在的工作流创建触发器（异常）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/workflow-defs/nonexistent-wf-99999/triggers`
  - Headers：`Cookie: session=xxx`
  - Body：
    ```json
    {
      "type": "cron",
      "config": {"schedule": "0 0 * * *"}
    }
    ```
- **步骤**：
  1. 用不存在的工作流 ID 发送 POST 请求
  2. 检查返回 404 或 400
- **预期结果**：返回 404/400 错误

---

## 模块：Workflow Def Recover API

### TC-WFDEFADV-012：获取可恢复工作流列表（正向）

- **前置条件**：已登录
- **请求信息**：
  - 方法：GET
  - URL：`/web/workflow-defs/recoverable`
  - Headers：`Cookie: session=xxx`
- **步骤**：
  1. 发送 GET 请求
  2. 检查返回为数组
- **预期结果**：返回可恢复工作流列表（数组）

---

### TC-WFDEFADV-013：确认恢复工作流（正向）

- **前置条件**：已登录，有可恢复的工作流
- **请求信息**：
  - 方法：POST
  - URL：`/web/workflow-defs/recover`
  - Headers：`Cookie: session=xxx`
  - Body：`{"workflowIds": ["{wf_id}"]}`
- **步骤**：
  1. GET 获取可恢复工作流列表
  2. 取第一个工作流 ID
  3. POST 确认恢复
  4. 检查返回为 dict/list/None
- **预期结果**：恢复成功

---

### TC-WFDEFADV-014：空列表恢复工作流（边界）

- **前置条件**：已登录
- **请求信息**：
  - 方法：POST
  - URL：`/web/workflow-defs/recover`
  - Headers：`Cookie: session=xxx`
  - Body：`{"workflowIds": []}`
- **步骤**：
  1. POST 发送空 workflowIds 数组
  2. 检查返回成功（no-op）或 400
- **预期结果**：返回成功（无操作）或 400 参数错误
