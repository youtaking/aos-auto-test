# Staging 环境自动回归测试

## 概述

监控长期测试环境（`http://100.105.9.16:38879`）的 `/health` 端点，检测到新代码部署后自动触发回归测试。

## 背景

PR Pipeline 针对临时环境（自己 build + deploy），Staging Monitor 针对长期测试环境（别人部署的）。开发部署新功能到测试环境后，自动跑回归测试验证。

## 架构

```
Jenkins Job (每 30 分钟)
  ↓
轮询 TARGET_URL + HEALTH_PATH
  ↓
对比上次响应（hash）
  ↓
有变化 → 调 AutoTest API 拿用例 → spawn test-runner → 跑测试 → 上报结果
```

## 配置分工

| 配置项 | 位置 | 说明 |
|--------|------|------|
| HEALTH_URL | Jenkins job 参数 | 健康检查完整 URL |
| TARGET_URL | Jenkins job 参数 | 测试目标地址 |
| POLL_INTERVAL | Jenkins job 参数 | 轮询间隔（分钟） |
| staging_collection_ids | AutoTest CIConfig | Staging 测试集 ID 数组 |

## 组件

### 1. 后端：CIConfig 扩展

**文件**：`backend/db/models.py`

```python
class CIConfig(Base):
    # ... 现有字段 ...
    staging_collection_ids = Column(JSON, nullable=True)  # Staging 测试集 ID 数组
```

**迁移**：
```sql
ALTER TABLE ci_configs ADD COLUMN staging_collection_ids JSON;
```

### 1b. 后端：PRPipeline 模型调整

**文件**：`backend/db/models.py`

Staging 复用 PRPipeline 记录，需调整字段：

```python
class PRPipeline(Base):
    # pr_id 改成 nullable，staging 没有 PR
    pr_id = Column(Integer, nullable=True)  # 原为 nullable=False
```

**Staging 记录字段映射**：

| PRPipeline 字段 | Staging 来源 |
|----------------|--------------|
| `commit_sha` | `/health` → `commitId` |
| `branch` | 固定 `"staging"` |
| `pr_id` | `null` |
| `pr_title` | `"Staging: v{version}"` |
| `author` | `"system"` |
| `target_url` | Jenkins 参数 `TARGET_URL` |
| `build_info` | `{version, startedAt, commitId}` |
| `status` | `"running"` → `"passed"/"failed"` |

**迁移**：
```sql
ALTER TABLE pr_pipelines ALTER COLUMN pr_id DROP NOT NULL;
```

### 2. 后端：Staging Resolve API

**文件**：`backend/api/ci.py`

**端点**：`GET /api/ci/staging-resolve-tests`

**逻辑**：
1. 读取 `CIConfig.staging_collection_ids`
2. 查询 TestCollection，合并所有 case_ids
3. 查询 TestCase，生成 pytest node IDs
4. 返回 `{"node_ids": [...]}`

**响应格式**（同 `/api/ci/resolve-tests`）：
```json
{
  "success": true,
  "data": {
    "node_ids": [
      "tests/suites/test_auth.py::test_auth_001_login_success",
      "tests/api_suites/test_agent_api.py::TestAgentWebAPI::test_list_agents"
    ]
  }
}
```

### 3. 前端：CIConfigModal 扩展

**文件**：`frontend/src/components/CIConfigModal.tsx`

**改动**：
- 加 "Staging 测试集" 区域（与 PR 测试集选择器并列）
- 读写 `staging_collection_ids` 字段

### 3b. 前端：PRPipeline 页面适配 Staging 记录

**文件**：`frontend/src/pages/PRPipeline.tsx`

**改动**：
- 表格根据 `branch === "staging"` 显示不同内容
- Staging 记录：`pr_id` 列显示 "Staging"，`commit_sha` 正常显示，`branch` 显示 "staging"
- 可加筛选器：全部 / PR / Staging

### 4. Jenkins：Staging Monitor 脚本

