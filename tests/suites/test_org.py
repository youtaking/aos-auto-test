# tests/suites/test_org.py
"""组织管理模块 E2E 测试 — 新版「左侧目录 + 右侧详情」双栏布局（基于真实 DOM）

覆盖 Excel 5-组织管理 sheet 的用例。
数据安全铁律：
- 环境中已存在组织（ORG_001_new / ORG_AUTO_TEST 等）一律禁止改/删/加人/删人。
- 涉及成员增删/角色变更/删除组织的用例，全部在自建组织上执行，测完 API 删除。
"""
import json
import re
import time
import uuid
import pytest
import allure
from tests.pages.org_page import OrgPage

_PREFIX = uuid.uuid4().hex[:6]


# ==================== 工具函数 ====================

def _api_create_org(page, base_url, name, slug=None):
    """POST /web/organizations，返回 (org_id or None, resp)。"""
    slug = slug or name.lower().replace(" ", "-")
    resp = page.request.post(
        f"{base_url}/web/organizations",
        data=json.dumps({"name": name, "slug": slug}),
        headers={"Content-Type": "application/json"},
    )
    try:
        return resp.json().get("data", {}).get("id", ""), resp
    except Exception:
        return "", resp


def _api_delete_org(page, base_url, org_id):
    return page.request.delete(f"{base_url}/web/organizations/{org_id}")


def _api_orgs(page, base_url):
    r = page.request.get(f"{base_url}/web/organizations")
    if r.status == 200:
        return r.json().get("data", [])
    return []


def _org_id_by_name(page, base_url, name):
    for o in _api_orgs(page, base_url):
        if o.get("name") == name:
            return o.get("id")
    return None


def _wait_until(pred, timeout=10.0, msg="等待超时"):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if pred():
                return
        except Exception:
            pass
        time.sleep(0.25)
    raise AssertionError(msg)


# ==================== UI 测试 ====================


@allure.epic("组织管理")
@pytest.mark.order(300)
@pytest.mark.p0
def test_org_001_list_loads(logged_in_page, base_url):
    """✅ TC-ORG-001: 组织列表数据加载"""
    org = OrgPage(logged_in_page, base_url)
    api_resp = org.intercept_api("/web/organizations")
    org.goto()
    assert org.is_loaded(), "组织管理页面未加载"

    # 1. 发起组织列表请求
    list_called = any("/web/organizations" in r["url"] and r["method"] == "GET"
                      for r in api_resp)
    if not list_called:
        # 重新导航触发一次 GET，再判定
        org.goto()
        list_called = any("/web/organizations" in r["url"] and r["method"] == "GET"
                          for r in api_resp)
    assert list_called, "未发起组织列表 API 请求"

    # 2. 展示已有组织
    org_names = org.get_org_names()
    count = org.get_org_count()
    assert count > 0, "组织列表为空"

    # 3. 数据与 API 响应一致 — 至少有一个含 "org" 的组织（不区分大小写）
    has_org = any("org" in name.lower() for name in org_names)
    assert has_org, f"列表中未找到包含 'org' 的组织: {org_names}"


@allure.epic("组织管理")
@pytest.mark.order(301)
@pytest.mark.p0
def test_org_002_create_org(logged_in_page, base_url):
    """✅ TC-ORG-002: 创建新组织（新版弹窗字段：名称 + Slug）"""
    org = OrgPage(logged_in_page, base_url)
    org.goto()
    _wait_until(lambda: org.get_org_count() >= 0, timeout=5)

    api_resp = org.intercept_api("/web/organizations")
    org_name = f"测试组织{_PREFIX}"

    # 点击创建
    org.click_create_org()
    assert org.is_dialog_open(), "创建组织弹窗未打开"
    assert "创建组织" in org.get_dialog_title(), "弹窗标题不正确"

    # 填写表单（新弹窗只有 名称 + Slug，无描述字段）
    org.fill_create_name(org_name)
    org.fill_create_slug(f"test-org-{_PREFIX}")
    _wait_until(lambda: org.create_submit_enabled(), timeout=6,
                msg="填写名称+Slug 后创建按钮仍禁用")

    # 提交
    org.click_create_submit()
    _wait_until(lambda: not org.is_dialog_open(), timeout=8, msg="创建后弹窗未关闭")

    # 获取创建后的 org_id，供 finally 清理
    org_id = _org_id_by_name(logged_in_page, base_url, org_name)

    try:
        # 刷新验证
        org.goto()
        _wait_until(lambda: org.has_org(org_name), timeout=8,
                    msg=f"新组织未出现在列表中")
        assert org.has_org(org_name), f"新组织未出现在列表中"

        # POST 请求验证
        post_calls = [r for r in api_resp if r["method"] == "POST"
                      and "/web/organizations" in r["url"]]
        assert len(post_calls) > 0, "未检测到创建组织的 POST 请求"
    finally:
        if org_id:
            _api_delete_org(logged_in_page, base_url, org_id)


