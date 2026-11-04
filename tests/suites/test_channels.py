# tests/suites/test_channels.py
"""消息通道（Channels）模块 E2E 测试

新版 UI（2026-11 部署）：LangBot 通道机器人 + 路由列表。
页面路径 /ctrl/agent/channels，标题「消息通道」。
本套用例只做读取与弹窗取消操作，不修改已有通道数据。
"""
import pytest
import allure
from tests.pages.channels_page import ChannelsPage


def _first_bot_name(ch: ChannelsPage) -> str:
    row = ch.bot_rows().first
    row.wait_for(state="visible", timeout=10000)
    name = row.inner_text().strip().splitlines()[0].strip()
    assert name, "通道行首行未展示机器人名称"
    return name


@allure.epic("消息通道")
@pytest.mark.order(500)
@pytest.mark.p0
def test_channels_page_loads(logged_in_page, base_url):
    """TC-CH-001: 消息通道页面正常加载"""
    ch = ChannelsPage(logged_in_page, base_url)
    ch.goto()
    assert ch.is_loaded(), "消息通道页面未加载（标题不可见或 URL 不对）"

    assert logged_in_page.get_by_role("heading", name="消息通道").is_visible(), \
        "页面标题「消息通道」不可见"
    create_btn = logged_in_page.locator("main").get_by_role(
        "button", name="创建消息连接", exact=True
    )
    assert create_btn.count() == 1, \
        f"「创建消息连接」按钮应唯一，实际 {create_btn.count()} 个"
    assert create_btn.is_visible(), "「创建消息连接」按钮不可见"


@allure.epic("消息通道")
@pytest.mark.order(501)
@pytest.mark.p0
def test_channels_bot_tree_actions(logged_in_page, base_url):
    """TC-CH-002: 通道机器人列表 — 每个机器人头部提供完整操作入口"""
    ch = ChannelsPage(logged_in_page, base_url)
    ch.goto()
    assert ch.is_loaded(), "消息通道页面未加载"

    bot_count = ch.get_binding_count()
    if bot_count == 0:
        pytest.skip("当前环境没有任何通道机器人（前置数据缺失），无法校验操作入口")

    bot_name = _first_bot_name(ch)
    header = ch.bot_header(bot_name)
    for action in ["对接智能体", "测试发送", "编辑", "删除"]:
        btn = header.get_by_role("button", name=action, exact=True)
        assert btn.count() == 1, \
            f"通道 {bot_name!r} 头部「{action}」按钮应唯一，实际 {btn.count()} 个"


@allure.epic("消息通道")
@pytest.mark.order(502)
@pytest.mark.p0
def test_channels_create_dialog(logged_in_page, base_url):
    """TC-CH-003: 创建通道弹窗 — 名称输入框与适配器选项齐全，取消可关闭"""
    ch = ChannelsPage(logged_in_page, base_url)
    ch.goto()
    assert ch.is_loaded(), "消息通道页面未加载"

    ch.click_create_button()
    assert ch.is_dialog_open(), "点击「创建消息连接」后弹窗未打开"

    dialog = ch.dialog_locator()
    dialog_text = dialog.inner_text()
    assert "创建通道" in dialog_text, "弹窗标题不是「创建通道」"
    name_input = dialog.locator("input#channel-bot-name")
    assert name_input.count() == 1, "弹窗中未找到通道名称输入框"
    assert name_input.get_attribute("placeholder") == "例如：客服机器人", \
        "名称输入框 placeholder 与预期不一致"

    adapter_btns = [
        btn for btn in ["Telegram", "飞书 / Lark", "Slack", "Discord",
                        "企业微信", "钉钉", "QQ 官方 API", "OneBot v11"]
        if dialog.get_by_role("button", name=btn, exact=True).count() == 1
    ]
    assert len(adapter_btns) == 8, \
        f"适配器选项缺失，实际只匹配到 {adapter_btns}"

    ch.click_cancel()
    assert not ch.is_dialog_open(), "点击取消后弹窗未关闭"


