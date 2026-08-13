# Spec: 分支测试用例隔离

**日期**: 2026-08-11
**状态**: 待实施

## 1. 背景

autotest 是 Fenix AI Agent 的自动化测试平台。当前所有测试用例（UI、API、单元测试）只有一套，对应 Fenix 的 main 分支。

Fenix 开发过程中，feature 分支会通过 Jenkins PR-poll 自动构建、部署、运行测试。但测试用例只有 main 版本，无法覆盖 feature 分支的新功能和变更。

**核心需求**: 支持针对 Fenix feature 分支编写独立的测试用例，且不污染 main 用例。

## 2. 设计原则

1. **autotest 永远在 main 分支** — 不在 autotest 项目上切 git 分支，平台功能开发和分支用例编写互不阻塞
2. **只有 API 测试和单元测试需要分支隔离** — UI E2E 测试用 main 基线即可，不需要分支隔离
3. **分支用例完全独立** — 分支用例集是完整的、独立的，不从 main 继承，不与 main 合并
4. **AI 驱动** — 用例由 AI 生成，人工评审后提交

## 3. 目录结构

```
autotest/
├── tests/
│   ├── suites/                          ← UI E2E 用例（不变，无分支隔离）
│   ├── api_suites/                      ← API 测试 main 基线
│   │   ├── test_agent_api.py
│   │   ├── test_auth_api.py
│   │   └── ...
│   ├── api_clients/                     ← API Client（不变）
│   ├── api_contracts/                   ← API Schema（不变）
│   └── pages/                           ← Page Object（不变）
│
├── unit_tests/                          ← 单元测试 main 基线（40 个文件）
│   ├── auth/
│   │   └── trusted-origins.test.ts
│   ├── errors/
│   │   └── error-classes.test.ts
│   ├── packages/sandbox-provider/
│   │   ├── http-client.test.ts
│   │   ├── integration-flow.test.ts
│   │   ├── opensandbox-cluster-provider.test.ts
│   │   └── request-mapping.test.ts
│   ├── services/
│   │   ├── sandbox-manager.test.ts
│   │   ├── sandbox-config.test.ts
│   │   └── ... (25 个文件)
│   ├── transport/
│   │   ├── client-payload.test.ts
│   │   └── event-bus.test.ts
│   └── utils/
│       └── executable.test.ts
│
├── branches/                            ← 🆕 分支用例区（统一管理）
│   └── feature-xxx/
│       ├── api_suites/                  ← 分支的完整 API 用例集
│       │   ├── test_agent_api.py
│       │   ├── test_auth_api.py
│       │   └── test_new_feature_api.py  ← 新增
│       └── unit_tests/                  ← 分支的完整单元测试集（保留子目录结构）
│           ├── services/
│           │   ├── sandbox-manager.test.ts
│           │   └── new-service.test.ts  ← 新增
│           ├── packages/sandbox-provider/
│           └── ...
```

**关键**: `branches/feature-xxx/` 下是完整的用例集，不是增量。

## 4. 生命周期

### 4.1 发现与创建分支

autotest 后端通过 GitHub Pulls API 轮询 Fenix 仓库的 open PR，发现新 PR 时**只记录不创建目录**：

```
轮询发现新 PR → BranchTracker 入库（dev_status=open, case_status=pending）
```

用户在前端"分支用例"页面看到新 PR 后，手动点击"创建"才复制用例目录：

```python
# 用户点击"创建" → 后端执行
cp -r tests/api_suites → branches/{branch_name}/api_suites
cp -r unit_tests → branches/{branch_name}/unit_tests
# case_status: pending → active
```

- 轮询只负责发现，不自动创建目录
- 也可通过平台 UI 手动创建（调用 `POST /api/branches`），此时 dev_status=manual

### 4.2 分支开发

- AI 读取 Fenix feature 分支代码，在 `branches/feature-xxx/` 下生成/修改/删除用例
- 测试人员逐条评审，OK 则 commit push 到 autotest main
- 分支目录是用例的唯一操作区域，main 用例不受影响

### 4.3 运行测试

Jenkins Pipeline 的 Resolve Tests 阶段：

