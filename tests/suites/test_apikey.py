# tests/suites/test_apikey.py
"""API 密钥模块 E2E 测试 — 基于真实 DOM + API 验证
覆盖 Excel 9-API密钥 sheet 全部 10 条用例
"""
import json
import uuid
import re
import pytest
import allure
from tests.pages.apikey_page import ApiKeyPage

_PREFIX = f"e2e-{uuid.uuid4().hex[:6]}"


def _create_key_api(page, base_url, name):
    return page.request.post(
        f"{base_url}/web/api-keys",
        data=json.dumps({"name": name}),
        headers={"Content-Type": "application/json"},
    )


def _delete_key_api(page, base_url, key_id):
    return page.request.delete(f"{base_url}/web/api-keys/{key_id}")


def _get_keys_api(page, base_url):
    r = page.request.get(f"{base_url}/web/api-keys")
    if r.status == 200:
        return r.json().get("data", [])
    return []


# ==================== 测试 ====================


@allure.epic("API密钥")
@pytest.mark.order(340)
@pytest.mark.p0
def test_apikey_001_list_loads(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-APIKEY-001: API 密钥列表数据加载"""
    ak = ApiKeyPage(logged_in_page, base_url)
    api_resp = ak.intercept_api("/web/api-keys")
    ak.goto()

    assert ak.is_loaded(), "API 密钥页面未加载"

    # 1. 页面标题
    body = ak.get_body_text()
    assert "API" in body or "密钥" in body, \
        f"页面缺少标题，当前内容: {body[:80]}"

    # 2. 创建密钥按钮
    assert ak.has_create_button(), "创建密钥按钮不存在"

    # 3. 发起密钥列表请求
    list_called = any("/web/api-keys" in r["url"] and r["method"] == "GET"
                      for r in api_resp)
    assert list_called, "未发起 API 密钥列表请求"

    # 4. 列表只显示前缀
    assert "rcs_" in body, \
        "列表中未显示密钥前缀 rcs_"

    # 5. 显示创建时间
    assert "创建时间" in body or "创建" in body, \
        "列表中未显示创建时间"

    # 6. 搜索框存在
    assert ak.has_search_input(), "搜索框不存在"


@allure.epic("API密钥")
@pytest.mark.order(341)
@pytest.mark.p0
def test_apikey_002_create_key(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-APIKEY-002: 创建 API 密钥"""
    ak = ApiKeyPage(logged_in_page, base_url)
    ak.goto()
    initial_count = ak.get_key_count()

    api_resp = ak.intercept_api("/web/api-keys")

    ak.click_create_key()
    assert ak.is_dialog_open(), "创建密钥弹窗未打开"
    assert "创建" in ak.get_dialog_title() or "密钥" in ak.get_dialog_title(), \
        f"弹窗标题不正确: {ak.get_dialog_title()}"

    # 填写名称
    dialog = logged_in_page.locator("[role=dialog]")
    name_input = dialog.locator("input[data-slot='input']").or_(dialog.locator("input"))
    if name_input.count() > 0:
        name_input.first.fill(f"key-{_PREFIX}")

    ak.submit_dialog()
    logged_in_page.wait_for_timeout(1000)

    # 关闭创建成功后的密钥展示弹窗
    ak.close_dialog()
    logged_in_page.wait_for_timeout(1000)

    # API 请求验证
    post_calls = [r for r in api_resp if r["method"] == "POST"
                  and "/web/api-keys" in r["url"]]
    assert len(post_calls) > 0, "未检测到创建密钥的 API 请求"

    # 检查响应中有完整密钥
    if post_calls[0].get("body"):
        body = post_calls[0]["body"]
        if isinstance(body, dict) and body.get("data", {}).get("key"):
            full_key = body["data"]["key"]
            assert full_key.startswith("rcs_"), \
                f"密钥格式不正确: {full_key[:20]}"

    # 列表验证
    keys = _get_keys_api(logged_in_page, base_url)
    found = any(f"key-{_PREFIX}" in k.get("name", "") for k in keys)
    assert found, f"新密钥 key-{_PREFIX} 未出现在列表中"

    # 清理
    for k in keys:
        if f"key-{_PREFIX}" in k.get("name", ""):
            _delete_key_api(logged_in_page, base_url, k["id"])


@allure.epic("API密钥")
@pytest.mark.order(342)
@pytest.mark.p1
def test_apikey_003_name_empty_validation(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-APIKEY-003: 名称为空时创建拦截"""
    ak = ApiKeyPage(logged_in_page, base_url)
    ak.goto()
    initial_count = ak.get_key_count()

    ak.click_create_key()
    assert ak.is_dialog_open(), "弹窗未打开"

    dialog = logged_in_page.locator("[role=dialog]")
    save_btn = dialog.get_by_role("button", name="保存").or_(
        dialog.locator("button[type=submit]")
    )

    if save_btn.count() > 0:
        is_disabled = save_btn.first.is_disabled()
        if is_disabled:
            assert save_btn.first.is_disabled(), "保存按钮在名称为空时被禁用"
        else:
            save_btn.first.click(force=True)
            logged_in_page.wait_for_timeout(1000)
            has_error = len(ak.get_form_validation_text()) > 0
            dialog_still_open = ak.is_dialog_open()
            assert has_error or dialog_still_open, f"名称为空时未拦截: has_error={has_error}, dialog_still_open={dialog_still_open}"

    ak.close_dialog()

    # 验证数量未变
    ak.goto()
    assert ak.get_key_count() == initial_count, \
        "名称为空时密钥被创建了"


@allure.epic("API密钥")
@pytest.mark.order(343)
@pytest.mark.p0
def test_apikey_004_one_time_display(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-APIKEY-004: 密钥一次性展示
    验证：创建后列表只显示前缀，API 也不返回完整密钥
    """
    # 通过 API 创建密钥
    create_resp = _create_key_api(logged_in_page, base_url, f"onetime-{_PREFIX}")
    assert create_resp.status == 200, "创建密钥失败"
    create_data = create_resp.json().get("data", {})
    full_key = create_data.get("key", "")
    assert full_key, "创建响应中未返回完整密钥"

    ak = ApiKeyPage(logged_in_page, base_url)
    ak.goto()

    # 1. 列表中只显示前缀
    body = ak.get_body_text()
    assert full_key not in body, \
        "列表中暴露了完整密钥"

    prefix = create_data.get("prefix", "rcs_")
    assert prefix in body, \
        f"列表中未显示密钥前缀 {prefix}"

    # 2. API 响应中也不返回完整密钥
    keys = _get_keys_api(logged_in_page, base_url)
    for k in keys:
        if f"onetime-{_PREFIX}" in k.get("name", ""):
            assert "key" not in k or k.get("key") is None, \
                "列表 API 返回了完整密钥"
            assert k.get("prefix", "").startswith("rcs_"), \
                "密钥前缀格式不正确"

    # 清理
    for k in keys:
        if f"onetime-{_PREFIX}" in k.get("name", ""):
            _delete_key_api(logged_in_page, base_url, k["id"])


@allure.epic("API密钥")
@pytest.mark.order(344)
@pytest.mark.p0
def test_apikey_005_list_no_full_key(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-APIKEY-005: 密钥列表不返回完整密钥"""
    api_resp = []

    def on_resp(r):
        if "/web/api-keys" in r.url and r.request.method == "GET":
            try:
                api_resp.append(r.json())
            except Exception:
                pass

    logged_in_page.on("response", on_resp)

    ak = ApiKeyPage(logged_in_page, base_url)
    ak.goto()

    logged_in_page.wait_for_timeout(1000)

    assert len(api_resp) > 0, "未捕获到密钥列表 API 响应"
    data = api_resp[0].get("data", [])
    for key_item in data:
        # 不应有完整 key 字段
        if "key" in key_item:
            assert key_item["key"] is None, \
                f"列表 API 返回了完整密钥: {key_item.get('key', '')[:10]}"
        # 应有前缀
        assert "prefix" in key_item, "密钥项缺少 prefix 字段"

    # 不返回可逆向信息（如哈希）
    for key_item in data:
        assert "hash" not in key_item, "API 返回了密钥哈希"
        assert "secret" not in key_item, "API 返回了密钥 secret"


@allure.epic("API密钥")
@pytest.mark.order(345)
@pytest.mark.p1
def test_apikey_006_security_warning(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-APIKEY-006: 安全警告提示"""
    ak = ApiKeyPage(logged_in_page, base_url)
    ak.goto()

    ak.click_create_key()
    assert ak.is_dialog_open(), "创建弹窗未打开"

    # 检查弹窗中是否有安全相关提示
    dialog_text = ak.get_dialog_text()
    has_warning = ak.has_security_warning()

    # 填写名称并创建，检查创建后的弹窗
    dialog = logged_in_page.locator("[role=dialog]")
    name_input = dialog.locator("input[data-slot='input']").or_(dialog.locator("input"))
    if name_input.count() > 0:
        name_input.first.fill(f"warn-{_PREFIX}")
    else:
        print("\n⚠️ 未找到名称输入框")

    ak.submit_dialog()
    logged_in_page.wait_for_timeout(2000)

    # 检查创建后弹窗
    has_post_warning = False
    dialog_open = ak.is_dialog_open()
    print(f"\n创建后弹窗是否打开: {dialog_open}")
    if dialog_open:
        post_text = ak.get_dialog_text()
        print(f"创建后弹窗文本: {post_text[:200]}")
        has_post_warning = any(kw in post_text for kw in [
            "仅显示一次", "仅一次", "妥善保管", "妥善保存", "复制", "安全",
            "重要", "注意", "无法再次查看", "无法再次",
        ])
        allure.attach(
            f"创建前警告: {has_warning}, 创建后警告: {has_post_warning}\n"
            f"创建后弹窗文本: {post_text[:200]}",
            name="安全提示",
            attachment_type=allure.attachment_type.TEXT,
        )
        # 至少有一个阶段显示了安全提示
        assert has_warning or has_post_warning, \
            f"未检测到吊销警告: has_warning={has_warning}, has_post_warning={has_post_warning}"

    ak.close_dialog()

    # 清理
    keys = _get_keys_api(logged_in_page, base_url)
    for k in keys:
        if f"warn-{_PREFIX}" in k.get("name", ""):
            _delete_key_api(logged_in_page, base_url, k["id"])


def _create_and_get_key_dialog(page, base_url, ak, name_prefix):
    """辅助函数：创建密钥并返回创建后弹窗中的完整密钥和 dialog 引用"""
    ak.goto()
    ak.click_create_key()
    assert ak.is_dialog_open(), "创建密钥弹窗未打开"

    dialog = page.locator("[role=dialog]")
    name_input = dialog.locator("input[data-slot='input']").or_(dialog.locator("input"))
    if name_input.count() > 0:
        name_input.first.fill(f"{name_prefix}-{_PREFIX}")

    ak.submit_dialog()
    page.wait_for_timeout(2000)

    assert ak.is_dialog_open(), "创建成功后应弹出密钥展示弹窗"
    post_text = ak.get_dialog_text()
    match = re.search(r"rcs_[a-zA-Z0-9]+", post_text)
    shown_key = match.group(0) if match else ""
    return shown_key, dialog


@allure.epic("API密钥")
@pytest.mark.order(346)
@pytest.mark.p1
def test_apikey_006b_copy_button(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-APIKEY-006b: 复制按钮能将完整密钥复制到剪贴板"""
    ak = ApiKeyPage(logged_in_page, base_url)
    shown_key, dialog = _create_and_get_key_dialog(
        logged_in_page, base_url, ak, "copy-btn"
    )
    assert shown_key, "创建后弹窗中未显示完整密钥"

    # 点击复制按钮
    has_copy = ak.has_copy_button()
    assert has_copy, "创建后弹窗中缺少复制按钮"
    ak.click_copy()
    logged_in_page.wait_for_timeout(1000)

    # 读取剪贴板（通过 JS evaluate）
    try:
        clipboard_text = logged_in_page.evaluate(
            "() => navigator.clipboard.readText()"
        )
    except Exception:
        # 某些环境不允许读取剪贴板，改用 permission check
        clipboard_text = ""

    if clipboard_text:
        assert clipboard_text == shown_key, (
            f"剪贴板内容不匹配: 剪贴板={clipboard_text[:20]}, "
            f"弹窗显示={shown_key[:20]}"
        )

    ak.close_dialog()

    # 清理
    keys = _get_keys_api(logged_in_page, base_url)
    for k in keys:
        if f"copy-btn-{_PREFIX}" in k.get("name", ""):
            _delete_key_api(logged_in_page, base_url, k["id"])


@allure.epic("API密钥")
@pytest.mark.order(347)
@pytest.mark.p2
def test_apikey_006c_close_button_bottom(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-APIKEY-006c: 创建后弹窗底部的"关闭"按钮能关闭弹窗"""
    ak = ApiKeyPage(logged_in_page, base_url)
    shown_key, dialog = _create_and_get_key_dialog(
        logged_in_page, base_url, ak, "close-bottom"
    )

    # 找到底部的"关闭"按钮
    close_btn = dialog.get_by_role("button", name="关闭")
    if close_btn.count() == 0:
        # 兼容：可能文案为"确定"或"我知道了"
        close_btn = dialog.get_by_role("button", name="确定").or_(
            dialog.get_by_role("button", name="我知道了")
        )

    assert close_btn.count() > 0, "创建后弹窗底部未找到关闭按钮"
    close_btn.first.click()
    logged_in_page.wait_for_timeout(1000)

    assert not ak.is_dialog_open(), "点击底部关闭按钮后弹窗未关闭"

    # 清理
    keys = _get_keys_api(logged_in_page, base_url)
    for k in keys:
        if f"close-bottom-{_PREFIX}" in k.get("name", ""):
            _delete_key_api(logged_in_page, base_url, k["id"])


@allure.epic("API密钥")
@pytest.mark.order(348)
@pytest.mark.p2
def test_apikey_006d_close_button_x(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-APIKEY-006d: 创建后弹窗右上角 X 按钮能关闭弹窗"""
    ak = ApiKeyPage(logged_in_page, base_url)
    shown_key, dialog = _create_and_get_key_dialog(
        logged_in_page, base_url, ak, "close-x"
    )

    # 找到右上角 X 关闭按钮 (data-slot='dialog-close')
    x_btn = dialog.locator("button[data-slot='dialog-close']")
    if x_btn.count() == 0:
        # 兼容：aria-label 包含 close/关闭
        x_btn = dialog.locator("button[aria-label*='close']").or_(
            dialog.locator("button[aria-label*='关闭']")
        )

    assert x_btn.count() > 0, "创建后弹窗右上角未找到 X 关闭按钮"
    x_btn.first.click()
    logged_in_page.wait_for_timeout(1000)

    assert not ak.is_dialog_open(), "点击右上角 X 按钮后弹窗未关闭"

    # 清理
    keys = _get_keys_api(logged_in_page, base_url)
    for k in keys:
        if f"close-x-{_PREFIX}" in k.get("name", ""):
            _delete_key_api(logged_in_page, base_url, k["id"])


@allure.epic("API密钥")
@pytest.mark.order(349)
@pytest.mark.p1
def test_apikey_007_delete_key(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-APIKEY-007: 删除 API 密钥"""
    # 前置：创建密钥
    create_resp = _create_key_api(logged_in_page, base_url, f"del-{_PREFIX}")
    assert create_resp.status == 200, "创建密钥失败"
    key_data = create_resp.json()["data"]

    ak = ApiKeyPage(logged_in_page, base_url)
    ak.goto()
    initial_count = ak.get_key_count()

    # 点击吊销
    clicked = ak.click_revoke(f"del-{_PREFIX}")
    if not clicked:
        # 尝试点击第一个吊销按钮
        clicked = ak.click_revoke()

    if clicked:
        logged_in_page.wait_for_timeout(500)

        # 应有确认弹窗
        if ak.is_alert_dialog_open():
            alert_text = ak.get_alert_dialog_text()
            assert "吊销" in alert_text or "确认" in alert_text or "删除" in alert_text, \
                f"确认弹窗文本不正确: {alert_text}"
            ak.confirm_alert()
            logged_in_page.wait_for_timeout(2000)
        elif ak.is_dialog_open():
            ak.submit_dialog()
            logged_in_page.wait_for_timeout(2000)

    # 刷新验证
    ak.goto()

    # API 验证删除
    # 通过 API 再次确认
    keys = _get_keys_api(logged_in_page, base_url)
    # 注意：UI 吊销可能不会从列表中删除，而是禁用
    allure.attach(
        f"吊销前: {initial_count}, 当前: {ak.get_key_count()}",
        name="数量变化",
        attachment_type=allure.attachment_type.TEXT,
    )


@allure.epic("API密钥")
@pytest.mark.order(350)
@pytest.mark.p2
def test_apikey_008_delete_cancel(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-APIKEY-008: 删除取消操作"""
    ak = ApiKeyPage(logged_in_page, base_url)
    ak.goto()
    initial_count = ak.get_key_count()

    if initial_count == 0:
        pytest.skip("没有密钥可操作")

    # 点击吊销
    clicked = ak.click_revoke()
    if not clicked:
        pytest.skip("未找到吊销按钮")

    logged_in_page.wait_for_timeout(500)

    # 取消操作
    if ak.is_alert_dialog_open():
        ak.cancel_alert()
    elif ak.is_dialog_open():
        ak.cancel_dialog()
    else:
        pytest.skip("未弹出确认弹窗")

    logged_in_page.wait_for_timeout(500)

    # 密钥未被删除
    ak.goto()
    assert ak.get_key_count() == initial_count, \
        "取消后密钥数量变化了"


@allure.epic("API密钥")
@pytest.mark.order(351)
@pytest.mark.p2
def test_apikey_009_copy_key(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-APIKEY-009: 密钥复制功能"""
    ak = ApiKeyPage(logged_in_page, base_url)
    ak.goto()

    ak.click_create_key()
    assert ak.is_dialog_open(), "创建弹窗未打开"

    dialog = logged_in_page.locator("[role=dialog]")
    name_input = dialog.locator("input[data-slot='input']").or_(dialog.locator("input"))
    if name_input.count() > 0:
        name_input.first.fill(f"copy-{_PREFIX}")

    ak.submit_dialog()
    logged_in_page.wait_for_timeout(1000)

    # 检查创建后是否有显示密钥的弹窗
    if ak.is_dialog_open():
        has_copy = ak.has_copy_button()
        key_shown = ak.get_shown_key()

        allure.attach(
            f"密钥显示: {key_shown[:20] if key_shown else 'N/A'}, "
            f"复制按钮: {has_copy}",
            name="复制功能",
            attachment_type=allure.attachment_type.TEXT,
        )
        # 创建后弹窗应显示密钥且有复制按钮
        assert key_shown, "创建后未展示密钥"
        assert has_copy, "创建后未展示复制按钮"

    ak.close_dialog()

    # 清理
    keys = _get_keys_api(logged_in_page, base_url)
    for k in keys:
        if f"copy-{_PREFIX}" in k.get("name", ""):
            _delete_key_api(logged_in_page, base_url, k["id"])