@allure.epic("组织管理")
@pytest.mark.order(302)
@pytest.mark.p1
def test_org_003_name_empty_validation(logged_in_page, base_url):
    """✅ TC-ORG-003: 名称为空时创建拦截"""
    org = OrgPage(logged_in_page, base_url)
    org.goto()
    _wait_until(lambda: org.get_org_count() > 0, timeout=8)
    initial_names = set(org.get_org_names())

    org.click_create_org()
    assert org.is_dialog_open(), "弹窗未打开"

    # 不填写名称：创建按钮应被禁用（名称为空时前端直接拦截提交）
    create_btn = logged_in_page.locator("[role=dialog] button").filter(has_text="创建").first
    create_btn.wait_for(state="visible", timeout=5000)
    is_disabled = create_btn.is_disabled()

    # 若按钮未禁用（兼容非 disabled 的校验实现），点创建后弹窗不得关闭，否则视为校验缺失
    if not is_disabled:
        create_btn.click(force=True)
        logged_in_page.wait_for_timeout(800)
        assert org.is_dialog_open(), "【应用Bug】名称为空时点击创建弹窗被关闭（未触发校验）"

    org.close_dialog()
    _wait_until(lambda: not org.is_dialog_open(), timeout=6, msg="弹窗未关闭")

    # 验证没有创建新组织
    org.goto()
    _wait_until(lambda: org.get_org_count() > 0, timeout=8)
    final_names = set(org.get_org_names())
    new_names = final_names - initial_names
    assert len(new_names) == 0, \
        f"名称为空时组织被创建了，新增组织: {new_names}"


@allure.epic("组织管理")
@pytest.mark.order(303)
@pytest.mark.p0
def test_org_004_data_isolation(logged_in_page, base_url):
    """✅ TC-ORG-004: 切换组织后数据隔离"""
    org = OrgPage(logged_in_page, base_url)
    org.goto()
    _wait_until(lambda: org.get_org_count() > 0, timeout=8)
    names = org.get_org_names()
    if len(names) < 2:
        pytest.skip("用户只有 1 个组织，无法测试数据隔离")

    org.click_org(names[0])
    detail1 = org.get_detail_text()

    org.click_org(names[1])
    detail2 = org.get_detail_text()

    assert detail1 != detail2, "切换组织后详情内容未变化"


@allure.epic("组织管理")
@pytest.mark.order(304)
@pytest.mark.p0
def test_org_005_cross_org_access(logged_in_page, base_url):
    """✅ TC-ORG-005: 跨组织 API 访问拦截"""
    orgs = _api_orgs(logged_in_page, base_url)
    if len(orgs) < 2:
        pytest.skip("只有 1 个组织，无法测试跨组织访问")

    # 用当前 token 访问组织列表应成功
    r = logged_in_page.request.get(f"{base_url}/web/organizations")
    assert r.status == 200, "认证请求应成功"

    # 无认证请求应被拒绝
    browser = logged_in_page.context.browser
    no_auth_ctx = browser.new_context(locale="zh-CN")
    no_auth_page = no_auth_ctx.new_page()
    try:
        r2 = no_auth_page.request.get(f"{base_url}/web/organizations")
        is_rejected = r2.status in [401, 403]
        if r2.status == 200:
            try:
                is_rejected = not r2.json().get("success", True)
            except Exception:
                is_rejected = False
        assert is_rejected, f"无认证请求未被拒绝: status={r2.status}"
    finally:
        no_auth_page.close()
        no_auth_ctx.close()