```
# 集成测试（API + UI E2E）
GET /api/ci/resolve-tests?branch=feature-xxx
→ 返回 API 用例: branches/feature-xxx/api_suites/ 下的 node_ids
→ 返回 UI 用例: tests/suites/ 下的 node_ids（UI 始终用 main）

# 单元测试
GET /api/ci/resolve-unit-tests?branch=feature-xxx
→ 返回: branches/feature-xxx/unit_tests/ 下的文件列表
```

如果 `branch` 参数为空或 `main`，则使用 main 基线目录。

### 4.4 Fenix 合并后

Fenix PR 合入 main 后，轮询检测到 PR 消失且 `merged_at` 有值：

1. **状态变更**: dev_status → `merged`，case_status → `ready_to_sync`
2. 前端显示"📦 可同步"，用户决定是否 Promote

用户点击 Promote 时：
1. **提取新增**: 从分支目录中找出 main 里没有的文件（新增用例），移入 main 基线目录
2. **丢弃修改和删除**: 分支对已有用例的修改和删除不处理
3. **Promote 后**: case_status 回到 `active`
4. **用户手动删除**: 确认不再需要后点删除，清理 `branches/feature-xxx/`

也可选择不 Promote，直接让 AI 根据最新 main 代码重新生成 main 基线用例，然后删除分支目录。

## 5. 后端改动

### 5.1 数据库

TestCase 和 UnitTestCase 模型新增字段：

```python
# TestCase 模型
branch = Column(String(200), default="main")  # 所属分支，默认 main

# UnitTestCase 模型
branch = Column(String(200), default="main")  # 所属分支，默认 main
```

现有 UnitTestCase 的 `full_name` 字段有 `unique=True` 约束，加 branch 后需改为联合唯一：
```python
__table_args__ = (
    UniqueConstraint("full_name", "branch", name="uq_unit_test_case_full_name_branch"),
)
```

### 5.2 AutoDiscover 扫描

启动时扫描逻辑扩展：

```python
# 现有：扫描 tests/api_suites/ → branch="main"
# 新增：扫描 branches/*/api_suites/ → branch=目录名

# 现有：扫描 unit_tests/ → branch="main"
# 新增：扫描 branches/*/unit_tests/ → branch=目录名
```

UI E2E (`tests/suites/`) 不变，始终 branch="main"。

### 5.3 分支轮询服务

#### 轮询机制

autotest 后端通过 GitHub Pulls API 定时轮询 Fenix 仓库的 open PR：

```
GET https://api.github.com/repos/{owner}/{repo}/pulls?state=open&base=main
Authorization: Bearer {GITHUB_TOKEN}

每个 PR 返回 head.ref（源分支名）、head.sha（最新 commit）。

对比 BranchTracker 表：
- 表里没有、API 有 → 新 PR → 入库（case_status=pending，不自动创建目录）
- 表里有、API 有但 commit SHA 变了 → dev_status=open（保持不变）
- 表里有、API 没有 → 查 closed PRs 判断合入还是关闭：
  - merged_at 有值 → dev_status=merged
  - merged_at 为空 → dev_status=closed
```

#### 前端配置（Settings 页面新增区块）

| Setting Key | 说明 | 默认值 |
|-------------|------|--------|
| `branch_poll_enabled` | 轮询开关 | `false` |
| `branch_poll_interval` | 轮询间隔（分钟） | `30` |
| `branch_poll_repo` | Fenix 仓库地址 | `https://github.com/HuangPuStar/FenixAgent` |
| `github_token` | GitHub Personal Access Token | 空 |

前端 Settings 页面展示为一个"分支轮询"区块，包含开关、输入框和手动轮询按钮。

#### BranchTracker 表

```python
class BranchTracker(Base):
    __tablename__ = "branch_trackers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    branch_name = Column(String(200), unique=True, nullable=False)
    last_commit_sha = Column(String(40), default="")
    pr_number = Column(Integer, nullable=True)  # 关联的 PR 编号
    dev_status = Column(String(20), default="open")
    # open / merged / closed / manual（手动创建的无 PR）
    case_status = Column(String(20), default="pending")
    # pending（未创建）/ active（使用中）/ ready_to_sync（可同步）/ disposable（可清理）
    discovered_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)
```

#### 状态联动规则

