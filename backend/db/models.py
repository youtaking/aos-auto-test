# backend/db/models.py
"""数据库 ORM 模型"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, Index, JSON
)
from sqlalchemy.orm import relationship
from backend.db.base import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    url = Column(String(500), nullable=False)
    description = Column(Text, default="")
    is_active = Column(Integer, default=0)  # 1=激活, 0=未激活
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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


class TestCase(Base):
    __tablename__ = "test_cases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    suite_id = Column(Integer, ForeignKey("test_suites.id"), nullable=False)
    name = Column(String(300), nullable=False)
    file_path = Column(String(500), nullable=False)
    function_name = Column(String(300), nullable=False)
    tags = Column(String(500), default="")
    priority = Column(String(10), default="P1")
    timeout = Column(Integer, default=60)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    suite = relationship("TestSuite", back_populates="cases")
    results = relationship("TestResult", back_populates="case", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_test_cases_suite_id", "suite_id"),
        Index("ix_test_cases_function_name", "function_name"),
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
    created_at = Column(DateTime, default=datetime.utcnow)

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
    """环境 Slot 配置：每个 Slot 对应一组端口，用于部署 PR 环境"""
    __tablename__ = "environment_slots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    rcs_port = Column(Integer, nullable=False)
    postgres_port = Column(Integer, nullable=False)
    litellm_port = Column(Integer, nullable=False)
    status = Column(String(20), default="available")  # available / occupied / maintenance
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    pipelines = relationship("PRPipeline", back_populates="slot")


class PRPipeline(Base):
    """PR 流水线记录：每次 PR 触发的完整生命周期"""
    __tablename__ = "pr_pipelines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pr_id = Column(Integer, nullable=False)
    pr_title = Column(String(500), default="")
    commit_sha = Column(String(40), nullable=False)
    branch = Column(String(200), default="")
    repo_url = Column(String(500), default="")
    author = Column(String(200), default="")
    slot_id = Column(Integer, ForeignKey("environment_slots.id"), nullable=True)
    status = Column(String(20), default="queued")  # queued/building/deploying/running/passed/failed/error/destroyed
    docker_image = Column(String(500), default="")
    rcs_url = Column(String(500), default="")
    run_id = Column(Integer, ForeignKey("test_runs.id"), nullable=True)
    queue_position = Column(Integer, default=0)
    timeout_at = Column(DateTime, nullable=True)
    environment_info = Column(Text, default="")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


