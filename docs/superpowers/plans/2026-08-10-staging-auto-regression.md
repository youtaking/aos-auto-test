# Staging 环境自动回归测试 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Jenkins 轮询测试环境 `/health` 端点，检测到新部署（commitId 变化）后自动触发回归测试，结果上报 AutoTest。

**Architecture:** Jenkins 定时 Job 轮询目标环境 `/health`，对比 commitId 发现新版本后，调 AutoTest API 解析测试用例、spawn test-runner 容器执行测试、上报结果。后端复用 PRPipeline 模型（branch="staging", pr_id=null），前端 CIConfig 扩展 staging_collection_ids 字段。

**Tech Stack:** Python/FastAPI + SQLAlchemy, React/TypeScript, Jenkins Pipeline Groovy

## Global Constraints

- CIConfig 新增字段 `staging_collection_ids: JSON nullable`
- PRPipeline.pr_id 改为 nullable（当前为 nullable=False）
- Jenkins 参数：`HEALTH_URL`（完整健康检查 URL）、`TARGET_URL`（测试目标地址）分开
- Health 响应对比字段：`commitId`
- Staging 记录标识：`branch="staging"`、`pr_id=null`

---

### Task 1: 数据库迁移 — PRPipeline.pr_id 改 nullable + CIConfig 加字段

**Files:**
- Modify: `backend/db/models.py:205`（PRPipeline.pr_id）
- Modify: `backend/db/models.py:255-268`（CIConfig）
- Create: SQL 迁移脚本（手动执行）

**Interfaces:**
- Produces: `CIConfig.staging_collection_ids: JSON nullable`
- Produces: `PRPipeline.pr_id: Integer nullable=True`

- [ ] **Step 1: 修改 PRPipeline 模型**

`backend/db/models.py` 第 205 行：

```python
# 改前
pr_id = Column(Integer, nullable=False)

# 改后
pr_id = Column(Integer, nullable=True)
```

- [ ] **Step 2: CIConfig 模型新增 staging_collection_ids**

`backend/db/models.py`，在 `collection_ids` 字段后追加：

```python
class CIConfig(Base):
    # ... 现有字段 ...
    collection_ids = Column(JSON, nullable=True)
    staging_collection_ids = Column(JSON, nullable=True)  # Staging 测试集 ID 数组
```

- [ ] **Step 3: 生成并执行数据库迁移 SQL**

在 PostgreSQL 中执行：

```sql
ALTER TABLE pr_pipelines ALTER COLUMN pr_id DROP NOT NULL;
ALTER TABLE ci_configs ADD COLUMN staging_collection_ids JSON;
```

- [ ] **Step 4: 重启后端验证**

```bash
# 重启后端服务
cd /path/to/AgentTest
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8111
```

确认无报错后，访问 `/api/ci/config` 响应中包含 `staging_collection_ids: null`。

- [ ] **Step 5: Commit**

```bash
git add backend/db/models.py
git commit -m "feat: CIConfig add staging_collection_ids, PRPipeline.pr_id nullable"
```

---

### Task 2: 后端 Schema — CIConfigUpdate/Response + CreatePipelineRequest 支持 staging

**Files:**
- Modify: `backend/schemas/ci.py`

**Interfaces:**
- Consumes: Task 1 的 CIConfig.staging_collection_ids 字段
- Produces: `CIConfigResponse.staging_collection_ids`, `CIConfigUpdate.staging_collection_ids`
- Produces: `CreatePipelineRequest.pr_id: Optional[int]`

- [ ] **Step 1: CIConfigResponse 加 staging_collection_ids**

`backend/schemas/ci.py`，`CIConfigResponse` 类：

```python
class CIConfigResponse(BaseModel):
    # ... 现有字段 ...
    collection_ids: Optional[List[int]] = None
    staging_collection_ids: Optional[List[int]] = None   # 新增
```

- [ ] **Step 2: CIConfigUpdate 加 staging_collection_ids**

