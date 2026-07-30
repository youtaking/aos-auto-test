# 接口测试模块实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 AutoTest 平台新增后端接口测试模块，覆盖 FenixAgent 的 `/web/*` 和 `/api/*` 接口，含功能验证、契约验证、看板独立 Tab、实时日志。

**Architecture:** 在 `tests/` 下新增 `api_clients/`（HTTP 客户端层）、`api_contracts/`（JSON Schema 契约）、`api_suites/`（pytest 用例）三个平行目录，复用现有 pytest + runner + WebSocket 基础设施。后端新增 `api_tests.py` 路由和 `test_type` 字段区分 UI/API 测试。前端新增"接口测试"侧边栏 Tab 页面。

**Tech Stack:** Python (httpx, jsonschema, pytest), FastAPI, React + TypeScript, WebSocket

## Global Constraints

- 所有文件读写、命令执行使用 UTF-8 编码（`encoding="utf-8"`）
- 现有 UI 测试代码（`tests/suites/`、`tests/pages/`、`tests/conftest.py`）零改动
- 接口测试第一阶段只覆盖 Agent 相关接口
- 认证方式：`/web/*` 用 session cookie，`/api/*` 用 API Key
- 测试数据：读操作依赖固定数据，写操作自行创建+清理
- 看板独立 Tab，不与 UI 测试混在一起
- 禁止在 commit message 中添加 Co-Authored-By

## File Map

### New Files

| File | Responsibility |
|------|---------------|
| `tests/api_clients/__init__.py` | Package init |
| `tests/api_clients/base_client.py` | HTTP 基础客户端：请求、响应解析、Schema 校验 |
| `tests/api_clients/web_client.py` | `/web/*` 接口客户端（session cookie 认证） |
| `tests/api_clients/api_client.py` | `/api/*` 接口客户端（API Key 认证） |
| `tests/api_contracts/__init__.py` | Package init |
| `tests/api_contracts/agent_schemas.py` | Agent 接口 JSON Schema 定义 |
| `tests/api_suites/__init__.py` | Package init |
| `tests/api_suites/conftest.py` | API 测试专用 pytest fixtures |
| `tests/api_suites/test_agent_api.py` | Agent 接口测试用例 |
| `backend/api/api_tests.py` | 接口测试后端 API 路由 |
| `frontend/src/pages/ApiTests.tsx` | 接口测试看板页面 |
| `frontend/src/api/apiTests.ts` | 接口测试前端 API 调用 |

### Modified Files

| File | Change |
|------|--------|
| `requirements.txt` | 新增 `jsonschema>=4.20.0` |
| `tests/fixtures/test_data.yaml` | 新增 `api_key` 配置项 |
| `backend/db/models.py` | `TestSuite` 表新增 `test_type` 字段 |
| `backend/main.py` | 注册 `api_tests` 路由 + 扩展用例自动发现 |
| `frontend/src/App.tsx` | 新增 `/api-tests` 路由 |
| `frontend/src/components/Sidebar.tsx` | 新增"接口测试"导航项 |
| `frontend/src/api/types.ts` | `TestSuite` 类型新增 `test_type` 字段 |

---

### Task 1: 依赖与配置

**Files:**
- Modify: `requirements.txt`
- Modify: `tests/fixtures/test_data.yaml`

**Interfaces:**
- Consumes: nothing
- Produces: `jsonschema` 库可用；`test_data.yaml` 中 `fenixagent.api_key` 可读取

- [ ] **Step 1: 在 requirements.txt 末尾新增 jsonschema 依赖**

在 `requirements.txt` 末尾追加一行：

```
jsonschema>=4.20.0
```

注意：`httpx==0.28.1` 已存在于文件中，无需重复添加。

- [ ] **Step 2: 安装 jsonschema**

```bash
pip install jsonschema>=4.20.0
```

验证安装成功：

```bash
python -X utf8 -c "import jsonschema; print(jsonschema.__version__)"
```

Expected: 输出版本号（如 `4.23.0`）

- [ ] **Step 3: 在 test_data.yaml 中新增 api_key 配置**

在 `tests/fixtures/test_data.yaml` 的 `fenixagent` 节点下新增 `api_key` 字段：

```yaml
# 测试数据配置
fenixagent:
  url: "https://fenix-agent-ver.pazhoulab-huangpu.com"
  admin:
    email: "xiaochun@agent.com"
    password: "12345678"
  api_key: "test-api-key-placeholder"

test_users:
  - email: "test@example.com"
    password: "test123"
    role: "user"
```

> 注意：`api_key` 的值需要替换为真实的测试用 API Key。如果系统中尚未创建 API Key，先手动在 FenixAgent 控制台创建一个并填入。

- [ ] **Step 4: 提交**

```bash
git add requirements.txt tests/fixtures/test_data.yaml
git commit -m "feat: 添加 jsonschema 依赖和 API Key 测试配置"
```

---

### Task 2: BaseClient — HTTP 基础客户端

**Files:**
- Create: `tests/api_clients/__init__.py`
- Create: `tests/api_clients/base_client.py`
- Test: 直接在 Task 5 的用例中验证

**Interfaces:**
- Consumes: `httpx.Client`, `jsonschema.validate`
- Produces: `BaseClient` 类，供 `WebClient` 和 `ApiClient` 继承

```python
class BaseClient:
    def __init__(self, base_url: str, headers: dict | None = None, timeout: int = 30) -> None
    def get(self, path: str, params: dict | None = None) -> dict
    def post(self, path: str, json: dict | None = None) -> dict
    def put(self, path: str, json: dict | None = None) -> dict
    def delete(self, path: str, params: dict | None = None) -> dict
    def validate_schema(self, data: dict, schema: dict) -> None
    def close(self) -> None
```

- [ ] **Step 1: 创建 `__init__.py`**

创建 `tests/api_clients/__init__.py`，内容为空文件。

- [ ] **Step 2: 编写 BaseClient**

创建 `tests/api_clients/base_client.py`：

```python
# tests/api_clients/base_client.py
"""HTTP 基础客户端：封装请求、响应解析、Schema 校验"""
import httpx
import jsonschema


class BaseClient:
    """HTTP 基础客户端，供 WebClient / ApiClient 继承"""

    def __init__(self, base_url: str, headers: dict | None = None, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(
            base_url=self.base_url,
            headers=headers or {},
            timeout=timeout,
            verify=False,  # 测试环境可能用自签证书
        )

    def get(self, path: str, params: dict | None = None) -> dict:
        """发送 GET 请求，返回解析后的 JSON"""
        resp = self.client.get(path, params=params)
        return self._parse_response(resp)

    def post(self, path: str, json: dict | None = None) -> dict:
        """发送 POST 请求"""
        resp = self.client.post(path, json=json)
        return self._parse_response(resp)

    def put(self, path: str, json: dict | None = None) -> dict:
        """发送 PUT 请求"""
        resp = self.client.put(path, json=json)
        return self._parse_response(resp)

    def delete(self, path: str, params: dict | None = None) -> dict:
        """发送 DELETE 请求"""
        resp = self.client.delete(path, params=params)
        return self._parse_response(resp)

    def validate_schema(self, data: dict, schema: dict) -> None:
        """用 JSON Schema 校验响应结构，不符合则抛出 ValidationError"""
        jsonschema.validate(instance=data, schema=schema)

    def close(self):
        """释放 HTTP 连接"""
        self.client.close()

    def _parse_response(self, resp: httpx.Response) -> dict:
        """统一解析响应：检查状态码 + 解析 JSON"""
        resp.raise_for_status()
        return resp.json()
```

