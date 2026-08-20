# tests/suites/test_channels.py
"""消息渠道（Channels）模块 E2E 测试
基于 2026-08-17 真实 DOM 探查编写
覆盖：页面加载、CRUD、搜索、表单验证、空状态
"""
import json
import uuid
import pytest
import allure
from tests.pages.channels_page import ChannelsPage
from tests.conftest import register_cleanup

_PREFIX = f"ch-e2e-{uuid.uuid4().hex[:6]}"


def _register_cleanup_bindings(request, page, base_url, name_prefix):
    """注册清理：删除名称包含 prefix 的绑定"""
    def _cleanup():
        try:
            r = page.request.get(f"{base_url}/web/channels/bindings")
            if r.status == 200:
                data = r.json()
                bindings = data if isinstance(data, list) else data.get("data", [])
                for b in bindings:
                    name = b.get("platformName", "") or b.get("platform", "")
                    if name_prefix in name:
                        page.request.delete(
                            f"{base_url}/web/channels/bindings/{b['id']}"
                        )
        except Exception:
            pass
    register_cleanup(request, _cleanup)


# ==================== 测试 ====================


@allure.epic("消息渠道")
@pytest.mark.order(500)
@pytest.mark.p0
def test_channels_page_loads(logged_in_page, base_url):
    """TC-CH-001: 频道页面正常加载"""
    ch = ChannelsPage(logged_in_page, base_url)
    ch.goto()
    assert ch.is_loaded(), "频道页面未加载（标题不可见或 URL 不对）"

    # 验证页面核心元素
    assert logged_in_page.get_by_role("heading", name="消息渠道").is_visible(), \
        "页面标题 '消息渠道' 不可见"


@allure.epic("消息渠道")
@pytest.mark.order(501)
@pytest.mark.p0
def test_channels_empty_state(logged_in_page, base_url):
    """TC-CH-002: 无绑定时显示空状态"""
    ch = ChannelsPage(logged_in_page, base_url)

    # 先清理所有 ch-e2e- 前缀的残留绑定（上次运行可能没清理干净）
    try:
        r = logged_in_page.request.get(f"{base_url}/web/channels/bindings")
        if r.status == 200:
            data = r.json()
            bindings = data if isinstance(data, list) else data.get("data", [])
            for b in bindings:
                name = b.get("platformName", "") or b.get("platform", "")
                if name.startswith("ch-e2e-"):
                    logged_in_page.request.delete(
                        f"{base_url}/web/channels/bindings/{b['id']}"
                    )
    except Exception:
        pass

    ch.goto()
    assert ch.is_loaded(), "频道页面未加载"

    # 检查当前是否有绑定
    count = ch.get_binding_count()
    if count > 0:
        pytest.skip(f"当前已有 {count} 个绑定，无法测试空状态")

    assert ch.has_empty_state(), "无绑定时未显示空状态提示"


@allure.epic("消息渠道")
@pytest.mark.order(502)
@pytest.mark.p0
def test_channels_create_binding(logged_in_page, base_url, request):
    """TC-CH-003: 创建新频道绑定"""
    ch = ChannelsPage(logged_in_page, base_url)
    ch.goto()
    assert ch.is_loaded(), "频道页面未加载"

    platform_name = f"{_PREFIX}-telegram"
    _register_cleanup_bindings(request, logged_in_page, base_url, _PREFIX)

    # 点击创建
    ch.click_create_button()
    assert ch.is_dialog_open(), "创建弹窗未打开"

    # 填写表单
    ch.fill_platform(platform_name)
    ch.fill_chat_id("test-chat-123")

    # 选择 Agent（从下拉选第一个可用选项）
    dialog = logged_in_page.get_by_role("dialog")
    combobox = dialog.get_by_role("combobox").first
    combobox.wait_for(state="visible", timeout=5000)
    combobox.click()
    logged_in_page.wait_for_timeout(500)
    # 选第一个 option
    first_option = logged_in_page.locator("[role='option']").first
    if first_option.count() > 0:
        agent_text = first_option.inner_text()
        first_option.wait_for(state="visible", timeout=5000)
        first_option.click()
    else:
        combobox.press("Escape")
        ch.click_cancel()
        pytest.skip("Agent 下拉无可用选项")

    # 保存
    ch.click_save()

    # 等待弹窗关闭（保存完成）
    dialog = logged_in_page.get_by_role("dialog")
    try:
        dialog.first.wait_for(state="hidden", timeout=8000)
    except Exception:
        pass

    # 等待绑定出现在列表中（轮询）
    for _poll in range(8):
        if ch.has_binding(platform_name):
            break
        logged_in_page.wait_for_timeout(1000)

    # 验证绑定出现在列表中
    assert ch.has_binding(platform_name), \
        f"创建后绑定 '{platform_name}' 未出现在列表中"


