# 接口测试模块设计规格

> 创建日期：2026-07-27
> 状态：已确认，待实施

## 1. 概述

为 AutoTest 平台新增"后端接口测试"模块，对 FenixAgent 的 `/web/*` 和 `/api/*` 接口做功能验证 + 契约验证。与现有 Playwright UI 测试并存，在看板上独立展示。

### 1.1 目标

- 覆盖 FenixAgent 后端接口的功能正确性验证
- 自动校验响应结构是否符合预期（契约验证）
- 看板独立 Tab 展示接口测试结果
- 支持选择单条/多条用例执行，实时查看 pytest 原始日志
- 与现有 UI 测试基础设施（runner、DB、WebSocket）最大程度复用

### 1.2 范围与优先级

两套 API 都覆盖，分阶段实施：

| 阶段 | 模块 | 接口类型 |
|------|------|----------|
| 第一阶段 | Agent 相关 | `/web/*` + `/api/*` |
| 第二阶段 | 技能管理（Skills） | `/web/*` + `/api/*` |
| 第三阶段 | MCP 相关 | `/web/*` |
| 第四阶段 | 其他模块（org、apikey、tasks、channels 等） | `/web/*` + `/api/*` |
| 最后阶段 | 知识库（Knowledge Bases） | `/web/*` + `/api/*` |

## 2. 架构

### 2.1 目录结构

```
tests/
├── api_clients/                 # 接口客户端层（对应 UI 的 Page Object）
│   ├── __init__.py
│   ├── base_client.py           # HTTP 基础类：认证、重试、统一响应解析、Schema 校验
│   ├── web_client.py            # /web/* 接口客户端（session cookie 认证）
│   └── api_client.py            # /api/* 接口客户端（API Key 认证）
├── api_contracts/               # JSON Schema 契约定义
│   ├── __init__.py
│   ├── agent_schemas.py         # Agent 相关接口的响应 Schema
│   └── skill_schemas.py         # Skill 相关接口的响应 Schema
├── api_suites/                  # 接口测试用例
│   ├── __init__.py
│   ├── conftest.py              # API 测试专用 fixtures（认证客户端、测试数据清理等）
│   ├── test_agent_api.py        # Agent 接口测试
│   └── test_skill_api.py        # Skill 接口测试
├── suites/                      # 现有 UI 测试（不动）
├── pages/                       # 现有 Page Object（不动）
└── conftest.py                  # 现有全局 conftest（不动）
```

### 2.2 分层职责

| 层 | 职责 | 类比 |
|----|------|------|
| `api_clients/` | 封装 HTTP 请求、认证、响应解析、Schema 校验 | 对应 UI 的 `pages/` |
| `api_contracts/` | 定义每个接口响应的 JSON Schema | UI 测试无对应 |
| `api_suites/` | pytest 测试用例，调用 Client 方法 + assert | 对应 UI 的 `suites/` |

### 2.3 现有代码零改动

UI 测试相关的 `tests/conftest.py`、`tests/pages/`、`tests/suites/` 不做任何修改。接口测试是完全平行的新增模块。

## 3. API Client 层

### 3.1 BaseClient — 统一基础类

```python
class BaseClient:
    """HTTP 基础客户端"""

    def __init__(self, base_url: str, headers: dict = None, timeout: int = 30):
        self.client = httpx.Client(base_url=base_url, headers=headers or {}, timeout=timeout)

    def get(self, path: str, params: dict = None) -> dict:
        """发送 GET 请求，返回解析后的 JSON"""

    def post(self, path: str, json: dict = None) -> dict:
        """发送 POST 请求"""

    def put(self, path: str, json: dict = None) -> dict:
        """发送 PUT 请求"""

    def delete(self, path: str) -> dict:
        """发送 DELETE 请求"""

    def validate_schema(self, data: dict, schema: dict) -> None:
        """用 jsonschema 校验响应结构，不符合则 raise"""

    def close(self):
        """释放 HTTP 连接"""
```

**关键行为：**
- 所有请求方法自动检查 HTTP 状态码（非 2xx 抛异常）
- 自动解析 JSON 响应，解析失败抛异常
- `validate_schema()` 调用 `jsonschema.validate()`，校验失败抛 `ValidationError`

### 3.2 WebClient — 控制台接口（session cookie 认证）