- [ ] **Step 3: 验证模块可导入**

```bash
python -X utf8 -c "from tests.api_clients.base_client import BaseClient; print('BaseClient OK')"
```

Expected: `BaseClient OK`

- [ ] **Step 4: 提交**

```bash
git add tests/api_clients/__init__.py tests/api_clients/base_client.py
git commit -m "feat: 添加 API 测试基础客户端 BaseClient"
```

---

### Task 3: WebClient — 控制台接口客户端

**Files:**
- Create: `tests/api_clients/web_client.py`

**Interfaces:**
- Consumes: `BaseClient`（Task 2）
- Produces: `WebClient` 类

```python
class WebClient(BaseClient):
    def login(self, email: str, password: str) -> None
    def list_agents(self, params: dict | None = None) -> dict
    def get_agent(self, agent_id: str) -> dict
    def create_agent(self, data: dict) -> dict
    def update_agent(self, agent_id: str, data: dict) -> dict
    def delete_agent(self, agent_id: str) -> dict
```

- [ ] **Step 1: 编写 WebClient**

创建 `tests/api_clients/web_client.py`：

```python
# tests/api_clients/web_client.py
"""/web/* 控制台接口客户端（session cookie 认证）"""
from tests.api_clients.base_client import BaseClient


class WebClient(BaseClient):
    """控制台内部接口客户端，通过登录获取 session cookie"""

    def login(self, email: str, password: str) -> None:
        """登录，cookie 自动保存在 httpx.Client 中"""
        resp = self.client.post("/web/auth/login", json={
            "email": email,
            "password": password,
        })
        resp.raise_for_status()

    # ── Agent 模块 ──

    def list_agents(self, params: dict | None = None) -> dict:
        """获取 Agent 列表"""
        return self.get("/web/agents", params=params)

    def get_agent(self, agent_id: str) -> dict:
        """获取 Agent 详情"""
        return self.get(f"/web/agents/{agent_id}")

    def create_agent(self, data: dict) -> dict:
        """创建 Agent"""
        return self.post("/web/agents", json=data)

    def update_agent(self, agent_id: str, data: dict) -> dict:
        """更新 Agent"""
        return self.put(f"/web/agents/{agent_id}", json=data)

    def delete_agent(self, agent_id: str) -> dict:
        """删除 Agent"""
        return self.delete(f"/web/agents/{agent_id}")
```

> **注意：** 以上路径（`/web/auth/login`、`/web/agents` 等）是基于 FenixAgent 路由结构推断的。实施时需要对照 FenixAgent 源码 `src/routes/web/` 确认实际路径。如果路径不对，需要调整。

- [ ] **Step 2: 验证模块可导入**

```bash
python -X utf8 -c "from tests.api_clients.web_client import WebClient; print('WebClient OK')"
```

Expected: `WebClient OK`

- [ ] **Step 3: 提交**

```bash
git add tests/api_clients/web_client.py
git commit -m "feat: 添加 WebClient 控制台接口客户端"
```

---

### Task 4: ApiClient — 对外接口客户端

**Files:**
- Create: `tests/api_clients/api_client.py`

**Interfaces:**
- Consumes: `BaseClient`（Task 2）
- Produces: `ApiClient` 类

```python
class ApiClient(BaseClient):
    def __init__(self, base_url: str, api_key: str, timeout: int = 30) -> None
    def list_agents(self, params: dict | None = None) -> dict
    def get_agent(self, agent_id: str) -> dict
```

- [ ] **Step 1: 编写 ApiClient**

创建 `tests/api_clients/api_client.py`：

```python
# tests/api_clients/api_client.py
"""/api/* 对外接口客户端（API Key 认证）"""
from tests.api_clients.base_client import BaseClient


class ApiClient(BaseClient):
    """对外 OpenAPI 接口客户端，通过 API Key 认证"""

    def __init__(self, base_url: str, api_key: str, timeout: int = 30):
        super().__init__(
            base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )

    # ── Agent 模块 ──

    def list_agents(self, params: dict | None = None) -> dict:
        """获取 Agent 列表"""
        return self.get("/api/agents", params=params)

    def get_agent(self, agent_id: str) -> dict:
        """获取 Agent 详情"""
        return self.get(f"/api/agents/{agent_id}")
```

- [ ] **Step 2: 验证模块可导入**

```bash
python -X utf8 -c "from tests.api_clients.api_client import ApiClient; print('ApiClient OK')"
```

Expected: `ApiClient OK`

- [ ] **Step 3: 提交**

```bash
git add tests/api_clients/api_client.py
git commit -m "feat: 添加 ApiClient 对外接口客户端"
```

---

### Task 5: Agent 接口 Schema 定义

**Files:**
- Create: `tests/api_contracts/__init__.py`
- Create: `tests/api_contracts/agent_schemas.py`

**Interfaces:**
- Consumes: nothing
- Produces: `AGENT_SCHEMA`, `AGENT_LIST_RESPONSE`, `AGENT_DETAIL_RESPONSE`, `CREATE_AGENT_RESPONSE` 四个 Schema dict

- [ ] **Step 1: 创建 `__init__.py`**

创建 `tests/api_contracts/__init__.py`，内容为空文件。

- [ ] **Step 2: 编写 Agent Schema**

创建 `tests/api_contracts/agent_schemas.py`：

```python
# tests/api_contracts/agent_schemas.py
"""Agent 接口响应 JSON Schema 定义"""

AGENT_SCHEMA = {
    "type": "object",
    "required": ["id", "name"],
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "description": {"type": ["string", "null"]},
        "avatar": {"type": ["string", "null"]},
        "model": {"type": ["string", "null"]},
        "systemPrompt": {"type": ["string", "null"]},
        "createdAt": {"type": "string"},
        "updatedAt": {"type": ["string", "null"]},
    },
    "additionalProperties": True,
}

AGENT_LIST_RESPONSE = {
    "type": "object",
    "required": ["success", "data"],
    "properties": {
        "success": {"type": "boolean"},
        "data": {"type": "array", "items": AGENT_SCHEMA},
    },
}

AGENT_DETAIL_RESPONSE = {
    "type": "object",
    "required": ["success", "data"],
    "properties": {
        "success": {"type": "boolean"},
        "data": AGENT_SCHEMA,
    },
}

CREATE_AGENT_RESPONSE = {
    "type": "object",
    "required": ["success", "data"],
    "properties": {
        "success": {"type": "boolean"},
        "data": AGENT_SCHEMA,
    },
}
```