```python
class CIConfigUpdate(BaseModel):
    # ... 现有字段 ...
    collection_ids: Optional[List[int]] = None
    staging_collection_ids: Optional[List[int]] = None   # 新增
```

- [ ] **Step 3: CreatePipelineRequest.pr_id 改 Optional**

```python
class CreatePipelineRequest(BaseModel):
    pr_id: Optional[int] = None   # 改前为 int，staging 无 PR
    # 其余字段不变
```

- [ ] **Step 4: PipelineResponse.pr_id 改 Optional**

```python
class PipelineResponse(BaseModel):
    pr_id: Optional[int] = None   # 改前为 int
    # 其余字段不变
```

- [ ] **Step 5: Commit**

```bash
git add backend/schemas/ci.py
git commit -m "feat: schema support staging_collection_ids and nullable pr_id"
```

---

### Task 3: 后端 API — CI Config 读写 staging_collection_ids

**Files:**
- Modify: `backend/api/ci.py`（update_ci_config 函数）

**Interfaces:**
- Consumes: CIConfigUpdate.staging_collection_ids
- Produces: CIConfig API 响应包含 staging_collection_ids

- [ ] **Step 1: 找到 update_ci_config 函数**

在 `backend/api/ci.py` 中找到 `PUT /ci/config` 端点，查看它如何处理 `collection_ids` 字段。

- [ ] **Step 2: 添加 staging_collection_ids 处理**

在 `update_ci_config` 函数中，找到 `config.collection_ids = body.collection_ids` 这类代码，在其后追加：

```python
if body.staging_collection_ids is not None:
    config.staging_collection_ids = body.staging_collection_ids
```

- [ ] **Step 3: 验证 API 响应**

重启后端，`GET /api/ci/config` 返回体中包含 `staging_collection_ids` 字段。

```bash
curl -s http://localhost:8111/api/ci/config | python -m json.tool
```

- [ ] **Step 4: Commit**

```bash
git add backend/api/ci.py
git commit -m "feat: CI config API reads/writes staging_collection_ids"
```

---

### Task 4: 后端 API — staging-resolve-tests 端点

**Files:**
- Modify: `backend/api/ci.py`

**Interfaces:**
- Consumes: CIConfig.staging_collection_ids
- Produces: `GET /api/ci/staging-resolve-tests` → `{"data": {"node_ids": [...]}}`

- [ ] **Step 1: 添加 staging-resolve-tests 端点**

在 `backend/api/ci.py` 的 `resolve_tests` 函数后面添加：

```python
@router.get("/ci/staging-resolve-tests", response_model=ApiResponse)
async def staging_resolve_tests(db: AsyncSession = Depends(get_async_session)):
    """根据 CI 配置的 Staging 用例集，解析出 pytest node ID 列表"""
    config = await _get_ci_config(db)

    if not config.staging_collection_ids:
        return ApiResponse(data={"node_ids": []})

    # 查询用例集，合并所有 case_ids
    result = await db.execute(
        select(TestCollection).where(TestCollection.id.in_(config.staging_collection_ids))
    )
    collections = result.scalars().all()

    all_case_ids: set[int] = set()
    for c in collections:
        if c.case_ids:
            all_case_ids.update(c.case_ids)

    if not all_case_ids:
        return ApiResponse(data={"node_ids": []})

    # 查询 TestCase，生成 pytest node IDs
    cases_result = await db.execute(
        select(TestCase).where(TestCase.id.in_(list(all_case_ids)))
    )
    cases = cases_result.scalars().all()

    node_ids = [f"{c.file_path}::{c.function_name}" for c in cases]
    return ApiResponse(data={"node_ids": node_ids})
```

- [ ] **Step 2: 手动验证端点**

重启后端，调用端点：

```bash
curl -s http://localhost:8111/api/ci/staging-resolve-tests
# 预期：{"success": true, "data": {"node_ids": []}}（未配置 staging_collection_ids 时）
```

- [ ] **Step 3: Commit**

```bash
git add backend/api/ci.py
git commit -m "feat: add /api/ci/staging-resolve-tests endpoint"
```