```python
class WebClient(BaseClient):
    """/web/* 接口，通过登录获取 session cookie"""

    def login(self, email: str, password: str) -> None:
        """登录，cookie 自动保存在 httpx.Client 中"""

    # Agent 模块
    def list_agents(self, params: dict = None) -> dict:
    def get_agent(self, agent_id: str) -> dict:
    def create_agent(self, data: dict) -> dict:
    def update_agent(self, agent_id: str, data: dict) -> dict:
    def delete_agent(self, agent_id: str) -> dict:

    # Skill 模块（第二阶段）
    def list_skills(self, params: dict = None) -> dict:
    def get_skill(self, skill_id: str) -> dict:
    def create_skill(self, data: dict) -> dict:
    def delete_skill(self, skill_id: str) -> dict:

    # 后续模块逐步扩展...
```

### 3.3 ApiClient — 对外接口（API Key 认证）

```python
class ApiClient(BaseClient):
    """/api/* 接口，通过 API Key 认证"""

    def __init__(self, base_url: str, api_key: str):
        super().__init__(base_url, headers={"Authorization": f"Bearer {api_key}"})

    # Agent 模块
    def list_agents(self, params: dict = None) -> dict:
    def get_agent(self, agent_id: str) -> dict:

    # 后续模块逐步扩展...
```

### 3.4 新增模块扩展方式

每新增一个被测模块，只需：
1. 在 `WebClient` / `ApiClient` 中加对应方法
2. 在 `api_contracts/` 中加对应的 Schema
3. 在 `api_suites/` 中加对应的 test 文件

## 4. 契约验证

### 4.1 技术选型

使用 `jsonschema` 库，基于 JSON Schema Draft 7 定义响应结构。

### 4.2 Schema 定义示例

```python
# api_contracts/agent_schemas.py

AGENT_SCHEMA = {
    "type": "object",
    "required": ["id", "name", "createdAt"],
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "description": {"type": ["string", "null"]},
        "createdAt": {"type": "string"},
    }
}

AGENT_LIST_RESPONSE = {
    "type": "object",
    "required": ["success", "data"],
    "properties": {
        "success": {"type": "boolean"},
        "data": {"type": "array", "items": AGENT_SCHEMA}
    }
}

AGENT_DETAIL_RESPONSE = {
    "type": "object",
    "required": ["success", "data"],
    "properties": {
        "success": {"type": "boolean"},
        "data": AGENT_SCHEMA
    }
}
```

### 4.3 验证时机

每个测试用例中，调接口后立即做两层校验：

```python
def test_list_agents(web_client):
    resp = web_client.list_agents()
    web_client.validate_schema(resp, AGENT_LIST_RESPONSE)  # 契约校验
    assert len(resp["data"]) > 0                            # 功能校验
    assert resp["data"][0]["name"] != ""                    # 功能校验
```

## 5. 认证策略

### 5.1 双模式认证

| 接口类型 | 认证方式 | 客户端 |
|---------|---------|--------|
| `/web/*` | session cookie（模拟登录） | `WebClient` |
| `/api/*` | API Key（Bearer Token） | `ApiClient` |

### 5.2 认证配置

在 `tests/fixtures/test_data.yaml` 中扩展：

```yaml
fenixagent:
  url: "https://fenix-agent-ver.pazhoulab-huangpu.com"
  admin:
    email: "xiaochun@agent.com"
    password: "12345678"
  api_key: "test-api-key-xxx"     # 新增：测试用 API Key
```

### 5.3 Fixture 注入

```python
# tests/api_suites/conftest.py

@pytest.fixture(scope="session")
def web_client(test_config, base_url):
    """WebClient 实例，登录后复用"""
    client = WebClient(base_url)
    admin = test_config["fenixagent"]["admin"]
    client.login(admin["email"], admin["password"])
    yield client
    client.close()

@pytest.fixture(scope="session")
def api_client(test_config, base_url):
    """ApiClient 实例，API Key 认证"""
    api_key = test_config["fenixagent"]["api_key"]
    client = ApiClient(base_url, api_key)
    yield client
    client.close()
```

## 6. 测试数据管理

### 6.1 混合策略

| 操作类型 | 数据来源 | 示例 |
|---------|---------|------|
| 读操作（GET） | 依赖系统中已有的固定数据 | 获取 Agent 列表、查看 Agent 详情 |
| 写操作（POST/PUT/DELETE） | 测试自行创建，结束后清理 | 创建 Agent → 验证 → 删除 |

### 6.2 写操作生命周期

```python
def test_create_and_delete_agent(web_client):
    # 1. 创建测试数据
    resp = web_client.create_agent({"name": "test-agent-001", ...})
    agent_id = resp["data"]["id"]
    web_client.validate_schema(resp, AGENT_DETAIL_RESPONSE)

    # 2. 验证创建结果
    detail = web_client.get_agent(agent_id)
    assert detail["data"]["name"] == "test-agent-001"

    # 3. 清理（即使断言失败也要执行）
    web_client.delete_agent(agent_id)
```

