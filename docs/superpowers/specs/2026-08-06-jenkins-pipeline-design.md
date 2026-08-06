# Jenkins PR Pipeline 集成设计

## 概述

将 PR Pipeline 的构建/部署职责从 AutoTest 迁移到 Jenkins，AutoTest 专注于测试管理和结果展示。Jenkins 负责代码克隆、Docker 构建、容器部署、测试执行编排和环境清理。

## 动机

- **简化 AutoTest**：移除自研的 SSH 远程执行、Docker 管理、Slot 分配等复杂逻辑
- **复用 Jenkins 能力**：Jenkins 有成熟的构建缓存、并发控制、插件生态
- **职责分离**：构建/部署和测试解耦，各自独立演进

## 架构

```
PR 事件
  │
  ▼
GitHub Webhook → Jenkins Server（Linux 单机）
  │
  ├─ 1. git clone PR 分支代码（被测应用）
  ├─ 2. git clone AutoTest 仓库（最新测试代码）
  ├─ 3. docker build 应用镜像
  ├─ 4. docker compose up（postgres + litellm + rcs + test-runner）
  ├─ 5. test-runner 容器跑 pytest
  ├─ 6. 调 AutoTest API 创建记录 + 提交结果
  └─ 7. docker compose down -v（清理）
```

### 职责分工

| 模块 | 职责 |
|------|------|
| **Jenkins** | clone → build → deploy → health check → 触发测试 → 收集结果 → 清理 |
| **test-runner 容器** | 每个 PR 环境自带一个，跑 pytest，天然解决并发问题 |
| **AutoTest** | 接收 Pipeline 记录、存储测试结果、看板展示、手动/定时测试执行 |
| **GitHub Webhook** | PR 事件触发 Jenkins Job |

### 并发模型

每个 PR 拥有独立的 docker-compose 容器栈（postgres + litellm + rcs + test-runner），互不干扰。并发上限仅取决于服务器资源（CPU、内存），无需锁或队列管理。

```
PR #1 → Stack 1 (postgres + litellm + rcs + test-runner) → 端口 30000 组
PR #2 → Stack 2 (postgres + litellm + rcs + test-runner) → 端口 30003 组
PR #3 → Stack 3 (postgres + litellm + rcs + test-runner) → 端口 30006 组
```

端口分配基于 Jenkins `BUILD_NUMBER`：`PORT_OFFSET = (BUILD_NUMBER % 10) * 3`

## AutoTest API 变更

### 新增接口（供 Jenkins 和 test-runner 调用）

| 方法 | 路径 | 调用者 | 说明 |
|------|------|--------|------|
| POST | `/api/pipelines` | Jenkins | 创建 Pipeline 记录（部署完成后调用） |
| POST | `/api/pipelines/{id}/results` | test-runner/Jenkins | 提交测试结果（JSON report） |
| PUT | `/api/pipelines/{id}/status` | Jenkins | 更新 Pipeline 状态 |
| GET | `/api/pipelines/{id}/logs` | Jenkins/前端 | 获取测试日志（支持 SSE follow 模式） |

### POST `/api/pipelines` 请求体

```json
{
  "pr_id": 123,
  "pr_title": "feat: add new feature",
  "commit_sha": "abc123...",
  "branch": "feature-branch",
  "repo_url": "https://github.com/xxx/yyy",
  "author": "username",
  "target_url": "http://localhost:30000",
  "build_info": {
    "jenkins_url": "http://jenkins:8080/job/PR-Pipeline/45",
    "build_number": 45,
    "docker_image": "pr-env-45:45",
    "rcs_port": 30000,
    "pg_port": 30001,
    "litellm_port": 30002
  }
}
```

### POST `/api/pipelines/{id}/results` 请求体

pytest-json-report 生成的 JSON 报告原文，AutoTest 解析并存入 TestRun/TestResult。

### GET `/api/pipelines/{id}/logs`

- `follow=false`（默认）：返回当前日志文本
- `follow=true`：SSE 流式推送，测试完成后自动关闭

### 删除的接口

- `POST /api/ci/pr-trigger` — 改为 Jenkins 入口
- `POST /api/ci/pr-update` — Jenkins 自己处理新 commit
- `POST /api/pipelines/{id}/rerun` — Jenkins 重新跑 Job
- `DELETE /api/pipelines/{id}` — Jenkins 自己清理
- `POST /api/pipelines/{id}/cancel` — Jenkins 取消 Job
- Slot 相关全部 API（`/api/slots`）

### 保留的接口

- `GET /api/pipelines` — 看板列表
- `GET /api/pipelines/{id}` — 看板详情
- CI 配置 API — 测试策略配置（用例集选择、超时等）