> **注意：** `AGENT_SCHEMA` 中的字段名（`id`、`name`、`createdAt` 等）是基于 FenixAgent Drizzle Schema 推断的。实施时需要对照 `FenixAgent/src/db/schema.ts` 确认实际字段名。`additionalProperties: True` 允许响应包含未定义的额外字段，不会因此校验失败。

- [ ] **Step 3: 验证模块可导入**

```bash
python -X utf8 -c "from tests.api_contracts.agent_schemas import AGENT_LIST_RESPONSE; print('agent_schemas OK')"
```

Expected: `agent_schemas OK`

- [ ] **Step 4: 提交**

```bash
git add tests/api_contracts/__init__.py tests/api_contracts/agent_schemas.py
git commit -m "feat: 添加 Agent 接口 JSON Schema 契约定义"
```

---

### Task 6: API 测试 Fixtures

**Files:**
- Create: `tests/api_suites/__init__.py`
- Create: `tests/api_suites/conftest.py`

**Interfaces:**
- Consumes: `WebClient`（Task 3）、`ApiClient`（Task 4）、`tests/fixtures/test_data.yaml`（Task 1）
- Produces: pytest fixtures `api_base_url`, `web_client`, `api_client`

- [ ] **Step 1: 创建 `__init__.py`**

创建 `tests/api_suites/__init__.py`，内容为空文件。

- [ ] **Step 2: 编写 conftest.py**

创建 `tests/api_suites/conftest.py`：

```python
# tests/api_suites/conftest.py
"""API 测试专用 pytest fixtures"""
import pytest
import yaml
from pathlib import Path
from tests.api_clients.web_client import WebClient
from tests.api_clients.api_client import ApiClient


@pytest.fixture(scope="session")
def api_test_config():
    """加载测试配置"""
    config_path = Path(__file__).parent.parent / "fixtures" / "test_data.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="session")
def api_base_url(request, api_test_config):
    """被测系统 URL"""
    cli_url = request.config.getoption("--base-url", default="")
    if cli_url:
        return cli_url
    return api_test_config["fenixagent"]["url"]


@pytest.fixture(scope="session")
def web_client(api_base_url, api_test_config):
    """WebClient 实例，登录后复用"""
    client = WebClient(api_base_url)
    admin = api_test_config["fenixagent"]["admin"]
    client.login(admin["email"], admin["password"])
    yield client
    client.close()


@pytest.fixture(scope="session")
def api_client(api_base_url, api_test_config):
    """ApiClient 实例，API Key 认证"""
    api_key = api_test_config["fenixagent"]["api_key"]
    client = ApiClient(api_base_url, api_key)
    yield client
    client.close()
```

- [ ] **Step 3: 验证 conftest 可加载**

```bash
python -X utf8 -m pytest tests/api_suites/ --collect-only -q 2>&1 | head -5
```

Expected: 输出 `no tests ran` 或 `collected 0 items`（因为还没有测试文件），不应报错。

- [ ] **Step 4: 提交**

```bash
git add tests/api_suites/__init__.py tests/api_suites/conftest.py
git commit -m "feat: 添加 API 测试专用 pytest fixtures"
```

---

### Task 7: Agent 接口测试用例

**Files:**
- Create: `tests/api_suites/test_agent_api.py`

**Interfaces:**
- Consumes: `web_client`（Task 6）、`api_client`（Task 6）、`AGENT_LIST_RESPONSE` / `AGENT_DETAIL_RESPONSE` / `CREATE_AGENT_RESPONSE`（Task 5）
- Produces: pytest 测试函数（自动被 runner 发现）

- [ ] **Step 1: 编写 Agent 接口测试用例**

创建 `tests/api_suites/test_agent_api.py`：

```python
# tests/api_suites/test_agent_api.py
"""Agent 接口测试：功能验证 + 契约验证"""
import pytest
from tests.api_contracts.agent_schemas import (
    AGENT_LIST_RESPONSE,
    AGENT_DETAIL_RESPONSE,
    CREATE_AGENT_RESPONSE,
)


class TestAgentWebAPI:
    """/web/* Agent 接口测试（session cookie 认证）"""

    def test_list_agents(self, web_client):
        """获取 Agent 列表：返回非空数组"""
        resp = web_client.list_agents()
        web_client.validate_schema(resp, AGENT_LIST_RESPONSE)
        assert isinstance(resp["data"], list)
        assert len(resp["data"]) > 0

    def test_get_agent(self, web_client):
        """获取单个 Agent 详情：先拿列表取第一个 ID，再查详情"""
        list_resp = web_client.list_agents()
        assert len(list_resp["data"]) > 0, "Agent 列表为空，无法测试详情"
        agent_id = list_resp["data"][0]["id"]

        resp = web_client.get_agent(agent_id)
        web_client.validate_schema(resp, AGENT_DETAIL_RESPONSE)
        assert resp["data"]["id"] == agent_id

    def test_create_and_delete_agent(self, web_client):
        """创建并删除 Agent：写操作生命周期测试"""
        test_name = "api-test-agent-001"
        create_data = {
            "name": test_name,
            "description": "API 测试自动创建的 Agent，测试结束后删除",
        }

        # 创建
        create_resp = web_client.create_agent(create_data)
        web_client.validate_schema(create_resp, CREATE_AGENT_RESPONSE)
        agent_id = create_resp["data"]["id"]
        assert create_resp["data"]["name"] == test_name

        try:
            # 验证创建成功
            get_resp = web_client.get_agent(agent_id)
            assert get_resp["data"]["name"] == test_name
        finally:
            # 清理：无论断言是否失败都要删除
            web_client.delete_agent(agent_id)

    def test_update_agent(self, web_client):
        """更新 Agent：创建 → 修改名称 → 验证 → 删除"""
        test_name = "api-test-agent-002"
        updated_name = "api-test-agent-002-updated"

        create_resp = web_client.create_agent({"name": test_name})
        agent_id = create_resp["data"]["id"]

        try:
            update_resp = web_client.update_agent(agent_id, {"name": updated_name})
            assert update_resp["data"]["name"] == updated_name

            # 再次获取确认更新生效
            get_resp = web_client.get_agent(agent_id)
            assert get_resp["data"]["name"] == updated_name
        finally:
            web_client.delete_agent(agent_id)

    def test_get_nonexistent_agent(self, web_client):
        """获取不存在的 Agent：应返回 404 或 success=false"""
        with pytest.raises(Exception):
            web_client.get_agent("nonexistent-agent-id-99999")


class TestAgentOpenAPI:
    """/api/* Agent 接口测试（API Key 认证）"""

    def test_list_agents(self, api_client):
        """通过 OpenAPI 获取 Agent 列表"""
        resp = api_client.list_agents()
        api_client.validate_schema(resp, AGENT_LIST_RESPONSE)
        assert isinstance(resp["data"], list)

    def test_get_agent(self, api_client):
        """通过 OpenAPI 获取单个 Agent 详情"""
        list_resp = api_client.list_agents()
        if len(list_resp["data"]) == 0:
            pytest.skip("Agent 列表为空，跳过详情测试")
        agent_id = list_resp["data"][0]["id"]

        resp = api_client.get_agent(agent_id)
        api_client.validate_schema(resp, AGENT_DETAIL_RESPONSE)
        assert resp["data"]["id"] == agent_id
```