---

### Task 5: 前端类型 — CIConfig 和 Pipeline 类型更新

**Files:**
- Modify: `frontend/src/api/types.ts`

**Interfaces:**
- Consumes: Task 2 的 Schema 变更
- Produces: 前端类型定义与后端一致

- [ ] **Step 1: CIConfig 类型加 staging_collection_ids**

`frontend/src/api/types.ts`，`CIConfig` interface：

```typescript
export interface CIConfig {
  // ... 现有字段 ...
  collection_ids: number[] | null;
  staging_collection_ids: number[] | null;  // 新增
  created_at: string;
  updated_at: string;
}
```

- [ ] **Step 2: Pipeline 类型 pr_id 改可选**

```typescript
export interface Pipeline {
  // ...
  pr_id: number | null;   // 改前为 number，staging 时为 null
  // ...
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/types.ts
git commit -m "feat: frontend types support staging_collection_ids and nullable pr_id"
```

---

### Task 6: 前端 CIConfigModal — Staging 测试集选择区域

**Files:**
- Modify: `frontend/src/components/CIConfigModal.tsx`

**Interfaces:**
- Consumes: CIConfig.staging_collection_ids, Collection[]
- Produces: UI 可读写 staging_collection_ids

- [ ] **Step 1: 新增 stagingCollectionIds state**

`CIConfigModal.tsx`，在 `selectedCollectionIds` state 后追加：

```typescript
const [stagingCollectionIds, setStagingCollectionIds] = useState<number[]>([]);
```

- [ ] **Step 2: load 函数中读取 staging_collection_ids**

在 `getCIConfig().then(...)` 回调中追加：

```typescript
const load = () => {
  getCIConfig().then((c) => {
    setConfig(c);
    if (c.collection_ids) setSelectedCollectionIds(c.collection_ids);
    if (c.staging_collection_ids) setStagingCollectionIds(c.staging_collection_ids);  // 新增
  }).catch(console.error);
  listCollections().then(setCollections).catch(console.error);
};
```

- [ ] **Step 3: handleSave 中提交 staging_collection_ids**

```typescript
const handleSave = async () => {
  if (!config) return;
  setSaving(true);
  try {
    await updateCIConfig({
      timeout_minutes: config.timeout_minutes,
      max_queue_size: config.max_queue_size,
      collection_ids: selectedCollectionIds.length > 0 ? selectedCollectionIds : null,
      staging_collection_ids: stagingCollectionIds.length > 0 ? stagingCollectionIds : null,  // 新增
    });
    onClose();
  } catch (e) {
    console.error(e);
  } finally {
    setSaving(false);
  }
};
```

- [ ] **Step 4: UI 增加 Staging 测试集区域**

在 "CI 运行用例集" 区域的 `</div>` 闭合标签后，"认证 Token" 之前，插入：

```tsx
<div>
  <label className="block text-sm font-medium mb-1">Staging 测试集</label>
  <p className="text-xs text-gray-400 mb-1">Staging 环境自动回归时执行的用例集</p>
  {collections.length === 0 ? (
    <p className="text-xs text-gray-400">暂无用例集，请先在用例管理页创建</p>
  ) : (
    <div className="space-y-1 max-h-32 overflow-y-auto border rounded p-2">
      {collections.map(c => (
        <label key={c.id} className="flex items-center gap-2 text-sm">
          <input type="checkbox"
            checked={stagingCollectionIds.includes(c.id)}
            onChange={e => {
              if (e.target.checked) setStagingCollectionIds(prev => [...prev, c.id]);
              else setStagingCollectionIds(prev => prev.filter(id => id !== c.id));
            }} />
          {c.name} <span className="text-gray-400">({c.case_ids.length} 用例)</span>
        </label>
      ))}
    </div>
  )}
</div>
```

- [ ] **Step 5: 本地验证**

```bash
cd frontend && npm run dev
```