@allure.epic("组织管理")
@pytest.mark.order(305)
@pytest.mark.p1
def test_org_006_add_member(logged_in_page, base_url):
    """✅ TC-ORG-006: 添加组织成员（自建组织上执行，避免污染既有组织）"""
    org = OrgPage(logged_in_page, base_url)
    org_name = f"auto-{_PREFIX}-addm"
    org_id, resp = _api_create_org(logged_in_page, base_url, org_name)
    assert org_id, f"API 创建测试组织失败: {resp.status} {resp.text()[:200]}"
    try:
        org.goto()
        _wait_until(lambda: org.has_org(org_name), timeout=8, msg="自建组织未出现在目录")
        org.click_org(org_name)

        assert org.has_add_member_button(), "【应用Bug】未找到「添加成员」按钮"

        # 打开添加成员弹窗
        org.click_add_member()
        assert "添加成员" in org.get_dialog_title(), "添加成员弹窗标题不正确"

        # 搜索候选人（perftest001 → 压测用户001）并添加
        added = org.add_member("perftest001", role="成员")
        assert added, "【应用Bug】选中用户后「添加」按钮仍禁用"

        # 等待弹窗关闭
        _wait_until(lambda: not org.is_dialog_open(), timeout=8, msg="添加后弹窗未关闭")

        # 验证成员已加入
        _wait_until(lambda: org.has_member("压测用户001"), timeout=8,
                    msg="添加后成员未出现在列表中")
        assert org.has_member("压测用户001"), "添加后成员未出现在列表中"

        # 数量 +1
        assert org.get_member_count() >= 2, \
            f"成员数量未增加: 当前 {org.get_member_count()}"
    finally:
        if org_id:
            _api_delete_org(logged_in_page, base_url, org_id)


@allure.epic("组织管理")
@pytest.mark.order(306)
@pytest.mark.p1
def test_org_008_remove_member(logged_in_page, base_url):
    """✅ TC-ORG-008: 移除组织成员（自建组织上加人→移除，避免污染既有组织）"""
    org = OrgPage(logged_in_page, base_url)
    org_name = f"auto-{_PREFIX}-rm"
    org_id, resp = _api_create_org(logged_in_page, base_url, org_name)
    assert org_id, f"API 创建测试组织失败: {resp.status} {resp.text()[:200]}"
    try:
        org.goto()
        _wait_until(lambda: org.has_org(org_name), timeout=8, msg="自建组织未出现在目录")
        org.click_org(org_name)
        initial_count = org.get_member_count()

        # 先添加成员
        org.click_add_member()
        added = org.add_member("perftest001", role="成员")
        assert added, "【应用Bug】添加成员失败（添加按钮禁用）"
        _wait_until(lambda: not org.is_dialog_open(), timeout=8, msg="添加后弹窗未关闭")
        _wait_until(lambda: org.has_member("压测用户001"), timeout=8,
                    msg="前置添加成员失败")
        count_after_add = org.get_member_count()

        # 1. 点击成员行移除按钮，弹出确认弹窗
        org.click_remove_member("压测用户001")
        assert org.is_alert_dialog_open(), "移除成员确认弹窗未出现"
        alert_text = org.get_alert_dialog_text()
        assert "确认移除" in alert_text, "确认弹窗内容不正确"
        assert "压测用户001" in alert_text, "确认弹窗未指明移除对象"

        # 2. 确认移除
        org.click_alert_button("确认移除")

        # 3. 成员从列表消失
        _wait_until(lambda: not org.has_member("压测用户001"), timeout=8,
                    msg="移除后成员仍在列表中")
        assert not org.has_member("压测用户001"), "移除后成员仍在列表中"

        # 4. 成员数量回落
        assert org.get_member_count() == count_after_add - 1 or \
               org.get_member_count() == initial_count, \
            f"成员数量未正确回落: 前 {count_after_add}，后 {org.get_member_count()}"
    finally:
        if org_id:
            _api_delete_org(logged_in_page, base_url, org_id)


