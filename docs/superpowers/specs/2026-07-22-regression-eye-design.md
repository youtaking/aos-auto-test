# RegressionEye 设计文档

> UI 自动化回归测试平台，为 FenixAgent 项目提供持续回归测试能力，支持 CI/CD 集成和可视化看板。

## 1. 项目概述

### 1.1 定位

RegressionEye 是一个独立的 UI 自动化回归测试平台，先服务 FenixAgent 项目，验证跑通后扩展为团队通用测试基础设施。

### 1.2 核心能力

- **测试执行**：Python + Playwright E2E 测试，POM 模式编写用例
- **多种触发**：看板手动触发 / GitHub Actions 自动触发 / API 外部触发
- **可视化看板**：实时执行进度 + 历史报告 + 趋势分析
- **CI/CD 集成**：GitHub Actions workflow，代码提交/PR/发版自动回归

### 1.3 被测项目

| 属性 | 信息 |
|------|------|
| 项目 | FenixAgent（ACP Agent 统一管理平台） |
| 仓库 | https://github.com/HuangPuStar/FenixAgent |
| 类型 | SPA 单页应用 |
| 前端 | React 19 + Vite 8 + TanStack Router + Radix UI + Tailwind CSS 4 |
| 后端 | Elysia + Bun |
| 数据库 | PostgreSQL + Drizzle ORM |
| 部署 | Docker Compose |

## 2. 架构设计

### 2.1 整体架构：前后端分离 + 独立测试引擎

```
┌──────────────┐     ┌──────────────────┐
│  React 前端  │◄───►│  FastAPI 后端     │
│  (看板 UI)   │ API │  (调度+WebSocket) │
└──────────────┘     └───────┬──────────┘
                             │
                    ┌────────┴────────┐
                    │                 │
              ┌─────▼─────┐    ┌─────▼─────┐
              │ 测试引擎   │    │ PostgreSQL │
              │ (独立模块) │    │  结果存储   │
              └───────────┘    └───────────┘
                    ▲
                    │ 也可独立运行
              ┌─────┴──────────┐
              │ GitHub Actions │
              │  直接调用测试   │
              └────────────────┘
```

### 2.2 三种触发方式

| 触发方式 | 入口 | 运行位置 | 结果上报 |
|---------|------|---------|---------|
| 看板手动触发 | UI 按钮 → API → engine/runner.py | RegressionEye 服务器 | 直接写入 DB |
| CI/CD 自动触发 | GitHub Actions workflow | GitHub Runner | HTTP POST 到看板 API |
| API 外部触发 | REST API `/api/runs` | RegressionEye 服务器 | 直接写入 DB |

## 3. 项目结构

```
RegressionEye/
├── tests/                        # Playwright 测试用例
│   ├── conftest.py               # pytest 全局 fixtures（登录、浏览器配置）
│   ├── pages/                    # Page Object Model（页面对象封装）
│   │   ├── login_page.py
│   │   ├── dashboard_page.py
│   │   ├── agent_page.py
│   │   └── chat_page.py
│   ├── suites/                   # 测试套件（按模块分组）
│   │   ├── test_login.py
│   │   ├── test_dashboard.py
│   │   ├── test_agent.py
│   │   └── test_chat.py
│   └── fixtures/                 # 测试数据（JSON/YAML）
│       └── test_data.yaml
│
├── engine/                       # 测试执行引擎
│   ├── __init__.py
│   ├── runner.py                 # 测试调度器（触发 pytest、收集结果）
│   ├── reporter.py               # 自定义 Playwright Reporter（实时推送状态）
│   └── result_parser.py          # 解析 pytest 输出 → 结构化结果
│
├── backend/                      # FastAPI 后端
│   ├── main.py                   # FastAPI 入口
│   ├── api/                      # API 路由
│   │   ├── runs.py               # 测试运行 CRUD + 触发
│   │   ├── cases.py              # 用例管理
│   │   ├── projects.py           # 项目管理
│   │   └── dashboard.py          # 看板统计 API
│   ├── models/                   # SQLAlchemy/Pydantic 模型
│   ├── db/                       # 数据库配置和迁移
│   └── ws.py                     # WebSocket 实时推送
│
├── frontend/                     # React 前端（看板）
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx     # 总览看板
│   │   │   ├── RunDetail.tsx     # 单次运行详情
│   │   │   ├── CaseList.tsx      # 用例列表
│   │   │   └── RunLive.tsx       # 实时执行进度
│   │   ├── components/           # 通用组件
│   │   └── api/                  # API 调用封装
│   └── package.json
│
├── .github/
│   └── workflows/
│       └── regression.yml        # GitHub Actions CI/CD 配置
│
├── docker-compose.yml            # 一键部署
├── Dockerfile.backend            # FastAPI 镜像
├── Dockerfile.frontend           # React 镜像
├── Dockerfile.runner             # 测试运行器镜像
├── pytest.ini                    # pytest 配置
├── requirements.txt              # Python 依赖
└── README.md
```

