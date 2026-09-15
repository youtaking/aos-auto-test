# tests/suites/test_model_gateway_usage.py
"""模型网关用量页（/ctrl/agent/model-gateway-usage/:providerId）E2E 测试 — 只读

对应 2026-09-15 E2E 覆盖率评审报告 §4.2（模型网关用量页 UI 零覆盖）。
真实 DOM 探查时间：2026-09-15（staging commitId da5eb543，与线上一致）：
  入口：模型库 /ctrl/agent/models → 左侧 aside.models-provider-index nav>button 逐个选中，
        详情头部 .models-provider-detail__header 出现「我的用量」按钮者即 gateway Provider
        （实测 7 个 Provider 中索引 4 为 gateway；不依赖名称，逐项探测）
  页面：h1「我的用量 · <provider 显示名>」、副标题「仅统计通过当前 Gateway Provider 发起的调用…」、
        「返回模型」按钮（回 /ctrl/agent/models）、「全局共享预算」说明块、
        「本周期预算使用」卡（$已用/$总额 或「暂未设置预算」、额度状态、剩余额度/下次重置/预算周期）、
        「Token 与请求」卡（总 Token / 请求数 / 输入 Token / 输出 Token）、
        「按 Agent 消耗」「按模型消耗」两张卡、「以下用量数据统计自最近 30 天。」
安全约定：本文件只读 —— 不修改预算、不重置额度、不点任何写操作。
"""
import re

import allure
import pytest

MODELS_PATH = "/ctrl/agent/models"
USAGE_URL_RE = re.compile(r"/ctrl/agent/model-gateway-usage/[^/]+$")
MODELS_URL_RE = re.compile(r"/ctrl/agent/models$")
USAGE_BTN = "我的用量"


def _open_gateway_usage(page, base_url) -> str:
    """从模型库选中 gateway Provider 并进入「我的用量」页，返回所选 Provider 名"""
    page.goto(f"{base_url}{MODELS_PATH}", wait_until="domcontentloaded")
    nav = page.locator("aside.models-provider-index nav button")
    nav.first.wait_for(state="visible", timeout=15000)
    detail = page.locator(".models-provider-detail__header")
    for i in range(nav.count()):
        nav.nth(i).click()
        detail.first.wait_for(state="visible", timeout=5000)
        usage_btn = detail.get_by_role("button", name=USAGE_BTN, exact=True)
        if usage_btn.count() == 1:
            provider_name = nav.nth(i).inner_text().strip().split("\n")[0]
            usage_btn.click()
            page.wait_for_url(USAGE_URL_RE, timeout=15000)
            return provider_name
    pytest.fail("模型库中未找到 gateway Provider（详情头部无「我的用量」按钮）")


def _info_value(page, label: str) -> str:
    """读取 Info 组件字段值（结构：<div><p>值</p><p>标签</p></div>）"""
    node = page.get_by_text(label, exact=True).first
    return node.locator("xpath=preceding-sibling::p[1]").inner_text().strip()


@allure.epic("模型网关")
@pytest.mark.order(70)
@pytest.mark.p0
def test_gateway_usage_001_page_loads(logged_in_page, base_url):
    """从模型库进入用量页：URL、标题、副标题、返回模型按钮均正确"""
    page = logged_in_page
    provider_name = _open_gateway_usage(page, base_url)

    h1 = page.locator("h1").first
    h1.wait_for(state="visible", timeout=15000)
    # 数据到达前标题为「我的用量」（gateway.usageTitleLoading），需等待 Provider 名渲染出来
    page.wait_for_function(
        "() => /^我的用量 · .+/.test((document.querySelector('h1')?.innerText || '').trim())",
        timeout=20000,
    )
    title = h1.inner_text().strip()
    assert re.fullmatch(r"我的用量 · .+", title), f"用量页标题格式异常: {title!r}"
    assert provider_name in title, f"标题未包含所选 Provider 名「{provider_name}」: {title!r}"

    subtitle = page.get_by_text(
        "仅统计通过当前 Gateway Provider 发起的调用，不包含普通直连 Provider。", exact=True
    )
    assert subtitle.count() == 1, f"用量页副标题匹配 {subtitle.count()} 个，预期唯一"

    back = page.get_by_role("button", name="返回模型", exact=True)
    assert back.count() == 1, f"「返回模型」按钮匹配 {back.count()} 个，预期唯一"
    back.click()
    page.wait_for_url(MODELS_URL_RE, timeout=15000)


@allure.epic("模型网关")
@pytest.mark.order(71)
@pytest.mark.p1
def test_gateway_usage_002_budget_and_token_stats(logged_in_page, base_url):
    """用量页数据区：预算卡与 Token 卡字段齐全、数值已渲染、无加载/错误态"""
    page = logged_in_page
    _open_gateway_usage(page, base_url)
    page.get_by_text("以下用量数据统计自最近 30 天。", exact=True).first.wait_for(
        state="visible", timeout=15000
    )

    assert page.get_by_text("全局共享预算", exact=True).count() == 1, "缺少「全局共享预算」说明块"
    assert page.get_by_text(
        "预算、已消耗和剩余额度合并该用户在所有组织中的调用。", exact=True
    ).count() == 1, "缺少共享预算说明文案"

    for label in ("本周期预算使用", "剩余额度", "下次重置", "预算周期"):
        assert page.get_by_text(label, exact=True).count() == 1, f"预算卡缺少字段「{label}」"

    for label in ("Token 与请求", "总 Token", "请求数", "输入 Token", "输出 Token"):
        assert page.get_by_text(label, exact=True).count() == 1, f"Token 卡缺少字段「{label}」"

    total_tokens = _info_value(page, "总 Token")
    assert re.fullmatch(r"\d[\d.,]*[KMB]?", total_tokens), f"总 Token 数值格式异常: {total_tokens!r}"
    requests = _info_value(page, "请求数")
    assert re.fullmatch(r"\d[\d,]*", requests), f"请求数数值格式异常: {requests!r}"

    assert page.get_by_text("按 Agent 消耗", exact=True).count() == 1, "缺少「按 Agent 消耗」卡"
    assert page.get_by_text("按模型消耗", exact=True).count() == 1, "缺少「按模型消耗」卡"

    assert page.get_by_text("正在加载用量…", exact=True).count() == 0, "用量页仍处于加载中"
    assert page.get_by_text(
        "加载模型网关用量失败，请稍后重试。", exact=True
    ).count() == 0, "用量页数据加载失败"