@allure.epic("组织管理")
@pytest.mark.order(308)
@pytest.mark.p1
def test_org_011_delete_org(logged_in_page, base_url):
    """✅ TC-ORG-011: 删除组织（自建组织，UI 删除 + API 二次确认）"""
    org_name = f"auto-{_PREFIX}-del"
    org_id, resp = _api_create_org(logged_in_page, base_url, org_name)
    assert org_id, f"创建测试组织失败: {resp.status} {resp.text()[:200]}"

    try:
        org = OrgPage(logged_in_page, base_url)
        org.goto()
        _wait_until(lambda: org.has_org(org_name), timeout=8, msg="新建组织未出现在列表")
        org.click_org(org_name)

        # 1. 危险区域 + 删除按钮
        assert org.has_danger_zone(), "未找到危险区域"
        assert org.has_delete_org_button(), "未找到删除组织按钮"

        # 2. 点击删除
        org.click_delete_org()

        # 3. 确认弹窗（alertdialog）且确认对象是自己建的组织
        assert org.is_alert_dialog_open(), "删除组织确认弹窗未出现"
        alert_text = org.get_alert_dialog_text()
        assert "确认删除" in alert_text, "确认弹窗内容不正确"
        assert org_name in alert_text, \
            f"确认弹窗对象不是本次自建组织（{org_name}）:\n{alert_text[:200]}"

        # 4. 确认删除
        org.click_alert_button("确认删除")

        # 5. 验证组织从列表消失
        _wait_until(lambda: not org.has_org(org_name), timeout=8,
                    msg="删除后组织仍在目录中")
        org.goto()
        assert not org.has_org(org_name), f"删除后 {org_name} 仍在组织列表中"

        # 6. API 二次确认
        assert _org_id_by_name(logged_in_page, base_url, org_name) is None, \
            "UI 删除后组织仍存在于 API"
        org_id = None  # UI 已删除，避免 finally 重复删除
    finally:
        if org_id:
            _api_delete_org(logged_in_page, base_url, org_id)


@allure.epic("组织管理")
@pytest.mark.order(309)
@pytest.mark.p1
def test_org_012_edit_org(logged_in_page, base_url):
    """✅ TC-ORG-012: 修改组织信息（header 内联编辑：input + 保存）"""
    org_name = f"auto-{_PREFIX}-edit"
    org_id, resp = _api_create_org(logged_in_page, base_url, org_name)
    assert org_id, f"创建测试组织失败: {resp.status} {resp.text()[:200]}"

    new_name = f"{org_name}-edited"
    try:
        org = OrgPage(logged_in_page, base_url)
        org.goto()
        _wait_until(lambda: org.has_org(org_name), timeout=8, msg="自建组织未出现在目录")
        org.click_org(org_name)

        # 1. 编辑按钮存在
        assert org.has_edit_button(), "未找到编辑按钮"

        # 2. 点击编辑 → header 内联编辑
        org.click_edit()
        _wait_until(lambda: org.is_editing(), timeout=6, msg="编辑模式下名称输入框未出现")
        assert org.is_editing(), "编辑模式下名称输入框未出现"

        # 3. 修改名称并保存
        name_input = org.edit_name_input()
        name_input.fill("")
        name_input.fill(new_name)
        org.save_edit()

        # 4. 刷新验证持久化
        _wait_until(lambda: org.active_org_name() == new_name, timeout=8,
                    msg="保存后详情未更新为新名称")
        org.goto()
        _wait_until(lambda: org.has_org(new_name), timeout=8,
                    msg="编辑保存后新名称未出现在列表中")
        assert org.has_org(new_name), f"编辑保存后新名称 {new_name} 未出现在列表中"
    finally:
        # 改名不影响 ID
        if org_id:
            _api_delete_org(logged_in_page, base_url, org_id)


@allure.epic("组织管理")
@pytest.mark.order(310)
@pytest.mark.p0
def test_org_013_switch_redirect(logged_in_page, base_url):
    """✅ TC-ORG-013: 组织变更后详情正确展示"""
    org = OrgPage(logged_in_page, base_url)
    org.goto()
    _wait_until(lambda: org.get_org_count() > 0, timeout=8)
    names = org.get_org_names()
    if len(names) < 2:
        pytest.skip("只有 1 个组织")

    # 切换到第二个组织
    org.click_org(names[1])
    detail = org.get_detail_text()
    assert names[1] in detail, f"切换后详情中未显示 '{names[1]}'"