## 4. 数据模型

### 4.1 实体关系

```
Project (项目)
├── id, name, url, description, created_at
│
└── TestSuite (测试套件)
    ├── id, project_id, name, description, tags
    │
    └── TestCase (测试用例)
        ├── id, suite_id, name, file_path, function_name
        ├── tags, priority (P0/P1/P2), timeout
        └── created_at, updated_at

TestRun (测试运行)
├── id, project_id, trigger_type (manual/ci/api)
├── trigger_user, git_commit, git_branch
├── status (pending/running/passed/failed/error)
├── total, passed, failed, skipped, duration
├── started_at, finished_at
│
└── TestResult (用例结果)
    ├── id, run_id, case_id
    ├── status (passed/failed/skipped/error)
    ├── duration, error_message, stack_trace
    └── screenshot_path, retry_count
```

### 4.2 用例自动发现

测试引擎在每次运行时通过 `pytest --collect-only` 扫描 `tests/suites/` 下所有 `test_*.py` 文件中的 `test_*` 函数，自动注册新用例到数据库。开发人员只需遵循命名约定即可，无需在看板上手动录入。

## 5. 后端 API 设计

### 5.1 项目管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/projects` | 项目列表 |
| POST | `/api/projects` | 创建项目 |
| PUT | `/api/projects/{id}` | 更新项目 |
| DELETE | `/api/projects/{id}` | 删除项目 |

### 5.2 套件管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/projects/{id}/suites` | 套件列表 |
| POST | `/api/projects/{id}/suites` | 创建套件 |
| PUT | `/api/suites/{id}` | 更新套件 |
| DELETE | `/api/suites/{id}` | 删除套件 |

### 5.3 用例管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/suites/{id}/cases` | 套件下的用例列表 |
| GET | `/api/cases/{id}` | 用例详情（含历史通过率） |

### 5.4 测试运行

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/runs` | 触发测试运行 |
| GET | `/api/runs` | 运行历史（分页+筛选） |
| GET | `/api/runs/{id}` | 运行详情 |
| GET | `/api/runs/{id}/results` | 该次运行的所有用例结果 |
| GET | `/api/runs/{id}/results/{case_id}/screenshot` | 获取失败截图 |
| POST | `/api/runs/{id}/report` | CI/CD 结果上报 |

**触发请求 body**：
```json
{
  "project_id": "proj_001",
  "suite_ids": ["suite_login", "suite_chat"],  // 可选，留空=全部
  "case_ids": [],                              // 可选，精确到用例
  "trigger_type": "manual"
}
```

**CI/CD 上报的 report.json 格式**（由自定义 pytest 插件 `engine/reporter.py` 生成）：
```json
{
  "project_name": "FenixAgent",
  "trigger_type": "ci",
  "git_commit": "abc123",
  "git_branch": "main",
  "started_at": "2026-07-22T10:00:00Z",
  "finished_at": "2026-07-22T10:05:30Z",
  "results": [
    {
      "suite_name": "login",
      "case_name": "test_login_success",
      "file_path": "tests/suites/test_login.py",
      "function_name": "test_login_success",
      "status": "passed",
      "duration_ms": 3200,
      "error_message": null,
      "stack_trace": null,
      "screenshot_path": null
    },
    {
      "suite_name": "chat",
      "case_name": "test_send_message",
      "file_path": "tests/suites/test_chat.py",
      "function_name": "test_send_message",
      "status": "failed",
      "duration_ms": 5100,
      "error_message": "TimeoutError: Element not found",
      "stack_trace": "...",
      "screenshot_path": "screenshots/test_send_message_failed.png"
    }
  ]
}
```

### 5.5 实时推送

| 协议 | 路径 | 说明 |
|------|------|------|
| WebSocket | `/ws/runs/{id}` | 实时推送用例执行进度 |

推送消息格式：
```json
{
  "event": "case_status",
  "data": {
    "case_id": "case_001",
    "case_name": "test_login_success",
    "status": "running",
    "started_at": "2026-07-22T10:30:00Z"
  }
}
```

### 5.6 看板统计

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/dashboard/summary` | 总览统计（通过率、用例数） |
| GET | `/api/dashboard/trend?limit=10` | 最近 N 次运行趋势 |