## AutoTest 代码变更

### 删除的文件

| 文件 | 原因 |
|------|------|
| `backend/services/docker_manager.py` | Docker 构建/compose 由 Jenkins 负责 |
| `backend/services/executor.py` | SSH 远程执行器不再需要 |
| `backend/services/slot_manager.py` | Slot 概念移除 |
| `backend/services/timeout_checker.py` | 生命周期由 Jenkins 控制 |
| `backend/schemas/slot.py` | Slot Schema |
| `backend/api/slots.py` | Slot API 路由 |
| `frontend/src/components/SlotCard.tsx` | Slot 卡片组件 |
| `frontend/src/api/slots.ts` | Slot API 客户端 |

### 大幅简化的文件

| 文件 | 变化 |
|------|------|
| `backend/services/pipeline_runner.py` | 700 行 → ~150 行，只保留测试执行（供手动/定时触发用） |
| `backend/api/ci.py` | 删 pr-trigger/pr-update/rerun/destroy/cancel，新增 Jenkins 调用接口 |
| `backend/db/models.py` | PRPipeline 新增 target_url、build_info、test_report 字段；EnvironmentSlot 标记废弃（保留不删，避免迁移） |
| `frontend/src/components/CIConfigModal.tsx` | 去掉 Slot 管理，只保留测试策略配置 |
| `frontend/src/pages/PRPipeline.tsx` | 去掉 Slot 卡片，增加 Jenkins 链接和 target_url 展示 |

### 保留不动

- 测试执行核心（pytest subprocess 调用）— 手动触发仍需要
- WebSocket 推送（pipeline 事件 + 测试日志）
- TestRun / TestResult 模型和存储
- 认证配置管理（AuthConfig）
- 用例集管理（TestCollection）
- AI 分析

### PRPipeline 模型新增字段

```python
target_url = Column(String(500), default="")       # Jenkins 部署后的 PR 环境地址
build_info = Column(JSON, nullable=True)            # Jenkins 构建信息（job URL、镜像 tag 等）
test_report = Column(JSON, nullable=True)           # test-runner 提交的完整 pytest JSON 报告
```

## 前端变更

| 变化 | 说明 |
|------|------|
| 去掉 SlotCard 组件 | Slot 概念移除 |
| 去掉 CIConfigModal 的 Slot 管理 | 只保留测试策略配置（用例集选择、超时等） |
| Pipeline 详情增加 Jenkins 链接 | 点击可跳转到 Jenkins Job 页面 |
| Pipeline 详情增加 target_url | 显示 PR 环境地址，可直接访问 |
| 去掉手动触发/重跑/销毁按钮 | 这些操作改在 Jenkins 上做 |
| Pipeline 状态展示不变 | queued → building → deploying → running → passed/failed/error → destroyed |

## Jenkins 部署

### 服务器要求

- Linux 服务器（推荐 Ubuntu 22.04+）
- Docker 20.10+
- 内存 8GB+（每个 PR 环境约占 2-3GB）
- 磁盘 50GB+（Docker 镜像和构建缓存）

### 安装步骤

```bash
# 1. 安装 Docker
curl -fsSL https://get.docker.com | sh

# 2. 安装 Jenkins（Docker 方式）
docker run -d \
  --name jenkins \
  --restart unless-stopped \
  -p 8080:8080 \
  -p 50000:50000 \
  -v jenkins_home:/var/jenkins_home \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -u root \
  jenkins/jenkins:lts

# 3. 获取初始密码
docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword
```

### Jenkins 配置

1. 浏览器打开 `http://服务器IP:8080`
2. 输入初始密码 → 安装推荐插件 → 创建管理员
3. 安装额外插件：
   - Generic Webhook Trigger
   - Credentials Binding
4. 添加凭据（Manage Jenkins → Credentials）：
   - `github-token`：Secret text，值为 GitHub Personal Access Token
   - `autotest-token`：Secret text，值为 AutoTest CI auth_token

### test-runner 镜像

**Dockerfile.runner**（放在 AutoTest 仓库根目录）：

```dockerfile
FROM mcr.microsoft.com/playwright/python:v1.50.0-noble

WORKDIR /app

COPY requirements-test.txt .
RUN pip install --no-cache-dir -r requirements-test.txt

RUN mkdir -p /app/results

CMD ["echo", "test-runner ready"]
```

**requirements-test.txt**（放在 AutoTest 仓库根目录）：

```
pytest==8.3.4
pytest-base-url==2.1.0
pytest-playwright==0.7.0
pytest-json-report==1.5.0
httpx==0.28.1
```