- [ ] **Step 2: 验证用例可被 pytest 发现**

```bash
python -X utf8 -m pytest tests/api_suites/test_agent_api.py --collect-only -q
```

Expected: 输出 7 个测试函数名（`test_list_agents`, `test_get_agent`, `test_create_and_delete_agent`, `test_update_agent`, `test_get_nonexistent_agent` × 2 类）

- [ ] **Step 3: 提交**

```bash
git add tests/api_suites/test_agent_api.py
git commit -m "feat: 添加 Agent 接口测试用例（功能验证 + 契约验证）"
```

---

### Task 8: 后端数据库模型 — 新增 test_type 字段

**Files:**
- Modify: `backend/db/models.py`

**Interfaces:**
- Consumes: nothing
- Produces: `TestSuite.test_type` 字段（`"ui"` 或 `"api"`）

- [ ] **Step 1: 在 TestSuite 模型中新增 test_type 字段**

在 `backend/db/models.py` 的 `TestSuite` 类中，`created_at` 字段后面新增一行：

```python
    test_type = Column(String(20), default="ui")  # "ui" 或 "api"
```

修改后的 `TestSuite` 类如下：

```python
class TestSuite(Base):
    __tablename__ = "test_suites"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    tags = Column(String(500), default="")
    test_type = Column(String(20), default="ui")  # "ui" 或 "api"
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="suites")
    cases = relationship("TestCase", back_populates="suite", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_test_suites_project_id", "project_id"),
    )
```

- [ ] **Step 2: 验证模型可导入**

```bash
python -X utf8 -c "from backend.db.models import TestSuite; print('test_type' in [c.name for c in TestSuite.__table__.columns])"
```

Expected: `True`

- [ ] **Step 3: 提交**

```bash
git add backend/db/models.py
git commit -m "feat: TestSuite 模型新增 test_type 字段区分 UI/API 测试"
```

---

### Task 9: 后端 API 路由 — 接口测试端点

**Files:**
- Create: `backend/api/api_tests.py`
- Modify: `backend/main.py`

**Interfaces:**
- Consumes: `TestSuite`（Task 8）、`TestRun`、`TestCase`、`TestResult`、`ws.broadcast`
- Produces: 4 个 API 端点 + `_execute_api_tests` 后台任务

- [ ] **Step 1: 创建 api_tests.py 路由文件**

创建 `backend/api/api_tests.py`：