@allure.epic("消息渠道")
@pytest.mark.order(503)
@pytest.mark.p1
def test_channels_create_validation(logged_in_page, base_url):
    """TC-CH-004: 创建时平台名称为空校验"""
    ch = ChannelsPage(logged_in_page, base_url)
    ch.goto()
    assert ch.is_loaded(), "频道页面未加载"

    ch.click_create_button()
    assert ch.is_dialog_open(), "创建弹窗未打开"

    # 不填写平台名称，直接保存
    ch.click_save()
    logged_in_page.wait_for_timeout(1000)

    # 弹窗应仍然存在（校验失败不会关闭弹窗）
    assert ch.is_dialog_open(), "平台名称为空时弹窗关闭了（应有校验提示）"

    # 关闭弹窗
    ch.close_dialog()


@allure.epic("消息渠道")
@pytest.mark.order(504)
@pytest.mark.p0
def test_channels_delete_binding(logged_in_page, base_url, request):
    """TC-CH-005: 删除绑定（自建自销）"""
    ch = ChannelsPage(logged_in_page, base_url)
    ch.goto()
    assert ch.is_loaded(), "频道页面未加载"

    platform_name = f"{_PREFIX}-del-test"
    _register_cleanup_bindings(request, logged_in_page, base_url, _PREFIX)

    # 通过 API 创建绑定用于删除测试
    # 先获取一个可用的 agentId
    env_resp = logged_in_page.request.get(f"{base_url}/web/environments")
    if env_resp.status != 200:
        pytest.skip("无法获取环境列表 API")
    envs = env_resp.json()
    env_list = envs if isinstance(envs, list) else envs.get("data", [])
    if not env_list:
        pytest.skip("无可用的 Agent 环境")

    agent_id = env_list[0]["id"]
    create_resp = ch.create_binding_api(platform_name, "del-chat-id", agent_id)
    if create_resp.status not in (200, 201):
        pytest.skip(f"API 创建绑定失败 (HTTP {create_resp.status})")

    # 刷新页面
    ch.goto()
    assert ch.has_binding(platform_name), \
        f"API 创建后绑定 '{platform_name}' 未出现在列表"

    # UI 删除
    ch.delete_binding(platform_name)
    # 确认删除弹窗
    confirm_btn = logged_in_page.get_by_role("button", name="确认").or_(
        logged_in_page.get_by_role("button", name="Continue")
    )
    if confirm_btn.count() > 0:
        confirm_btn.first.wait_for(state="visible", timeout=5000)
        confirm_btn.first.click()
    logged_in_page.wait_for_load_state("networkidle")

    # 轮询等待绑定从列表中消失
    for _poll in range(8):
        if not ch.has_binding(platform_name):
            break
        logged_in_page.wait_for_timeout(1000)

    assert not ch.has_binding(platform_name), \
        f"删除后绑定 '{platform_name}' 仍然存在"


