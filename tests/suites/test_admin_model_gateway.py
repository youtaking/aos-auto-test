# tests/suites/test_admin_model_gateway.py
"""模型网关管理页（/ctrl/admin/model-gateway）E2E 测试 — 只读

对应 2026-09-15 E2E 覆盖率评审报告 §4.1（P0：模型网关页 UI 零覆盖）。
真实 DOM 探查时间：2026-09-15，实测结构：
  h1「模型网关」+ 副标题 + 5 个 Tab（概览 / 模型 / 配额管理 / 消耗统计 / Key 管理，
  Tab 为普通 button，在 main 内名称唯一）；
  概览：统计卡（最近 7 天总消耗 / 活跃用户 / 已配置模型）+ 消耗趋势图 + Gateway Provider 卡片；
  模型：检查状态 / 同步模型 + 状态筛选 + 搜索模型 + 表格（模型 / 来源 / 同步状态）；
  配额管理：组织/用户/状态筛选 + 查询 / 重置额度 / 批量设置 + 用户预算表格；
  消耗统计：日期区间 + 组织/用户/Agent/模型筛选 + 查询；
  Key 管理：刷新 / 删除所选 Key + Key ID / 主体 / 当前可用性 / 创建时间。

安全约定：本文件不点击任何写操作（检查状态 / 同步模型 / 重置额度 / 批量设置 / 删除所选 Key）。
"""
import re

import allure
import pytest

from tests.pages.admin_page import AdminPage

GATEWAY_PATH = "/ctrl/admin/model-gateway"
TABS = ["概览", "模型", "配额管理", "消耗统计", "Key 管理"]


@pytest.fixture
def master_key(test_config):
    """获取 Master Key"""
    key = test_config.get("fenixagent", {}).get("system_api_key", "")
    if not key:
        pytest.skip("test_data.yaml 中未配置 system_api_key")
    return key


def _open_gateway(page, base_url, master_key):
    """打开模型网关页并确保通过 Master Key 门禁（门禁为该页自带，与 /ctrl/admin 共用 admin key）

    实测：门禁未通过时页面只有「需要 Master Key」表单，5 个 Tab 均不存在；
    门禁可通过登录后首次访问 /ctrl/admin 完成，也可直接在网关页完成，故两轮尝试。
    """
    admin = AdminPage(page, base_url)
    for _attempt in range(2):
        page.goto(f"{base_url}{GATEWAY_PATH}", wait_until="domcontentloaded")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(1200)
        gate = page.locator("text=需要 Master Key")
        if gate.count() > 0 and gate.first.is_visible():
            admin.enter_master_key(master_key)
            admin.click_enter()
        try:
            page.get_by_role("button", name="Key 管理", exact=True).first.wait_for(
                state="visible", timeout=15000
            )
            return page
        except Exception:
            continue
    pytest.fail("模型网关页未渲染（Master Key 门禁未通过或 5 个 Tab 未加载）")


@pytest.fixture
def gateway_page(logged_in_page, base_url, master_key):
    """通过 Master Key 门禁后打开模型网关页（已确认仪表盘渲染完成）"""
    return _open_gateway(logged_in_page, base_url, master_key)


def _gate_main(page):
    return page.locator("main")


def _click_tab(page, name: str):
    """点击网关 Tab 并断言该 Tab 在 main 内唯一（页面级同名按钮存在风险）"""
    main = _gate_main(page)
    tab = main.get_by_role("button", name=name, exact=True)
    assert tab.count() == 1, f"网关 Tab「{name}」在 main 内应唯一，实际 {tab.count()} 个"
    tab.first.wait_for(state="visible", timeout=8000)
    tab.first.click()
    page.wait_for_timeout(1500)


@allure.epic("Admin")
@allure.feature("模型网关")
@pytest.mark.order(96)
@pytest.mark.p0
def test_gateway_001_page_loads(gateway_page):
    """TC-GW-001: 模型网关页面加载 — 标题、副标题与 5 个 Tab"""
    page = gateway_page
    main = _gate_main(page)

    h1 = main.locator("h1").first
    assert h1.inner_text().strip() == "模型网关", \
        f"页面标题不是「模型网关」: {h1.inner_text()!r}"

    subtitle = main.locator("header p").first.inner_text().strip()
    assert subtitle == "统一发布网关模型、管理用户预算并查看全系统消耗。", \
        f"副标题与源码文案不一致: {subtitle!r}"

    # 5 个 Tab 全部存在且名称唯一（实测：普通 button，无 role=tab）
    for name in TABS:
        tab = main.get_by_role("button", name=name, exact=True)
        assert tab.count() == 1, f"缺少网关 Tab「{name}」（实际 {tab.count()} 个）"

    # 默认停在概览 Tab：统计卡可见
    assert main.get_by_text("最近 7 天总消耗").count() > 0, \
        "默认 Tab 未渲染概览统计（最近 7 天总消耗）"