```python
# backend/api/api_tests.py
"""接口测试 API 路由"""
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.db.config import get_async_session, async_session
from backend.db.models import TestRun, TestResult, TestCase, TestSuite, Project
from backend.schemas.run import RunResponse, ResultResponse
from backend.schemas.common import ApiResponse
from backend import ws as ws_module

router = APIRouter()

API_TEST_DIR = "tests/api_suites/"


def _parse_pytest_line(line: str) -> dict | None:
    """解析 pytest -v 输出的单行结果"""
    m = re.match(r"^(tests/\S+::\w+)\s+(PASSED|FAILED|SKIPPED|ERROR)", line.strip())
    if not m:
        return None
    nodeid = m.group(1)
    outcome = m.group(2).lower()
    parts = nodeid.split("::")
    file_path = parts[0] if parts else ""
    func_name = parts[-1] if len(parts) > 1 else ""
    suite_name = Path(file_path).stem.replace("test_", "")
    return {
        "nodeid": nodeid,
        "file_path": file_path,
        "func_name": func_name,
        "suite_name": suite_name,
        "outcome": outcome,
    }


async def _execute_api_tests(
    run_id: int,
    api_base_url: str,
    api_key: str,
    case_ids: list[int] | None = None,
):
    """后台任务：执行 pytest api_suites，逐条实时更新结果 + WebSocket 广播日志"""
    async with async_session() as db:
        run = await db.get(TestRun, run_id)
        if not run:
            return

        run.status = "running"
        run.started_at = datetime.utcnow()
        await db.commit()

        await ws_module.broadcast(run_id, "run_start", {"run_id": run_id, "status": "running"})

        report_path = f"api_report_{run_id}.json"
        cmd = [
            sys.executable, "-m", "pytest", API_TEST_DIR,
            "-v", "--tb=short",
            f"--base-url={api_base_url}",
            "--json-report", f"--json-report-file={report_path}",
        ]

        if case_ids:
            cases_query = await db.execute(
                select(TestCase).where(TestCase.id.in_(case_ids))
            )
            func_names = [c.function_name for c in cases_query.scalars().all()]
            if func_names:
                k_expr = " or ".join(func_names)
                cmd.extend(["-k", k_expr])

        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
        )

        passed = 0
        failed = 0
        skipped = 0

        for line in proc.stdout:
            stripped = line.rstrip()
            if stripped:
                await ws_module.broadcast(run_id, "log", {"line": stripped})

            parsed = _parse_pytest_line(line)
            if not parsed:
                continue

            func_name = parsed["func_name"]
            outcome = parsed["outcome"]

            case_query = await db.execute(
                select(TestCase).where(TestCase.function_name == func_name)
            )
            case = case_query.scalar_one_or_none()

            result = TestResult(
                run_id=run_id,
                case_id=case.id if case else None,
                case_name=func_name,
                suite_name=parsed["suite_name"],
                status=outcome if outcome in ("passed", "failed", "skipped") else "error",
                duration_ms=0,
            )
            db.add(result)

            if outcome == "passed":
                passed += 1
            elif outcome in ("failed", "error"):
                failed += 1
            else:
                skipped += 1

            run.total = passed + failed + skipped
            run.passed = passed
            run.failed = failed
            run.skipped = skipped
            await db.commit()

            await ws_module.broadcast(run_id, "result_update", {
                "case_name": func_name,
                "suite_name": parsed["suite_name"],
                "status": outcome,
                "passed": passed, "failed": failed, "skipped": skipped,
            })

        proc.wait(timeout=300)
        finished = datetime.utcnow()

        # 用 JSON 报告补充 duration 和 error 信息
        rf = Path(report_path)
        if rf.exists():
            with open(rf, "r", encoding="utf-8") as f:
                report = json.load(f)
            for test in report.get("tests", []):
                nodeid = test.get("nodeid", "")
                func_name = nodeid.split("::")[-1] if "::" in nodeid else ""
                call_info = test.get("call", {})
                duration_ms = int(call_info.get("duration", 0) * 1000)
                longrepr = str(call_info.get("longrepr", "")) if call_info.get("longrepr") else None
                existing = await db.execute(
                    select(TestResult).where(
                        TestResult.run_id == run_id,
                        TestResult.case_name == func_name,
                    )
                )
                r = existing.scalar_one_or_none()
                if r:
                    r.duration_ms = duration_ms
                    r.error_message = longrepr[:500] if longrepr else None
                    r.stack_trace = longrepr
            rf.unlink(missing_ok=True)

        run.status = "passed" if failed == 0 else "failed"
        run.finished_at = finished
        run.duration_ms = int((finished - run.started_at).total_seconds() * 1000)
        await db.commit()

        await ws_module.broadcast(run_id, "run_complete", {
            "run_id": run_id,
            "status": run.status,
            "total": run.total,
            "passed": run.passed,
            "failed": run.failed,
            "skipped": run.skipped,
            "duration_ms": run.duration_ms,
        })


@router.get("/api-tests/cases", response_model=ApiResponse)
async def list_api_cases(
    module: str | None = None,
    priority: str | None = None,
    db: AsyncSession = Depends(get_async_session),
):
    """获取接口测试用例列表"""
    # 先找到 test_type=api 的 suites
    suite_query = await db.execute(
        select(TestSuite).where(TestSuite.test_type == "api")
    )
    suite_ids = [s.id for s in suite_query.scalars().all()]
    if not suite_ids:
        return ApiResponse(data=[])

    query = select(TestCase).where(TestCase.suite_id.in_(suite_ids))
    if module:
        query = query.where(TestCase.tags.contains(module))
    if priority:
        query = query.where(TestCase.priority == priority)
    query = query.order_by(TestCase.id)

    result = await db.execute(query)
    cases = result.scalars().all()

    return ApiResponse(data=[{
        "id": c.id,
        "suite_id": c.suite_id,
        "name": c.name,
        "file_path": c.file_path,
        "function_name": c.function_name,
        "tags": c.tags,
        "priority": c.priority,
        "timeout": c.timeout,
    } for c in cases])


@router.post("/api-tests/run", response_model=ApiResponse)
async def trigger_api_run(
    background_tasks: BackgroundTasks,
    project_id: int,
    case_ids: str = "",
    db: AsyncSession = Depends(get_async_session),
):
    """触发接口测试运行"""
    project = await db.get(Project, project_id)
    if not project:
        return ApiResponse(success=False, error="项目不存在")

    parsed_case_ids = None
    if case_ids:
        try:
            parsed_case_ids = [int(x.strip()) for x in case_ids.split(",") if x.strip()]
        except ValueError:
            parsed_case_ids = None

    run = TestRun(
        project_id=project_id,
        trigger_type="manual",
        status="pending",
        started_at=datetime.utcnow(),
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    # 从配置读取 api_key（这里简化处理，实际应从项目配置或环境变量读取）
    import os
    api_key = os.environ.get("FENIX_API_KEY", "test-api-key-placeholder")

    background_tasks.add_task(
        _execute_api_tests, run.id, project.url, api_key, parsed_case_ids
    )

    return ApiResponse(data=RunResponse.model_validate(run))


@router.get("/api-tests/runs", response_model=ApiResponse)
async def list_api_runs(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_async_session),
):
    """获取接口测试运行历史"""
    # 只返回关联了 api 类型 suite 的运行
    # 简化处理：返回所有运行，前端可通过 suite 类型筛选
    api_suite_ids_q = await db.execute(
        select(TestSuite.id).where(TestSuite.test_type == "api")
    )
    api_suite_ids = {r[0] for r in api_suite_ids_q.all()}

    # 查找包含 api 结果的运行
    api_run_ids_q = await db.execute(
        select(TestResult.run_id).distinct().where(
            TestResult.suite_name.in_(["agent_api"])  # 根据 suite 命名
        )
    )
    api_run_ids = {r[0] for r in api_run_ids_q.all()}

    query = select(TestRun).where(TestRun.id.in_(api_run_ids)).order_by(TestRun.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    runs = result.scalars().all()
    return ApiResponse(data=[RunResponse.model_validate(r) for r in runs])


@router.get("/api-tests/runs/{run_id}", response_model=ApiResponse)
async def get_api_run(run_id: int, db: AsyncSession = Depends(get_async_session)):
    """获取接口测试单次运行详情"""
    run = await db.get(TestRun, run_id)
    if not run:
        return ApiResponse(success=False, error="运行记录不存在")

    results_q = await db.execute(
        select(TestResult).where(TestResult.run_id == run_id).order_by(TestResult.id)
    )
    results = results_q.scalars().all()

    return ApiResponse(data={
        "run": RunResponse.model_validate(run),
        "results": [ResultResponse.model_validate(r) for r in results],
    })
```

- [ ] **Step 2: 在 main.py 中注册路由**

在 `backend/main.py` 顶部的 import 区域，修改 `from backend.api import` 行：

```python
from backend.api import projects, suites, runs, cases, dashboard, api_tests
```

在 `app.include_router` 区域追加一行：

```python
app.include_router(api_tests.router, prefix="/api", tags=["api-tests"])
```

- [ ] **Step 3: 验证服务可启动**

```bash
python -X utf8 -c "from backend.main import app; print('routes:', [r.path for r in app.routes if 'api-test' in r.path])"
```

Expected: 输出包含 `/api/api-tests/cases` 等路径的列表

- [ ] **Step 4: 提交**

```bash
git add backend/api/api_tests.py backend/main.py
git commit -m "feat: 添加接口测试后端 API 路由（用例列表、触发运行、运行历史）"
```

---

### Task 10: 后端用例自动发现 — 扩展 lifespan

**Files:**
- Modify: `backend/main.py`

**Interfaces:**
- Consumes: `tests/api_suites/` 目录（Task 7）
- Produces: 启动时自动扫描 `api_suites/` 并注册 `test_type="api"` 的 TestSuite

- [ ] **Step 1: 扩展 main.py 的 lifespan 函数**

在 `backend/main.py` 的 `lifespan` 函数中，现有的用例发现逻辑（扫描 `tests/suites/`）之后，新增扫描 `tests/api_suites/` 的逻辑。

在 `print(f"[AutoDiscover] 发现 {len(collected)} 条用例，新增 {new_cases} 条")` 这行之后，`except Exception as e:` 之前，插入以下代码块：

```python
            # ── 接口测试用例自动发现 ──
            try:
                api_collected = runner.collect_tests_api()
                if api_collected:
                    api_new = 0
                    for item in api_collected:
                        suite_key = item["suite_name"]
                        func_name = item["function_name"]
                        suite_label = SUITE_LABELS.get(suite_key, suite_key.title()) + " (API)"

                        if suite_label not in suites:
                            suite = TestSuite(
                                project_id=project.id,
                                name=suite_label,
                                description=f"自动发现的 {suite_key} 接口测试套件",
                                tags=suite_key,
                                test_type="api",
                            )
                            db.add(suite)
                            await db.flush()
                            suites[suite_label] = suite

                        suite = suites[suite_label]
                        existing = await db.execute(
                            select(TestCase).where(TestCase.function_name == func_name)
                        )
                        if existing.scalar_one_or_none():
                            continue

                        db.add(TestCase(
                            suite_id=suite.id,
                            name=func_name.replace("test_", "").replace("_", " ").title(),
                            file_path=item["file_path"],
                            function_name=func_name,
                            tags=f"api,{suite_key}",
                            priority="P0",
                            timeout=15,
                        ))
                        api_new += 1

                    await db.commit()
                    print(f"[AutoDiscover] 接口测试：发现 {len(api_collected)} 条用例，新增 {api_new} 条")
            except Exception as e:
                print(f"[AutoDiscover] 接口测试用例发现失败: {e}")
```