构建命令（一次性，依赖变更时重建）：

```bash
cd /opt/autotest
docker build -t test-runner:latest -f Dockerfile.runner .
```

### Jenkins Job 配置

1. Jenkins 首页 → **新建任务**
2. 名称：`PR-Pipeline-FenixAgent`
3. 选择 **流水线（Pipeline）**

**General 配置：**

- ☑ This project is parameterized
  - String Parameter: `PR_BRANCH`（Default: main）
  - String Parameter: `PR_ID`（Default: 0）
  - String Parameter: `PR_TITLE`（Default: 空）
  - String Parameter: `COMMIT_SHA`（Default: 空）
  - String Parameter: `AUTHOR`（Default: 空）

**Pipeline 配置：**

- 定义：Pipeline script
- 粘贴以下脚本：

```groovy
pipeline {
    agent any

    environment {
        AUTOTEST_URL = "http://localhost:8000"
        APP_REPO     = "https://github.com/your-org/FenixAgent.git"
        TEST_REPO    = "https://github.com/your-org/AutoTest.git"
        PROJECT_NAME = "pr-env-${BUILD_NUMBER}"

        PORT_OFFSET = "${(BUILD_NUMBER.toInteger() % 10) * 3}"
        RCS_PORT    = "${30000 + PORT_OFFSET.toInteger()}"
        PG_PORT     = "${30001 + PORT_OFFSET.toInteger()}"
        LITE_PORT   = "${30002 + PORT_OFFSET.toInteger()}"
    }

    stages {
        stage('Clone Repos') {
            steps {
                dir('app') {
                    git url: env.APP_REPO,
                        branch: params.PR_BRANCH,
                        credentialsId: 'github-token'
                }
                dir('autotest') {
                    git url: env.TEST_REPO,
                        branch: 'main',
                        credentialsId: 'github-token'
                }
            }
        }

        stage('Build Image') {
            steps {
                dir('app') {
                    sh "docker build -t ${PROJECT_NAME}:${BUILD_NUMBER} ."
                }
            }
        }

        stage('Write Compose') {
            steps {
                writeFile file: 'docker-compose.yml', text: """
services:
  postgres:
    image: postgres:16-alpine
    privileged: true
    ports:
      - "${PG_PORT}:5432"
    environment:
      POSTGRES_USER: rcs
      POSTGRES_PASSWORD: rcs
      POSTGRES_DB: rcs
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U rcs"]
      interval: 5s
      timeout: 5s
      retries: 5

  litellm:
    image: ghcr.io/berriai/litellm:main-stable
    depends_on:
      postgres:
        condition: service_healthy
    ports:
      - "${LITE_PORT}:4000"
    environment:
      DATABASE_URL: postgresql://rcs:rcs@postgres:5432/litellm
      LITELLM_MASTER_KEY: sk-litellm-admin-dev-key
      STORE_MODEL_IN_DB: "True"

  rcs:
    image: ${PROJECT_NAME}:${BUILD_NUMBER}
    depends_on:
      postgres:
        condition: service_healthy
    ports:
      - "${RCS_PORT}:3000"
    environment:
      DATABASE_URL: postgres://rcs:rcs@postgres:5432/rcs
      RCS_HOST: 0.0.0.0
      RCS_PORT: 3000
      RCS_API_KEYS: sk-rcs-dev-key
      RCS_SECRET_LITELLM_ADMIN_KEY: sk-litellm-admin-dev-key
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
      interval: 10s
      timeout: 5s
      retries: 12

  test-runner:
    image: test-runner:latest
    depends_on:
      rcs:
        condition: service_healthy
    volumes:
      - ${WORKSPACE}/autotest/tests:/app/tests
      - ${WORKSPACE}/autotest/conftest.py:/app/conftest.py
    environment:
      FENIX_URL: http://rcs:3000
      FENIX_API_BASE_URL: http://rcs:3000
      HEADLESS: "true"
      PYTHONUNBUFFERED: "1"
    command: >
      pytest /app/tests -v --tb=short
      --base-url=http://rcs:3000
      --json-report --json-report-file=/app/results/report.json
"""
            }
        }

        stage('Deploy') {
            steps {
                sh "docker compose -p ${PROJECT_NAME} up -d postgres litellm rcs"
                sh """
                    echo "Waiting for RCS to be healthy..."
                    for i in \$(seq 1 60); do
                        if curl -sf http://localhost:${RCS_PORT}/health > /dev/null 2>&1; then
                            echo "RCS is healthy!"
                            exit 0
                        fi
                        echo "Attempt \$i/60 - waiting..."
                        sleep 5
                    done
                    echo "RCS health check timeout!"
                    exit 1
                """
            }
        }

        stage('Create Pipeline Record') {
            steps {
                withCredentials([string(credentialsId: 'autotest-token', variable: 'TOKEN')]) {
                    sh """
                        curl -s -X POST ${AUTOTEST_URL}/api/pipelines \\
                          -H "Authorization: Bearer \$TOKEN" \\
                          -H "Content-Type: application/json" \\
                          -d '{
                            "pr_id": ${params.PR_ID ?: 0},
                            "pr_title": "${params.PR_TITLE ?: ""}",
                            "commit_sha": "${params.COMMIT_SHA ?: env.GIT_COMMIT}",
                            "branch": "${params.PR_BRANCH}",
                            "repo_url": "${env.APP_REPO}",
                            "author": "${params.AUTHOR ?: ""}",
                            "target_url": "http://localhost:${RCS_PORT}",
                            "build_info": {
                              "jenkins_url": "${env.BUILD_URL}",
                              "build_number": ${BUILD_NUMBER},
                              "docker_image": "${PROJECT_NAME}:${BUILD_NUMBER}",
                              "rcs_port": ${RCS_PORT},
                              "pg_port": ${PG_PORT},
                              "litellm_port": ${LITE_PORT}
                            }
                          }' > pipeline.json

                        echo "Pipeline created:"
                        cat pipeline.json
                    """
                }
            }
        }

        stage('Run Tests') {
            steps {
                sh "docker compose -p ${PROJECT_NAME} logs -f test-runner &"
                sh "docker compose -p ${PROJECT_NAME} up test-runner"
            }
        }

        stage('Collect Results') {
            steps {
                sh "docker cp ${PROJECT_NAME}-test-runner-1:/app/results/report.json report.json || true"
                withCredentials([string(credentialsId: 'autotest-token', variable: 'TOKEN')]) {
                    sh """
                        PIPELINE_ID=\$(cat pipeline.json | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")
                        if [ -f report.json ]; then
                            curl -s -X POST ${AUTOTEST_URL}/api/pipelines/\${PIPELINE_ID}/results \\
                              -H "Authorization: Bearer \$TOKEN" \\
                              -H "Content-Type: application/json" \\
                              -d @report.json
                        fi
                    """
                }
            }
        }
    }

    post {
        success {
            withCredentials([string(credentialsId: 'autotest-token', variable: 'TOKEN')]) {
                sh """
                    PIPELINE_ID=\$(cat pipeline.json | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")
                    curl -s -X PUT ${AUTOTEST_URL}/api/pipelines/\${PIPELINE_ID}/status \\
                      -H "Authorization: Bearer \$TOKEN" \\
                      -H "Content-Type: application/json" \\
                      -d '{"status": "passed"}'
                """
            }
        }
        failure {
            withCredentials([string(credentialsId: 'autotest-token', variable: 'TOKEN')]) {
                sh """
                    if [ -f pipeline.json ]; then
                        PIPELINE_ID=\$(cat pipeline.json | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")
                        curl -s -X PUT ${AUTOTEST_URL}/api/pipelines/\${PIPELINE_ID}/status \\
                          -H "Authorization: Bearer \$TOKEN" \\
                          -H "Content-Type: application/json" \\
                          -d '{"status": "failed"}'
                    fi
                """
            }
        }
        always {
            sh """
                docker compose -p ${PROJECT_NAME} down -v || true
                docker rmi -f ${PROJECT_NAME}:${BUILD_NUMBER} || true
            """
        }
    }
}
```

### GitHub Webhook 配置

在目标仓库（如 FenixAgent）→ Settings → Webhooks → Add webhook：

- **Payload URL**: `http://jenkins-server:8080/generic-webhook-trigger/invoke?token=YOUR_JENKINS_TOKEN`
- **Content type**: `application/json`
- **Events**: Pull requests

## 数据库迁移

```sql
ALTER TABLE pr_pipelines ADD COLUMN target_url VARCHAR(500) DEFAULT '';
ALTER TABLE pr_pipelines ADD COLUMN build_info JSON;
ALTER TABLE pr_pipelines ADD COLUMN test_report JSON;
```

## 后续扩展

- **分布式部署**：Jenkins 通过 SSH Agent 插件将构建/部署分发到远程服务器
- **Jenkinsfile 迁移**：稳定后将 Pipeline 脚本从 Job UI 移到目标仓库的 Jenkinsfile
- **Shared Library**：多仓库接入时，抽取公共 Pipeline 逻辑为 Jenkins Shared Library