| 事件 | dev_status | case_status |
|------|-----------|-------------|
| 发现新 open PR | `open` | `pending`（不自动创建目录） |
| 用户点击"创建" | 不变 | `active`（创建目录，从 main 复制用例） |
| PR 合入 main | `merged` | `ready_to_sync`（提示可同步到 main） |
| PR 关闭未合入 | `closed` | `disposable`（提示可清理） |
| 手动创建分支 | `manual` | `active` |
| 用户执行 Promote | 不变 | `active`（Promote 后回到使用中） |

#### 轮询 API

```
POST /api/branches/poll-now              — 手动触发一次轮询
GET  /api/branches/trackers              — 获取所有分支追踪记录
```

### 5.4 新增 API

#### 分支管理

```
GET    /api/branches                    — 列出所有分支（读 branches/ 目录）
POST   /api/branches                    — 创建分支（从 main 复制）
DELETE /api/branches/{branch_name}      — 删除分支目录
POST   /api/branches/{branch_name}/promote — 提取新增用例到 main
```

#### 修改 resolve-tests

```
GET /api/ci/resolve-tests?branch=feature-xxx
```

逻辑：
- `branch` 为空或 "main" → 从 CI config 的 collection_ids 解析（现有逻辑）
- `branch` 有值 → 扫描 `branches/{branch}/api_suites/` 目录，返回 pytest node_ids
- UI E2E 用例始终从 `tests/suites/` 加载（不受 branch 影响）

#### 新增 resolve-unit-tests

```
GET /api/ci/resolve-unit-tests?branch=feature-xxx
```

逻辑：
- `branch` 为空或 "main" → rglob 扫描 `unit_tests/**/*.test.ts` 返回文件列表（含子目录）
- `branch` 有值 → rglob 扫描 `branches/{branch}/unit_tests/**/*.test.ts` 返回文件列表

### 5.5 Promote 逻辑

`POST /api/branches/{branch_name}/promote` 的执行步骤：

```
1. 对比 branches/{branch}/api_suites/ vs tests/api_suites/
   - 找出分支独有的文件（新增）→ 复制到 tests/api_suites/
2. 对比 branches/{branch}/unit_tests/ vs unit_tests/
   - 找出分支独有的文件（新增）→ 复制到 unit_tests/
3. 返回 promote 报告（新增了哪些文件）
4. 不删除分支目录（留给用户手动或后续清理）
```

## 6. Jenkins Pipeline 改动

### 6.1 Resolve Tests 阶段修改

现有 groovy 中 Resolve Tests 阶段改为传 branch 参数：

```groovy
// 集成测试
curl -s -H "Authorization: Bearer $TOKEN" \
  "${AUTOTEST_URL}/api/ci/resolve-tests?branch=${APP_BRANCH}" > resolve_resp.json

// 单元测试
curl -s -H "Authorization: Bearer $TOKEN" \
  "${AUTOTEST_URL}/api/ci/resolve-unit-tests?branch=${APP_BRANCH}" > unit_resolve_resp.json
```

### 6.2 Test Runner 命令

```groovy
// 集成测试 runner
command: 'pytest ${test_targets} -v --tb=short ...'
// test_targets 来自 resolve-tests API，已包含正确路径

// 单元测试 runner
command: 'bun test ${unit_test_targets}'
// unit_test_targets 来自 resolve-unit-tests API
```

### 6.3 entrypoint-unit.sh 适配

当前 `entrypoint-unit.sh` 在 `/app/tests` 下生成 `tsconfig.json` 和 `bunfig.toml`，然后 `cd /app/tests && bun test`。

分支测试时，测试文件在 `/app/branches/{branch}/unit_tests/` 下，entrypoint 需要支持：

```sh
# 通过环境变量 TEST_ROOT 指定测试根目录，默认 /app/tests
TEST_ROOT="${TEST_ROOT:-/app/tests}"

# 在 TEST_ROOT 下生成 tsconfig.json 和 bunfig.toml
cat > ${TEST_ROOT}/tsconfig.json << TSEOF
...
TSEOF

cd ${TEST_ROOT}
bun test --reporter=junit --reporter-outfile=results/unit-junit.xml
```

Jenkins 传 `TEST_ROOT` 环境变量：
- main: `TEST_ROOT=/app/tests`（默认）
- 分支: `TEST_ROOT=/app/branches/feature-xxx/unit_tests`

### 6.4 Docker Volume Mount

