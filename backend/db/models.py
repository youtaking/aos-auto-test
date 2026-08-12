# backend/db/models.py
"""数据库 ORM 模型"""
from datetime import datetime, timezone, timedelta
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, Index, JSON, UniqueConstraint
)
from sqlalchemy.orm import relationship
from backend.db.base import Base

# 北京时间 UTC+8
_CST = timezone(timedelta(hours=8))
def _now():
    return datetime.now(_CST).replace(tzinfo=None)


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    url = Column(String(500), nullable=False)
    description = Column(Text, default="")
    is_active = Column(Integer, default=0)  # 1=激活, 0=未激活
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    suites = relationship("TestSuite", back_populates="project", cascade="all, delete-orphan")
    runs = relationship("TestRun", back_populates="project", cascade="all, delete-orphan")


class AuthConfig(Base):
    """认证配置：独立于项目，可创建多份，同时只能激活一份"""
    __tablename__ = "auth_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    ui_test_email = Column(String(200), default="")
    ui_test_password = Column(String(200), default="")
    api_test_email = Column(String(200), default="")
    api_test_password = Column(String(200), default="")
    open_api_key = Column(String(500), default="")
    is_active = Column(Integer, default=0)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


class LLMConfig(Base):
    """LLM 配置：支持多个 LLM 提供商，同时只能激活一个"""
    __tablename__ = "llm_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    provider = Column(String(50), default="openai")  # openai, anthropic, custom
    base_url = Column(String(500), nullable=False)
    api_key = Column(String(500), nullable=False)
    model = Column(String(200), nullable=False)
    is_active = Column(Integer, default=0)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


class ZentaoConfig(Base):
    """禅道配置：同时只能激活一个"""
    __tablename__ = "zentao_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    base_url = Column(String(500), nullable=False)  # 禅道服务地址
    username = Column(String(200), default="")       # 禅道登录账号
    password = Column(String(200), default="")       # 禅道登录密码
    product_id = Column(Integer, default=1)          # 禅道产品 ID
    is_active = Column(Integer, default=0)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


class TestSuite(Base):
    __tablename__ = "test_suites"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    tags = Column(String(500), default="")
    test_type = Column(String(20), default="ui")  # "ui" 或 "api"
    created_at = Column(DateTime, default=_now)

    project = relationship("Project", back_populates="suites")
    cases = relationship("TestCase", back_populates="suite", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_test_suites_project_id", "project_id"),
    )


class TestCase(Base):
    __tablename__ = "test_cases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    suite_id = Column(Integer, ForeignKey("test_suites.id"), nullable=False)
    name = Column(String(300), nullable=False)
    file_path = Column(String(500), nullable=False)
    function_name = Column(String(300), nullable=False)
    tags = Column(String(500), default="")
    priority = Column(String(10), default="P1")
    branch = Column(String(200), default="main")  # 所属分支，默认 main
    timeout = Column(Integer, default=60)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    suite = relationship("TestSuite", back_populates="cases")
    results = relationship("TestResult", back_populates="case", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_test_cases_suite_id", "suite_id"),
        Index("ix_test_cases_function_name", "function_name"),
        Index("ix_test_cases_branch", "branch"),
    )


class TestRun(Base):
    __tablename__ = "test_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    trigger_type = Column(String(20), nullable=False, default="manual")
    trigger_user = Column(String(200), default="")
    git_commit = Column(String(40), default="")
    git_branch = Column(String(200), default="")
    pr_id = Column(Integer, nullable=True)
    pipeline_id = Column(Integer, nullable=True)
    collection_ids = Column(JSON, nullable=True)  # 本次运行使用的用例集 ID 数组
    status = Column(String(20), default="pending")
    total = Column(Integer, default=0)
    passed = Column(Integer, default=0)
    failed = Column(Integer, default=0)
    skipped = Column(Integer, default=0)
    duration_ms = Column(Integer, default=0)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_now)

    project = relationship("Project", back_populates="runs")
    results = relationship("TestResult", back_populates="run", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_test_runs_project_id", "project_id"),
        Index("ix_test_runs_status", "status"),
        Index("ix_test_runs_created_at", "created_at"),
    )


class TestResult(Base):
    __tablename__ = "test_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("test_runs.id"), nullable=False)
    case_id = Column(Integer, ForeignKey("test_cases.id"), nullable=True)
    case_name = Column(String(300), nullable=False)
    suite_name = Column(String(200), default="")
    status = Column(String(20), nullable=False)
    duration_ms = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    stack_trace = Column(Text, nullable=True)
    screenshot_path = Column(String(500), nullable=True)
    retry_count = Column(Integer, default=0)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    run = relationship("TestRun", back_populates="results")
    case = relationship("TestCase", back_populates="results")

    __table_args__ = (
        Index("ix_test_results_run_id", "run_id"),
        Index("ix_test_results_case_id", "case_id"),
    )


class EnvironmentSlot(Base):
    """环境 Slot 配置：每个 Slot 对应一组端口和目标服务器，用于部署 PR 环境"""
    __tablename__ = "environment_slots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    rcs_port = Column(Integer, nullable=False)
    postgres_port = Column(Integer, nullable=False)
    litellm_port = Column(Integer, nullable=False)
    status = Column(String(20), default="available")  # available / occupied / maintenance
    # 远程服务器配置（host=localhost 时本地执行）
    host = Column(String(200), default="localhost")
    ssh_user = Column(String(50), default="root")
    ssh_port = Column(Integer, default=22)
    ssh_key_path = Column(String(500), default="")
    ssh_password = Column(String(200), default="")
    work_dir = Column(String(500), default="/tmp/pr-environments")
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    pipelines = relationship("PRPipeline", back_populates="slot")