**文件**：`docs/jenkins-staging-monitor.groovy`

**Job 参数**：
```groovy
parameters {
    string(name: 'HEALTH_URL', defaultValue: 'http://100.105.9.16:38879/health', description: '健康检查完整 URL')
    string(name: 'TARGET_URL', defaultValue: 'http://100.105.9.16:38879', description: '测试目标地址')
    string(name: 'POLL_INTERVAL', defaultValue: '30', description: '轮询间隔（分钟）')
    string(name: 'AUTOTEST_URL', defaultValue: 'http://100.105.181.173:8111')
    string(name: 'TEST_REPO', defaultValue: 'https://github.com/youtaking/aos-auto-test.git')
    string(name: 'TEST_REPO_BRANCH', defaultValue: 'feat/jenkins-pipeline')
}
```

**流程**：
1. **Check Runner Images**：检查 `test-runner:latest`，没有就 build
2. **Poll Health**：`curl HEALTH_URL`，对比 `commitId` 与上次记录
3. **Create Pipeline Record**（有变化时）：调 `POST /api/pipelines` 创建 staging 记录
4. **Resolve Tests**：调 `AUTOTEST_URL/api/ci/staging-resolve-tests`
   - Fallback 1：读 `autotest/tests/ci/staging-cases.txt`
   - Fallback 2：跑全部 `/app/tests/suites /app/tests/api_suites`
5. **Run Tests**：spawn test-runner 容器，目标地址用 Jenkins 参数 `TARGET_URL`
6. **Upload Results**：结果上报 AutoTest，更新 pipeline 状态

**test-runner 容器配置**：
```yaml
test-runner:
  image: test-runner:latest
  volumes:
    - autotest/tests:/app/tests
    - autotest/conftest.py:/app/conftest.py
    - autotest/pytest.ini:/app/pytest.ini
  environment:
    FENIX_URL: ${TARGET_URL}
    FENIX_API_BASE_URL: ${TARGET_URL}
    HEADLESS: "true"
    PYTHONUNBUFFERED: "1"
  command: 'pytest ${TEST_TARGETS} -v --tb=short --base-url=${TARGET_URL} --json-report'
```

**Health 对比逻辑**：
```bash
HEALTH_RESP=$(curl -s $HEALTH_URL)
CURRENT_COMMIT=$(echo "$HEALTH_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('commitId',''))")
LAST_COMMIT=$(cat .last_commit_id 2>/dev/null || echo "")
if [ -n "$CURRENT_COMMIT" ] && [ "$CURRENT_COMMIT" != "$LAST_COMMIT" ]; then
    echo "Commit changed: $LAST_COMMIT → $CURRENT_COMMIT"
    echo "$CURRENT_COMMIT" > .last_commit_id
    # ... run tests ...
fi
```

## 数据流

```
Jenkins                    AutoTest Backend              Test Environment
  │                              │                              │
  ├── curl /health ────────────────────────────────────────────>│
  │<── health response ─────────────────────────────────────────│
  │                              │                              │
  ├── GET /staging-resolve ────>│                              │
  │<── node_ids ─────────────────│                              │
  │                              │                              │
  ├── spawn test-runner ───────────────────────────────────────>│
  │   (TARGET_URL, node_ids)     │                              │
  │<── test results ────────────────────────────────────────────│
  │                              │                              │
  ├── POST /runs ──────────────>│                              │
  │                              │                              │
```

## 错误处理

- **Health 端点不可达**：跳过本次轮询，下次重试
- **AutoTest API 不可达**：走 fallback（cases.txt → 全部）
- **测试执行失败**：正常上报失败结果，不阻塞下次轮询

## 验收标准

1. Jenkins job 每 30 分钟轮询一次
2. `/health` 响应变化时触发测试
3. 测试用例从 `staging_collection_ids` 读取
4. 前端 CI 配置可选择 Staging 测试集
5. 测试结果上报到 AutoTest