@allure.epic("Admin")
@allure.feature("模型网关")
@pytest.mark.order(97)
@pytest.mark.p0
def test_gateway_002_overview_stats(gateway_page):
    """TC-GW-002: 概览 Tab — 统计卡与数值格式、消耗趋势"""
    page = gateway_page
    main = _gate_main(page)
    _click_tab(page, "概览")

    assert "US$" in main.inner_text(), \
        f"概览未渲染消耗金额（US$）: {main.inner_text()[:200]!r}"

    # 金额格式：US$1,234.56 形态
    amount_text = main.get_by_text(re.compile(r"US\$[\d,]+(\.\d+)?")).count()
    assert amount_text > 0, "概览未渲染符合格式的消耗金额（US$xxx.xx）"

    # 三项统计标签齐全（实测：最近 7 天总消耗 / 活跃用户 / 已配置模型）
    for label in ["最近 7 天总消耗", "活跃用户", "已配置模型"]:
        assert main.get_by_text(label).count() > 0, f"概览缺少统计项「{label}」"

    body = main.inner_text()
    assert re.search(r"输入\s*[\d.]+[万亿]?\s*·\s*输出\s*[\d.]+[万亿]?", body), \
        f"概览缺少输入/输出 Token 统计格式: {body[:200]!r}"
    assert re.search(r"\d+\s*近\s*7\s*天有调用", body), \
        f"概览缺少活跃用户说明（N 近 7 天有调用）: {body[:200]!r}"

    # 消耗趋势图：7 天日期轴标签
    assert main.get_by_text("消耗趋势").count() > 0, "概览缺少消耗趋势图标题"
    assert len(re.findall(r"\d{2}-\d{2}", body)) >= 7, \
        "消耗趋势图缺少 7 天日期轴标签"


@allure.epic("Admin")
@allure.feature("模型网关")
@pytest.mark.order(98)
@pytest.mark.p0
def test_gateway_003_provider_card(gateway_page):
    """TC-GW-003: 概览 Tab — Gateway Provider 卡片（连接状态/所有者/类型/地址）"""
    page = gateway_page
    main = _gate_main(page)
    _click_tab(page, "概览")

    body = main.inner_text()
    assert "Gateway Provider" in body, "概览缺少 Gateway Provider 卡片"
    assert ("连接正常" in body) or ("连接异常" in body), \
        f"Gateway Provider 卡片未显示连接状态: {body[:200]!r}"

    for label in ["所有者", "网关类型", "连接地址"]:
        assert label in body, f"Gateway Provider 卡片缺少「{label}」字段"

    # 连接地址为 URL 格式
    assert re.search(r"https?://[\w.:\-/]+", body), \
        f"Gateway Provider 未渲染连接地址 URL: {body[:200]!r}"

    # 只读校验：两个操作按钮存在（不点击，避免触发同步/状态检查写操作）
    for btn_name in ["管理模型配置", "刷新状态"]:
        btn = main.get_by_role("button", name=btn_name, exact=True)
        assert btn.count() == 1, f"Gateway Provider 卡片缺少「{btn_name}」按钮（{btn.count()} 个）"


@allure.epic("Admin")
@allure.feature("模型网关")
@pytest.mark.order(99)
@pytest.mark.p1
def test_gateway_004_models_tab(gateway_page):
    """TC-GW-004: 模型 Tab — 状态筛选、搜索、模型目录表格与同步状态"""
    page = gateway_page
    main = _gate_main(page)
    _click_tab(page, "模型")

    body = main.inner_text()
    assert "模型配置在 LiteLLM 管理后台完成" in body, \
        f"模型 Tab 缺少配置说明文案: {body[:200]!r}"

    # 操作按钮（只断言存在，不点击：检查状态/同步模型会触发写操作）
    for btn_name in ["检查状态", "同步模型"]:
        assert main.get_by_role("button", name=btn_name, exact=True).count() == 1, \
            f"模型 Tab 缺少「{btn_name}」按钮"

    # 状态筛选（实测为分段控件，非 role=button，故按文本断言）+ 搜索
    for f in ["全部状态", "待同步变更", "已同步"]:
        assert main.get_by_text(f, exact=True).count() > 0, \
            f"模型 Tab 缺少状态筛选项「{f}」"
    assert main.locator("input[placeholder='搜索模型']").count() == 1, \
        "模型 Tab 缺少「搜索模型」输入框"

    # 表格结构与同步状态取值
    table = main.locator("table").first
    assert table.count() == 1, "模型 Tab 未渲染模型目录表格"
    header = table.locator("tr").first.inner_text()
    for col in ["模型", "来源", "同步状态"]:
        assert col in header, f"模型目录表格缺少列「{col}」，表头: {header!r}"

    rows = table.locator("tbody tr")
    if rows.count() > 0:
        statuses = []
        for i in range(rows.count()):
            cells = rows.nth(i).locator("td")
            assert cells.count() >= 3, f"模型表格第 {i + 1} 行缺少列: {rows.nth(i).inner_text()!r}"
            statuses.append(cells.nth(2).inner_text().strip())
        allowed = {"已同步", "待同步", "同步失败", "未知"}
        assert all(s in allowed for s in statuses), \
            f"模型表格同步状态取值异常: {statuses}"