class PRPipeline(Base):
    """PR 流水线记录：每次 PR 触发的完整生命周期"""
    __tablename__ = "pr_pipelines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pr_id = Column(Integer, nullable=True)
    pr_title = Column(String(500), default="")
    commit_sha = Column(String(40), nullable=False)
    branch = Column(String(200), default="")
    repo_url = Column(String(500), default="")
    author = Column(String(200), default="")
    slot_id = Column(Integer, ForeignKey("environment_slots.id"), nullable=True)  # 废弃：Jenkins 集成后不再使用 Slot
    status = Column(String(20), default="queued")  # queued/building/deploying/running/passed/failed/error/destroyed
    docker_image = Column(String(500), default="")
    rcs_url = Column(String(500), default="")
    run_id = Column(Integer, ForeignKey("test_runs.id"), nullable=True)
    queue_position = Column(Integer, default=0)  # 废弃：Jenkins 集成后不再使用队列
    timeout_at = Column(DateTime, nullable=True)
    environment_info = Column(Text, default="")
    error_message = Column(Text, nullable=True)
    # Jenkins 集成字段
    target_url = Column(String(500), default="")       # Jenkins 部署后的 PR 环境地址
    build_info = Column(JSON, nullable=True)            # Jenkins 构建信息（job URL、镜像 tag 等）
    test_report = Column(JSON, nullable=True)           # test-runner 提交的完整 pytest JSON 报告
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    slot = relationship("EnvironmentSlot", back_populates="pipelines")
    run = relationship("TestRun", foreign_keys=[run_id])

    __table_args__ = (
        Index("ix_pr_pipelines_pr_id", "pr_id"),
        Index("ix_pr_pipelines_status", "status"),
    )


class TestCollection(Base):
    """用户自定义测试用例集"""
    __tablename__ = "test_collections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    case_ids = Column(JSON, default=list)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    project = relationship("Project", backref="collections")

    __table_args__ = (
        Index("ix_test_collections_project_id", "project_id"),
    )


class CIConfig(Base):
    """CI 全局配置：超时时间、队列上限、认证 Token 等"""
    __tablename__ = "ci_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timeout_minutes = Column(Integer, default=60)
    max_queue_size = Column(Integer, default=5)
    auth_token = Column(String(500), default="")
    run_api_tests = Column(Integer, default=1)
    run_e2e_p0 = Column(Integer, default=1)
    run_e2e_all = Column(Integer, default=0)
    collection_ids = Column(JSON, nullable=True)  # 选中的用例集 ID 数组
    staging_collection_ids = Column(JSON, nullable=True)  # Staging 测试集 ID 数组
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


class UnitTestCase(Base):
    """单元测试用例（从 .test.ts 文件扫描发现）"""
    __tablename__ = "unit_test_cases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_path = Column(String(500), nullable=False)        # 相对路径，如 services/phone-number.test.ts
    describe_block = Column(String(200), default="")       # describe 名称
    test_name = Column(String(300), nullable=False)         # test/it 名称
    full_name = Column(String(500), nullable=False)  # describe > test 完整名
    branch = Column(String(200), default="main")
    discovered_at = Column(DateTime, default=_now)

    results = relationship("UnitTestResult", back_populates="case", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_unit_test_cases_file_path", "file_path"),
        Index("ix_unit_test_cases_branch", "branch"),
        UniqueConstraint("full_name", "branch", name="uq_unit_test_case_full_name_branch"),
    )


class UnitTestRun(Base):
    """单元测试运行记录"""
    __tablename__ = "unit_test_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    total = Column(Integer, default=0)
    passed = Column(Integer, default=0)
    failed = Column(Integer, default=0)
    skipped = Column(Integer, default=0)
    duration_ms = Column(Integer, default=0)
    status = Column(String(20), default="completed")  # running / completed / failed
    trigger_type = Column(String(20), default="manual")  # manual / pipeline
    pipeline_id = Column(Integer, ForeignKey("pr_pipelines.id"), nullable=True)
    started_at = Column(DateTime, default=_now)

    results = relationship("UnitTestResult", back_populates="run", cascade="all, delete-orphan")


class UnitTestResult(Base):
    """单元测试运行结果"""
    __tablename__ = "unit_test_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("unit_test_runs.id"), nullable=True)
    pipeline_id = Column(Integer, ForeignKey("pr_pipelines.id"), nullable=True)
    test_case_id = Column(Integer, ForeignKey("unit_test_cases.id"), nullable=True)
    name = Column(String(300), default="")          # 测试名
    classname = Column(String(300), default="")     # describe 名
    status = Column(String(20), nullable=False)  # passed / failed / skipped / error
    duration_ms = Column(Integer, default=0)
    failure_message = Column(Text, nullable=True)
    ran_at = Column(DateTime, default=_now)

    case = relationship("UnitTestCase", back_populates="results")
    run = relationship("UnitTestRun", back_populates="results")

    __table_args__ = (
        Index("ix_unit_test_results_run_id", "run_id"),
        Index("ix_unit_test_results_pipeline_id", "pipeline_id"),
        Index("ix_unit_test_results_test_case_id", "test_case_id"),
    )


class Setting(Base):
    """系统配置（key-value 存储）"""
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(200), nullable=False, unique=True, index=True)
    value = Column(Text, default="")
    description = Column(String(500), default="")
    updated_at = Column(DateTime, default=_now, onupdate=_now)


class BranchTracker(Base):
    """Fenix 分支追踪记录"""
    __tablename__ = "branch_trackers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    branch_name = Column(String(200), unique=True, nullable=False)
    last_commit_sha = Column(String(40), default="")
    status = Column(String(20), default="up_to_date")
    # up_to_date / needs_update / deleted
    discovered_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