- [ ] **Step 2: 在 TestRunner 中添加 collect_tests_api 方法**

在 `engine/runner.py` 的 `TestRunner` 类中，`collect_tests` 方法之后新增：

```python
    def collect_tests_api(self, test_dir: str = "tests/api_suites") -> list[dict]:
        """扫描 api_suites 目录的测试用例"""
        return self._collect_from_dir(test_dir)

    def _collect_from_dir(self, test_dir: str) -> list[dict]:
        """从指定目录收集测试用例"""
        result = subprocess.run(
            [sys.executable, "-m", "pytest", test_dir, "--collect-only", "-q",
             "--no-header", "-p", "no:cacheprovider"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )

        stdout = result.stdout or ""
        collected = []
        current_file = ""

        for line in stdout.splitlines():
            line_stripped = line.strip()

            if "<Module " in line_stripped:
                module_name = line_stripped.split("<Module ")[-1].rstrip(">").strip()
                current_file = f"{test_dir}/{module_name}"
                continue

            if "<Function " in line_stripped and current_file:
                func_name = line_stripped.split("<Function ")[-1].rstrip(">").strip()
                suite_name = Path(current_file).stem.replace("test_", "")
                collected.append({
                    "suite_name": suite_name,
                    "file_path": current_file,
                    "function_name": func_name,
                })
                continue

            if "::" in line_stripped and line_stripped.startswith(("tests/", ".")):
                parts = line_stripped.split("::")
                if len(parts) >= 2:
                    file_path = parts[0]
                    func_name = parts[-1]
                    suite_name = Path(file_path).stem.replace("test_", "")
                    collected.append({
                        "suite_name": suite_name,
                        "file_path": file_path,
                        "function_name": func_name,
                    })

        return collected
```

- [ ] **Step 3: 验证自动发现逻辑**

```bash
python -X utf8 -c "from engine.runner import TestRunner; r = TestRunner(); print(len(r.collect_tests_api()), 'api cases')"
```

Expected: 输出发现的接口测试用例数（应 ≥ 7）

- [ ] **Step 4: 提交**

```bash
git add backend/main.py engine/runner.py
git commit -m "feat: 扩展用例自动发现，支持扫描 api_suites 目录"
```

---

### Task 11: 前端类型与 API 层

**Files:**
- Modify: `frontend/src/api/types.ts`
- Create: `frontend/src/api/apiTests.ts`

**Interfaces:**
- Consumes: `get`/`post` from `client.ts`
- Produces: `listApiCases()`, `triggerApiRun()`, `listApiRuns()`, `getApiRun()`

- [ ] **Step 1: 在 types.ts 中扩展 TestSuite 类型**

在 `frontend/src/api/types.ts` 的 `TestSuite` 接口中，`tags: string;` 之后新增：

```typescript
  test_type: string;
```

- [ ] **Step 2: 创建 apiTests.ts**

创建 `frontend/src/api/apiTests.ts`：

```typescript
import { get, post } from "./client";
import type { TestRun, TestResult } from "./types";

export interface ApiTestCase {
  id: number;
  suite_id: number;
  name: string;
  file_path: string;
  function_name: string;
  tags: string;
  priority: string;
  timeout: number;
}

export interface ApiRunDetail {
  run: TestRun;
  results: TestResult[];
}

export const listApiCases = (params?: { module?: string; priority?: string }) =>
  get<ApiTestCase[]>("/api-tests/cases", params);

export const triggerApiRun = (projectId: number, caseIds?: number[]) => {
  const params = new URLSearchParams({ project_id: String(projectId) });
  if (caseIds && caseIds.length > 0) {
    params.set("case_ids", caseIds.join(","));
  }
  return post<TestRun>(`/api-tests/run?${params}`);
};

export const listApiRuns = (page = 1, pageSize = 20) =>
  get<TestRun[]>("/api-tests/runs", { page, page_size: pageSize });

export const getApiRun = (id: number) =>
  get<ApiRunDetail>(`/api-tests/runs/${id}`);
```

- [ ] **Step 3: 验证 TypeScript 编译**

```bash
cd frontend && npx tsc --noEmit --skipLibCheck 2>&1 | head -10
```

Expected: 无新增错误

- [ ] **Step 4: 提交**

```bash
git add frontend/src/api/types.ts frontend/src/api/apiTests.ts
git commit -m "feat: 添加接口测试前端 API 层和类型定义"
```

---

### Task 12: 前端接口测试页面

**Files:**
- Create: `frontend/src/pages/ApiTests.tsx`

**Interfaces:**
- Consumes: `listApiCases`, `triggerApiRun`, `listApiRuns`, `getApiRun`（Task 11）、WebSocket `ws/runs/{id}`
- Produces: 完整的接口测试看板页面组件

- [ ] **Step 1: 编写 ApiTests.tsx**

创建 `frontend/src/pages/ApiTests.tsx`：