打开 CI 配置弹窗，确认 "Staging 测试集" 区域与 "CI 运行用例集" 并列显示，勾选/取消勾选后保存成功。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/CIConfigModal.tsx
git commit -m "feat: CIConfigModal add Staging test set selection area"
```

---

### Task 7: 前端 PRPipeline 页面 — 适配 Staging 记录

**Files:**
- Modify: `frontend/src/pages/PRPipeline.tsx`

**Interfaces:**
- Consumes: Pipeline.pr_id 可为 null, Pipeline.branch === "staging"
- Produces: Staging 记录在表格中正确展示

- [ ] **Step 1: PR 列适配 staging**

`PRPipeline.tsx`，表格 `<td>` 的 PR 列（第 162-165 行附近），替换为：

```tsx
<td className="px-4 py-3">
  {p.branch === "staging" ? (
    <div>
      <div className="font-medium text-purple-600">Staging</div>
      <div className="text-xs text-gray-500 truncate max-w-[200px]">{p.pr_title}</div>
    </div>
  ) : (
    <div>
      <div className="font-medium">#{p.pr_id}</div>
      <div className="text-xs text-gray-500 truncate max-w-[200px]">{p.pr_title}</div>
    </div>
  )}
</td>
```

- [ ] **Step 2: 分支列样式区分**

分支列（第 169 行附近），替换为：

```tsx
<td className="px-4 py-3">
  <span className={`text-xs px-1.5 py-0.5 rounded ${
    p.branch === "staging" ? "bg-purple-100 text-purple-700" : "text-gray-600"
  }`}>
    {p.branch}
  </span>
</td>
```

- [ ] **Step 3: 增加类型筛选器**

在 `statusFilters` 数组后面新增：

```typescript
const typeFilters = [
  { key: "", label: "全部类型" },
  { key: "pr", label: "PR" },
  { key: "staging", label: "Staging" },
];
```

- [ ] **Step 4: 增加类型筛选 state 和逻辑**

```typescript
const [typeFilter, setTypeFilter] = useState("");
```

在 `load` 函数中，传入 `branch` 参数（如果后端支持按 branch 筛选的话），或在前端做 client-side 过滤：

在 `pipelines.map(...)` 前加前端过滤：

```typescript
const filteredPipelines = typeFilter
  ? pipelines.filter(p => typeFilter === "staging" ? p.branch === "staging" : p.branch !== "staging")
  : pipelines;
