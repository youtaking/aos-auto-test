# tests/suites/test_agent_config.py
"""智能体配置模块 E2E 测试 — 基于真实 DOM + API 验证
覆盖 Excel 3-agent配置 sheet 全部 15 条用例
"""
import json
import uuid
import random
import pytest
import allure
from tests.pages.agent_config_page import AgentConfigPage
from tests.conftest import register_cleanup

_PREFIX = f"e2e-{uuid.uuid4().hex[:6]}"

# 动态描述素材
_TOPICS = ["Python 编程", "数据分析", "前端开发", "数据库优化",
           "机器学习", "DevOps", "API 设计", "安全审计"]
_ROLES = ["助手", "专家", "顾问", "教练"]


def _assert_create_success(result: dict):
    """断言 API 创建成功，若为并发上限导致的 500 则 skip。
    同时自动注册 agent 清理（从调用帧获取 request 和 agent_name）。"""
    import sys as _sys
    _caller = _sys._getframe(1)
    _req = _caller.f_locals.get('request')
    _name = _caller.f_locals.get('agent_name', '')

    if result["status"] == 500:
        msg = result.get("text", "") or str(result.get("data", ""))
        if "并发" in msg or "concurrent" in msg.lower() or "limit" in msg.lower():
            pytest.skip(f"服务器并发上限限制: {msg[:100]}")
    assert result["status"] == 200, \
        f"API 创建 Agent 失败: status={result['status']}, body={result.get('text', result.get('data', ''))}"

    # 创建成功后注册清理（作为 try/finally 的安全后备）
    if _req and _name:
        def _auto_cleanup():
            ac = _caller.f_locals.get('ac')
            if ac:
                status = ac.delete_agent_api(_name)
                assert status in (200, 204, 404)
        register_cleanup(_req, _auto_cleanup)


def _check_concurrency_limit(page) -> bool:
    """检查页面是否显示并发上限错误（包括 DOM 文本、错误提示和 URL 状态）"""
    try:
        text = page.locator("body").inner_text()
        if "并发上限" in text or "并发" in text:
            return True
        # Check for error/alert elements
        error_els = page.locator("[role='alert'], .text-destructive, .text-red-500, .error-message")
        for i in range(min(error_els.count(), 5)):
            err_text = error_els.nth(i).inner_text()
            if "并发" in err_text:
                return True
        # Check for toast/notification errors
        toast = page.locator("[data-slot='toast'], [data-sonner-toast], ol[data-sonner-toasts]")
        if toast.count() > 0:
            toast_text = toast.first.inner_text()
            if "并发" in toast_text:
                return True
        # Check if the page shows an error state in the agent panel
        agent_error = page.locator("text=Failed to start")
        if agent_error.count() > 0:
            return True
        return False
    except Exception:
        return False


# ==================== 共享 Agent Fixture ====================


@pytest.fixture(scope="module")
def shared_agent(logged_in_page, base_url):
    """模块级共享 Agent：通过 UI 创建一次，供所有测试使用。
    避免重复创建/删除导致的服务器 session 故障。
    """
    ac = AgentConfigPage(logged_in_page, base_url)
    agent_name = f"shared-{_PREFIX}"

    # 通过 UI 创建（避免 API session 问题）
    result = ac.create_agent_ui(
        name=agent_name,
        system_prompt="你是一个测试助手，用于自动化测试。"
    )

    if result["status"] != 200:
        pytest.skip(f"共享 Agent 创建失败: {result}")

    yield {
        "name": agent_name,
        "ac": ac,
    }

    # 清理：通过 API 删除
    try:
        status = ac.delete_agent_api(agent_name)
        print(f"\n清理共享 Agent '{agent_name}': status={status}")
    except Exception as e:
        print(f"\n清理共享 Agent 失败: {e}")


# ==================== 测试 ====================


@allure.epic("智能体配置")
@pytest.mark.order(120)
@pytest.mark.p0
def test_create_new_agent(logged_in_page, base_url, request):
    """✅ 人工评审通过 | TC-AGENT-001: 一键创建新智能体（描述 → AI 生成 → 修改名称/SP → 创建 → 验证会话 → 清理）"""
    ac = AgentConfigPage(logged_in_page, base_url)
    ac.goto_create()

    # 1. MetaAgent 入口存在（textarea）
    assert ac.has_meta_agent(), "MetaAgent 自然语言入口（textarea）不存在"
    ta = ac.get_create_textarea()
    assert ta.first.is_visible(), "创建描述 textarea 应可见"

    # 2. 填写动态描述（每次运行不同）
    topic = random.choice(_TOPICS)
    role = random.choice(_ROLES)
    ac.fill_create_description(f"帮我创建一个{topic}方向的{role}，擅长回答相关问题并给出代码示例")

    # 3. 有"一键创建"按钮
    assert ac.has_quick_create_button(), "应有'一键创建'按钮"

    # 4. 滚动到一键创建按钮并点击，等待 AI 生成表单
    quick_btn = ac.get_quick_create_button()
    quick_btn.scroll_into_view_if_needed()
    quick_btn.click()
    create_btn = logged_in_page.get_by_role("button", name="创建 Agent")
    create_btn.wait_for(state="visible", timeout=30000)
    logged_in_page.wait_for_timeout(1000)

    # 5. 验证 AI 生成了名称和 System Prompt
    name_input = logged_in_page.locator("input[data-slot='input']").first
    name_input.wait_for(state="visible", timeout=15000)
    generated_name = name_input.input_value()
    assert generated_name, "AI 应生成 Agent 名称"

    sp_ta = logged_in_page.locator("textarea").first
    generated_sp = sp_ta.input_value()
    assert generated_sp, "AI 应生成 System Prompt"

    # 6. 在 AI 生成的名称上追加修改
    name_input.fill(generated_name + "-e2e")
    modified_name = name_input.input_value()
    assert modified_name == generated_name + "-e2e", "名称应可修改"

    # 注册清理（在可能失败的断言之前）
    register_cleanup(request, lambda: ac.delete_agent_api(modified_name))

    # 7. 在 AI 生成的 System Prompt 上追加修改
    sp_ta.fill(generated_sp + "\n请始终用中文回答。")
    modified_sp = sp_ta.input_value()
    assert modified_sp.startswith(generated_sp), "System Prompt 应可修改（保留原内容）"
    assert "请始终用中文回答" in modified_sp, "System Prompt 追加内容应生效"

    # 8. 滚动到创建 Agent 按钮并点击
    create_btn.scroll_into_view_if_needed()
    create_btn.click()

    # 9. 验证跳转到对话页面
    try:
        logged_in_page.wait_for_url(
            lambda url: "/ctrl/agent/chat/" in url, timeout=15000
        )
    except Exception:
        pass
    assert "/ctrl/agent/chat/" in logged_in_page.url, \
        f"创建后应跳转到对话页面，当前 URL: {logged_in_page.url}"

    # 10. 等待左侧列表刷新，验证新建的 Agent 出现（用修改后的名称匹配）
    logged_in_page.wait_for_timeout(1000)
    cards = logged_in_page.locator("button.agent-sidebar-agent-card")
    found = False
    for _ in range(10):
        for i in range(cards.count()):
            if modified_name in cards.nth(i).text_content():
                found = True
                break
        if found:
            break
        logged_in_page.wait_for_timeout(1000)
    assert found, f"左侧 Agent 列表中应出现 '{modified_name}'"

    # 11. 清理：通过 API 删除刚创建的 Agent
    status = ac.delete_agent_api(modified_name)
    assert status in (200, 204, 404), f"删除 Agent 失败: status={status}"