@allure.epic("组织管理")
@pytest.mark.order(360)
@pytest.mark.p1
def test_org_default_machine(logged_in_page, base_url):
    """TC-ORG-014: 默认执行节点 — 详情页存在默认执行节点选择器且可选"""
    org = OrgPage(logged_in_page, base_url)
    org.goto()
    _wait_until(lambda: org.get_org_count() > 0, timeout=8)
    names = org.get_org_names()
    if not names:
        pytest.skip("无可用组织")

    org.click_org(names[0])
    _wait_until(lambda: org.has_engine_strip(), timeout=8,
                msg="组织详情无默认执行节点区域")
    assert org.has_engine_strip(), "组织详情中未找到默认执行节点区域"

    sel = org.default_node_select()
    assert sel.count() > 0, "默认执行节点缺少选择器"
    assert sel.locator("option").count() >= 1, "默认执行节点无可选项"

    # 刷新后仍加载
    org.goto()
    _wait_until(lambda: org.is_loaded(), timeout=8)
    assert org.is_loaded(), "组织页面刷新后未加载"


@allure.epic("组织管理")
@pytest.mark.order(361)
@pytest.mark.p2
def test_org_add_member_dialog(logged_in_page, base_url):
    """TC-ORG-015: 添加成员对话框 — 打开对话框并验证含搜索框（自建组织，只读验证）"""
    org = OrgPage(logged_in_page, base_url)
    org_name = f"auto-{_PREFIX}-dlg"
    org_id, resp = _api_create_org(logged_in_page, base_url, org_name)
    assert org_id, f"API 创建测试组织失败: {resp.status} {resp.text()[:200]}"
    try:
        org.goto()
        _wait_until(lambda: org.has_org(org_name), timeout=8, msg="自建组织未出现在目录")
        org.click_org(org_name)
        _wait_until(lambda: org.has_add_member_button(), timeout=8,
                    msg="当前组织无「添加成员」按钮")

        org.click_add_member()
        assert org.is_dialog_open(), "点击「添加成员」后对话框未打开"

        dialog_text = logged_in_page.locator("[role=dialog]").first.inner_text()
        assert "添加成员" in dialog_text, f"对话框缺少「添加成员」标题: {dialog_text[:100]}"

        search_input = logged_in_page.locator(
            "[role=dialog] input[placeholder*='搜索']"
        )
        assert search_input.count() > 0, "对话框中缺少搜索输入框"
        assert search_input.first.is_visible(), "搜索输入框不可见"

        # 关闭
        org.cancel_dialog()
        _wait_until(lambda: not org.is_dialog_open(), timeout=6, msg="对话框未关闭")
    finally:
        if org_id:
            _api_delete_org(logged_in_page, base_url, org_id)


@allure.epic("组织管理")
@pytest.mark.order(362)
@pytest.mark.p1
def test_org_member_search_add(logged_in_page, base_url):
    """TC-ORG-016: 成员搜索 — 搜索候选人出现结果（自建组织，搜索后取消不实际添加）"""
    org = OrgPage(logged_in_page, base_url)
    org_name = f"auto-{_PREFIX}-srch"
    org_id, resp = _api_create_org(logged_in_page, base_url, org_name)
    assert org_id, f"API 创建测试组织失败: {resp.status} {resp.text()[:200]}"
    try:
        org.goto()
        _wait_until(lambda: org.has_org(org_name), timeout=8, msg="自建组织未出现在目录")
        org.click_org(org_name)
        _wait_until(lambda: org.has_add_member_button(), timeout=8,
                    msg="当前组织无添加成员按钮")

        org.click_add_member()
        assert org.is_dialog_open(), "添加成员弹窗未打开"

        search_input = logged_in_page.locator("[role=dialog] input[placeholder*='搜索']")
        assert search_input.count() > 0, "添加成员弹窗中无搜索输入框"

        # 输入 >=3 字符触发搜索
        org.search_add_candidate("perftest", enter=False, wait=8000)
        options = org.add_candidates()
        assert options.count() > 0, "搜索结果未显示"

        # 取消关闭（不实际添加）
        org.cancel_dialog()
        _wait_until(lambda: not org.is_dialog_open(), timeout=6, msg="弹窗未关闭")
    finally:
        if org_id:
            _api_delete_org(logged_in_page, base_url, org_id)