```tsx
import { useEffect, useState, useRef, useCallback } from "react";
import { listApiCases, triggerApiRun, listApiRuns, getApiRun } from "../api/apiTests";
import { listProjects } from "../api/projects";
import type { ApiTestCase, ApiRunDetail } from "../api/apiTests";
import type { TestRun, TestResult, Project } from "../api/types";

const statusIcon: Record<string, string> = {
  passed: "✅", failed: "❌", skipped: "⏭️", error: "⚠️",
  running: "🔄", pending: "⏳",
};

const statusBadge: Record<string, string> = {
  passed: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
  running: "bg-blue-100 text-blue-700",
  pending: "bg-gray-100 text-gray-700",
};

export default function ApiTests() {
  const [cases, setCases] = useState<ApiTestCase[]>([]);
  const [runs, setRuns] = useState<TestRun[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [running, setRunning] = useState(false);
  const [activeRunId, setActiveRunId] = useState<number | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [runResults, setRunResults] = useState<TestResult[]>([]);
  const [activeRun, setActiveRun] = useState<TestRun | null>(null);
  const [moduleFilter, setModuleFilter] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("");
  const [projects, setProjects] = useState<Project[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const logEndRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const scrollToEnd = useCallback(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    if (logs.length > 0) scrollToEnd();
  }, [logs, scrollToEnd]);

  // 加载用例和项目
  useEffect(() => {
    const params: Record<string, string> = {};
    if (moduleFilter) params.module = moduleFilter;
    if (priorityFilter) params.priority = priorityFilter;
    listApiCases(params).then(setCases).catch(console.error);
    listProjects().then(setProjects).catch(console.error);
    listApiRuns().then(setRuns).catch(console.error);
  }, [moduleFilter, priorityFilter]);

  // 轮询运行列表
  useEffect(() => {
    const fetch = () => {
      listApiRuns().then((data) => {
        setRuns(data);
        const hasActive = data.some((r) => r.status === "pending" || r.status === "running");
        if (hasActive && !timerRef.current) {
          timerRef.current = setInterval(fetch, 2000);
        } else if (!hasActive && timerRef.current) {
          clearInterval(timerRef.current);
          timerRef.current = null;
        }
      }).catch(console.error);
    };
    fetch();
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, []);

  // WebSocket 实时日志
  useEffect(() => {
    if (!activeRunId) return;
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws/runs/${activeRunId}`);
    wsRef.current = ws;

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg.event === "log") {
          setLogs((prev) => [...prev, msg.data.line || ""]);
        } else if (msg.event === "run_complete") {
          setRunning(false);
          getApiRun(activeRunId).then((detail) => {
            setActiveRun(detail.run);
            setRunResults(detail.results);
          }).catch(console.error);
          listApiRuns().then(setRuns).catch(console.error);
        }
      } catch { /* ignore */ }
    };

    return () => { ws.close(); wsRef.current = null; };
  }, [activeRunId]);

  const toggleCase = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (selectedIds.size === cases.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(cases.map((c) => c.id)));
    }
  };

  const handleRun = async (caseIds?: number[]) => {
    const activeProject = projects.find((p) => p.is_active) ?? projects[0];
    if (!activeProject || running) return;
    setRunning(true);
    setLogs([]);
    setRunResults([]);
    setActiveRun(null);
    try {
      const run = await triggerApiRun(activeProject.id, caseIds);
      setActiveRunId(run.id);
      setActiveRun(run);
    } catch (e) {
      console.error(e);
      setRunning(false);
    }
  };

  // 统计
  const totalCases = cases.length;
  const latestRun = runs[0];
  const passRate = latestRun && latestRun.total > 0
    ? ((latestRun.passed / latestRun.total) * 100).toFixed(1)
    : "0";

  // 模块分组统计
  const moduleStats = cases.reduce((acc, c) => {
    const mod = c.tags.split(",")[1]?.trim() || "unknown";
    if (!acc[mod]) acc[mod] = { total: 0, name: mod };
    acc[mod].total++;
    return acc;
  }, {} as Record<string, { total: number; name: string }>);

  const isRunning = running || activeRun?.status === "running" || activeRun?.status === "pending";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">接口测试</h1>
        <div className="flex gap-2">
          <button
            onClick={() => handleRun(Array.from(selectedIds))}
            disabled={running || selectedIds.size === 0}
            className={`px-4 py-2 text-white rounded-lg text-sm transition-colors ${
              running || selectedIds.size === 0
                ? "bg-gray-400 cursor-not-allowed"
                : "bg-blue-600 hover:bg-blue-700"
            }`}
          >
            {running ? "运行中..." : `运行选中 (${selectedIds.size})`}
          </button>
          <button
            onClick={() => handleRun()}
            disabled={running}
            className={`px-4 py-2 text-white rounded-lg text-sm transition-colors ${
              running ? "bg-gray-400 cursor-not-allowed" : "bg-green-600 hover:bg-green-700"
            }`}
          >
            {running ? "运行中..." : "全部运行"}
          </button>
        </div>
      </div>

      {/* 统计卡片 */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-white rounded-xl p-6 shadow-sm">
          <div className="text-sm text-gray-500">总用例</div>
          <div className="text-2xl font-bold mt-2">{totalCases}</div>
        </div>
        <div className="bg-white rounded-xl p-6 shadow-sm">
          <div className="text-sm text-gray-500">通过率</div>
          <div className="text-2xl font-bold mt-2">{passRate}%</div>
        </div>
        <div className="bg-white rounded-xl p-6 shadow-sm">
          <div className="text-sm text-gray-500">运行次数</div>
          <div className="text-2xl font-bold mt-2">{runs.length}</div>
        </div>
        <div className="bg-white rounded-xl p-6 shadow-sm">
          <div className="text-sm text-gray-500">平均耗时</div>
          <div className="text-2xl font-bold mt-2">
            {latestRun ? `${(latestRun.duration_ms / 1000).toFixed(1)}s` : "-"}
          </div>
        </div>
      </div>

      {/* 实时日志面板（运行时显示） */}
      {isRunning && (
        <div className="bg-gray-900 rounded-xl shadow-sm overflow-hidden">
          <div className="flex items-center justify-between px-4 py-2 bg-gray-800">
            <span className="text-sm text-gray-300 font-medium">
              实时日志 {logs.length > 0 && <span className="text-gray-500">({logs.length} 行)</span>}
            </span>
            <span className="flex items-center gap-1.5 text-xs text-green-400">
              <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
              运行中
            </span>
          </div>
          <div className="h-80 overflow-y-auto p-4 font-mono text-xs text-gray-300 leading-relaxed">
            {logs.length === 0 ? (
              <p className="text-gray-600">等待日志输出...</p>
            ) : (
              logs.map((line, i) => (
                <div key={i} className="whitespace-pre-wrap break-all">{line}</div>
              ))
            )}
            <div ref={logEndRef} />
          </div>
        </div>
      )}

      {/* 运行结果（运行完成后显示） */}
      {activeRun && !isRunning && runResults.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b bg-gray-50">
            <span className="font-medium">运行 #{activeRun.id} 结果</span>
            <span className={`ml-2 px-2 py-0.5 rounded-full text-xs ${statusBadge[activeRun.status] ?? ""}`}>
              {activeRun.status}
            </span>
            <span className="ml-3 text-sm text-gray-500">
              通过 {activeRun.passed} / 失败 {activeRun.failed} / 跳过 {activeRun.skipped}
            </span>
          </div>
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2 text-left text-sm font-medium text-gray-500">状态</th>
                <th className="px-4 py-2 text-left text-sm font-medium text-gray-500">用例名</th>
                <th className="px-4 py-2 text-left text-sm font-medium text-gray-500">耗时</th>
                <th className="px-4 py-2 text-left text-sm font-medium text-gray-500">错误</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {runResults.map((r) => (
                <tr key={r.id} className="hover:bg-gray-50">
                  <td className="px-4 py-2">{statusIcon[r.status] ?? "❓"}</td>
                  <td className="px-4 py-2 text-sm font-mono">{r.case_name}</td>
                  <td className="px-4 py-2 text-sm">{r.duration_ms}ms</td>
                  <td className="px-4 py-2 text-sm text-red-600 max-w-xs truncate">{r.error_message ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* 用例列表 */}
      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <div className="px-4 py-3 border-b bg-gray-50 flex items-center justify-between">
          <span className="font-medium">接口用例</span>
          <div className="flex items-center gap-3">
            <select
              value={moduleFilter}
              onChange={(e) => setModuleFilter(e.target.value)}
              className="text-sm border rounded px-2 py-1"
            >
              <option value="">全部模块</option>
              {Object.values(moduleStats).map((m) => (
                <option key={m.name} value={m.name}>{m.name} ({m.total})</option>
              ))}
            </select>
            <select
              value={priorityFilter}
              onChange={(e) => setPriorityFilter(e.target.value)}
              className="text-sm border rounded px-2 py-1"
            >
              <option value="">全部优先级</option>
              <option value="P0">P0</option>
              <option value="P1">P1</option>
            </select>
            <button
              onClick={toggleAll}
              className="text-sm text-blue-600 hover:underline"
            >
              {selectedIds.size === cases.length ? "取消全选" : "全选"}
            </button>
          </div>
        </div>
        <table className="w-full">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2 w-10">
                <input
                  type="checkbox"
                  checked={selectedIds.size === cases.length && cases.length > 0}
                  onChange={toggleAll}
                  className="w-4 h-4 rounded"
                />
              </th>
              <th className="px-4 py-2 text-left text-sm font-medium text-gray-500">用例名</th>
              <th className="px-4 py-2 text-left text-sm font-medium text-gray-500">模块</th>
              <th className="px-4 py-2 text-left text-sm font-medium text-gray-500">优先级</th>
              <th className="px-4 py-2 text-left text-sm font-medium text-gray-500">文件</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {cases.map((c) => (
              <tr
                key={c.id}
                className={`hover:bg-gray-50 cursor-pointer ${selectedIds.has(c.id) ? "bg-blue-50" : ""}`}
                onClick={() => toggleCase(c.id)}
              >
                <td className="px-4 py-2">
                  <input
                    type="checkbox"
                    checked={selectedIds.has(c.id)}
                    onChange={() => toggleCase(c.id)}
                    className="w-4 h-4 rounded"
                  />
                </td>
                <td className="px-4 py-2 text-sm font-mono">{c.name}</td>
                <td className="px-4 py-2 text-sm">{c.tags.split(",")[1]?.trim() || "-"}</td>
                <td className="px-4 py-2">
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                    c.priority === "P0" ? "bg-red-100 text-red-700" : "bg-yellow-100 text-yellow-700"
                  }`}>
                    {c.priority}
                  </span>
                </td>
                <td className="px-4 py-2 text-sm text-gray-500">{c.file_path}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 运行历史 */}
      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <div className="px-4 py-3 border-b bg-gray-50">
          <span className="font-medium">运行历史</span>
        </div>
        <table className="w-full">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2 text-left text-sm font-medium text-gray-500">ID</th>
              <th className="px-4 py-2 text-left text-sm font-medium text-gray-500">状态</th>
              <th className="px-4 py-2 text-left text-sm font-medium text-gray-500">通过率</th>
              <th className="px-4 py-2 text-left text-sm font-medium text-gray-500">耗时</th>
              <th className="px-4 py-2 text-left text-sm font-medium text-gray-500">时间</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {runs.map((run) => (
              <tr key={run.id} className="hover:bg-gray-50">
                <td className="px-4 py-2 text-sm">#{run.id}</td>
                <td className="px-4 py-2">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusBadge[run.status] ?? ""}`}>
                    {run.status}
                  </span>
                </td>
                <td className="px-4 py-2 text-sm">
                  {run.total > 0 ? `${((run.passed / run.total) * 100).toFixed(1)}%` : "-"}
                </td>
                <td className="px-4 py-2 text-sm">{(run.duration_ms / 1000).toFixed(1)}s</td>
                <td className="px-4 py-2 text-sm">{new Date(run.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 验证 TypeScript 编译**

```bash
cd frontend && npx tsc --noEmit --skipLibCheck 2>&1 | head -10
```

Expected: 无新增错误

- [ ] **Step 3: 提交**

```bash
git add frontend/src/pages/ApiTests.tsx
git commit -m "feat: 添加接口测试看板页面（用例选择、实时日志、运行历史）"
```

---

### Task 13: 前端路由与导航集成

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/Sidebar.tsx`

**Interfaces:**
- Consumes: `ApiTests` 组件（Task 12）
- Produces: `/api-tests` 路由 + 侧边栏导航项

- [ ] **Step 1: 在 App.tsx 中注册路由**

在 `frontend/src/App.tsx` 顶部 import 区域新增：

```typescript
import ApiTests from "./pages/ApiTests";
```

在 `<Route path="settings" element={<Settings />} />` 之前新增：

```tsx
          <Route path="api-tests" element={<ApiTests />} />
```

- [ ] **Step 2: 在 Sidebar.tsx 中新增导航项**

在 `frontend/src/components/Sidebar.tsx` 中：

1. 顶部 import 新增 `Plug` 图标：

```typescript
import { LayoutDashboard, PlayCircle, ListChecks, Settings, Eye, Plug } from "lucide-react";
```

2. 在 `navItems` 数组中，`settings` 项之前新增：

```typescript
  { to: "/api-tests", icon: Plug, label: "接口测试" },
```

- [ ] **Step 3: 验证前端构建**

```bash
cd frontend && npm run build 2>&1 | tail -5
```

Expected: 构建成功，无错误

- [ ] **Step 4: 提交**

```bash
git add frontend/src/App.tsx frontend/src/components/Sidebar.tsx
git commit -m "feat: 注册接口测试路由和侧边栏导航"
```

---

### Task 14: 端到端联调验证

**Files:**
- 不新建文件，验证所有已有文件协同工作

**Interfaces:**
- Consumes: 所有前序 Task 的产出
- Produces: 确认可运行的端到端链路

- [ ] **Step 1: 启动后端服务**

```bash
uvicorn backend.main:app --reload --port 8000
```

Expected: 服务启动成功，`[AutoDiscover]` 日志中显示发现了接口测试用例

- [ ] **Step 2: 验证 API 端点**

```bash
curl -s http://localhost:8000/api/api-tests/cases | python -X utf8 -m json.tool | head -20
```

Expected: 返回接口测试用例列表（`success: true`）

- [ ] **Step 3: 运行接口测试**

```bash
python -X utf8 -m pytest tests/api_suites/test_agent_api.py -v --tb=short --base-url=https://fenix-agent-ver.pazhoulab-huangpu.com
```

Expected: 至少部分用例通过（取决于实际 API 路径是否匹配）

- [ ] **Step 4: 启动前端并验证页面**

```bash
cd frontend && npm run dev
```

打开浏览器访问看板，点击侧边栏"接口测试"：
- 页面正常加载
- 用例列表有数据
- 勾选用例后点击"运行选中"能触发运行
- 实时日志区能看到 pytest 输出

- [ ] **Step 5: 修复联调中发现的问题**

根据实际运行情况修复：
- API 路径不匹配 → 调整 `WebClient` / `ApiClient` 中的路径
- Schema 字段不对 → 调整 `agent_schemas.py`
- 前端显示异常 → 调整 `ApiTests.tsx`

- [ ] **Step 6: 提交修复**

```bash
git add -A
git commit -m "fix: 修复接口测试端到端联调问题"
```