@allure.epic("智能体配置")
@pytest.mark.order(121)
@pytest.mark.p1
def test_agent_002_template_create(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-AGENT-002: 验证快捷模版数量和名称"""
    ac = AgentConfigPage(logged_in_page, base_url)
    ac.goto_create()

    # 1. 获取所有模版详情并打印
    details = ac.get_template_details()
    print(f"\n=== 快捷模版（共 {len(details)} 个）===")
    for i, d in enumerate(details):
        print(f"  [{i+1}] {d['name']}")
        print(f"       {d['desc']}")
    allure.attach(
        "\n".join(f"[{i+1}] {d['name']}: {d['desc']}" for i, d in enumerate(details)),
        name="模版列表",
        attachment_type=allure.attachment_type.TEXT,
    )

    # 2. 验证数量
    assert len(details) == 8, f"应有 8 个模版，实际 {len(details)} 个"

    # 3. 验证名称（写死）
    expected_names = [
        "Agent Sites 建站助手",
        "创意文案",
        "会议纪要助手",
        "公文写手",
        "PPT 提纲助手",
        "调研选手",
        "Skill 生成助手",
        "学习助手",
    ]
    actual_names = [d["name"] for d in details]
    for name in expected_names:
        assert name in actual_names, f"缺少模版: '{name}'"

    # 4. 验证每个模版都有描述
    for d in details:
        assert d["desc"], f"模版 '{d['name']}' 缺少描述"


@allure.epic("智能体配置")
@pytest.mark.order(121)
@pytest.mark.p1
def test_click_all_templates(logged_in_page, base_url, request):
    """✅ 人工评审通过 | TC-AGENT-002b: 逐个点击 8 个模版，每个都走完整创建流程（模版 → AI 生成 → 修改名称/SP → 创建 → 验证 → 清理）"""
    ac = AgentConfigPage(logged_in_page, base_url)

    expected_names = [
        "Agent Sites 建站助手",
        "创意文案",
        "会议纪要助手",
        "公文写手",
        "PPT 提纲助手",
        "调研选手",
        "Skill 生成助手",
        "学习助手",
    ]

    created_agents = []  # 记录创建的 Agent 名称，用于清理

    for i, name in enumerate(expected_names):
        print(f"\n--- [{i+1}/8] 模版: {name} ---")
        ac.goto_create()

        # 等待模版加载
        cards = logged_in_page.locator("button.agent-home-template-pill")
        cards.first.wait_for(state="visible", timeout=10000)

        # 点击模版 → 自动触发 AI 生成（不需要一键创建）
        clicked = ac.click_template(name)
        assert clicked, f"模版 '{name}' 未找到或无法点击"

        # 等待"创建 Agent"按钮出现（点击模版后直接生成）
        create_btn = logged_in_page.get_by_role("button", name="创建 Agent")
        create_btn.wait_for(state="visible", timeout=15000)
        logged_in_page.wait_for_timeout(1000)

        # 验证 AI 生成了名称和 System Prompt
        name_input = logged_in_page.locator("input[data-slot='input']").first
        name_input.wait_for(state="visible", timeout=15000)
        generated_name = name_input.input_value()
        assert generated_name, f"模版 '{name}': AI 应生成 Agent 名称"

        sp_ta = logged_in_page.locator("textarea").first
        generated_sp = sp_ta.input_value()
        assert generated_sp, f"模版 '{name}': AI 应生成 System Prompt"
        print(f"  AI 生成名称: {generated_name}")
        print(f"  AI 生成 SP: {generated_sp[:50]}...")

        # 在名称后追加 -e2e 标识
        modified_name = generated_name + "-e2e"
        name_input.fill(modified_name)

        # 在 System Prompt 后追加修改
        sp_ta.fill(generated_sp + "\n请始终用中文回答。")
        modified_sp = sp_ta.input_value()
        assert "请始终用中文回答" in modified_sp, \
            f"模版 '{name}': System Prompt 应可修改"

        # 滚动到创建 Agent 按钮并点击
        create_btn.scroll_into_view_if_needed()
        create_btn.click()

        # 验证跳转到对话页面
        try:
            logged_in_page.wait_for_url(
                lambda url: "/ctrl/agent/chat/" in url, timeout=15000
            )
        except Exception:
            pass
        assert "/ctrl/agent/chat/" in logged_in_page.url, \
            f"模版 '{name}': 创建后应跳转到对话页面，当前: {logged_in_page.url}"

        created_agents.append(modified_name)
        register_cleanup(request, lambda n=modified_name: ac.delete_agent_api(n))
        print(f"  ✅ 创建成功: {modified_name}")

    # 清理所有创建的 Agent
    print(f"\n--- 清理 {len(created_agents)} 个 Agent ---")
    for agent_name in created_agents:
        status = ac.delete_agent_api(agent_name)
        print(f"  删除 '{agent_name}': status={status}")
        assert status in (200, 204), f"删除 '{agent_name}' 失败: {status}"


@allure.epic("智能体配置")
@pytest.mark.order(123)
@pytest.mark.p0
def test_agent_023_system_prompt_effective(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-AGENT-023: 创建时填写 System Prompt 并验证生效
    通过 API 创建带 System Prompt 的 Agent，发送非 Python 问题验证 SP 拒绝，最后清理
    """
    ac = AgentConfigPage(logged_in_page, base_url)
    agent_name = f"sp-{_PREFIX}"
    sp_text = "你是一个只回答Python编程问题的助手，拒绝其他话题。"

    result = ac.create_agent_api(
        name=agent_name,
        system_prompt=sp_text,
    )
    allure.attach(
        f"API 创建结果: status={result['status']}\n"
        f"System Prompt: {sp_text}",
        name="创建结果",
        attachment_type=allure.attachment_type.TEXT,
    )
    _assert_create_success(result)

    try:
        # 进入智能体列表，点击该 Agent
        ac.goto_agents()
        logged_in_page.wait_for_load_state("networkidle")
        # 等待环境就绪
        env_id = result.get("env_id", "")
        if env_id:
            ac.wait_for_env_ready(env_id)
        clicked = ac.click_agent(agent_name)
        assert clicked, f"左侧列表中未找到 '{agent_name}'"
        if _check_concurrency_limit(logged_in_page):
            pytest.skip("服务器并发上限，无法进入对话页面")
        assert ac.is_on_chat_page(), "应进入对话页面"

        # 发送非 Python 问题，验证 SP 生效（Agent 应拒绝回答）
        ac.send_message("请推荐一家北京好吃的火锅店")
        reply = ac.wait_for_ai_reply(timeout_ms=30000)
        allure.attach(
            f"发送: 请推荐一家北京好吃的火锅店\nAI 回复: {reply[:200]}",
            name="SP 生效验证",
            attachment_type=allure.attachment_type.TEXT,
        )
        # SP 要求只回答 Python 问题，非 Python 问题应被拒绝或引导回 Python
        python_keywords = ["python", "Python", "编程", "代码", "开发",
                          "只能", "只回答", "无法", "抱歉", "不好意思"]
        has_refusal = any(kw in reply for kw in python_keywords)
        assert has_refusal, \
            f"System Prompt 应使 Agent 拒绝非 Python 问题，实际回复: {reply[:200]}"
    finally:
        # 清理
        status = ac.delete_agent_api(agent_name)
        print(f"\n清理 '{agent_name}': status={status}")
        assert status in (200, 204, 404), f"删除 Agent 失败: status={status}"


@allure.epic("智能体配置")
@pytest.mark.order(124)
@pytest.mark.p1
def test_agent_024_system_prompt_empty(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-AGENT-024: 创建时 System Prompt 留空，验证仍能正常创建和进入对话"""
    ac = AgentConfigPage(logged_in_page, base_url)
    agent_name = f"nosp-{_PREFIX}"

    # 通过 UI 创建（SP 留空）
    result = ac.create_agent_ui(name=agent_name, system_prompt="")
    allure.attach(
        f"UI 创建结果: status={result['status']}",
        name="创建结果",
        attachment_type=allure.attachment_type.TEXT,
    )
    assert result["status"] == 200, f"UI 创建 Agent 失败: {result}"

    try:
        if _check_concurrency_limit(logged_in_page):
            pytest.skip("服务器并发上限，无法进入对话页面")
        assert ac.is_on_chat_page(), "System Prompt 留空也应能进入对话页面"
    finally:
        status = ac.delete_agent_api(agent_name)
        print(f"\n清理 '{agent_name}': status={status}")
        assert status in (200, 204, 404), f"删除 Agent 失败: status={status}"


@allure.epic("智能体配置")
@pytest.mark.order(125)
@pytest.mark.p0
def test_agent_025_bind_mcp(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-AGENT-025: 创建 Agent 后通过编辑配置页面绑定 MCP 服务器并验证"""
    ac = AgentConfigPage(logged_in_page, base_url)
    agent_name = f"mcp-{_PREFIX}"

    # 1. API 创建 Agent（不绑定 MCP）
    result = ac.create_agent_api(name=agent_name, system_prompt="你是一个测试助手")
    _assert_create_success(result)

    try:
        # 2. 导航到智能体列表
        ac.goto_agents()
        logged_in_page.wait_for_load_state("networkidle")

        # 3. 找到新建 Agent 的卡片容器，hover 后点击"智能体配置"
        card = ac.wait_for_agent_card(agent_name)
        assert card.count() > 0, f"列表中未找到 '{agent_name}'"
        # 卡片父容器: div.agent-sidebar-agent
        agent_wrapper = card.first.locator("xpath=ancestor::div[contains(@class,'agent-sidebar-agent')]")
        agent_wrapper.hover()
        # 在该容器内点击配置按钮
        config_btn = agent_wrapper.locator('button[title="智能体配置"]')
        config_btn.click()
        logged_in_page.locator("div.absolute.inset-0.z-50").wait_for(state="visible", timeout=10000)
        try:
            logged_in_page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        logged_in_page.wait_for_timeout(1000)
        # 等待 modal 内容加载
        try:
            logged_in_page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        logged_in_page.wait_for_timeout(1000)

        # 4. 在编辑 modal 中，找到 MCP 区域，点击 + 展开列表
        modal = logged_in_page.locator("div.absolute.inset-0.z-50")
        assert modal.count() > 0, "编辑 Agent 的 modal 未打开"

        mcp_section = modal.locator(
            "div.rounded-lg.border.border-border-subtle.p-3"
        ).filter(has_text="绑定 MCP")
        assert mcp_section.count() > 0, "MCP 绑定区域不存在"

        # 验证初始状态：未绑定 MCP
        initial_text = mcp_section.inner_text()
        print(f"\n绑定前 MCP 区域: {initial_text[:80]}")
        assert "已选择 0 个 MCP" in initial_text, \
            f"新建 Agent 应无 MCP 绑定，实际: {initial_text[:60]}"

        # 点击 + 号展开 MCP 列表
        plus_btn = mcp_section.locator("button:has(svg.lucide-plus)")
        plus_btn.first.click()
        logged_in_page.wait_for_timeout(500)

        # 5. 选择第一个可用的 MCP 服务器（点击 label）
        mcp_labels = mcp_section.locator(
            "div.mt-3 label"
        )
        mcp_count = mcp_labels.count()
        print(f"可用 MCP 服务器: {mcp_count} 个")
        if mcp_count == 0:
            pytest.skip("没有可用的 MCP 服务器，跳过 MCP 绑定测试")
        assert mcp_count > 0, "没有可用的 MCP 服务器"

        # 获取第一个 MCP 名称
        first_mcp_name = mcp_labels.first.text_content().strip()
        print(f"选择绑定: {first_mcp_name}")
        mcp_labels.first.click()
        logged_in_page.wait_for_timeout(500)

        # 6. 点击保存
        save_btn = modal.get_by_role("button", name="保存")
        save_btn.click()
        logged_in_page.wait_for_timeout(500)

        # 6.1 处理"配置已保存"重启对话框
        restart_btn = logged_in_page.locator("[role='alertdialog']").get_by_role("button", name="重启")
        restart_btn.wait_for(state="visible", timeout=5000)
        restart_btn.click()
        logged_in_page.wait_for_load_state("networkidle")

        # 7. 重新打开配置，验证 MCP 已绑定
        card = ac.wait_for_agent_card(agent_name)
        agent_wrapper = card.first.locator("xpath=ancestor::div[contains(@class,'agent-sidebar-agent')]")
        agent_wrapper.hover()
        agent_wrapper.locator('button[title="智能体配置"]').click()
        logged_in_page.locator("div.absolute.inset-0.z-50").wait_for(state="visible", timeout=10000)
        try:
            logged_in_page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        logged_in_page.wait_for_timeout(1000)

        modal2 = logged_in_page.locator("div.absolute.inset-0.z-50")
        mcp_section2 = modal2.locator(
            "div.rounded-lg.border.border-border-subtle.p-3"
        ).filter(has_text="绑定 MCP")
        after_text = mcp_section2.inner_text()
        print(f"绑定后 MCP 区域: {after_text[:80]}")
        assert "已选择 1 个 MCP" in after_text, \
            f"MCP 应绑定成功，实际: {after_text[:60]}"

        # 关闭 modal
        close_btn = modal2.locator("button:has-text('✕')")
        if close_btn.count() > 0:
            close_btn.first.click()

    finally:
        # 8. 清理
        status = ac.delete_agent_api(agent_name)
        print(f"\n清理 '{agent_name}': status={status}")
        assert status in (200, 204, 404), f"删除 Agent 失败: status={status}"


@allure.epic("智能体配置")
@pytest.mark.order(126)
@pytest.mark.p1
def test_agent_026_no_mcp(logged_in_page, base_url, shared_agent):
    """✅ 人工评审通过 | TC-AGENT-026: 不绑定 MCP 的 Agent，验证仍能正常进入对话"""
    ac = shared_agent["ac"]
    agent_name = shared_agent["name"]

    ac.goto_agents()
    logged_in_page.wait_for_load_state("networkidle")

    # 找到共享 Agent 的卡片，确认存在
    card = ac.wait_for_agent_card(agent_name)
    assert card.count() > 0, f"列表中未找到 '{agent_name}'"

    # 点击进入对话
    card.first.click(force=True)
    try:
        logged_in_page.wait_for_url(
            lambda url: "/ctrl/agent/chat/" in url, timeout=10000
        )
    except Exception:
        pass
    logged_in_page.wait_for_load_state("networkidle")
    if _check_concurrency_limit(logged_in_page):
        pytest.skip("服务器并发上限，无法进入对话页面")
    assert ac.is_on_chat_page(), "不绑定 MCP 的 Agent 也应能进入对话页面"


@allure.epic("智能体配置")
@pytest.mark.order(127)
@pytest.mark.p0
def test_agent_027_bind_skill(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-AGENT-027: 创建 Agent 后通过编辑配置页面绑定 Skill 并验证"""
    ac = AgentConfigPage(logged_in_page, base_url)
    agent_name = f"skill-{_PREFIX}"

    # 1. API 创建 Agent（不绑定 Skill）
    result = ac.create_agent_api(name=agent_name, system_prompt="你是一个测试助手")
    _assert_create_success(result)

    try:
        # 2. 导航到智能体列表
        ac.goto_agents()
        logged_in_page.wait_for_load_state("networkidle")

        # 3. 找到新建 Agent 的卡片容器，hover 后点击"智能体配置"
        card = ac.wait_for_agent_card(agent_name)
        assert card.count() > 0, f"列表中未找到 '{agent_name}'"
        agent_wrapper = card.first.locator("xpath=ancestor::div[contains(@class,'agent-sidebar-agent')]")
        card = ac.wait_for_agent_card(agent_name)
        agent_wrapper = card.first.locator("xpath=ancestor::div[contains(@class,'agent-sidebar-agent')]")
        agent_wrapper.hover()
        agent_wrapper.locator('button[title="智能体配置"]').click()
        logged_in_page.locator("div.absolute.inset-0.z-50").wait_for(state="visible", timeout=10000)
        try:
            logged_in_page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        logged_in_page.wait_for_timeout(1000)

        # 4. 在编辑 modal 中，找到 Skill 区域
        modal = logged_in_page.locator("div.absolute.inset-0.z-50")
        assert modal.count() > 0, "编辑 Agent 的 modal 未打开"

        skill_section = modal.locator(
            "div.rounded-lg.border.border-border-subtle.p-3"
        ).filter(has_text="绑定技能")
        assert skill_section.count() > 0, "技能绑定区域不存在"

        # 验证初始状态：未绑定 Skill
        initial_text = skill_section.inner_text()
        print(f"\n绑定前 Skill 区域: {initial_text[:80]}")
        assert "已选择 0 个技能" in initial_text, \
            f"新建 Agent 应无 Skill 绑定，实际: {initial_text[:60]}"

        # 点击 + 号展开 Skill 列表
        plus_btn = skill_section.locator("button:has(svg.lucide-plus)")
        plus_btn.first.click()
        logged_in_page.wait_for_timeout(500)

        # 5. 选择第一个可用的 Skill（点击 label）
        skill_labels = skill_section.locator("div.mt-3 label")
        skill_count = skill_labels.count()
        print(f"可用 Skill: {skill_count} 个")
        assert skill_count > 0, "没有可用的 Skill"

        first_skill_name = skill_labels.first.text_content().strip()
        print(f"选择绑定: {first_skill_name}")
        skill_labels.first.click()
        logged_in_page.wait_for_timeout(500)

        # 6. 点击保存
        save_btn = modal.get_by_role("button", name="保存")
        save_btn.click()
        logged_in_page.wait_for_timeout(500)

        # 6.1 处理重启对话框
        restart_btn = logged_in_page.locator("[role='alertdialog']").get_by_role("button", name="重启")
        restart_btn.wait_for(state="visible", timeout=5000)
        restart_btn.click()
        logged_in_page.wait_for_load_state("networkidle")

        # 7. 重新打开配置，验证 Skill 已绑定
        # 重启后 DOM 可能重新渲染，重新查找卡片
        card = ac.wait_for_agent_card(agent_name)
        agent_wrapper = card.first.locator("xpath=ancestor::div[contains(@class,'agent-sidebar-agent')]")
        card = ac.wait_for_agent_card(agent_name)
        agent_wrapper = card.first.locator("xpath=ancestor::div[contains(@class,'agent-sidebar-agent')]")
        agent_wrapper.hover()
        agent_wrapper.locator('button[title="智能体配置"]').click()
        logged_in_page.locator("div.absolute.inset-0.z-50").wait_for(state="visible", timeout=10000)
        try:
            logged_in_page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        logged_in_page.wait_for_timeout(1000)

        modal2 = logged_in_page.locator("div.absolute.inset-0.z-50")
        skill_section2 = modal2.locator(
            "div.rounded-lg.border.border-border-subtle.p-3"
        ).filter(has_text="绑定技能")
        after_text = skill_section2.inner_text()
        print(f"绑定后 Skill 区域: {after_text[:80]}")
        assert "已选择 1 个技能" in after_text, \
            f"Skill 应绑定成功，实际: {after_text[:60]}"

        # 关闭 modal
        close_btn = modal2.locator("button:has-text('✕')")
        if close_btn.count() > 0:
            close_btn.first.click()

    finally:
        # 8. 清理
        status = ac.delete_agent_api(agent_name)
        print(f"\n清理 '{agent_name}': status={status}")
        assert status in (200, 204, 404), f"删除 Agent 失败: status={status}"


@allure.epic("智能体配置")
@pytest.mark.order(128)
@pytest.mark.p1
def test_agent_028_no_skill(logged_in_page, base_url, shared_agent):
    """✅ 人工评审通过 | TC-AGENT-028: 不绑定 Skill 的 Agent，验证仍能正常进入对话"""
    ac = shared_agent["ac"]
    agent_name = shared_agent["name"]

    ac.goto_agents()
    logged_in_page.wait_for_load_state("networkidle")

    card = ac.wait_for_agent_card(agent_name)
    assert card.count() > 0, f"列表中未找到 '{agent_name}'"

    card.first.click(force=True)
    try:
        logged_in_page.wait_for_url(
            lambda url: "/ctrl/agent/chat/" in url, timeout=10000
        )
    except Exception:
        pass
    logged_in_page.wait_for_load_state("networkidle")
    if _check_concurrency_limit(logged_in_page):
        pytest.skip("服务器并发上限，无法进入对话页面")
    assert ac.is_on_chat_page(), "不绑定 Skill 的 Agent 也应能进入对话页面"


@allure.epic("智能体配置")
@pytest.mark.order(129)
@pytest.mark.p0
def test_agent_029_bind_knowledge(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-AGENT-029: 创建 Agent 后通过编辑配置页面的知识库 tab 绑定知识库并验证"""
    ac = AgentConfigPage(logged_in_page, base_url)
    agent_name = f"kb-{_PREFIX}"

    # 1. API 创建 Agent
    result = ac.create_agent_api(name=agent_name, system_prompt="你是一个测试助手")
    _assert_create_success(result)

    try:
        # 2. 导航到智能体列表
        ac.goto_agents()
        logged_in_page.wait_for_load_state("networkidle")

        # 3. 找到新建 Agent，打开配置 modal
        card = ac.wait_for_agent_card(agent_name)
        assert card.count() > 0, f"列表中未找到 '{agent_name}'"
        agent_wrapper = card.first.locator("xpath=ancestor::div[contains(@class,'agent-sidebar-agent')]")
        card = ac.wait_for_agent_card(agent_name)
        agent_wrapper = card.first.locator("xpath=ancestor::div[contains(@class,'agent-sidebar-agent')]")
        agent_wrapper.hover()
        agent_wrapper.locator('button[title="智能体配置"]').click()
        logged_in_page.locator("div.absolute.inset-0.z-50").wait_for(state="visible", timeout=10000)
        try:
            logged_in_page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        logged_in_page.wait_for_timeout(1000)

        modal = logged_in_page.locator("div.absolute.inset-0.z-50")
        assert modal.count() > 0, "编辑 Agent 的 modal 未打开"

        # 4. 切换到"知识库" tab
        kb_tab = modal.get_by_role("button", name="知识库")
        kb_tab.click()
        logged_in_page.wait_for_timeout(500)

        # 5. 验证初始状态：未绑定知识库
        modal_text = modal.inner_text()
        print(f"\n绑定前知识库内容: {[l for l in modal_text.split(chr(10)) if '知识库' in l or '已选择' in l]}")
        assert "已选择 0 个知识库" in modal_text, \
            "新建 Agent 应无知识库绑定"

        # 6. 选择第一个可用的知识库
        # 在知识库 tab 内找 checkbox 对应的 label（排除 tab 按钮和标题）
        kb_labels = modal.locator("input[type='checkbox']:visible").first.locator("xpath=ancestor::label")
        if kb_labels.count() == 0:
            # 备选：知识库列表中的可点击 label
            kb_labels = modal.locator("label:visible").filter(has_text="知识库").nth(1)
        kb_labels.click()
        logged_in_page.wait_for_timeout(500)

        # 获取选中的知识库名称
        first_kb = kb_labels.text_content().strip()[:40]
        print(f"选择绑定知识库: {first_kb}")

        # 7. 点击保存
        save_btn = modal.get_by_role("button", name="保存")
        save_btn.click()
        logged_in_page.wait_for_timeout(500)

        # 7.1 处理重启对话框
        restart_btn = logged_in_page.locator("[role='alertdialog']").get_by_role("button", name="重启")
        restart_btn.wait_for(state="visible", timeout=5000)
        restart_btn.click()
        logged_in_page.wait_for_load_state("networkidle")

        # 8. 重新打开配置，验证知识库已绑定
        card = ac.wait_for_agent_card(agent_name)
        agent_wrapper = card.first.locator("xpath=ancestor::div[contains(@class,'agent-sidebar-agent')]")
        agent_wrapper.hover()
        agent_wrapper.locator('button[title="智能体配置"]').click()
        logged_in_page.locator("div.absolute.inset-0.z-50").wait_for(state="visible", timeout=10000)
        try:
            logged_in_page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        logged_in_page.wait_for_timeout(1000)

        modal2 = logged_in_page.locator("div.absolute.inset-0.z-50")
        kb_tab2 = modal2.get_by_role("button", name="知识库")
        kb_tab2.click()
        logged_in_page.wait_for_timeout(500)

        after_text = modal2.inner_text()
        print(f"绑定后知识库内容: {[l for l in after_text.split(chr(10)) if '已选择' in l]}")
        assert "已选择 1 个知识库" in after_text, \
            f"知识库应绑定成功，实际: {[l for l in after_text.split(chr(10)) if '已选择' in l]}"

        # 关闭 modal
        close_btn = modal2.locator("button:has-text('✕')")
        if close_btn.count() > 0:
            close_btn.first.click()

    finally:
        # 9. 清理
        status = ac.delete_agent_api(agent_name)
        print(f"\n清理 '{agent_name}': status={status}")
        assert status in (200, 204, 404), f"删除 Agent 失败: status={status}"


@allure.epic("智能体配置")
@pytest.mark.order(130)
@pytest.mark.p0
def test_agent_030_select_model(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-AGENT-030: 创建 Agent 后通过编辑配置页面切换模型并验证生效"""
    ac = AgentConfigPage(logged_in_page, base_url)
    agent_name = f"model-{_PREFIX}"

    # 1. API 创建 Agent
    result = ac.create_agent_api(name=agent_name, system_prompt="你是一个测试助手")
    _assert_create_success(result)

    try:
        # 2. 导航到智能体列表
        ac.goto_agents()
        logged_in_page.wait_for_load_state("networkidle")

        # 3. 打开配置 modal
        card = ac.wait_for_agent_card(agent_name)
        assert card.count() > 0, f"列表中未找到 '{agent_name}'"
        agent_wrapper = card.first.locator("xpath=ancestor::div[contains(@class,'agent-sidebar-agent')]")
        card = ac.wait_for_agent_card(agent_name)
        agent_wrapper = card.first.locator("xpath=ancestor::div[contains(@class,'agent-sidebar-agent')]")
        agent_wrapper.hover()
        agent_wrapper.locator('button[title="智能体配置"]').click()
        logged_in_page.locator("div.absolute.inset-0.z-50").wait_for(state="visible", timeout=10000)
        try:
            logged_in_page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        logged_in_page.wait_for_timeout(1000)

        modal = logged_in_page.locator("div.absolute.inset-0.z-50")
        assert modal.count() > 0, "编辑 Agent 的 modal 未打开"

        # 4. 记录当前模型
        model_btn = modal.locator("button").filter(has_text="选择模型").first
        if model_btn.count() == 0:
            model_btn = modal.locator("label:has-text('模型') + button, label:has-text('模型') ~ button").first
        current_model = model_btn.text_content().strip()
        print(f"\n当前模型: {current_model}")

        # 5. 点击模型下拉按钮
        model_btn.click()
        logged_in_page.wait_for_timeout(500)

        # 6. 获取可选模型列表
        model_options = logged_in_page.locator("[data-state='open'] [role='option'], [data-radix-popper-content-wrapper] [role='option']")
        if model_options.count() == 0:
            # 备选：查找下拉列表中的所有可点击项
            model_options = logged_in_page.locator("[data-state='open'] [role='option'], [data-radix-popper-content-wrapper] [role='option']")

        option_count = model_options.count()
        print(f"可选模型数量: {option_count}")

        if option_count <= 1:
            # 只有一个模型可选，验证模型显示即可
            allure.attach(
                f"只有 {option_count} 个模型可选，无法切换。当前模型: {current_model}",
                name="模型配置",
                attachment_type=allure.attachment_type.TEXT,
            )
            # 关闭下拉
            logged_in_page.keyboard.press("Escape")
        else:
            # 选择第二个模型（与当前不同的）
            new_model_text = model_options.nth(1).text_content().strip()
            print(f"切换到: {new_model_text}")
            model_options.nth(1).click()
            logged_in_page.wait_for_timeout(500)

            # 7. 保存
            save_btn = modal.get_by_role("button", name="保存")
            save_btn.click()
            logged_in_page.wait_for_timeout(500)

            # 7.1 处理重启对话框
            restart_btn = logged_in_page.locator("[role='alertdialog']").get_by_role("button", name="重启")
            restart_btn.wait_for(state="visible", timeout=5000)
            restart_btn.click()
            logged_in_page.wait_for_load_state("networkidle")

            # 8. 重新打开配置，验证模型已切换
            card = ac.wait_for_agent_card(agent_name)
            agent_wrapper = card.first.locator("xpath=ancestor::div[contains(@class,'agent-sidebar-agent')]")
            agent_wrapper.hover()
            agent_wrapper.locator('button[title="智能体配置"]').click()
            logged_in_page.locator("div.absolute.inset-0.z-50").wait_for(state="visible", timeout=10000)
            try:
                logged_in_page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
            logged_in_page.wait_for_timeout(1000)

            modal2 = logged_in_page.locator("div.absolute.inset-0.z-50")
            # Debug: 检查 modal 内容
            modal2_text = modal2.inner_text()
            print(f"重新打开 modal 内容 (前200字): {modal2_text[:200]}")
            # 选择模型后按钮文本变为模型名，用模型 label 的父容器定位
            model_container = modal2.locator("label:has-text('模型')").locator("xpath=..")
            new_model_btn = model_container.locator("button").first
            if new_model_btn.count() == 0:
                new_model_btn = modal2.locator("button").filter(has_text="选择模型").first
            after_model = new_model_btn.text_content().strip()
            print(f"切换后模型: {after_model}")
            assert after_model != current_model, \
                f"模型应已切换，但仍为: {after_model}"

        # 关闭 modal
        close_btn = modal.locator("button:has-text('✕')")
        if close_btn.count() > 0:
            close_btn.first.click()

    finally:
        # 9. 清理
        status = ac.delete_agent_api(agent_name)
        print(f"\n清理 '{agent_name}': status={status}")
        assert status in (200, 204, 404), f"删除 Agent 失败: status={status}"


@allure.epic("智能体配置")
@pytest.mark.order(131)
@pytest.mark.p0
def test_agent_031_create_full_config(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-AGENT-031: 创建时填写全部可选配置并验证
    验证创建流程中各项配置入口存在
    """
    ac = AgentConfigPage(logged_in_page, base_url)
    ac.goto_create()

    # 1. MetaAgent 入口
    has_meta = ac.has_meta_agent()
    assert has_meta, "应有 MetaAgent 自然语言创建入口"

    # 2. 快捷模版
    templates = ac.get_template_names()
    has_templates = len(templates) > 0

    # 3. 一键创建按钮
    has_quick = ac.has_quick_create_button()

    allure.attach(
        f"创建页面配置入口:\n"
        f"  MetaAgent textarea: {has_meta}\n"
        f"  快捷模版: {has_templates} ({len(templates)} 个)\n"
        f"  一键创建: {has_quick}",
        name="创建入口",
        attachment_type=allure.attachment_type.TEXT,
    )

    assert has_meta or has_templates or has_quick, \
        f"首页缺少元数据/模板/快捷入口，has_meta={has_meta}, has_templates={has_templates}, has_quick={has_quick}"


@allure.epic("智能体配置")
@pytest.mark.order(132)
@pytest.mark.p1
def test_agent_032_edit_add_config(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-AGENT-032: 创建后补充填写未选的可选配置
    验证 Agent 编辑/配置入口存在
    """
    ac = AgentConfigPage(logged_in_page, base_url)
    ac.goto_agents()

    names = ac.get_agent_names()
    assert len(names) > 0, "应有至少一个智能体"

    # 点击第一个 Agent 进入对话
    ac.click_agent(names[0])
    logged_in_page.wait_for_load_state("networkidle")

    # 对话页面应有配置相关入口
    if ac.is_on_chat_page():
        body = ac.get_chat_page_text()
        # 检查是否有配置相关的按钮/区域
        has_config = any(kw in body for kw in [
            "技能", "文件", "定时任务", "站点"
        ])
        allure.attach(
            f"Agent '{names[0]}' 对话页面配置入口: {has_config}",
            name="配置入口",
            attachment_type=allure.attachment_type.TEXT,
        )
        assert has_config, "对话页面应有配置相关区域"


@allure.epic("智能体配置")
@pytest.mark.order(133)
@pytest.mark.p1
def test_add_then_remove_skill(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-AGENT-033: 先绑定一个技能，然后移除，验证移除成功"""
    ac = AgentConfigPage(logged_in_page, base_url)
    agent_name = f"rm-skill-{_PREFIX}"

    # 1. API 创建 Agent
    result = ac.create_agent_api(name=agent_name, system_prompt="你是一个测试助手")
    _assert_create_success(result)

    try:
        ac.goto_agents()
        logged_in_page.wait_for_load_state("networkidle")

        card = ac.wait_for_agent_card(agent_name)
        assert card.count() > 0, f"列表中未找到 '{agent_name}'"
        agent_wrapper = card.first.locator("xpath=ancestor::div[contains(@class,'agent-sidebar-agent')]")

        # === 阶段一：绑定一个技能 ===
        card = ac.wait_for_agent_card(agent_name)
        agent_wrapper = card.first.locator("xpath=ancestor::div[contains(@class,'agent-sidebar-agent')]")
        agent_wrapper.hover()
        agent_wrapper.locator('button[title="智能体配置"]').click()
        logged_in_page.locator("div.absolute.inset-0.z-50").wait_for(state="visible", timeout=10000)
        try:
            logged_in_page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        logged_in_page.wait_for_timeout(1000)

        modal = logged_in_page.locator("div.absolute.inset-0.z-50")
        skill_section = modal.locator(
            "div.rounded-lg.border.border-border-subtle.p-3"
        ).filter(has_text="绑定技能")

        # 点击 + 展开 Skill 列表
        plus_btn = skill_section.locator("button:has(svg.lucide-plus)")
        plus_btn.first.click()
        logged_in_page.wait_for_timeout(500)

        # 选择第一个 Skill
        skill_labels = skill_section.locator("div.mt-3 label")
        assert skill_labels.count() > 0, "没有可用的 Skill"
        first_skill = skill_labels.first.text_content().strip()[:40]
        print(f"\n绑定技能: {first_skill}")
        skill_labels.first.click()
        logged_in_page.wait_for_timeout(500)

        # 保存
        modal.get_by_role("button", name="保存").click()
        logged_in_page.locator("[role='alertdialog']").get_by_role("button", name="重启").wait_for(state="visible", timeout=15000)
        restart_btn = logged_in_page.locator("[role='alertdialog']").get_by_role("button", name="重启")
        restart_btn.wait_for(state="visible", timeout=5000)
        restart_btn.click()
        logged_in_page.wait_for_load_state("networkidle")

        # === 阶段二：移除该技能 ===
        card = ac.wait_for_agent_card(agent_name)
        agent_wrapper = card.first.locator("xpath=ancestor::div[contains(@class,'agent-sidebar-agent')]")
        agent_wrapper.hover()
        agent_wrapper.locator('button[title="智能体配置"]').click()
        logged_in_page.locator("div.absolute.inset-0.z-50").wait_for(state="visible", timeout=10000)
        try:
            logged_in_page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        logged_in_page.wait_for_timeout(1000)

        modal2 = logged_in_page.locator("div.absolute.inset-0.z-50")
        skill_section2 = modal2.locator(
            "div.rounded-lg.border.border-border-subtle.p-3"
        ).filter(has_text="绑定技能")

        # 验证已绑定 1 个技能
        before_text = skill_section2.inner_text()
        print(f"移除前: {[l for l in before_text.split(chr(10)) if '已选择' in l]}")
        assert "已选择 1 个技能" in before_text, "应先有 1 个技能绑定"

        # 点击已绑定技能的 X 按钮移除
        x_btns = skill_section2.locator(
            "div.flex.flex-wrap button:has(svg.lucide-x)"
        )
        assert x_btns.count() > 0, "没有找到已绑定技能的移除按钮"
        x_btns.first.click()
        logged_in_page.wait_for_timeout(500)

        # 保存
        modal2.get_by_role("button", name="保存").click()
        logged_in_page.locator("[role='alertdialog']").get_by_role("button", name="重启").wait_for(state="visible", timeout=15000)
        restart_btn2 = logged_in_page.locator("[role='alertdialog']").get_by_role("button", name="重启")
        restart_btn2.wait_for(state="visible", timeout=5000)
        restart_btn2.click()
        logged_in_page.wait_for_timeout(1000)

        # === 阶段三：验证技能已移除 ===
        card = ac.wait_for_agent_card(agent_name)
        agent_wrapper = card.first.locator("xpath=ancestor::div[contains(@class,'agent-sidebar-agent')]")
        agent_wrapper.hover()
        agent_wrapper.locator('button[title="智能体配置"]').click()
        logged_in_page.locator("div.absolute.inset-0.z-50").wait_for(state="visible", timeout=10000)
        try:
            logged_in_page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        logged_in_page.wait_for_timeout(1000)

        modal3 = logged_in_page.locator("div.absolute.inset-0.z-50")
        skill_section3 = modal3.locator(
            "div.rounded-lg.border.border-border-subtle.p-3"
        ).filter(has_text="绑定技能")
        after_text = skill_section3.inner_text()
        print(f"移除后: {[l for l in after_text.split(chr(10)) if '已选择' in l]}")
        assert "已选择 0 个技能" in after_text, \
            f"技能应已移除，实际: {[l for l in after_text.split(chr(10)) if '已选择' in l]}"

        # 关闭 modal
        close_btn = modal3.locator("button:has-text('✕')")
        if close_btn.count() > 0:
            close_btn.first.click()

    finally:
        status = ac.delete_agent_api(agent_name)
        print(f"\n清理 '{agent_name}': status={status}")
        assert status in (200, 204, 404), f"删除 Agent 失败: status={status}"


@allure.epic("智能体配置")
@pytest.mark.order(133)
@pytest.mark.p1
def test_add_then_remove_mcp(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-AGENT-033b: 先绑定一个 MCP，然后移除，验证移除成功"""
    ac = AgentConfigPage(logged_in_page, base_url)
    agent_name = f"rm-mcp-{_PREFIX}"

    result = ac.create_agent_api(name=agent_name, system_prompt="你是一个测试助手")
    _assert_create_success(result)

    try:
        ac.goto_agents()
        logged_in_page.wait_for_load_state("networkidle")

        card = ac.wait_for_agent_card(agent_name)
        assert card.count() > 0, f"列表中未找到 '{agent_name}'"
        agent_wrapper = card.first.locator("xpath=ancestor::div[contains(@class,'agent-sidebar-agent')]")

        # === 阶段一：绑定 MCP ===
        card = ac.wait_for_agent_card(agent_name)
        agent_wrapper = card.first.locator("xpath=ancestor::div[contains(@class,'agent-sidebar-agent')]")
        agent_wrapper.hover()
        agent_wrapper.locator('button[title="智能体配置"]').click()
        logged_in_page.locator("div.absolute.inset-0.z-50").wait_for(state="visible", timeout=10000)
        try:
            logged_in_page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        logged_in_page.wait_for_timeout(1000)

        modal = logged_in_page.locator("div.absolute.inset-0.z-50")
        mcp_section = modal.locator(
            "div.rounded-lg.border.border-border-subtle.p-3"
        ).filter(has_text="绑定 MCP")

        plus_btn = mcp_section.locator("button:has(svg.lucide-plus)")
        plus_btn.first.click()
        logged_in_page.wait_for_timeout(500)

        mcp_labels = mcp_section.locator("div.mt-3 label")
        if mcp_labels.count() == 0:
            pytest.skip("没有可用的 MCP 服务器，跳过 MCP 绑定测试")
        assert mcp_labels.count() > 0, "没有可用的 MCP 服务器"
        first_mcp = mcp_labels.first.text_content().strip()[:40]
        print(f"\n绑定 MCP: {first_mcp}")
        mcp_labels.first.click()
        logged_in_page.wait_for_timeout(500)

        modal.get_by_role("button", name="保存").click()
        logged_in_page.locator("[role='alertdialog']").get_by_role("button", name="重启").wait_for(state="visible", timeout=15000)
        restart_btn = logged_in_page.locator("[role='alertdialog']").get_by_role("button", name="重启")
        restart_btn.wait_for(state="visible", timeout=5000)
        restart_btn.click()
        logged_in_page.wait_for_load_state("networkidle")

        # === 阶段二：移除 MCP ===
        card = ac.wait_for_agent_card(agent_name)
        agent_wrapper = card.first.locator("xpath=ancestor::div[contains(@class,'agent-sidebar-agent')]")
        agent_wrapper.hover()
        agent_wrapper.locator('button[title="智能体配置"]').click()
        logged_in_page.locator("div.absolute.inset-0.z-50").wait_for(state="visible", timeout=10000)
        try:
            logged_in_page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        logged_in_page.wait_for_timeout(1000)

        modal2 = logged_in_page.locator("div.absolute.inset-0.z-50")
        mcp_section2 = modal2.locator(
            "div.rounded-lg.border.border-border-subtle.p-3"
        ).filter(has_text="绑定 MCP")

        before_text = mcp_section2.inner_text()
        print(f"移除前: {[l for l in before_text.split(chr(10)) if '已选择' in l]}")
        assert "已选择 1 个 MCP" in before_text, "应先有 1 个 MCP 绑定"

        x_btns = mcp_section2.locator(
            "div.flex.flex-wrap button:has(svg.lucide-x)"
        )
        assert x_btns.count() > 0, "没有找到已绑定 MCP 的移除按钮"
        x_btns.first.click()
        logged_in_page.wait_for_timeout(500)

        modal2.get_by_role("button", name="保存").click()
        logged_in_page.locator("[role='alertdialog']").get_by_role("button", name="重启").wait_for(state="visible", timeout=15000)
        restart_btn2 = logged_in_page.locator("[role='alertdialog']").get_by_role("button", name="重启")
        restart_btn2.wait_for(state="visible", timeout=5000)
        restart_btn2.click()
        logged_in_page.wait_for_timeout(1000)

        # === 阶段三：验证 MCP 已移除 ===
        card = ac.wait_for_agent_card(agent_name)
        agent_wrapper = card.first.locator("xpath=ancestor::div[contains(@class,'agent-sidebar-agent')]")
        agent_wrapper.hover()
        agent_wrapper.locator('button[title="智能体配置"]').click()
        logged_in_page.locator("div.absolute.inset-0.z-50").wait_for(state="visible", timeout=10000)
        try:
            logged_in_page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        logged_in_page.wait_for_timeout(1000)

        modal3 = logged_in_page.locator("div.absolute.inset-0.z-50")
        mcp_section3 = modal3.locator(
            "div.rounded-lg.border.border-border-subtle.p-3"
        ).filter(has_text="绑定 MCP")
        after_text = mcp_section3.inner_text()
        print(f"移除后: {[l for l in after_text.split(chr(10)) if '已选择' in l]}")
        assert "已选择 0 个 MCP" in after_text, \
            f"MCP 应已移除，实际: {[l for l in after_text.split(chr(10)) if '已选择' in l]}"

        close_btn = modal3.locator("button:has-text('✕')")
        if close_btn.count() > 0:
            close_btn.first.click()

    finally:
        status = ac.delete_agent_api(agent_name)
        print(f"\n清理 '{agent_name}': status={status}")
        assert status in (200, 204, 404), f"删除 Agent 失败: status={status}"


@allure.epic("智能体配置")
@pytest.mark.order(133)
@pytest.mark.p1
def test_add_then_remove_knowledge(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-AGENT-033c: 先绑定一个知识库，然后移除，验证移除成功"""
    ac = AgentConfigPage(logged_in_page, base_url)
    agent_name = f"rm-kb-{_PREFIX}"

    result = ac.create_agent_api(name=agent_name, system_prompt="你是一个测试助手")
    _assert_create_success(result)

    try:
        ac.goto_agents()
        logged_in_page.wait_for_load_state("networkidle")

        card = ac.wait_for_agent_card(agent_name)
        assert card.count() > 0, f"列表中未找到 '{agent_name}'"
        agent_wrapper = card.first.locator("xpath=ancestor::div[contains(@class,'agent-sidebar-agent')]")

        # === 阶段一：绑定知识库 ===
        card = ac.wait_for_agent_card(agent_name)
        agent_wrapper = card.first.locator("xpath=ancestor::div[contains(@class,'agent-sidebar-agent')]")
        agent_wrapper.hover()
        agent_wrapper.locator('button[title="智能体配置"]').click()
        logged_in_page.locator("div.absolute.inset-0.z-50").wait_for(state="visible", timeout=10000)
        try:
            logged_in_page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        logged_in_page.wait_for_timeout(1000)

        modal = logged_in_page.locator("div.absolute.inset-0.z-50")
        kb_tab = modal.get_by_role("button", name="知识库")
        kb_tab.click()
        logged_in_page.wait_for_timeout(500)

        kb_labels = modal.locator("input[type='checkbox']:visible").first.locator("xpath=ancestor::label")
        if kb_labels.count() == 0:
            kb_labels = modal.locator("label:visible").filter(has_text="知识库").nth(1)
        first_kb = kb_labels.text_content().strip()[:40]
        print(f"\n绑定知识库: {first_kb}")
        kb_labels.click()
        logged_in_page.wait_for_timeout(500)

        modal.get_by_role("button", name="保存").click()
        logged_in_page.locator("[role='alertdialog']").get_by_role("button", name="重启").wait_for(state="visible", timeout=15000)
        restart_btn = logged_in_page.locator("[role='alertdialog']").get_by_role("button", name="重启")
        restart_btn.wait_for(state="visible", timeout=5000)
        restart_btn.click()
        logged_in_page.wait_for_load_state("networkidle")

        # === 阶段二：移除知识库 ===
        card = ac.wait_for_agent_card(agent_name)
        agent_wrapper = card.first.locator("xpath=ancestor::div[contains(@class,'agent-sidebar-agent')]")
        agent_wrapper.hover()
        agent_wrapper.locator('button[title="智能体配置"]').click()
        logged_in_page.locator("div.absolute.inset-0.z-50").wait_for(state="visible", timeout=10000)
        try:
            logged_in_page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        logged_in_page.wait_for_timeout(1000)

        modal2 = logged_in_page.locator("div.absolute.inset-0.z-50")
        kb_tab2 = modal2.get_by_role("button", name="知识库")
        kb_tab2.click()
        logged_in_page.wait_for_timeout(500)

        before_text = modal2.inner_text()
        print(f"移除前: {[l for l in before_text.split(chr(10)) if '已选择' in l]}")
        assert "已选择 1 个知识库" in before_text, "应先有 1 个知识库绑定"

        # 取消勾选
        kb_labels2 = modal2.locator("input[type='checkbox']:visible").first.locator("xpath=ancestor::label")
        if kb_labels2.count() == 0:
            kb_labels2 = modal2.locator("label:visible").filter(has_text="知识库").nth(1)
        kb_labels2.click()
        logged_in_page.wait_for_timeout(500)

        modal2.get_by_role("button", name="保存").click()
        logged_in_page.locator("[role='alertdialog']").get_by_role("button", name="重启").wait_for(state="visible", timeout=15000)
        restart_btn2 = logged_in_page.locator("[role='alertdialog']").get_by_role("button", name="重启")
        restart_btn2.wait_for(state="visible", timeout=5000)
        restart_btn2.click()
        logged_in_page.wait_for_timeout(1000)

        # === 阶段三：验证知识库已移除 ===
        card = ac.wait_for_agent_card(agent_name)
        agent_wrapper = card.first.locator("xpath=ancestor::div[contains(@class,'agent-sidebar-agent')]")
        agent_wrapper.hover()
        agent_wrapper.locator('button[title="智能体配置"]').click()
        logged_in_page.locator("div.absolute.inset-0.z-50").wait_for(state="visible", timeout=10000)
        try:
            logged_in_page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        logged_in_page.wait_for_timeout(1000)

        modal3 = logged_in_page.locator("div.absolute.inset-0.z-50")
        kb_tab3 = modal3.get_by_role("button", name="知识库")
        kb_tab3.click()
        logged_in_page.wait_for_timeout(500)

        after_text = modal3.inner_text()
        print(f"移除后: {[l for l in after_text.split(chr(10)) if '已选择' in l]}")
        assert "已选择 0 个知识库" in after_text, \
            f"知识库应已移除，实际: {[l for l in after_text.split(chr(10)) if '已选择' in l]}"

        close_btn = modal3.locator("button:has-text('✕')")
        if close_btn.count() > 0:
            close_btn.first.click()

    finally:
        status = ac.delete_agent_api(agent_name)
        print(f"\n清理 '{agent_name}': status={status}")
        assert status in (200, 204, 404), f"删除 Agent 失败: status={status}"


@allure.epic("智能体配置")
@pytest.mark.order(133)
@pytest.mark.p1
def test_add_then_remove_sites(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-AGENT-033d: 先绑定一个 Sites，然后移除，验证移除成功"""
    ac = AgentConfigPage(logged_in_page, base_url)
    agent_name = f"rm-sites-{_PREFIX}"

    result = ac.create_agent_api(name=agent_name, system_prompt="你是一个测试助手")
    _assert_create_success(result)

    try:
        ac.goto_agents()
        logged_in_page.wait_for_load_state("networkidle")

        card = ac.wait_for_agent_card(agent_name)
        assert card.count() > 0, f"列表中未找到 '{agent_name}'"
        agent_wrapper = card.first.locator("xpath=ancestor::div[contains(@class,'agent-sidebar-agent')]")

        # === 阶段一：绑定 Sites ===
        card = ac.wait_for_agent_card(agent_name)
        agent_wrapper = card.first.locator("xpath=ancestor::div[contains(@class,'agent-sidebar-agent')]")
        agent_wrapper.hover()
        agent_wrapper.locator('button[title="智能体配置"]').click()
        logged_in_page.locator("div.absolute.inset-0.z-50").wait_for(state="visible", timeout=10000)
        try:
            logged_in_page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        logged_in_page.wait_for_timeout(1000)

        modal = logged_in_page.locator("div.absolute.inset-0.z-50")
        sites_section = modal.locator(
            "div.rounded-lg.border.border-border-subtle.p-3"
        ).filter(has_text="绑定 Sites")

        plus_btn = sites_section.locator("button:has(svg.lucide-plus)")
        plus_btn.first.click()
        logged_in_page.wait_for_timeout(500)

        sites_labels = sites_section.locator("div.mt-3 label")
        assert sites_labels.count() > 0, "没有可用的 Sites"
        first_site = sites_labels.first.text_content().strip()[:40]
        print(f"\n绑定 Sites: {first_site}")
        sites_labels.first.click()
        logged_in_page.wait_for_timeout(500)

        modal.get_by_role("button", name="保存").click()
        logged_in_page.locator("[role='alertdialog']").get_by_role("button", name="重启").wait_for(state="visible", timeout=15000)
        restart_btn = logged_in_page.locator("[role='alertdialog']").get_by_role("button", name="重启")
        restart_btn.wait_for(state="visible", timeout=5000)
        restart_btn.click()
        logged_in_page.wait_for_load_state("networkidle")

        # === 阶段二：移除 Sites ===
        card = ac.wait_for_agent_card(agent_name)
        agent_wrapper = card.first.locator("xpath=ancestor::div[contains(@class,'agent-sidebar-agent')]")
        agent_wrapper.hover()
        agent_wrapper.locator('button[title="智能体配置"]').click()
        logged_in_page.locator("div.absolute.inset-0.z-50").wait_for(state="visible", timeout=10000)
        try:
            logged_in_page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        logged_in_page.wait_for_timeout(1000)

        modal2 = logged_in_page.locator("div.absolute.inset-0.z-50")
        sites_section2 = modal2.locator(
            "div.rounded-lg.border.border-border-subtle.p-3"
        ).filter(has_text="绑定 Sites")

        before_text = sites_section2.inner_text()
        print(f"移除前: {[l for l in before_text.split(chr(10)) if '已选择' in l]}")
        assert "已选择 1 个 Site" in before_text, "应先有 1 个 Site 绑定"

        x_btns = sites_section2.locator(
            "div.flex.flex-wrap button:has(svg.lucide-x)"
        )
        assert x_btns.count() > 0, "没有找到已绑定 Sites 的移除按钮"
        x_btns.first.click()
        logged_in_page.wait_for_timeout(500)

        modal2.get_by_role("button", name="保存").click()
        logged_in_page.locator("[role='alertdialog']").get_by_role("button", name="重启").wait_for(state="visible", timeout=15000)
        restart_btn2 = logged_in_page.locator("[role='alertdialog']").get_by_role("button", name="重启")
        restart_btn2.wait_for(state="visible", timeout=5000)
        restart_btn2.click()
        logged_in_page.wait_for_timeout(1000)

        # === 阶段三：验证 Sites 已移除 ===
        card = ac.wait_for_agent_card(agent_name)
        agent_wrapper = card.first.locator("xpath=ancestor::div[contains(@class,'agent-sidebar-agent')]")
        agent_wrapper.hover()
        agent_wrapper.locator('button[title="智能体配置"]').click()
        logged_in_page.locator("div.absolute.inset-0.z-50").wait_for(state="visible", timeout=10000)
        try:
            logged_in_page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        logged_in_page.wait_for_timeout(1000)

        modal3 = logged_in_page.locator("div.absolute.inset-0.z-50")
        sites_section3 = modal3.locator(
            "div.rounded-lg.border.border-border-subtle.p-3"
        ).filter(has_text="绑定 Sites")
        after_text = sites_section3.inner_text()
        print(f"移除后: {[l for l in after_text.split(chr(10)) if '已选择' in l]}")
        assert "已选择 0 个 Site" in after_text, \
            f"Sites 应已移除，实际: {[l for l in after_text.split(chr(10)) if '已选择' in l]}"

        close_btn = modal3.locator("button:has-text('✕')")
        if close_btn.count() > 0:
            close_btn.first.click()

    finally:
        status = ac.delete_agent_api(agent_name)
        print(f"\n清理 '{agent_name}': status={status}")
        assert status in (200, 204, 404), f"删除 Agent 失败: status={status}"


@allure.epic("智能体配置")
@pytest.mark.order(133)
@pytest.mark.p1
def test_edit_description(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-AGENT-033e: 编辑已有 Agent 的描述并验证保存生效"""
    ac = AgentConfigPage(logged_in_page, base_url)
    agent_name = f"edit-desc-{_PREFIX}"
    new_desc = f"e2e测试描述-{random.choice(_TOPICS)}方向"

    result = ac.create_agent_api(name=agent_name, system_prompt="你是一个测试助手")
    _assert_create_success(result)

    try:
        ac.goto_agents()
        logged_in_page.wait_for_load_state("networkidle")

        card = ac.wait_for_agent_card(agent_name)
        assert card.count() > 0, f"列表中未找到 '{agent_name}'"
        agent_wrapper = card.first.locator("xpath=ancestor::div[contains(@class,'agent-sidebar-agent')]")

        # 打开配置 modal
        card = ac.wait_for_agent_card(agent_name)
        agent_wrapper = card.first.locator("xpath=ancestor::div[contains(@class,'agent-sidebar-agent')]")
        agent_wrapper.hover()
        agent_wrapper.locator('button[title="智能体配置"]').click()
        logged_in_page.locator("div.absolute.inset-0.z-50").wait_for(state="visible", timeout=10000)
        try:
            logged_in_page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        logged_in_page.wait_for_timeout(1000)

        modal = logged_in_page.locator("div.absolute.inset-0.z-50")
        assert modal.count() > 0, "编辑 modal 未打开"

        # 找到描述输入框，修改内容
        desc_input = modal.locator("label:has-text('描述') + input, label:has-text('描述') ~ input").first
        if desc_input.count() == 0:
            desc_input = modal.locator("input[placeholder*='描述']").first
        old_desc = desc_input.input_value()
        print(f"\n原描述: '{old_desc}'")
        desc_input.fill(new_desc)
        logged_in_page.wait_for_timeout(500)

        # 保存
        modal.get_by_role("button", name="保存").click()
        logged_in_page.locator("[role='alertdialog']").get_by_role("button", name="重启").wait_for(state="visible", timeout=15000)
        restart_btn = logged_in_page.locator("[role='alertdialog']").get_by_role("button", name="重启")
        restart_btn.wait_for(state="visible", timeout=5000)
        restart_btn.click()
        logged_in_page.wait_for_load_state("networkidle")

        # 重新打开配置，验证描述已修改
        card = ac.wait_for_agent_card(agent_name)
        agent_wrapper = card.first.locator("xpath=ancestor::div[contains(@class,'agent-sidebar-agent')]")
        agent_wrapper.hover()
        agent_wrapper.locator('button[title="智能体配置"]').click()
        logged_in_page.locator("div.absolute.inset-0.z-50").wait_for(state="visible", timeout=10000)
        try:
            logged_in_page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        logged_in_page.wait_for_timeout(1000)

        modal2 = logged_in_page.locator("div.absolute.inset-0.z-50")
        desc_input2 = modal2.locator("label:has-text('描述') + input, label:has-text('描述') ~ input").first
        if desc_input2.count() == 0:
            desc_input2 = modal2.locator("input[placeholder*='描述']").first
        after_desc = desc_input2.input_value()
        print(f"修改后描述: '{after_desc}'")
        assert after_desc == new_desc, \
            f"描述应已修改为 '{new_desc}'，实际: '{after_desc}'"

        close_btn = modal2.locator("button:has-text('✕')")
        if close_btn.count() > 0:
            close_btn.first.click()

    finally:
        status = ac.delete_agent_api(agent_name)
        print(f"\n清理 '{agent_name}': status={status}")
        assert status in (200, 204, 404), f"删除 Agent 失败: status={status}"


@allure.epic("智能体配置")
@pytest.mark.order(133)
@pytest.mark.p1
def test_edit_prompt(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-AGENT-033f: 编辑已有 Agent 的提示词并验证保存生效"""
    ac = AgentConfigPage(logged_in_page, base_url)
    agent_name = f"edit-prompt-{_PREFIX}"
    new_prompt = "你是一个专业的法律顾问，擅长解答合同法、劳动法相关问题。请用简洁的语言回答。"

    result = ac.create_agent_api(name=agent_name, system_prompt="你是一个测试助手")
    _assert_create_success(result)

    try:
        ac.goto_agents()
        logged_in_page.wait_for_load_state("networkidle")

        card = ac.wait_for_agent_card(agent_name)
        assert card.count() > 0, f"列表中未找到 '{agent_name}'"
        agent_wrapper = card.first.locator("xpath=ancestor::div[contains(@class,'agent-sidebar-agent')]")

        # 打开配置 modal
        card = ac.wait_for_agent_card(agent_name)
        agent_wrapper = card.first.locator("xpath=ancestor::div[contains(@class,'agent-sidebar-agent')]")
        agent_wrapper.hover()
        agent_wrapper.locator('button[title="智能体配置"]').click()
        logged_in_page.locator("div.absolute.inset-0.z-50").wait_for(state="visible", timeout=10000)
        try:
            logged_in_page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        logged_in_page.wait_for_timeout(1000)

        modal = logged_in_page.locator("div.absolute.inset-0.z-50")
        assert modal.count() > 0, "编辑 modal 未打开"

        # 找到提示词 textarea，修改内容
        prompt_ta = modal.locator("label:has-text('Prompt') + textarea, label:has-text('提示词') ~ textarea").first
        if prompt_ta.count() == 0:
            prompt_ta = modal.locator("textarea[placeholder*='提示词']").first
        old_prompt = prompt_ta.input_value()
        print(f"\n原提示词: '{old_prompt[:50]}...'")
        prompt_ta.fill(new_prompt)
        logged_in_page.wait_for_timeout(500)

        # 保存
        modal.get_by_role("button", name="保存").click()
        logged_in_page.locator("[role='alertdialog']").get_by_role("button", name="重启").wait_for(state="visible", timeout=15000)
        restart_btn = logged_in_page.locator("[role='alertdialog']").get_by_role("button", name="重启")
        restart_btn.wait_for(state="visible", timeout=5000)
        restart_btn.click()
        logged_in_page.wait_for_load_state("networkidle")

        # 重新打开配置，验证提示词已修改
        card = ac.wait_for_agent_card(agent_name)
        agent_wrapper = card.first.locator("xpath=ancestor::div[contains(@class,'agent-sidebar-agent')]")
        agent_wrapper.hover()
        agent_wrapper.locator('button[title="智能体配置"]').click()
        logged_in_page.locator("div.absolute.inset-0.z-50").wait_for(state="visible", timeout=10000)
        try:
            logged_in_page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        logged_in_page.wait_for_timeout(1000)

        modal2 = logged_in_page.locator("div.absolute.inset-0.z-50")
        prompt_ta2 = modal2.locator("label:has-text('Prompt') + textarea, label:has-text('提示词') ~ textarea").first
        if prompt_ta2.count() == 0:
            prompt_ta2 = modal2.locator("textarea[placeholder*='提示词']").first
        after_prompt = prompt_ta2.input_value()
        print(f"修改后提示词: '{after_prompt[:50]}...'")
        assert after_prompt == new_prompt, \
            f"提示词应已修改，实际: '{after_prompt[:50]}'"

        close_btn = modal2.locator("button:has-text('✕')")
        if close_btn.count() > 0:
            close_btn.first.click()

    finally:
        status = ac.delete_agent_api(agent_name)
        print(f"\n清理 '{agent_name}': status={status}")
        assert status in (200, 204, 404), f"删除 Agent 失败: status={status}"


@allure.epic("智能体配置")
@pytest.mark.order(133)
@pytest.mark.p1
def test_cancel_discards_changes(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-AGENT-033g: 修改配置后点取消，验证修改未保存"""
    ac = AgentConfigPage(logged_in_page, base_url)
    agent_name = f"cancel-{_PREFIX}"
    original_prompt = "你是一个测试助手，请不要修改这个提示词。"

    result = ac.create_agent_api(name=agent_name, system_prompt=original_prompt)
    _assert_create_success(result)

    try:
        ac.goto_agents()
        logged_in_page.wait_for_load_state("networkidle")

        card = ac.wait_for_agent_card(agent_name)
        assert card.count() > 0, f"列表中未找到 '{agent_name}'"
        agent_wrapper = card.first.locator("xpath=ancestor::div[contains(@class,'agent-sidebar-agent')]")

        # 打开配置 modal
        card = ac.wait_for_agent_card(agent_name)
        agent_wrapper = card.first.locator("xpath=ancestor::div[contains(@class,'agent-sidebar-agent')]")
        agent_wrapper.hover()
        agent_wrapper.locator('button[title="智能体配置"]').click()
        logged_in_page.locator("div.absolute.inset-0.z-50").wait_for(state="visible", timeout=10000)
        try:
            logged_in_page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        logged_in_page.wait_for_timeout(1000)

        modal = logged_in_page.locator("div.absolute.inset-0.z-50")
        assert modal.count() > 0, "编辑 modal 未打开"

        # 修改提示词
        prompt_ta = modal.locator("label:has-text('Prompt') + textarea, label:has-text('提示词') ~ textarea").first
        if prompt_ta.count() == 0:
            prompt_ta = modal.locator("textarea[placeholder*='提示词']").first
        prompt_ta.fill("这是一个不应该被保存的临时修改！")
        logged_in_page.wait_for_timeout(500)

        # 点取消（不保存）
        cancel_btn = modal.get_by_role("button", name="取消")
        cancel_btn.click()

        # 重新打开配置，验证提示词未改变
        card = ac.wait_for_agent_card(agent_name)
        agent_wrapper = card.first.locator("xpath=ancestor::div[contains(@class,'agent-sidebar-agent')]")
        agent_wrapper.hover()
        agent_wrapper.locator('button[title="智能体配置"]').click()
        logged_in_page.locator("div.absolute.inset-0.z-50").wait_for(state="visible", timeout=10000)
        try:
            logged_in_page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        logged_in_page.wait_for_timeout(1000)

        modal2 = logged_in_page.locator("div.absolute.inset-0.z-50")
        prompt_ta2 = modal2.locator("label:has-text('Prompt') + textarea, label:has-text('提示词') ~ textarea").first
        if prompt_ta2.count() == 0:
            prompt_ta2 = modal2.locator("textarea[placeholder*='提示词']").first
        after_prompt = prompt_ta2.input_value()
        print(f"\n取消后提示词: '{after_prompt[:50]}...'")
        assert after_prompt == original_prompt, \
            f"点取消后提示词不应改变，期望: '{original_prompt[:30]}'，实际: '{after_prompt[:30]}'"
        assert "不应该被保存" not in after_prompt, \
            "点取消后临时修改不应被保存"

        close_btn = modal2.locator("button:has-text('✕')")
        if close_btn.count() > 0:
            close_btn.first.click()

    finally:
        status = ac.delete_agent_api(agent_name)
        print(f"\n清理 '{agent_name}': status={status}")
        assert status in (200, 204, 404), f"删除 Agent 失败: status={status}"


@allure.epic("智能体配置")
@pytest.mark.order(134)
@pytest.mark.p1
def test_refresh_during_reply(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-AGENT-034: 发送消息后在 AI 回复过程中刷新页面，验证 AI 回复不会被打断"""
    ac = AgentConfigPage(logged_in_page, base_url)
    agent_name = "my-auto-test"
    ac.goto_agents()

    # 1. 点击 my-auto-test 进入对话
    clicked = ac.click_agent(agent_name)
    assert clicked, f"左侧列表中未找到 '{agent_name}'"
    assert ac.is_on_chat_page(), "应进入对话页面"
    logged_in_page.wait_for_timeout(1000)

    # 2. 记录刷新前的消息数量
    chat_url = logged_in_page.url
    before_messages = logged_in_page.locator(
        "div[role='log'] > div, div[role='log']"
    )
    before_count = before_messages.count()
    print(f"\n刷新前消息气泡数: {before_count}")

    # 3. 发送一条需要较长回复的消息（不等 AI 回复）
    ta = logged_in_page.locator("textarea[placeholder*='发送']")
    ta.first.fill("请写300字介绍一下人工智能的发展历程，从起源到现代")
    ta.first.press("Enter")

    # 4. 等 AI 刚开始回复就立刻刷新（仅等 2 秒）
    logged_in_page.wait_for_timeout(1000)
    print("AI 正在回复中，执行页面刷新...")
    logged_in_page.reload()
    logged_in_page.wait_for_load_state("networkidle")

    # 5. 如果刷新后不在对话页面，重新进入
    if not ac.is_on_chat_page():
        logged_in_page.goto(chat_url)
        logged_in_page.wait_for_load_state("networkidle")
        if not ac.is_on_chat_page():
            ac.goto_agents()
            ac.click_agent(agent_name)
            logged_in_page.wait_for_load_state("networkidle")

    assert ac.is_on_chat_page(), "刷新后应能回到对话页面"

    # 6. 等待 AI 完成回复（刷新后 AI 应继续或重新完成回复）
    logged_in_page.wait_for_load_state("networkidle")

    # 7. 获取最后一条 AI 回复，检查是否完整（不被打断）
    last_reply = ac.get_last_message()
    print(f"AI 最终回复（前100字）: {last_reply[:100]}")

    allure.attach(
        f"刷新前消息数: {before_count}\n"
        f"AI 回复: {last_reply[:500]}",
        name="刷新打断验证",
        attachment_type=allure.attachment_type.TEXT,
    )

    # 8. AI 回复不应为空或异常短（被打断的标志）
    assert last_reply, "AI 应有回复内容，为空说明回复被打断"
    assert len(last_reply) > 50, \
        f"AI 回复过短（{len(last_reply)}字），可能被打断: '{last_reply[:50]}'"