需要确保 `branches/` 目录也被挂载到容器中：

```yaml
test-runner:
  volumes:
    - ${WORKSPACE}/autotest/tests:/app/tests
    - ${WORKSPACE}/autotest/branches:/app/branches   # 🆕 分支目录
    - ${WORKSPACE}/autotest/conftest.py:/app/conftest.py
    - ${WORKSPACE}/autotest/pytest.ini:/app/pytest.ini

unit-runner:
  volumes:
    - ${WORKSPACE}/autotest/unit_tests:/app/tests
    - ${WORKSPACE}/autotest/branches:/app/branches   # 🆕 分支目录
```

**容器内路径映射**:
- resolve-tests 返回的 node_ids 使用容器内路径：
  - main: `tests/api_suites/test_xxx.py::test_yyy`（容器内 `/app/tests/api_suites/...`）
  - 分支: `branches/feature-xxx/api_suites/test_xxx.py::test_yyy`（容器内 `/app/branches/feature-xxx/api_suites/...`）
- resolve-unit-tests 返回的文件列表同理：
  - main: `tests/xxx.test.ts`
  - 分支: `branches/feature-xxx/unit_tests/xxx.test.ts`
- pytest 工作目录为 `/app`，conftest.py 和 pytest.ini 在 `/app/` 下，对两个目录都生效

### 6.5 Staging Monitor 适配

现有 `jenkins-staging-monitor.groovy` 轮询 staging 环境变化并触发测试。分支场景下：
- staging monitor 目前固定拉 `TEST_REPO_BRANCH` 分支的测试代码
- 如果 staging 环境部署的是 Fenix feature 分支，需要传 `APP_BRANCH` 参数给 resolve-tests API
- 改动方式与 pipeline-build 一致：调 API 时传 branch 参数

## 7. 前端改动

### 7.1 Cases 页面（API 测试区域）

- 顶部新增**分支选择器**下拉框：`[main ▾] [feature-xxx] [feature-yyy]`
- 选 main → 展示 main 基线 API 用例
- 选 feature-xxx → 展示 `branches/feature-xxx/api_suites/` 下的用例
- UI E2E 区域不受影响，始终展示 main 用例

### 7.2 UnitTests 页面

- 同样新增分支选择器
- 选 main → 展示 main 基线单元测试
- 选 feature-xxx → 展示 `branches/feature-xxx/unit_tests/` 下的用例

### 7.3 分支用例页面（新增 Sidebar 菜单）

新增"分支用例"页面，与 Cases / UnitTests / Settings 平级：

```
分支用例                                    [手动轮询] [Settings]
────────────────────────────────────────────────────────────────────────────────
分支名           PR         开发状态     测试集状态     最新 Commit    操作
feat/login       #123      🟢 开发中    📁 使用中      abc1234       [生成用例] [删除]
feat/payment     #456      ✅ 已合入    📦 可同步      def5678       [Promote] [删除]
feat/old         #789      ❌ 已关闭    🗑️ 可清理      ghi9012       [删除]
feat/new         #101      🟢 开发中    ⏳ 未创建      jkl3456       [创建]
feat/manual      —         ⚙️ 手动     📁 使用中      —             [生成用例] [删除]
```

#### 两列状态展示

**开发状态**（来自 PR）：
- 🟢 开发中 — PR open
- ✅ 已合入 — PR merged
- ❌ 已关闭 — PR closed without merge
- ⚙️ 手动 — 手动创建，无关联 PR

**测试集状态**（用例生命周期）：
- ⏳ 未创建 — 发现 PR 但还没建目录
- 📁 使用中 — 目录已创建，正常使用
- 📦 可同步 — PR 已合入 main，用例可 Promote
- 🗑️ 可清理 — PR 已关闭，用例可删除

#### 操作按钮

根据 case_status 动态展示：
- `pending` → [创建]
- `active` → [生成用例] [删除]
- `ready_to_sync` → [Promote] [删除]
- `disposable` → [删除]

#### "生成用例"按钮逻辑

后端通过 `shutil.which("claude")` 检测是否可拉起本地 Claude Code：

```
GET /api/branches/can-generate
→ {"can_generate": true, "autotest_dir": "/path/to/autotest"}
→ {"can_generate": false}
```

