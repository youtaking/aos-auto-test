# RegressionEye

UI 自动化回归测试平台

## 功能

- **Playwright E2E 测试**：Python + Playwright + pytest，POM 模式
- **可视化看板**：React 实时 Dashboard，展示运行状态和趋势
- **多种触发**：看板手动 / GitHub Actions / API
- **CI/CD 集成**：代码提交自动回归，结果上报看板

## 快速开始

### 1. 启动开发环境

```bash
# 启动 PostgreSQL
docker compose up db -d

# 安装 Python 依赖
pip install -r requirements.txt
playwright install chromium

# 启动后端
uvicorn backend.main:app --reload

# 启动前端（另一个终端）
cd frontend && npm install && npm run dev
```

### 2. 部署生产环境

```bash
docker compose up -d
```

看板访问 http://localhost:3000

### 3. 运行测试

```bash
# 运行全部测试
pytest tests/suites/ -v

# 只运行 P0 用例
pytest tests/suites/ -m p0 -v

# 运行指定套件
pytest tests/suites/test_login.py -v
```

## 项目结构

```
RegressionEye/
├── tests/          # Playwright 测试用例（POM 模式）
├── engine/         # 测试执行引擎
├── backend/        # FastAPI 后端
├── frontend/       # React 看板前端
├── .github/        # CI/CD 配置
└── docker-compose.yml
```

## 新增测试用例

1. 在 `tests/pages/` 下创建 Page Object
2. 在 `tests/suites/test_*.py` 下编写 `test_*` 函数
3. 提交代码，引擎自动发现注册

## API 文档

启动后端后访问 http://localhost:8000/docs 查看 Swagger 文档。