使用 pytest fixture 的 `yield` + `finally` 确保清理逻辑一定执行。

## 7. 后端改动

### 7.1 数据库模型

在 `TestSuite` 表新增 `test_type` 字段：

```python
class TestSuite(Base):
    # ... 现有字段 ...
    test_type = Column(String(20), default="ui")  # "ui" 或 "api"
```

不需要新建表，复用现有 `TestRun`、`TestCase`、`TestResult`、`TestSuite` 模型。

### 7.2 新增 API 路由

新建 `backend/api/api_tests.py`：

| 路由 | 方法 | 说明 |
|------|------|------|
| `/api/api-tests/cases` | GET | 获取接口用例列表（支持 module、priority 筛选） |
| `/api/api-tests/run` | POST | 触发接口测试运行（支持选中用例 ID 列表） |
| `/api/api-tests/runs` | GET | 获取接口测试运行历史 |
| `/api/api-tests/runs/{id}` | GET | 获取单次运行详情 + 用例结果 |

在 `backend/main.py` 中注册路由：

```python
from backend.api import api_tests
app.include_router(api_tests.router, prefix="/api", tags=["api-tests"])
```

### 7.3 执行引擎

复用现有 `_execute_tests` 的核心逻辑，新增 `_execute_api_tests` 函数，区别：

| 项 | UI 测试 | 接口测试 |
|----|---------|---------|
| pytest 目录 | `tests/suites/` | `tests/api_suites/` |
| 浏览器 | 需要 Chromium | 不需要 |
| 命令行参数 | `--base-url` | `--api-base-url` + `--api-key` |
| 超时 | 单条 30-60s | 单条 10-15s |

### 7.4 WebSocket 推送

完全复用现有 `backend/ws.py` 的 `broadcast()` 机制：
- `run_start`：运行开始
- `log`：逐行推送 pytest stdout 原始输出
- `result_update`：每条用例结果
- `run_complete`：运行完成

### 7.5 用例自动发现

在 `backend/main.py` 的 `lifespan` 中扩展自动发现逻辑：
- 扫描 `tests/api_suites/` 目录
- 为接口测试用例创建 `test_type="api"` 的 TestSuite
- 自动注册到数据库

## 8. 前端看板

### 8.1 侧边栏

新增"接口测试"导航项：

```
📊 总览
▶ 运行记录
📋 用例管理
🔌 接口测试  ← 新增
⚙ 设置
```

### 8.2 接口测试页面

页面包含四个区域：

**统计卡片区**：总用例数、通过率、运行次数、平均耗时

**用例列表区**：
- 展示所有接口用例，每条显示：模块名、用例名、HTTP 方法、路径、优先级
- 支持按模块和优先级筛选
- 支持勾选/全选/反选
- "运行选中"按钮 + "全部运行"按钮

**运行历史区**：
- 每次运行的编号、时间、状态、通过/总数、耗时
- 点击展开查看详情

**实时日志区**（运行时展示）：
- pytest 原始 stdout 输出，通过 WebSocket 逐行推送
- 自动滚动
- 进度条显示总体进度
- 停止运行按钮

### 8.3 新增前端文件

| 文件 | 说明 |
|------|------|
| `frontend/src/pages/ApiTests.tsx` | 接口测试页面 |
| `frontend/src/api/apiTests.ts` | 接口测试相关 API 调用 |

在 `App.tsx` 中新增路由，`Sidebar.tsx` 中新增导航项。

## 9. 依赖

### 9.1 新增 Python 依赖

```
httpx>=0.27.0       # 现代 HTTP 客户端
jsonschema>=4.20.0  # JSON Schema 校验
```

加入 `requirements.txt`。

### 9.2 现有依赖复用

- `pytest`、`pytest-json-report`、`allure-pytest`：测试框架
- `pyyaml`：配置文件加载
- `fastapi`、`sqlalchemy`：后端

## 10. 验收标准

### 10.1 第一阶段（Agent 接口）完成标准

- [ ] `WebClient` 和 `ApiClient` 实现 Agent 模块全部 CRUD 方法
- [ ] Agent 相关接口 Schema 定义完成
- [ ] 至少 10 条接口测试用例可正常运行
- [ ] 写操作测试自动创建 + 清理数据
- [ ] 看板"接口测试"Tab 可查看运行历史和实时日志
- [ ] 支持选择单条/多条用例执行

### 10.2 全量完成标准

- [ ] 五个阶段模块全部覆盖
- [ ] 接口用例总数 ≥ 50 条
- [ ] 契约验证覆盖所有已测接口
- [ ] CI 可触发接口测试并上报结果