@allure.epic("组织管理")
@pytest.mark.order(363)
@pytest.mark.p0
def test_org_set_active(logged_in_page, base_url):
    """TC-ORG-017: 组织切换（set-active）— 通过 API 切换活跃组织，验证 UI 反映"""
    orgs = _api_orgs(logged_in_page, base_url)
    if len(orgs) < 2:
        pytest.skip("只有 1 个组织，无法测试切换")

    target_org = orgs[1]
    target_id = target_org["id"]
    target_name = target_org.get("name", "")

    r = logged_in_page.request.post(
        f"{base_url}/web/organizations/{target_id}/set-active",
        headers={"Content-Type": "application/json"},
    )
    assert r.status < 400, \
        f"set-active API 失败: status={r.status}, body={r.text()[:200]}"

    # 刷新页面验证 UI 反映了切换
    try:
        logged_in_page.reload(wait_until="domcontentloaded", timeout=60000)
    except Exception:
        pass
    _wait_until(lambda: "org-directory" in logged_in_page.content(), timeout=10,
                msg="刷新后组织目录未加载")

    body_text = logged_in_page.inner_text("body")
    assert target_name in body_text, \
        f"切换活跃组织后，目标组织名 '{target_name}' 未出现在页面中"


@allure.epic("组织管理")
@pytest.mark.order(364)
@pytest.mark.p1
def test_org_member_role_management(logged_in_page, base_url):
    """TC-ORG-018: 成员角色管理 — 自建组织上添加成员并验证/变更角色"""
    org = OrgPage(logged_in_page, base_url)
    org_name = f"auto-{_PREFIX}-role"
    org_id, resp = _api_create_org(logged_in_page, base_url, org_name)
    assert org_id, f"API 创建测试组织失败: {resp.status} {resp.text()[:200]}"
    try:
        org.goto()
        _wait_until(lambda: org.has_org(org_name), timeout=8, msg="自建组织未出现在目录")
        org.click_org(org_name)

        # 添加成员压测用户001
        org.click_add_member()
        added = org.add_member("perftest001", role="成员")
        assert added, "添加成员失败"
        _wait_until(lambda: not org.is_dialog_open(), timeout=8, msg="弹窗未关闭")
        _wait_until(lambda: org.has_member("压测用户001"), timeout=8, msg="成员未加入")

        # 成员行应展示角色徽标 + 角色下拉
        row = org.member_row("压测用户001").first
        role_select = row.locator("select").first
        role_select.wait_for(state="visible", timeout=5000)
        options = [role_select.nth(0).locator("option").nth(i).get_attribute("value")
                   for i in range(role_select.locator("option").count())]
        assert "admin" in options and "member" in options, \
            f"角色下拉缺少管理员/成员选项: {options}"

        # 变更角色：成员 → 管理员，验证生效
        role_select.select_option("admin")
        _wait_until(lambda: role_select.input_value() == "admin", timeout=8,
                    msg="角色未变更为管理员")
        assert role_select.input_value() == "admin", "角色未变更为管理员"

        # 变更回 成员
        role_select.select_option("member")
        _wait_until(lambda: role_select.input_value() == "member", timeout=8,
                    msg="角色未变更回成员")
    finally:
        if org_id:
            _api_delete_org(logged_in_page, base_url, org_id)


@allure.epic("组织管理")
@pytest.mark.order(365)
@pytest.mark.p1
def test_org_default_engine(logged_in_page, base_url):
    """验证组织默认执行节点（默认引擎）配置区域存在"""
    org = OrgPage(logged_in_page, base_url)
    org.goto()
    _wait_until(lambda: org.is_loaded(), timeout=8)
    names = org.get_org_names()
    if not names:
        pytest.skip("无可用组织")

    org.click_org(names[0])
    _wait_until(lambda: org.has_engine_strip(), timeout=8,
                msg="组织详情无默认执行节点区域")
    assert org.has_engine_strip(), "组织详情中未找到默认执行节点区域"
    assert org.default_node_select().count() > 0, "默认执行节点选择器不存在"


