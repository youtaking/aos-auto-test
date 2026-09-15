# tests/suites/test_artifacts_file_tree.py
"""对话页 Artifacts 右侧工作区「文件」Tab 文件树 CRUD E2E 测试

对应 2026-09-15 E2E 覆盖率评审报告 §4.3（对话页 Artifacts 文件树新增/重命名/删除链路零覆盖）。
真实 DOM 探查时间：2026-09-15（staging commitId da5eb543，与线上一致）：
  - 面板 aside.artifacts-shell（折叠时 button.artifacts-open-button 展开）
  - 模式 Tab：button.artifacts-mode-tab[title=文件]（另有 站点 / 定时任务 / 发布视图）
  - 文件树面板 .file-tree-panel，头部按钮 刷新 / 新建文件夹 / 上传 / 上传文件夹
  - 两个分区：.file-tree-section--workspace（工作区）与 .file-tree-section--user（我的文件）
  - 条目行 div[data-tree-item][data-node-id][data-is-dir]，外层包裹 div[role=treeitem][aria-level]
  - 头部「新建文件夹」创建在「我的文件」区，路径为 user/<name>
  - 右键菜单 div.file-tree-context-menu[role=menu]：引用到聊天 / 下载 ZIP / 重命名 / 移动 /
    删除（is-danger）/ 新建文件夹 / 新建文件
  - 删除确认弹窗 [role=alertdialog]：标题「删除」、描述为目标名称、确认按钮「删除」

数据安全（自建自销）：本文件只操作自己创建的文件夹，每条用例结束前必删；
删除前断言确认弹窗对象为本次创建的对象，不触碰任何既有文件/文件夹。
"""
import uuid

import allure
import pytest

from tests.pages.chat_test_page import ChatTestPage

AGENT_NAME = "my-auto-test"


def _unique_name(tag: str) -> str:
    """自建对象名（e2e 前缀 + 随机后缀，便于识别与清理）"""
    return f"e2e-folder-{tag}-{uuid.uuid4().hex[:6]}"


@pytest.fixture
def file_tree(logged_in_page, base_url):
    """打开对话页的 Artifacts 文件树（「文件」Tab，已渲染完成）

    优先用 my-auto-test；该 Agent 不存在于当前环境（如正式环境只有别的 Agent）时，
    自动改用侧边栏第一个可用 Agent —— 不用 skip 掩盖「未执行」。
    """
    chat = ChatTestPage(logged_in_page, base_url)
    chat.goto_agent_chat(AGENT_NAME)
    if not chat.is_on_chat_page():
        fallback = chat.goto_any_agent_chat()
        assert chat.is_on_chat_page(), (
            f"「{AGENT_NAME}」与侧边栏可用 Agent{fallback!r} 均无法进入对话页（环境异常）"
        )
    chat.open_artifacts_file_tab()
    return chat


@allure.epic("对话 Artifacts")
@pytest.mark.order(80)
@pytest.mark.p1
def test_artifacts_001_new_folder(file_tree):
    """新建文件夹：弹窗文案正确，条目落在「我的文件」区且路径为 user/<name>"""
    chat = file_tree
    name = _unique_name("new")
    try:
        chat.create_artifact_folder(name)
        assert chat.wait_for_artifact(name), f"新建后文件树中未出现「{name}」"

        row = chat.artifact_row(name)
        assert row.count() == 1, f"「{name}」匹配到 {row.count()} 个条目，预期唯一"
        node_id = row.first.get_attribute("data-node-id")
        assert node_id == f"user/{name}", f"新建文件夹路径预期 user/{name}，实际 {node_id!r}"
        assert row.first.get_attribute("data-is-dir") == "true", \
            "新建条目 data-is-dir 不是 true（不是文件夹）"

        user_section = chat.get_file_tree_section_text("user")
        assert name in user_section, \
            f"新建文件夹未出现在「我的文件」区，该区当前文本: {user_section!r}"
    finally:
        if chat.artifact_row(name).count() == 1:
            chat.delete_artifact_via_menu(name)
        assert chat.wait_for_artifact(name, present=False), f"清理失败：文件夹「{name}」仍存在"


@allure.epic("对话 Artifacts")
@pytest.mark.order(81)
@pytest.mark.p1
def test_artifacts_002_rename_folder(file_tree):
    """重命名文件夹（右键菜单）：新名出现、旧名消失、路径同步更新"""
    chat = file_tree
    name = _unique_name("ren")
    renamed = f"{name}-r"
    try:
        chat.create_artifact_folder(name)
        assert chat.wait_for_artifact(name), f"前置失败：文件树中未出现「{name}」"

        chat.rename_artifact(name, renamed)

        assert chat.wait_for_artifact(renamed), f"重命名后未出现「{renamed}」"
        assert chat.wait_for_artifact(name, present=False), f"重命名后旧名「{name}」仍存在"
        row = chat.artifact_row(renamed)
        assert row.count() == 1, f"「{renamed}」匹配到 {row.count()} 个条目，预期唯一"
        node_id = row.first.get_attribute("data-node-id")
        assert node_id == f"user/{renamed}", f"重命名后路径预期 user/{renamed}，实际 {node_id!r}"
    finally:
        target = renamed if chat.artifact_row(renamed).count() == 1 else name
        if chat.artifact_row(target).count() == 1:
            chat.delete_artifact_via_menu(target)
        assert chat.wait_for_artifact(target, present=False), f"清理失败：文件夹「{target}」仍存在"


@allure.epic("对话 Artifacts")
@pytest.mark.order(82)
@pytest.mark.p1
def test_artifacts_003_delete_folder_confirms_target(file_tree):
    """删除文件夹（右键菜单）：确认弹窗对象必须是本次自建对象，删除后条目消失"""
    chat = file_tree
    name = _unique_name("del")
    try:
        chat.create_artifact_folder(name)
        assert chat.wait_for_artifact(name), f"前置失败：文件树中未出现「{name}」"

        # delete_artifact_via_menu 内部断言：弹窗标题「删除」且描述 == 本次自建对象名
        chat.delete_artifact_via_menu(name)

        assert chat.wait_for_artifact(name, present=False), f"删除后「{name}」仍存在于文件树"
    finally:
        if chat.artifact_row(name).count() == 1:
            chat.delete_artifact_via_menu(name)