@allure.epic("消息通道")
@pytest.mark.order(503)
@pytest.mark.p1
def test_channels_create_validation(logged_in_page, base_url):
    """TC-CH-004: 创建通道校验 — 名称留空提交显示「请填写名称」"""
    ch = ChannelsPage(logged_in_page, base_url)
    ch.goto()
    assert ch.is_loaded(), "消息通道页面未加载"

    ch.click_create_button()
    assert ch.is_dialog_open(), "创建通道弹窗未打开"

    ch.click_save()
    logged_in_page.wait_for_timeout(800)

    assert ch.is_dialog_open(), "名称为空时弹窗被关闭（应保留并提示）"
    dialog = ch.dialog_locator()
    error = dialog.get_by_text("请填写名称", exact=True)
    assert error.count() == 1, \
        f"名称为空未显示「请填写名称」错误提示，实际文本: {dialog.inner_text()[:150]}"
    assert error.first.is_visible(), "「请填写名称」错误提示不可见"

    ch.click_cancel()
    assert not ch.is_dialog_open(), "点击取消后弹窗未关闭"


@allure.epic("消息通道")
@pytest.mark.order(504)
@pytest.mark.p0
def test_channels_route_toggle(logged_in_page, base_url):
    """TC-CH-005: 路由折叠 — 收起后路由区消失，展开后恢复"""
    ch = ChannelsPage(logged_in_page, base_url)
    ch.goto()
    assert ch.is_loaded(), "消息通道页面未加载"

    bot_name = _first_bot_name(ch)
    assert ch.has_route_block(bot_name), \
        f"通道 {bot_name!r} 未渲染路由区，无法验证折叠"

    aria_before, aria_after = ch.toggle_routes(bot_name)
    assert "收起" in (aria_before or ""), \
        f"折叠按钮初始 aria-label 不是「收起…」: {aria_before}"
    assert "展开" in (aria_after or ""), \
        f"收起后 aria-label 未变为「展开…」: {aria_after}"
    assert not ch.has_route_block(bot_name), "收起后路由区仍存在"

    _, aria_restored = ch.toggle_routes(bot_name)
    assert "收起" in (aria_restored or ""), \
        f"再次点击后 aria-label 未恢复为「收起…」: {aria_restored}"
    assert ch.has_route_block(bot_name), "展开后路由区未恢复"


@allure.epic("消息通道")
@pytest.mark.order(505)
@pytest.mark.p1
def test_channels_custom_adapter_fields(logged_in_page, base_url):
    """TC-CH-006: 其他（插件适配器）— 显示适配器 ID 与 JSON 配置字段"""
    ch = ChannelsPage(logged_in_page, base_url)
    ch.goto()
    assert ch.is_loaded(), "消息通道页面未加载"

    ch.click_create_button()
    assert ch.is_dialog_open(), "创建通道弹窗未打开"

    ch.select_adapter("其他（插件适配器）")
    assert ch.has_field("channel-bot-custom-adapter"), \
        "选择插件适配器后未出现「适配器 ID」输入框"
    assert ch.has_field("channel-bot-config"), \
        "选择插件适配器后未出现「适配器配置（JSON）」输入框"

    ch.click_cancel()
    assert not ch.is_dialog_open(), "点击取消后弹窗未关闭"


@allure.epic("消息通道")
@pytest.mark.order(506)
@pytest.mark.p2
def test_channels_refresh(logged_in_page, base_url):
    """TC-CH-007: 刷新按钮 — 重新拉取列表且数量不变"""
    ch = ChannelsPage(logged_in_page, base_url)
    ch.goto()
    assert ch.is_loaded(), "消息通道页面未加载"

    count_before = ch.get_binding_count()
    if count_before == 0:
        pytest.skip("当前环境没有任何通道机器人（前置数据缺失），无法验证刷新后数量不变")

    refresh_btn = logged_in_page.locator("main").get_by_role(
        "button", name="刷新", exact=True
    )
    assert refresh_btn.count() == 1, \
        f"「刷新」按钮应唯一，实际 {refresh_btn.count()} 个"
    refresh_btn.click()
    logged_in_page.wait_for_load_state("networkidle")
    logged_in_page.wait_for_timeout(1000)

    assert ch.bot_rows().first.is_visible(), "刷新后通道列表未渲染"
    assert ch.get_binding_count() == count_before, \
        f"刷新后通道数量变化：{count_before} → {ch.get_binding_count()}"