@allure.epic("组织管理")
@pytest.mark.order(366)
@pytest.mark.p1
def test_org_machine_management(logged_in_page, base_url):
    """验证组织机器管理 — 详情中存在机器管理相关区域与按钮"""
    org = OrgPage(logged_in_page, base_url)
    org.goto()
    _wait_until(lambda: org.is_loaded(), timeout=8)
    names = org.get_org_names()
    if not names:
        pytest.skip("无可用组织")

    org.click_org(names[0])
    _wait_until(lambda: org.has_machine_region(), timeout=8,
                msg="组织详情无机器区域")

    assert org.has_machine_region(), "组织详情中未找到机器管理标题"
    # 机器数断言：标题「机器 (N)」的 N 必须等于机器区域实际渲染的行数（原 >= 0 永真）
    machine_title = org.get_machine_section_title()
    assert re.fullmatch(r"机器\s*\(\d+\)", machine_title.strip()), \
        f"机器区域标题格式异常: {machine_title!r}"
    assert org.get_machine_count() == org.get_machine_rows_count(), \
        (f"「{machine_title}」计数与机器列表行数不一致: "
         f"标题={org.get_machine_count()}, 行数={org.get_machine_rows_count()}")
    assert org.has_machine_buttons(), "机器区域缺少新增机器/刷新按钮"


@allure.epic("组织管理")
@pytest.mark.order(367)
@pytest.mark.p1
def test_org_danger_zone(logged_in_page, base_url):
    """P1: 组织危险区域 — 验证危险区域标题和删除组织按钮存在（不点击任何危险操作）"""
    org = OrgPage(logged_in_page, base_url)
    org.goto()
    _wait_until(lambda: org.is_loaded(), timeout=8)
    names = org.get_org_names()
    if not names:
        pytest.skip("无可用组织")

    org.click_org(names[0])
    _wait_until(lambda: org.has_danger_zone(), timeout=8, msg="组织详情无危险区域")

    # 1. 危险区域标题
    danger_text = org.get_danger_text()
    assert "危险区域" in danger_text, f"危险区域标题缺失: {danger_text[:100]}"

    # 2. 删除组织按钮存在（不点击）
    assert org.has_delete_org_button(), "'删除组织' 按钮不存在"

    # 3. 危险区域有不可撤销警告
    has_warning = any(kw in danger_text for kw in [
        "不可撤销", "不可恢复", "永久删除", "删除组织将",
        "irreversible", "cannot be undone",
    ])
    assert has_warning, f"危险区域缺少操作警告文本: {danger_text[:150]}"

    # 注意：绝对不点击 "删除组织" 按钮！仅验证其存在


@allure.epic("组织管理")
@pytest.mark.order(368)
@pytest.mark.p2
def test_org_create_all_fields(logged_in_page, base_url):
    """P2: 组织创建弹窗字段覆盖 — 验证 名称 + Slug 字段存在（新弹窗无描述字段），不提交"""
    org = OrgPage(logged_in_page, base_url)
    org.goto()
    _wait_until(lambda: org.is_loaded(), timeout=8)

    if not org.has_create_button():
        pytest.skip("无创建组织按钮（可能无管理权限）")

    org.click_create_org()
    assert org.is_dialog_open(), "创建组织弹窗未打开"

    dialog = logged_in_page.locator("[role=dialog]")
    dialog_text = dialog.first.inner_text()

    # 1. 名称输入框（placeholder="组织名称"）
    name_input = dialog.locator("input[placeholder='组织名称']")
    assert name_input.count() > 0, "名称输入框不存在"
    assert name_input.first.is_visible(), "名称输入框不可见"
    assert "名称" in dialog_text

    # 2. Slug 输入框（placeholder="url-identifier"）
    slug_input = dialog.locator("input[placeholder='url-identifier']")
    assert slug_input.count() > 0, "Slug 输入框不存在"
    assert slug_input.first.is_visible(), "Slug 输入框不可见"

    # Escape 关闭，不提交
    logged_in_page.keyboard.press("Escape")
    logged_in_page.wait_for_timeout(500)