## 6. 前端看板设计

### 6.1 页面结构

- **Dashboard（总览页）**
  - 最近一次运行状态（大绿/红灯）
  - 通过率饼图
  - 最近 10 次运行趋势折线图
  - 失败用例 Top 5（高频失败）
  - 快捷操作：「运行全部测试」「选择套件运行」

- **Runs（运行历史）**
  - 运行列表（时间、触发方式、状态、通过率、耗时）
  - 运行详情页：总体进度条（实时）、用例列表（每条的 通过/失败/运行中/等待 状态）、失败用例错误信息 + 截图 + 堆栈、运行元信息（触发人、Git commit、分支）

- **Cases（用例管理）**
  - 按套件分组展示
  - 用例详情（名称、优先级、标签、历史通过率）
  - 手动触发单条用例

- **Settings（设置）**
  - 项目配置（目标 URL、认证信息）
  - 通知配置（失败时通知方式）

- **实时面板（运行中自动显示）**
  - 当前正在执行的用例（高亮动画）
  - 实时进度更新（WebSocket）
  - 已完成用例的结果逐个填充

### 6.2 核心交互

1. 进入 Dashboard → 看到大绿灯/红灯，一眼判断项目健康状态
2. 点「运行测试」→ 选择套件 → 页面自动切换到实时面板，看到用例逐个执行
3. 运行结束 → 查看失败用例的截图和错误信息
4. 历史页面 → 按时间线查看每次运行的结果

## 7. 测试框架设计

### 7.1 技术选型

| 组件 | 选型 | 说明 |
|------|------|------|
| 测试框架 | pytest | Python 生态最成熟的测试框架 |
| 浏览器自动化 | Playwright | 支持 Chromium/Firefox/WebKit |
| 页面对象 | POM 模式 | 页面操作封装在 pages/ 下 |
| 数据驱动 | YAML fixtures | 测试数据与代码分离 |

### 7.2 Page Object Model

```python
# tests/pages/login_page.py
class LoginPage:
    def __init__(self, page):
        self.page = page
        self.url = "/login"

    def goto(self):
        self.page.goto(self.url)

    def login(self, email: str, password: str):
        self.page.fill('[data-testid="email"]', email)
        self.page.fill('[data-testid="password"]', password)
        self.page.click('[data-testid="submit"]')

    def is_logged_in(self) -> bool:
        return self.page.locator('[data-testid="dashboard"]').is_visible()

# tests/suites/test_login.py
def test_login_success(page, login_page):
    """测试正常登录流程"""
    login_page.goto()
    login_page.login("admin@fenix.com", "password")
    assert login_page.is_logged_in()

def test_login_invalid_password(page, login_page):
    """测试密码错误时的提示"""
    login_page.goto()
    login_page.login("admin@fenix.com", "wrong")
    assert page.locator('[data-testid="error-message"]').is_visible()
```

### 7.3 截图策略

- **失败自动截图**：Playwright 配置 `screenshot: "only-on-failure"`，失败用例自动保存截图
- **关键步骤手动截图**：测试代码中在关键节点调用 `page.screenshot()`
- **存储位置**：Docker Volume 本地存储，按 `screenshots/runs/{run_id}/` 组织目录
- **访问方式**：FastAPI 提供 `/api/runs/{id}/results/{case_id}/screenshot` 接口

### 7.4 首批测试范围