```

表格 `tbody` 改为遍历 `filteredPipelines`。

- [ ] **Step 5: 渲染类型筛选按钮**

在状态筛选按钮行后面增加：

```tsx
<div className="flex items-center gap-1 ml-4 pl-4 border-l">
  {typeFilters.map((f) => (
    <button
      key={f.key}
      onClick={() => setTypeFilter(f.key)}
      className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
        typeFilter === f.key
          ? "bg-purple-600 text-white"
          : "text-gray-600 hover:bg-gray-100"
      }`}
    >
      {f.label}
    </button>
  ))}
</div>
```

- [ ] **Step 6: 本地验证**

启动前端，打开 PR Pipeline 页面，确认：
- Staging 记录（如有）PR 列显示紫色 "Staging" 文字
- 类型筛选器可切换 PR / Staging / 全部

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/PRPipeline.tsx
git commit -m "feat: PRPipeline page adapts for staging records"
```

---

### Task 8: Jenkins 脚本 — jenkins-staging-monitor.groovy

**Files:**
- Create: `docs/jenkins-staging-monitor.groovy`

**Interfaces:**
- Consumes: `HEALTH_URL`, `TARGET_URL`, `POLL_INTERVAL`, `AUTOTEST_URL`, `TEST_REPO`, `TEST_REPO_BRANCH`
- Consumes: `GET /api/ci/staging-resolve-tests` → node_ids
- Consumes: `POST /api/pipelines` → pipeline_id
- Consumes: `PUT /api/pipelines/{id}/status`
- Consumes: `POST /api/pipelines/{id}/results`
- Produces: test-runner 容器在 Jenkins 机器上执行测试

- [ ] **Step 1: 写 pipeline 头部和参数定义**

创建 `docs/jenkins-staging-monitor.groovy`：

```groovy
pipeline {
    agent any

    parameters {
        string(name: 'HEALTH_URL',      defaultValue: 'http://100.105.9.16:38879/health', description: '健康检查完整 URL')
        string(name: 'TARGET_URL',      defaultValue: 'http://100.105.9.16:38879',        description: '测试目标地址')
        string(name: 'POLL_INTERVAL',   defaultValue: '30',                                description: '轮询间隔（分钟）')
        string(name: 'AUTOTEST_URL',    defaultValue: 'http://100.105.181.173:8111',      description: 'AutoTest 后端地址')
        string(name: 'TEST_REPO',       defaultValue: 'https://github.com/youtaking/aos-auto-test.git', description: '测试代码仓库')
        string(name: 'TEST_REPO_BRANCH', defaultValue: 'feat/jenkins-pipeline',            description: '测试代码分支')
    }

    environment {
        AUTOTEST_URL    = "${params.AUTOTEST_URL}"
        TARGET_URL      = "${params.TARGET_URL}"
        HEALTH_URL      = "${params.HEALTH_URL}"
    }

    triggers {
        cron("H/${params.POLL_INTERVAL ?: '30'} * * * *")
    }
```

- [ ] **Step 2: Check Runner Images stage**

```groovy
    stages {
        stage('Check Runner Images') {
            steps {
                sh '''
                    set +x
                    echo "============================================================"
                    echo "[Staging Monitor] Check Runner Images"
                    echo "============================================================"

                    if docker image inspect test-runner:latest > /dev/null 2>&1; then
                        echo ">>> test-runner:latest exists."
                    else
                        echo ">>> test-runner:latest not found, building..."
                        # 先拉测试代码
                        rm -rf /tmp/staging-autotest
                        mkdir -p /tmp/staging-autotest
                        ARCHIVE_URL="__TEST_REPO__/.git/archive/refs/heads/__TEST_BRANCH__.tar.gz"
                        curl -sSL "${ARCHIVE_URL}" -o /tmp/autotest.tar.gz || true
                        if [ -f /tmp/autotest.tar.gz ] && [ -s /tmp/autotest.tar.gz ]; then
                            tar xzf /tmp/autotest.tar.gz --strip-components=1 -C /tmp/staging-autotest
                        fi
                        if [ -f /tmp/staging-autotest/Dockerfile.runner ]; then
                            docker build -t test-runner:latest -f /tmp/staging-autotest/Dockerfile.runner /tmp/staging-autotest/
                        fi
                        rm -rf /tmp/staging-autotest /tmp/autotest.tar.gz
                    fi
                '''.replace('__TEST_REPO__', params.TEST_REPO.replace('.git', ''))
                  .replace('__TEST_BRANCH__', params.TEST_REPO_BRANCH ?: 'feat/jenkins-pipeline')
            }
        }
```

- [ ] **Step 3: Poll Health stage**

```groovy
        stage('Poll Health') {
            steps {
                sh '''
                    set +x
                    echo "============================================================"
                    echo "[Staging Monitor] Poll Health"
                    echo "  HEALTH_URL: __HEALTH_URL__"
                    echo "============================================================"

                    HEALTH_RESP=$(curl -sf --connect-timeout 10 --max-time 15 "__HEALTH_URL__" 2>/dev/null || echo "")

                    if [ -z "$HEALTH_RESP" ]; then
                        echo ">>> Health endpoint unreachable, skipping this poll."
                        echo "SKIP" > .poll_result
                        exit 0
                    fi

                    echo ">>> Health response: $HEALTH_RESP"

                    CURRENT_COMMIT=$(echo "$HEALTH_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('commitId',''))" 2>/dev/null || echo "")
                    CURRENT_VERSION=$(echo "$HEALTH_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('version',''))" 2>/dev/null || echo "")
                    STARTED_AT=$(echo "$HEALTH_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('startedAt',''))" 2>/dev/null || echo "")

                    if [ -z "$CURRENT_COMMIT" ]; then
                        echo ">>> No commitId in health response, skipping."
                        echo "SKIP" > .poll_result
                        exit 0
                    fi

                    LAST_COMMIT=$(cat .last_commit_id 2>/dev/null || echo "")

                    if [ "$CURRENT_COMMIT" = "$LAST_COMMIT" ]; then
                        echo ">>> No change: commitId=$CURRENT_COMMIT (same as last poll)"
                        echo "SKIP" > .poll_result
                        exit 0
                    fi

                    echo ">>> Commit changed: $LAST_COMMIT → $CURRENT_COMMIT"
                    echo "$CURRENT_COMMIT" > .last_commit_id

                    # 保存环境信息供后续 stage 使用
                    echo "$CURRENT_COMMIT" > .current_commit
                    echo "$CURRENT_VERSION" > .current_version
                    echo "$STARTED_AT" > .started_at
                    echo "$HEALTH_RESP" > .health_resp
                    echo "CHANGED" > .poll_result
                '''.replace('__HEALTH_URL__', params.HEALTH_URL)
            }
        }
```

- [ ] **Step 4: Clone Test Code stage**

```groovy
        stage('Clone Test Code') {
            when {
                expression { readFile('.poll_result').trim() == 'CHANGED' }
            }
            steps {
                sh '''
                    set +x
                    echo "============================================================"
                    echo "[Staging Monitor] Clone Test Code"
                    echo "============================================================"

                    rm -rf autotest
                    mkdir -p autotest

                    ARCHIVE_URL="__TEST_REPO__/.git/archive/refs/heads/__TEST_BRANCH__.tar.gz"
                    echo ">>> Downloading: ${ARCHIVE_URL}"

                    download_repo() {
                        local url="$1"
                        local output="$2"
                        local proxies="https://gh-proxy.com https://mirror.ghproxy.com https://ghfast.top https://ghproxy.net"
                        for proxy in $proxies ""; do
                            if [ -n "$proxy" ]; then
                                full_url="${proxy}/${url}"
                            else
                                full_url="$url"
                            fi
                            for i in 1 2 3; do
                                if curl --fail -SL --connect-timeout 10 --max-time 300 "${full_url}" -o "${output}" 2>/dev/null; then
                                    if [ -s "${output}" ] && tar tzf "${output}" > /dev/null 2>&1; then
                                        echo "    OK (proxy: ${proxy:-direct})"
                                        return 0
                                    fi
                                fi
                                sleep 2
                            done
                        done
                        return 1
                    }

                    download_repo "${ARCHIVE_URL}" /tmp/autotest.tar.gz
                    tar xzf /tmp/autotest.tar.gz --strip-components=1 -C autotest
                    rm -f /tmp/autotest.tar.gz
                    echo "    Test code: $(ls autotest/ | wc -l) files/dirs"
                '''.replace('__TEST_REPO__', params.TEST_REPO.replace('.git', ''))
                  .replace('__TEST_BRANCH__', params.TEST_REPO_BRANCH ?: 'feat/jenkins-pipeline')
            }
        }
```

- [ ] **Step 5: Create Pipeline Record + Resolve Tests stage**

```groovy
        stage('Prepare Tests') {
            when {
                expression { readFile('.poll_result').trim() == 'CHANGED' }
            }
            steps {
                withCredentials([string(credentialsId: 'autotest-token', variable: 'TOKEN')]) {
                    sh '''
                        set +x
                        echo "============================================================"
                        echo "[Staging Monitor] Create Pipeline Record + Resolve Tests"
                        echo "============================================================"

                        CURRENT_COMMIT=$(cat .current_commit)
                        CURRENT_VERSION=$(cat .current_version)
                        STARTED_AT=$(cat .started_at)

                        # 创建 Pipeline 记录
                        CREATE_RESP=$(curl -sf -X POST \\
                          -H "Authorization: Bearer $TOKEN" \\
                          -H "Content-Type: application/json" \\
                          -d "{
                            \\"pr_title\\": \\"Staging: v${CURRENT_VERSION}\\",
                            \\"commit_sha\\": \\"${CURRENT_COMMIT}\\",
                            \\"branch\\": \\"staging\\",
                            \\"author\\": \\"system\\",
                            \\"target_url\\": \\"__TARGET_URL__\\",
                            \\"build_info\\": {\\"version\\": \\"${CURRENT_VERSION}\\", \\"startedAt\\": \\"${STARTED_AT}\\", \\"commitId\\": \\"${CURRENT_COMMIT}\\"}
                          }" \\
                          "__AUTOTEST_URL__/api/pipelines" 2>/dev/null || echo "")

                        echo ">>> Create pipeline response: $CREATE_RESP"

                        PIPELINE_ID=$(echo "$CREATE_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('data',{}).get('id',''))" 2>/dev/null || echo "")
                        echo "$PIPELINE_ID" > .pipeline_id
                        echo "    Pipeline ID: $PIPELINE_ID"

                        # 解析测试用例
                        echo ">>> Resolving staging tests..."
                        curl -sf -H "Authorization: Bearer $TOKEN" \\
                          "__AUTOTEST_URL__/api/ci/staging-resolve-tests" > resolve_resp.json 2>/dev/null || true

                        python3 -c "
import json
try:
    data = json.load(open('resolve_resp.json'))
    ids = data.get('data', {}).get('node_ids', [])
    if ids:
        fixed = [('/app/' + i if not i.startswith('/') else i) for i in ids]
        print(' '.join(fixed))
except Exception as e:
    import sys
    print(f'Parse error: {e}', file=sys.stderr)
" > test_targets.txt 2>/dev/null

                        if [ -s test_targets.txt ]; then
                            echo "    Source: AutoTest API (staging)"
                            echo "    Targets: $(cat test_targets.txt)"
                        elif [ -f autotest/tests/ci/staging-cases.txt ]; then
                            echo "    Source: staging-cases.txt (API unavailable)"
                            grep -v '^#' autotest/tests/ci/staging-cases.txt | grep -v '^$' | sed 's|^tests/|/app/tests/|' | tr '\\n' ' ' > test_targets.txt
                            echo "    Targets: $(cat test_targets.txt)"
                        else
                            echo "    Source: fallback (all tests)"
                            echo "/app/tests/suites /app/tests/api_suites" > test_targets.txt
                            echo "    Targets: /app/tests/suites /app/tests/api_suites"
                        fi
                    '''.replace('__AUTOTEST_URL__', params.AUTOTEST_URL)
                      .replace('__TARGET_URL__', params.TARGET_URL)
                }
            }
        }
```

- [ ] **Step 6: Run Tests stage**

```groovy
        stage('Run Tests') {
            when {
                expression { readFile('.poll_result').trim() == 'CHANGED' }
            }
            steps {
                withCredentials([string(credentialsId: 'autotest-token', variable: 'TOKEN')]) {
                    sh '''
                        set +x
                        echo "============================================================"
                        echo "[Staging Monitor] Run Tests"
                        echo "  Target: __TARGET_URL__"
                        echo "  Targets: __TEST_TARGETS__"
                        echo "============================================================"

                        PIPELINE_ID=$(cat .pipeline_id)

                        # 更新状态为 running
                        if [ -n "$PIPELINE_ID" ]; then
                            curl -sf -X PUT \\
                              -H "Authorization: Bearer $TOKEN" \\
                              -H "Content-Type: application/json" \\
                              -d '{"status": "running"}' \\
                              "__AUTOTEST_URL__/api/pipelines/${PIPELINE_ID}/status" > /dev/null 2>&1 || true
                        fi

                        # 确保结果目录存在
                        mkdir -p autotest/tests/results

                        # 跑测试（直接在 Jenkins 机器上用 docker run）
                        set +e
                        docker run --rm \\
                          --name staging-test-runner-${BUILD_NUMBER} \\
                          -v "${WORKSPACE}/autotest/tests:/app/tests" \\
                          -v "${WORKSPACE}/autotest/conftest.py:/app/conftest.py" \\
                          -v "${WORKSPACE}/autotest/pytest.ini:/app/pytest.ini" \\
                          -e "FENIX_URL=__TARGET_URL__" \\
                          -e "FENIX_API_BASE_URL=__TARGET_URL__" \\
                          -e "HEADLESS=true" \\
                          -e "PYTHONUNBUFFERED=1" \\
                          --network host \\
                          test-runner:latest \\
                          pytest __TEST_TARGETS__ -v --tb=short \\
                            --base-url=__TARGET_URL__ \\
                            --json-report --json-report-file=/app/tests/results/report.json
                        TEST_EXIT=$?
                        set -e

                        echo ">>> Test exit code: $TEST_EXIT"

                        # 上报结果
                        if [ -f autotest/tests/results/report.json ]; then
                            echo ">>> Uploading test results..."
                            curl -sf -X POST \\
                              -H "Authorization: Bearer $TOKEN" \\
                              -H "Content-Type: application/json" \\
                              -d @autotest/tests/results/report.json \\
                              "__AUTOTEST_URL__/api/pipelines/${PIPELINE_ID}/results" > /dev/null 2>&1 || true
                        fi

                        # 更新最终状态
                        if [ $TEST_EXIT -eq 0 ]; then
                            FINAL_STATUS="passed"
                        else
                            FINAL_STATUS="failed"
                        fi

                        if [ -n "$PIPELINE_ID" ]; then
                            curl -sf -X PUT \\
                              -H "Authorization: Bearer $TOKEN" \\
                              -H "Content-Type: application/json" \\
                              -d "{\"status\": \"${FINAL_STATUS}\"}" \\
                              "__AUTOTEST_URL__/api/pipelines/${PIPELINE_ID}/status" > /dev/null 2>&1 || true
                        fi

                        echo ">>> Pipeline ${PIPELINE_ID}: ${FINAL_STATUS}"

                        # 非零退出码不阻塞 Jenkins job（下次还会继续轮询）
                        exit 0
                    '''.replace('__TARGET_URL__', params.TARGET_URL)
                      .replace('__AUTOTEST_URL__', params.AUTOTEST_URL)
                      .replace('__TEST_TARGETS__', readFile('test_targets.txt').trim())
                }
            }
        }
    }
}
```

- [ ] **Step 7: 完整脚本整合检查**

确认 `when` 条件使 `Poll Health` 之后的所有 stage 只在 commitId 变化时执行。确认无语法错误。

- [ ] **Step 8: Commit**

```bash
git add docs/jenkins-staging-monitor.groovy
git commit -m "feat: add jenkins-staging-monitor.groovy for staging auto regression"
```

---

## 验证清单

1. **数据库**：执行迁移 SQL，确认 `ci_configs` 有 `staging_collection_ids` 列，`pr_pipelines.pr_id` 可为 null
2. **后端 API**：
   - `GET /api/ci/config` 返回 `staging_collection_ids`
   - `PUT /api/ci/config` 可更新 `staging_collection_ids`
   - `GET /api/ci/staging-resolve-tests` 返回 node_ids
   - `POST /api/pipelines` 接受 `pr_id: null`
3. **前端**：
   - CI 配置弹窗有 "Staging 测试集" 区域，可保存
   - PR Pipeline 页面 Staging 记录显示紫色标识，类型筛选器工作正常
4. **Jenkins**：
   - 创建 Staging Monitor Job，粘贴 groovy 脚本
   - 首次运行：commitId 为空 → 记录当前 commitId，跑一次测试
   - 后续运行：commitId 不变 → 跳过；变化 → 跑测试
5. **端到端**：在前端 CI 配置中选择 Staging 测试集，Jenkins 触发后，PR Pipeline 页面出现 branch=staging 的记录，状态从 running → passed/failed