- `can_generate = true` → 显示"生成用例"按钮
- `can_generate = false` → 显示提示："请在本地 Claude Code 中执行 `/api-test-from-code --branch feat/xxx`"

#### 拉起 Claude Code

后端自动检测 autotest 仓库路径（即后端运行目录），在新终端窗口中启动 Claude Code：

```python
import subprocess, platform, os

AUTOTEST_DIR = os.getcwd()

def launch_claude(branch_name: str):
    prompt = (
        f"执行 /api-test-from-code，针对 Fenix 分支 {branch_name} "
        f"生成 API 测试用例，写入 branches/{branch_name}/api_suites/"
    )
    system = platform.system()
    if system == "Windows":
        subprocess.Popen([
            'cmd', '/c', 'start', 'cmd', '/k',
            'cd', '/d', AUTOTEST_DIR, '&&', 'claude', prompt
        ])
    elif system == "Darwin":
        subprocess.Popen([
            'osascript', '-e',
            f'tell app "Terminal" to do script "cd {AUTOTEST_DIR} && claude {prompt}"'
        ])
```

效果：点击按钮 → 弹出新终端窗口 → Claude Code 会话可见可交互。

#### 分支轮询配置

放在 Settings 页面的"分支轮询"区块（见 5.3 节配置项）。

### 7.4 分支用例入口

- Sidebar 新增"分支用例"菜单项
- 可手动创建分支（从 main 复制）、删除分支、执行 promote

## 8. AI 用例生成与触发

### 8.1 架构

本地 Claude Code 和远程 autotest 平台通过 **GitHub** 同步：

```
本地                                    远程
─────                                  ─────
autotest 仓库 (clone)                   autotest 平台 (Docker)
     ↓                                      ↑
Claude Code 生成用例                         │ AutoDiscover 扫描
     ↓                                      │
commit push ─────→ GitHub ←──────────────────┘
                    ↓
              Jenkins 拉代码跑测试
```

### 8.2 分支检测

autotest 后端通过 GitHub Pulls API 定时轮询：

```
GET /repos/{owner}/{repo}/pulls?state=open&base=main
```

- 发现新 open PR → 入库 BranchTracker（dev_status=open, case_status=pending）
- **不自动创建目录**，等用户在前端点击"创建"才复制用例
- PR 从 open 列表消失 → 查 closed PRs 判断：
  - `merged_at` 有值 → dev_status=merged, case_status=ready_to_sync
  - `merged_at` 为空 → dev_status=closed, case_status=disposable

后端数据库表 `BranchTracker`（见 5.3 节完整定义）：

```python
class BranchTracker(Base):
    __tablename__ = "branch_trackers"
    id = Column(Integer, primary_key=True)
    branch_name = Column(String(200), unique=True)
    last_commit_sha = Column(String(40))
    pr_number = Column(Integer, nullable=True)
    dev_status = Column(String(20), default="open")    # open / merged / closed / manual
    case_status = Column(String(20), default="pending") # pending / active / ready_to_sync / disposable
    updated_at = Column(DateTime, default=_now, onupdate=_now)
```

### 8.3 用例生成流程

1. 用户在远程 autotest 页面看到"分支 aaa 有更新，待生成用例"
2. 本地打开 Claude Code，执行 skill（如 `/api-test-from-code --branch aaa`）
3. AI 读取 Fenix 分支代码，生成用例到 `branches/aaa/api_suites/`
4. 用户在 Claude Code 会话中逐条评审
5. 评审通过后 commit push 到 GitHub
6. 远程 autotest 下次 AutoDiscover 扫描时拉取新文件，入库

### 8.4 Skill 适配

现有 skill 需要支持 `--branch` 参数：
- 有 `--branch` → 用例写入 `branches/{branch}/api_suites/` 或 `branches/{branch}/unit_tests/`
- 无 `--branch` → 写入 main 基线目录（现有行为不变）

具体 skill 改造不在本次范围内，但数据结构和 API 要为此留出扩展空间。

## 9. 不做的事情

- **不做** UI E2E 测试的分支隔离
- **不做** 分支间的用例继承/合并机制
- **不做** Page Object / API Client 的分支版本
- **不做** autotest 项目的 git 分支管理
- **不做** 分支用例的修改/删除合并到 main（由 AI 重新生成替代）