@allure.epic("Admin")
@allure.feature("模型网关")
@pytest.mark.order(100)
@pytest.mark.p1
def test_gateway_005_budgets_tab(gateway_page):
    """TC-GW-005: 配额管理 Tab — 全局预算说明、筛选、表头与分页"""
    page = gateway_page
    main = _gate_main(page)
    _click_tab(page, "配额管理")

    body = main.inner_text()
    assert "全局用户预算" in body, f"配额管理 Tab 缺少「全局用户预算」说明: {body[:200]!r}"

    for f in ["全部组织", "全部用户", "查询"]:
        assert main.get_by_role("button", name=f, exact=True).count() == 1, \
            f"配额管理缺少「{f}」控件"
    # 预算状态筛选为分段控件（非 role=button）
    assert main.get_by_text("全部状态", exact=True).count() > 0, \
        "配额管理缺少状态筛选项「全部状态」"

    # 写操作按钮只断言存在，不点击
    for btn_name in ["重置额度", "批量设置"]:
        assert main.get_by_role("button", name=btn_name, exact=True).count() == 1, \
            f"配额管理缺少「{btn_name}」按钮"

    table = main.locator("table").first
    assert table.count() == 1, "配额管理未渲染用户预算表格"
    header = table.locator("tr").first.inner_text()
    for col in ["用户", "预算策略", "已消耗", "剩余额度", "使用进度", "重置时间"]:
        assert col in header, f"用户预算表格缺少列「{col}」，表头: {header!r}"

    # 空态或分页统计至少渲染其一（实测空数据时显示「暂无匹配用户 / 共 0 位用户」）
    assert re.search(r"共\s*\d+\s*位用户", body), \
        f"配额管理未渲染用户总数（共 N 位用户）: {body[:200]!r}"
    assert re.search(r"\d+\s*位/页", body), \
        f"配额管理未渲染分页控件（N 位/页）: {body[:200]!r}"


@allure.epic("Admin")
@allure.feature("模型网关")
@pytest.mark.order(101)
@pytest.mark.p1
def test_gateway_006_usage_and_keys_tabs(gateway_page):
    """TC-GW-006: 消耗统计 + Key 管理 Tab — 查询条件、查询生效、Key 表列与取值"""
    page = gateway_page
    main = _gate_main(page)

    # === 消耗统计 ===
    _click_tab(page, "消耗统计")
    for f in ["最近 30 天", "最近 7 天", "自定义日期"]:
        assert main.get_by_text(f, exact=True).count() > 0, \
            f"消耗统计缺少日期区间选项「{f}」"
    for f in ["全部组织", "全部用户", "全部Agent"]:
        assert main.get_by_role("button", name=f, exact=True).count() == 1, \
            f"消耗统计缺少查询条件「{f}」"
    assert main.get_by_role("button", name="查询", exact=True).count() == 1, \
        "消耗统计缺少「查询」按钮"

    hint = main.get_by_text("点击“查询”后读取统计数据。")
    assert hint.count() > 0, "消耗统计未渲染初始提示文案"
    # 查询为只读操作：点击后提示应消失（说明查询确实执行）
    main.get_by_role("button", name="查询", exact=True).click()
    try:
        hint.first.wait_for(state="hidden", timeout=20000)
    except Exception:
        pytest.fail("点击「查询」后仍显示「点击“查询”后读取统计数据。」，查询未生效")

    # === Key 管理 ===
    _click_tab(page, "Key 管理")
    body = main.inner_text()
    assert "仅显示由 Fenix 创建的模型网关 Key" in body, \
        f"Key 管理缺少说明文案: {body[:200]!r}"

    assert main.get_by_role("button", name="刷新", exact=True).count() == 1, \
        "Key 管理缺少「刷新」按钮"
    # 写操作按钮只断言存在，不点击
    assert main.get_by_role("button", name="删除所选 Key", exact=True).count() == 1, \
        "Key 管理缺少「删除所选 Key」按钮"

    table = main.locator("table").first
    assert table.count() == 1, "Key 管理未渲染 Key 表格"
    header = table.locator("tr").first.inner_text()
    for col in ["Key ID", "主体", "当前可用性", "创建时间"]:
        assert col in header, f"Key 表格缺少列「{col}」，表头: {header!r}"

    rows = table.locator("tbody tr")
    if rows.count() > 0:
        first_row = rows.first.inner_text()
        assert ("可用" in first_row), f"Key 表格行未渲染可用性: {first_row[:120]!r}"
        assert re.search(r"\d{4}/\d{1,2}/\d{1,2}", first_row), \
            f"Key 表格行未渲染创建时间（YYYY/M/D）: {first_row[:120]!r}"