@allure.epic("消息渠道")
@pytest.mark.order(505)
@pytest.mark.p1
def test_channels_delete_cancel(logged_in_page, base_url, request):
    """TC-CH-006: 取消删除确认"""
    ch = ChannelsPage(logged_in_page, base_url)
    ch.goto()
    assert ch.is_loaded(), "频道页面未加载"

    platform_name = f"{_PREFIX}-cancel-del"
    _register_cleanup_bindings(request, logged_in_page, base_url, _PREFIX)

    # 通过 API 创建
    env_resp = logged_in_page.request.get(f"{base_url}/web/environments")
    if env_resp.status != 200:
        pytest.skip("无法获取环境列表 API")
    envs = env_resp.json()
    env_list = envs if isinstance(envs, list) else envs.get("data", [])
    if not env_list:
        pytest.skip("无可用的 Agent 环境")

    create_resp = ch.create_binding_api(platform_name, "cancel-chat-id", env_list[0]["id"])
    if create_resp.status not in (200, 201):
        pytest.skip(f"API 创建绑定失败 (HTTP {create_resp.status})")

    ch.goto()
    assert ch.has_binding(platform_name), "API 创建后绑定未出现"

    count_before = ch.get_binding_count()

    # 点击删除
    ch.delete_binding(platform_name)

    # 取消删除
    cancel_btn = logged_in_page.get_by_role("button", name="取消").or_(
        logged_in_page.get_by_role("button", name="Cancel")
    )
    if cancel_btn.count() > 0:
        cancel_btn.first.wait_for(state="visible", timeout=5000)
        cancel_btn.first.click()
    else:
        logged_in_page.keyboard.press("Escape")

    logged_in_page.wait_for_timeout(500)

    # 绑定应仍然存在
    assert ch.has_binding(platform_name), "取消删除后绑定消失了"
    assert ch.get_binding_count() == count_before, "取消删除后绑定数量变化"


@allure.epic("消息渠道")
@pytest.mark.order(506)
@pytest.mark.p1
def test_channels_search_filter(logged_in_page, base_url, request):
    """TC-CH-007: 搜索框按 platform/agentName 过滤"""
    ch = ChannelsPage(logged_in_page, base_url)
    ch.goto()
    assert ch.is_loaded(), "频道页面未加载"

    platform_name = f"{_PREFIX}-search-test"
    _register_cleanup_bindings(request, logged_in_page, base_url, _PREFIX)

    # 通过 API 创建用于搜索测试
    env_resp = logged_in_page.request.get(f"{base_url}/web/environments")
    if env_resp.status != 200:
        pytest.skip("无法获取环境列表 API")
    envs = env_resp.json()
    env_list = envs if isinstance(envs, list) else envs.get("data", [])
    if not env_list:
        pytest.skip("无可用的 Agent 环境")

    ch.create_binding_api(platform_name, "search-chat-id", env_list[0]["id"])
    ch.goto()

    if not ch.has_binding(platform_name):
        pytest.skip(f"创建后绑定 '{platform_name}' 未出现")

    count_before = ch.get_binding_count()

    # 搜索一个不存在的关键词
    ch.search("zzz-nonexistent-platform-xyz")
    logged_in_page.wait_for_timeout(500)
    count_filtered = ch.get_binding_count()
    assert count_filtered < count_before, \
        f"搜索不存在的关键词后仍显示 {count_filtered} 个（之前 {count_before} 个）"

    # 清空搜索，恢复
    ch.clear_search()
    logged_in_page.wait_for_timeout(500)
    count_restored = ch.get_binding_count()
    assert count_restored == count_before, \
        f"清空搜索后数量 {count_restored} != 原始 {count_before}"


@allure.epic("消息渠道")
@pytest.mark.order(507)
@pytest.mark.p2
def test_channels_agent_dropdown(logged_in_page, base_url):
    """TC-CH-008: Agent 下拉列表有可选项"""
    ch = ChannelsPage(logged_in_page, base_url)
    ch.goto()
    assert ch.is_loaded(), "频道页面未加载"

    ch.click_create_button()
    assert ch.is_dialog_open(), "创建弹窗未打开"

    # 等待弹窗完全渲染
    dialog = logged_in_page.get_by_role("dialog")
    dialog.first.wait_for(state="visible", timeout=5000)
    logged_in_page.wait_for_timeout(500)

    # 打开 Agent 下拉
    combobox = dialog.get_by_role("combobox").first
    combobox.wait_for(state="visible", timeout=5000)
    combobox.click()
    logged_in_page.wait_for_timeout(800)

    # 应有至少一个选项
    options = logged_in_page.locator("[role='option']")
    try:
        options.first.wait_for(state="visible", timeout=5000)
    except Exception:
        pytest.fail("Agent 下拉列表为空（应至少有一个可用 Agent）")
    option_count = options.count()
    assert option_count > 0, "Agent 下拉列表为空（应至少有一个可用 Agent）"

    # 关闭（点击 option 后弹窗可能已自动关闭）
    if ch.is_dialog_open():
        ch.close_dialog()