| 模块 | 优先级 | 核心用例 |
|------|--------|---------|
| 登录/认证 | P0 | 正常登录、错误密码、未登录跳转、登录后跳转 |
| Dashboard | P0 | 页面加载、数据展示、导航跳转 |
| Agent 管理 | P1 | Agent 列表查看、创建 Agent、编辑 Agent、删除 Agent |
| Chat 对话 | P1 | 新建会话、发送消息、消息展示、会话列表 |

## 8. CI/CD 集成

### 8.1 GitHub Actions 说明

GitHub Actions 是 GitHub 内置的 CI/CD 系统，无需额外安装。只需在仓库中放置一个 `.yml` 配置文件，GitHub 会自动按照配置执行测试。

### 8.2 触发策略

| 事件 | 触发策略 | 测试范围 |
|------|---------|---------|
| PR 提交/更新 | 自动触发 | P0 + P1 用例（快速回归） |
| 合并到 main | 自动触发 | 全部用例（完整回归） |
| 发版 Tag | 自动触发 | 全部用例 |
| 手动触发 | workflow_dispatch | 可选套件或用例范围 |

### 8.3 GitHub Actions 配置

```yaml
name: RegressionEye Tests

on:
  pull_request:
    branches: [main, develop]
  push:
    branches: [main]
    tags: ['v*']
  workflow_dispatch:
    inputs:
      suite:
        description: '测试套件（留空=全部）'
        type: string

jobs:
  regression:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_DB: fenixagent
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        ports:
          - 5432:5432
    steps:
      - uses: actions/checkout@v4

      - name: 启动 FenixAgent
        run: docker compose -f docker-compose.prod.yml up -d
        working-directory: ../FenixAgent

      - name: 安装 Python + 依赖
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - run: |
          pip install -r requirements.txt
          playwright install --with-deps chromium

      - name: 运行回归测试
        run: pytest tests/ --regression-eye-report=report.json

      - name: 上报结果到看板
        if: always()
        run: |
          curl -X POST ${{ secrets.REGRESSION_EYE_URL }}/api/runs/report \
            -H "Authorization: Bearer ${{ secrets.RE_TOKEN }}" \
            -H "Content-Type: application/json" \
            -d @report.json

      - name: 上传截图
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: screenshots
          path: test-results/screenshots/
```

### 8.4 连接方式

GitHub Actions 与 RegressionEye 看板的连接是**单向 HTTP**：
- 看板部署在你们的服务器上，暴露 API
- GitHub Actions 在 workflow 中配置看板的 URL 和 Token（存在 GitHub Secrets）
- 测试跑完后用 `curl` 把结果 JSON 发到看板 API
- GitHub PR 上自动显示通过/失败状态检查

## 9. 部署方案

### 9.1 Docker Compose 配置

```yaml
services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://re:re@db:5432/regression_eye
      - SCREENSHOTS_DIR=/screenshots
    volumes:
      - screenshots:/screenshots
    depends_on:
      - db

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.frontend
    ports:
      - "3000:80"
    depends_on:
      - backend

  db:
    image: postgres:16-alpine
    environment:
      - POSTGRES_DB=regression_eye
      - POSTGRES_USER=re
      - POSTGRES_PASSWORD=re
    volumes:
      - pgdata:/var/lib/postgresql/data

  runner:
    build:
      context: .
      dockerfile: Dockerfile.runner
    environment:
      - BACKEND_URL=http://backend:8000
    volumes:
      - screenshots:/screenshots
    profiles:
      - runner

volumes:
  pgdata:
  screenshots:
```

### 9.2 部署命令

```bash
# 启动看板（常驻服务）
docker compose up -d

# 手动触发测试
docker compose --profile runner run runner pytest tests/

# 停止所有
docker compose down
```

## 10. 新增用例工作流

开发人员新增测试用例的标准流程：

1. 在 `tests/pages/` 下创建或修改 Page Object（封装页面操作）
2. 在 `tests/suites/` 下创建 `test_*.py` 文件，编写 `test_*` 函数
3. 提交代码到 Git
4. 下次测试运行时，引擎自动发现并注册新用例到数据库
5. 看板「用例管理」页面自动出现新用例

**命名约定**：
- 测试文件：`test_*.py`
- 测试函数：`test_*`
- Page Object 文件：`*_page.py`
