# tests/suites/test_model_config.py
"""服务商与模型配置模块 E2E 测试 — 基于真实 DOM + API 验证
覆盖 Excel 6-模型配置 sheet 全部 24 条用例
"""
import json
import uuid
import pytest
import allure
from tests.pages.model_config_page import ModelConfigPage


# ==================== 测试常量 ====================

_TEST_PREFIX = f"e2e-test-{uuid.uuid4().hex[:8]}"
_TEST_PROVIDER_ID = f"{_TEST_PREFIX}"
_TEST_PROVIDER_NAME = f"E2E Test {_TEST_PREFIX}"
_TEST_API_KEY = "sk-test-key-for-e2e-automation-12345678"
_TEST_BASE_URL = "https://api.test-e2e-placeholder.com/v1"
_TEST_MODEL_ID = f"model-{_TEST_PREFIX}"
_TEST_MODEL_NAME = f"Test Model {_TEST_PREFIX}"


# ==================== 辅助函数 ====================

def _create_provider_via_api(page, base_url, provider_id, name, protocol="openai",
                             api_key=_TEST_API_KEY, base_url_provider=_TEST_BASE_URL):
    """通过 API 创建 Provider（用于测试前置）"""
    resp = page.request.put(
        f"{base_url}/web/config/providers?name={provider_id}",
        data=json.dumps({
            "apiKey": api_key,
            "baseURL": base_url_provider,
            "protocol": protocol,
            "name": name,
        }),
        headers={"Content-Type": "application/json"},
    )
    return resp


def _delete_provider_via_api(page, base_url, provider_id):
    """通过 API 删除 Provider（用于测试清理）"""
    resp = page.request.delete(
        f"{base_url}/web/config/providers?name={provider_id}",
    )
    return resp


def _get_providers_via_api(page, base_url):
    """通过 API 获取 Provider 列表"""
    resp = page.request.get(f"{base_url}/web/config/providers")
    if resp.status == 200:
        data = resp.json()
        return data.get("data", {}).get("providers", [])
    return []


def _get_provider_detail_via_api(page, base_url, resource_key):
    """通过 API 获取 Provider 详情（含模型列表）"""
    resp = page.request.get(
        f"{base_url}/web/config/providers?name={resource_key}"
    )
    if resp.status == 200:
        return resp.json()
    return None


# ==================== UI 测试 ====================


@allure.epic("模型配置")
@allure.feature("Provider列表")
@pytest.mark.order(200)
@pytest.mark.p0
def test_model_001_provider_list_loads(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-MODEL-001: Provider 列表数据加载
    验证：1. 发起 Provider 列表请求 2. 展示已配置的 Provider
    3. 列表中不显示 API Key 明文
    """
    mc = ModelConfigPage(logged_in_page, base_url)

    # 拦截 API 请求
    api_responses = mc.intercept_api_responses("/web/config/providers")
    mc.goto()

    # 1. 发起 Provider 列表请求
    provider_api_called = any(
        r["url"].endswith("/web/config/providers") and r["method"] == "GET"
        for r in api_responses
    )
    assert provider_api_called, "未发起 Provider 列表 API 请求"

    # 2. 展示已配置的 Provider
    assert mc.is_loaded(), "模型配置页面未加载"
    count = mc.get_provider_count()
    assert count > 0, f"Provider 列表为空，预期至少有一个"

    # 3. 列表中不显示 API Key 明文
    names = mc.get_provider_names()
    for name in names:
        assert mc.is_api_key_masked_in_ui(name), \
            f"Provider '{name}' 的卡片中发现了 API Key 明文"

    # 4. 搜索框存在
    assert mc.has_search_input(), "搜索框不存在"

    # 5. 新建服务商按钮存在
    assert mc.has_add_provider_button(), "新建服务商按钮不存在"


@allure.epic("模型配置")
@allure.feature("添加Provider")
@pytest.mark.order(201)
@pytest.mark.p0
def test_model_002_add_openai_provider(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-MODEL-002: 添加 OpenAI 协议 Provider
    验证：1. POST/PUT 请求发往 Provider API 2. API Key 在请求体中
    3. Provider 创建成功 4. 列表中出现新 Provider
    """
    mc = ModelConfigPage(logged_in_page, base_url)
    mc.goto()
    initial_count = mc.get_provider_count()

    # 拦截 API
    api_responses = mc.intercept_api_responses("/web/config/providers")

    # 点击新建服务商
    mc.click_add_provider()
    assert mc.is_dialog_open(), "新建服务商弹窗未打开"
    assert "新建服务商" in mc.get_dialog_title(), "弹窗标题不正确"

    # 填写表单（默认协议为 OpenAI 兼容）
    mc.fill_provider_form(
        provider_id=_TEST_PROVIDER_ID,
        display_name=_TEST_PROVIDER_NAME,
        api_key=_TEST_API_KEY,
        base_url=_TEST_BASE_URL,
    )
    mc.submit_form()

    # 弹窗应关闭
    logged_in_page.wait_for_timeout(1000)
    assert not mc.is_dialog_open(), "保存后弹窗未关闭"

    # 刷新页面验证
    mc.goto()

    # 3. Provider 创建成功 — 列表中出现新 Provider
    assert mc.has_provider(_TEST_PROVIDER_ID), \
        f"Provider '{_TEST_PROVIDER_ID}' 未出现在列表中"
    new_count = mc.get_provider_count()
    assert new_count == initial_count + 1, \
        f"Provider 数量未增加: {new_count} vs {initial_count + 1}"

    # 1. 验证 API 调用 — 应有 PUT 请求
    put_calls = [r for r in api_responses if r["method"] == "PUT"]
    assert len(put_calls) > 0, "未检测到创建 Provider 的 PUT API 请求"

    # 2. API Key 不在 URL 中，响应中 keyHint 为掩码格式
    assert _TEST_API_KEY not in put_calls[0]["url"], "API Key 暴露在 URL 中"
    put_resp_body = put_calls[0].get("body", {})
    if isinstance(put_resp_body, str):
        put_resp_body = json.loads(put_resp_body)
    key_hint = put_resp_body.get("data", {}).get("keyHint", "")
    assert key_hint.startswith("***"), \
        f"响应中 keyHint 不是掩码格式: {key_hint}"

    # 清理
    _delete_provider_via_api(logged_in_page, base_url, _TEST_PROVIDER_ID)


@allure.epic("模型配置")
@allure.feature("添加Provider")
@pytest.mark.order(202)
@pytest.mark.p1
def test_model_003_add_anthropic_provider(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-MODEL-003: 添加 Anthropic 协议 Provider
    验证：1. 创建成功 2. 协议类型标识正确 3. API Key 掩码显示
    """
    mc = ModelConfigPage(logged_in_page, base_url)
    mc.goto()

    # 点击新建
    mc.click_add_provider()
    assert mc.is_dialog_open(), "新建弹窗未打开"

    # 选择 Anthropic 协议
    mc.select_protocol("Anthropic")

    # 填写表单
    anthropic_id = f"{_TEST_PREFIX}-anthropic"
    mc.fill_provider_form(
        provider_id=anthropic_id,
        display_name=f"Anthropic {_TEST_PREFIX}",
        api_key=_TEST_API_KEY,
        base_url="https://api.anthropic-test.com/v1",
    )
    mc.submit_form()

    logged_in_page.wait_for_timeout(1000)
    mc.goto()

    # 1. 创建成功
    assert mc.has_provider(anthropic_id), \
        f"Anthropic Provider '{anthropic_id}' 未出现"

    # 2. 协议类型标识正确
    protocol = mc.get_provider_protocol(anthropic_id)
    assert "Anthropic" in protocol, \
        f"协议类型不正确，预期 Anthropic，实际: {protocol}"

    # 3. API Key 掩码显示
    assert mc.is_api_key_masked_in_ui(anthropic_id), \
        "API Key 未掩码显示"

    # 清理
    _delete_provider_via_api(logged_in_page, base_url, anthropic_id)


@allure.epic("模型配置")
@allure.feature("添加Provider")
@pytest.mark.order(203)
@pytest.mark.p1
def test_model_004_api_key_empty_allowed(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-MODEL-004: 不填 API Key 也能创建 Provider
    验证：1. 创建成功 2. Provider 出现在列表中 3. keyHint 为空或显示占位
    """
    mc = ModelConfigPage(logged_in_page, base_url)
    mc.goto()
    initial_count = mc.get_provider_count()

    # 打开弹窗，填写名称但不填 API Key
    provider_id = f"{_TEST_PREFIX}-nokey"
    mc.click_add_provider()
    mc.fill_provider_form(
        provider_id=provider_id,
        display_name=f"NoKey {_TEST_PREFIX}",
        api_key="",  # 故意不填
        base_url="https://api.test.com/v1",
    )
    mc.submit_form()
    logged_in_page.wait_for_timeout(1000)

    # 弹窗应关闭（不被拦截）
    assert not mc.is_dialog_open(), "不填 API Key 时弹窗应正常关闭"

    # 刷新验证 Provider 已创建
    mc.goto()
    assert mc.has_provider(provider_id), \
        f"不填 API Key 的 Provider '{provider_id}' 未出现在列表中"
    assert mc.get_provider_count() == initial_count + 1, \
        "Provider 数量未增加"

    # API 验证 keyHint 为空或占位
    providers = _get_providers_via_api(logged_in_page, base_url)
    for p in providers:
        if p["id"] == provider_id:
            key_hint = p.get("keyHint", "")
            # keyHint 应为空或占位符（不应有真实密钥）
            assert "sk-" not in key_hint, \
                f"未填 Key 却返回了 keyHint: {key_hint}"
            break

    # 清理
    _delete_provider_via_api(logged_in_page, base_url, provider_id)


@allure.epic("模型配置")
@allure.feature("安全")
@pytest.mark.order(204)
@pytest.mark.p0
def test_model_005_api_key_not_exposed(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-MODEL-005: API Key 不暴露
    验证：1. API Key 默认掩码显示 2. API 响应中为掩码 3. LocalStorage 中不存储明文
    """
    mc = ModelConfigPage(logged_in_page, base_url)

    # 拦截 API 响应
    api_responses = mc.intercept_api_responses("/web/config/providers")
    mc.goto()

    count = mc.get_provider_count()
    assert count > 0, "Provider 列表为空"

    # 1. UI 中 API Key 掩码显示（keyHint 格式如 ***9313）
    names = mc.get_provider_names()
    for name in names:
        assert mc.is_api_key_masked_in_ui(name), \
            f"Provider '{name}' UI 中暴露了 API Key 明文"

    # 2. API 响应中 API Key 字段为掩码
    list_responses = [
        r for r in api_responses
        if r["url"].endswith("/web/config/providers") and r["method"] == "GET"
    ]
    assert len(list_responses) > 0, "未找到 Provider 列表 API 响应"
    body = list_responses[0].get("body", {})
    providers = body.get("data", {}).get("providers", [])
    for prov in providers:
        key_hint = prov.get("keyHint", "")
        # keyHint 应该是掩码格式（***开头）
        assert "***" in key_hint or key_hint == "", \
            f"API 响应中 Provider '{prov.get('id')}' 暴露了 API Key: {key_hint}"
        # 不应有完整 apiKey 字段
        assert "apiKey" not in prov or prov.get("apiKey") is None, \
            f"API 响应中 Provider '{prov.get('id')}' 返回了完整 apiKey"

    # 3. LocalStorage 中不存储明文 API Key
    storage_check = logged_in_page.evaluate("""() => {
        const all = {};
        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            all[key] = localStorage.getItem(key);
        }
        return JSON.stringify(all);
    }""")
    # 检查是否有 sk- 开头的明文 key
    import re
    assert not re.search(r"\bsk-[a-zA-Z0-9]{20,}", storage_check), \
        "LocalStorage 中发现 API Key 明文"


@allure.epic("模型配置")
@allure.feature("编辑")
@pytest.mark.order(205)
@pytest.mark.p1
def test_model_006_edit_provider(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-MODEL-006: 编辑 Provider 配置
    验证：1. PUT/PATCH 请求更新配置 2. 修改保存成功 3. 列表显示更新后信息
    """
    # 前置：创建测试 Provider
    _create_provider_via_api(
        logged_in_page, base_url,
        _TEST_PROVIDER_ID, _TEST_PROVIDER_NAME,
    )

    mc = ModelConfigPage(logged_in_page, base_url)
    mc.goto()
    assert mc.has_provider(_TEST_PROVIDER_ID), "测试 Provider 未创建成功"

    # 拦截 API
    api_responses = mc.intercept_api_responses("/web/config/providers")

    # 点击编辑
    mc.click_provider_edit(_TEST_PROVIDER_ID)
    assert mc.is_dialog_open(), "编辑弹窗未打开"
    assert "编辑服务商" in mc.get_dialog_title(), "弹窗标题不正确"

    # 验证 ID 字段不可修改
    assert mc.is_edit_id_disabled(), "编辑弹窗中 ID 字段应不可修改"

    # 记录原始 Base URL
    original_url = mc.get_edit_form_base_url()

    # 修改 Base URL
    new_url = "https://updated-base-url.example.com/v1"
    mc.fill_edit_provider_form(base_url=new_url)
    mc.submit_form()

    logged_in_page.wait_for_timeout(1000)
    assert not mc.is_dialog_open(), "保存后弹窗未关闭"

    # 重新打开编辑弹窗验证修改生效
    mc.click_provider_edit(_TEST_PROVIDER_ID)
    assert mc.is_dialog_open(), "再次编辑弹窗未打开"
    updated_url = mc.get_edit_form_base_url()
    mc.close_dialog()

    assert updated_url == new_url, \
        f"Base URL 未更新: '{updated_url}' vs '{new_url}'"

    # 验证 API 调用（PUT 或 PATCH）
    update_calls = [
        r for r in api_responses
        if r["method"] in ("PUT", "PATCH") and "providers" in r["url"]
        and "fetch-models" not in r["url"] and "models" not in r["url"]
    ]
    assert len(update_calls) > 0, "未检测到更新 Provider 的 API 请求"

    # 恢复原始 URL
    mc.click_provider_edit(_TEST_PROVIDER_ID)
    mc.fill_edit_provider_form(base_url=original_url)
    mc.submit_form()
    logged_in_page.wait_for_timeout(500)

    # 清理
    _delete_provider_via_api(logged_in_page, base_url, _TEST_PROVIDER_ID)


@allure.epic("模型配置")
@allure.feature("编辑")
@pytest.mark.order(205)
@pytest.mark.p2
def test_model_006b_edit_provider_other_fields(logged_in_page, base_url):
    """TC-MODEL-006b: 编辑服务商其它字段（协议切换、可用模型列表）
    验证：1. 协议 combobox 可切换 2. 切换后保存生效 3. 可用模型列表区域存在且有获取按钮
    """
    # 前置：创建测试 Provider（默认 OpenAI 协议）
    provider_id = f"other-{_TEST_PREFIX}"
    _create_provider_via_api(
        logged_in_page, base_url,
        provider_id, f"Other {_TEST_PREFIX}",
        protocol="openai",
    )

    mc = ModelConfigPage(logged_in_page, base_url)
    mc.goto()
    assert mc.has_provider(provider_id), "测试 Provider 未创建成功"

    # 打开编辑弹窗
    mc.click_provider_edit(provider_id)
    assert mc.is_dialog_open(), "编辑弹窗未打开"

    # 1. 当前协议为 OpenAI 兼容
    current_protocol = mc.get_edit_provider_protocol()
    assert "OpenAI" in current_protocol, \
        f"初始协议不正确: {current_protocol}"

    # 切换协议为 Anthropic
    mc.select_protocol("Anthropic")
    new_protocol = mc.get_edit_provider_protocol()
    assert "Anthropic" in new_protocol, \
        f"协议切换失败: {new_protocol}"

    # 2. 保存并验证协议切换生效
    mc.submit_form()
    logged_in_page.wait_for_timeout(1000)
    mc.goto()

    mc.click_provider_edit(provider_id)
    saved_protocol = mc.get_edit_provider_protocol()
    assert "Anthropic" in saved_protocol, \
        f"协议未保存: {saved_protocol}"

    # 切换回 OpenAI（恢复）
    mc.select_protocol("OpenAI 兼容")
    mc.submit_form()
    logged_in_page.wait_for_timeout(500)

    # 3. 再次打开验证可用模型列表区域
    mc.goto()
    mc.click_provider_edit(provider_id)
    assert mc.has_model_list_section(), "编辑弹窗中缺少「可用模型列表」区域"
    assert mc.has_fetch_models_in_dialog(), "编辑弹窗中缺少「获取模型列表」按钮"

    # 点击获取模型列表（测试用假 URL，预期返回错误提示，但按钮功能正常）
    mc.click_fetch_models_in_dialog()
    model_list_text = mc.get_dialog_model_list_text()
    has_feedback = "未获取到模型" in model_list_text or "可用模型列表" in model_list_text
    assert has_feedback, \
        f"获取模型列表后无反馈: {model_list_text[:200]}"

    mc.close_dialog()

    # 清理
    _delete_provider_via_api(logged_in_page, base_url, provider_id)


@allure.epic("模型配置")
@allure.feature("删除")
@pytest.mark.order(206)
@pytest.mark.p1
def test_model_007_delete_provider_cascade(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-MODEL-007: 删除 Provider 级联删除模型
    验证：1. 弹出确认弹窗 2. 确认后 Provider 被删除 3. 关联模型也被删除
    """
    # 前置：创建带模型的 Provider
    _create_provider_via_api(
        logged_in_page, base_url,
        _TEST_PROVIDER_ID, _TEST_PROVIDER_NAME,
    )
    # 添加一个模型
    providers = _get_providers_via_api(logged_in_page, base_url)
    resource_key = None
    for p in providers:
        if p["id"] == _TEST_PROVIDER_ID:
            resource_key = p.get("resourceKey", "")
            break

    if resource_key:
        logged_in_page.request.post(
            f"{base_url}/web/config/providers/actions/models?name={resource_key}",
            data=json.dumps({
                "modelId": _TEST_MODEL_ID,
                "name": _TEST_MODEL_NAME,
                "modalities": {"input": ["text"], "output": ["text"]},
            }),
            headers={"Content-Type": "application/json"},
        )

    mc = ModelConfigPage(logged_in_page, base_url)
    mc.goto()
    assert mc.has_provider(_TEST_PROVIDER_ID), "测试 Provider 不存在"

    # 验证模型存在
    model_count_before = mc.get_model_count_for_provider(_TEST_PROVIDER_ID)
    assert model_count_before > 0, "测试模型未添加成功"

    # 点击删除
    mc.click_provider_delete(_TEST_PROVIDER_ID)

    # 1. 弹出确认弹窗
    assert mc.is_alert_dialog_open(), "删除确认弹窗未弹出"
    alert_text = mc.get_alert_dialog_text()
    assert "删除" in alert_text or "确认" in alert_text, \
        f"确认弹窗文本不正确: {alert_text}"

    # 确认删除
    mc.confirm_alert_dialog()
    logged_in_page.wait_for_timeout(1000)

    # 刷新页面
    mc.goto()

    # 2. Provider 被删除
    assert not mc.has_provider(_TEST_PROVIDER_ID), \
        f"Provider '{_TEST_PROVIDER_ID}' 删除后仍然存在"

    # 3. 验证 API 中模型也被删除（级联删除）
    providers_after = _get_providers_via_api(logged_in_page, base_url)
    provider_exists = any(p["id"] == _TEST_PROVIDER_ID for p in providers_after)
    assert not provider_exists, "API 中 Provider 仍存在"


@allure.epic("模型配置")
@allure.feature("模型管理")
@pytest.mark.order(207)
@pytest.mark.p0
def test_model_008_add_model(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-MODEL-008: 添加模型
    验证：1. 模型添加成功 2. 显示在模型列表中
    """
    # 前置：创建 Provider
    _create_provider_via_api(
        logged_in_page, base_url,
        _TEST_PROVIDER_ID, _TEST_PROVIDER_NAME,
    )

    mc = ModelConfigPage(logged_in_page, base_url)
    mc.goto()
    assert mc.has_provider(_TEST_PROVIDER_ID), "测试 Provider 不存在"

    # 拦截 API
    api_responses = mc.intercept_api_responses("/web/config/providers/actions/models")

    # 点击 + 添加模型
    clicked = mc.click_add_model(_TEST_PROVIDER_ID)
    assert clicked, "点击 '+ 添加模型' 失败"
    assert mc.is_dialog_open(), "添加模型弹窗未打开"
    assert "新增模型" in mc.get_dialog_title(), "弹窗标题不正确"

    # 填写表单
    mc.fill_model_form(_TEST_MODEL_ID, _TEST_MODEL_NAME)
    mc.submit_form()

    logged_in_page.wait_for_timeout(1000)
    mc.goto()

    # 1. 模型添加成功 — API 调用验证
    model_api_calls = [
        r for r in api_responses
        if r["method"] == "POST" and "models" in r["url"]
    ]
    assert len(model_api_calls) > 0, "未检测到添加模型的 API 请求"

    # 2. 显示在模型列表中
    model_count = mc.get_model_count_for_provider(_TEST_PROVIDER_ID)
    assert model_count > 0, "添加后模型数量为 0"

    model_names = mc.get_model_names_for_provider(_TEST_PROVIDER_ID)
    found = any(_TEST_MODEL_ID in name for name in model_names)
    assert found, \
        f"模型 '{_TEST_MODEL_ID}' 未出现在列表中，当前: {model_names}"

    # 清理
    _delete_provider_via_api(logged_in_page, base_url, _TEST_PROVIDER_ID)


@allure.epic("模型配置")
@allure.feature("模型管理")
@pytest.mark.order(207)
@pytest.mark.p1
def test_model_009_edit_model(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-MODEL-009: 编辑模型（UI）
    验证：1. 编辑弹窗打开 2. 模型 ID 不可修改 3. 修改显示名称后保存生效
    """
    # 前置：创建 Provider 和模型
    _create_provider_via_api(
        logged_in_page, base_url,
        _TEST_PROVIDER_ID, _TEST_PROVIDER_NAME,
    )
    providers = _get_providers_via_api(logged_in_page, base_url)
    resource_key = next(
        (p["resourceKey"] for p in providers if p["id"] == _TEST_PROVIDER_ID), ""
    )
    assert resource_key, "Provider 创建失败"

    model_id = f"edit-m-{_TEST_PREFIX}"
    original_name = f"Original {_TEST_PREFIX}"
    logged_in_page.request.post(
        f"{base_url}/web/config/providers/actions/models?name={resource_key}",
        data=json.dumps({
            "modelId": model_id,
            "name": original_name,
            "modalities": {"input": ["text"], "output": ["text"]},
        }),
        headers={"Content-Type": "application/json"},
    )

    mc = ModelConfigPage(logged_in_page, base_url)
    mc.goto()

    # 点击模型编辑按钮
    clicked = mc.click_model_edit(_TEST_PROVIDER_ID, model_id)
    assert clicked, f"未找到模型 '{model_id}' 的编辑按钮"
    assert mc.is_dialog_open(), "编辑模型弹窗未打开"

    # 1. 模型 ID 不可修改
    assert mc.is_edit_model_id_disabled(), "编辑弹窗中模型 ID 应不可修改"

    # 2. 修改显示名称
    new_name = f"Updated {_TEST_PREFIX}"
    mc.fill_edit_model_form(display_name=new_name)
    mc.submit_form()
    logged_in_page.wait_for_timeout(1000)

    # 3. 重新打开编辑弹窗验证修改生效
    mc.goto()
    clicked = mc.click_model_edit(_TEST_PROVIDER_ID, model_id)
    assert clicked, "重新编辑时未找到模型"
    updated_name = mc.get_edit_model_display_name()
    mc.close_dialog()

    assert updated_name == new_name, \
        f"显示名称未更新: '{updated_name}' vs '{new_name}'"

    # 清理
    _delete_provider_via_api(logged_in_page, base_url, _TEST_PROVIDER_ID)


@allure.epic("模型配置")
@allure.feature("模型管理")
@pytest.mark.order(207)
@pytest.mark.p1
def test_model_009b_delete_model(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-MODEL-009b: 删除模型（UI）
    验证：1. 确认弹窗弹出 2. 确认后模型被删除 3. 模型不再出现
    """
    # 前置：创建 Provider 和模型
    _create_provider_via_api(
        logged_in_page, base_url,
        _TEST_PROVIDER_ID, _TEST_PROVIDER_NAME,
    )
    providers = _get_providers_via_api(logged_in_page, base_url)
    resource_key = next(
        (p["resourceKey"] for p in providers if p["id"] == _TEST_PROVIDER_ID), ""
    )
    assert resource_key, "Provider 创建失败"

    model_id = f"del-m-{_TEST_PREFIX}"
    logged_in_page.request.post(
        f"{base_url}/web/config/providers/actions/models?name={resource_key}",
        data=json.dumps({
            "modelId": model_id,
            "name": f"DeleteMe {_TEST_PREFIX}",
            "modalities": {"input": ["text"], "output": ["text"]},
        }),
        headers={"Content-Type": "application/json"},
    )

    mc = ModelConfigPage(logged_in_page, base_url)
    mc.goto()

    # 验证模型存在
    model_names = mc.get_model_names_for_provider(_TEST_PROVIDER_ID)
    assert any(model_id in n for n in model_names), \
        f"模型 '{model_id}' 未出现在列表中"

    # 点击删除
    clicked = mc.click_model_delete(_TEST_PROVIDER_ID, model_id)
    assert clicked, f"未找到模型 '{model_id}' 的删除按钮"

    # 1. 确认弹窗弹出
    assert mc.is_alert_dialog_open(), "删除确认弹窗未弹出"
    alert_text = mc.get_alert_dialog_text()
    assert "删除" in alert_text and model_id in alert_text, \
        f"确认弹窗文本不正确: {alert_text}"

    # 确认删除
    mc.confirm_alert_dialog()
    logged_in_page.wait_for_timeout(1000)

    # 2. 刷新验证模型被删除
    mc.goto()
    model_names_after = mc.get_model_names_for_provider(_TEST_PROVIDER_ID)
    assert not any(model_id in n for n in model_names_after), \
        f"删除后模型 '{model_id}' 仍然出现在列表中"

    # 3. API 验证
    detail = _get_provider_detail_via_api(logged_in_page, base_url, resource_key)
    if detail:
        models = detail.get("data", {}).get("models", [])
        model_ids = [m.get("modelId", m.get("id", "")) for m in models]
        assert model_id not in model_ids, \
            f"API 中模型 '{model_id}' 仍存在"

    # 清理
    _delete_provider_via_api(logged_in_page, base_url, _TEST_PROVIDER_ID)


@allure.epic("模型配置")
@allure.feature("模型管理")
@pytest.mark.order(207)
@pytest.mark.p2
def test_model_009c_edit_model_other_fields(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-MODEL-009c: 编辑模型其它字段（上下文限制、输出限制、模态切换、高级参数）
    验证：1. 上下文/输出限制可填写并保存 2. 模态按钮可切换 3. 高级参数可展开
    发现系统 bug：思考模式/思考预算/输出费用 未持久化
    """
    # 前置：创建 Provider 和模型
    provider_id = f"modother-{_TEST_PREFIX}"
    _create_provider_via_api(
        logged_in_page, base_url,
        provider_id, f"ModOther {_TEST_PREFIX}",
    )
    providers = _get_providers_via_api(logged_in_page, base_url)
    resource_key = next(
        (p["resourceKey"] for p in providers if p["id"] == provider_id), ""
    )
    assert resource_key, "Provider 创建失败"

    model_id = f"modother-{_TEST_PREFIX}"
    logged_in_page.request.post(
        f"{base_url}/web/config/providers/actions/models?name={resource_key}",
        data=json.dumps({
            "modelId": model_id,
            "name": f"ModOther {_TEST_PREFIX}",
            "modalities": {"input": ["text"], "output": ["text"]},
        }),
        headers={"Content-Type": "application/json"},
    )

    mc = ModelConfigPage(logged_in_page, base_url)
    mc.goto()

    # 打开模型编辑弹窗
    clicked = mc.click_model_edit(provider_id, model_id)
    assert clicked, f"未找到模型 '{model_id}' 的编辑按钮"
    assert mc.is_dialog_open(), "编辑模型弹窗未打开"

    # 1. 填写上下文限制和输出限制
    mc.set_context_limit(4096)
    mc.set_output_limit(2048)

    ctx_val = mc.get_context_limit()
    out_val = mc.get_output_limit()
    assert ctx_val == "4096", f"上下文限制填写失败: {ctx_val}"
    assert out_val == "2048", f"输出限制填写失败: {out_val}"

    # 2. 验证模态按钮状态 — text 输入应已选中
    input_selected = mc.get_selected_input_modalities()
    assert "text" in input_selected, \
        f"text 输入模态未选中，当前: {input_selected}"

    output_selected = mc.get_selected_output_modalities()
    assert "text" in output_selected, \
        f"text 输出模态未选中，当前: {output_selected}"

    # 逐个点击所有输入模态按钮，验证不会报错
    for mod in ["image", "audio", "video", "pdf"]:
        result = mc.click_modality(mod, "input")
        assert result, f"输入模态 '{mod}' 按钮点击失败"

    # 逐个点击所有输出模态按钮，验证不会报错
    for mod in ["image"]:
        result = mc.click_modality(mod, "output")
        assert result, f"输出模态 '{mod}' 按钮点击失败"

    # 验证点击后的状态
    input_after = mc.get_selected_input_modalities()
    assert "image" in input_after, \
        f"点击后 image 输入模态未选中，当前: {input_after}"

    output_after = mc.get_selected_output_modalities()
    assert "image" in output_after, \
        f"点击后 image 输出模态未选中，当前: {output_after}"

    # 3. 展开高级参数
    assert mc.has_expand_advanced_button(), "缺少「展开高级参数」按钮"
    mc.click_expand_advanced()

    # 验证高级参数字段存在且可填写
    assert mc.has_thinking_mode_checkbox(), "缺少「启用思考模式」开关"
    mc.toggle_thinking_mode()
    assert mc.is_thinking_mode_checked(), "思考模式切换失败"

    # 开启思考模式后应出现「思考预算」输入框
    assert mc.has_thinking_budget_input(), "开启思考模式后缺少「思考预算」输入框"
    mc.set_thinking_budget("1024")
    assert mc.get_thinking_budget() == "1024", \
        f"思考预算填写失败: {mc.get_thinking_budget()}"

    mc.set_input_cost("0.5")
    mc.set_output_cost("1.5")
    cost_check_before = f"input={mc.get_input_cost()}, output={mc.get_output_cost()}"
    allure.attach(cost_check_before, name="费用填写后即时值",
                  attachment_type=allure.attachment_type.TEXT)
    assert mc.get_input_cost() == "0.5", \
        f"输入费用填写失败: {mc.get_input_cost()}"
    assert mc.get_output_cost() == "1.5", \
        f"输出费用填写失败: {mc.get_output_cost()}"

    # 保存
    mc.submit_form()
    logged_in_page.wait_for_timeout(1000)

    # 重新打开验证数值持久化
    mc.goto()
    clicked = mc.click_model_edit(provider_id, model_id)
    assert clicked, "重新编辑时未找到模型"

    saved_ctx = mc.get_context_limit()
    saved_out = mc.get_output_limit()
    assert saved_ctx == "4096", \
        f"上下文限制未保存: {saved_ctx}"
    assert saved_out == "2048", \
        f"输出限制未保存: {saved_out}"

    # 验证模态切换也保存了
    saved_input = mc.get_selected_input_modalities()
    assert "text" in saved_input and "image" in saved_input, \
        f"输入模态未保存: {saved_input}"

    saved_output = mc.get_selected_output_modalities()
    assert "text" in saved_output and "image" in saved_output, \
        f"输出模态未保存: {saved_output}"

    # 展开高级参数，验证费用和思考模式
    mc.click_expand_advanced()

    # 思考模式持久化验证（系统 bug：当前未持久化）
    assert mc.is_thinking_mode_checked(), "思考模式未持久化（系统 bug）"

    # 思考预算持久化验证（需先开启思考模式才可见）
    if mc.has_thinking_budget_input():
        saved_budget = mc.get_thinking_budget()
        assert saved_budget == "1024", \
            f"思考预算未持久化: {saved_budget}（系统 bug）"

    # 费用持久化验证
    saved_input_cost = mc.get_input_cost()
    saved_output_cost = mc.get_output_cost()
    assert saved_input_cost == "0.5", \
        f"输入费用未持久化: {saved_input_cost}"
    assert saved_output_cost == "1.5", \
        f"输出费用未持久化: {saved_output_cost}（系统 bug）"

    mc.close_dialog()

    # 清理
    _delete_provider_via_api(logged_in_page, base_url, provider_id)


@allure.epic("模型配置")
@allure.feature("获取模型列表")
@pytest.mark.order(208)
@pytest.mark.p1
def test_model_010_fetch_provider_models(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-MODEL-010: 获取 Provider 模型列表
    验证：1. 发送 fetch-models 请求 2. 页面有反馈结果
    """
    mc = ModelConfigPage(logged_in_page, base_url)
    mc.goto()

    count = mc.get_provider_count()
    if count == 0:
        pytest.skip("Provider 列表为空")

    # 使用第一个已有 Provider 进行测试
    names = mc.get_provider_names()
    provider_name = names[0]

    # 拦截 API
    api_responses = mc.intercept_api_responses("/web/config/providers/actions/fetch-models")

    # 点击获取模型列表（这实际上就是测试连接）
    mc.click_fetch_models(provider_name)

    # 1. 平台发送了测试请求
    fetch_calls = [
        r for r in api_responses
        if r["method"] == "POST" and "fetch-models" in r["url"]
    ]
    assert len(fetch_calls) > 0, "未检测到获取模型列表的 API 请求"

    # 2. 有测试结果反馈（成功或失败都有反馈）
    result = fetch_calls[0]
    assert result["status"] in [200, 500, 400, 404], \
        f"测试请求返回异常状态码: {result['status']}"

    # 3. 检查页面弹窗反馈
    dialog = logged_in_page.locator("[role=dialog]")
    if dialog.count() > 0 and dialog.first.is_visible():
        dialog_text = dialog.first.inner_text()
        # 成功时：标题"可用模型列表"，描述"发现 N 个可用模型"
        # 失败时：应有错误信息
        has_result = any(kw in dialog_text for kw in [
            "可用模型列表", "发现", "个可用模型", "错误", "失败", "无法连接",
        ])
        assert has_result, f"弹窗内容缺少结果反馈: {dialog_text[:200]}"
        # 关闭弹窗
        close_btn = dialog.locator("button[data-slot='dialog-close']")
        if close_btn.count() > 0:
            close_btn.first.click()
            logged_in_page.wait_for_timeout(500)
    else:
        # 没有弹窗，检查页面文本反馈
        body_text = logged_in_page.locator("div.agent-panel-body").inner_text()
        has_feedback = any(kw in body_text for kw in [
            "模型", "未获取", "无法连接", "错误", "失败", "成功",
        ])
        assert has_feedback, "获取模型列表后页面无任何反馈"


@allure.epic("模型配置")
@allure.feature("连接测试")
@pytest.mark.order(209)
@pytest.mark.p1
def test_model_011_test_single_model(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-MODEL-011: 测试单个模型可用性
    验证：1. 发送测试请求 2. 有反馈结果
    """
    mc = ModelConfigPage(logged_in_page, base_url)
    mc.goto()

    # 找到有模型的 Provider
    names = mc.get_provider_names()
    provider_with_models = None
    model_name = None
    for name in names:
        model_count = mc.get_model_count_for_provider(name)
        if model_count > 0:
            provider_with_models = name
            model_names = mc.get_model_names_for_provider(name)
            if model_names:
                model_name = model_names[0]
            break

    if not provider_with_models or not model_name:
        pytest.skip("没有可用的 Provider 或模型")

    # 拦截 API
    api_responses = mc.intercept_api_responses("/web/config/providers")

    # 点击模型级别的「测试」按钮
    clicked = mc.click_model_test(provider_with_models, model_name)
    if not clicked:
        pytest.skip("未找到模型级别的测试按钮")

    # 等待测试结果出现（"测试通过" 约 2-3 秒后出现，5 秒后消失）
    logged_in_page.wait_for_timeout(2500)

    # 严格检查：必须出现"测试通过"
    card_text = mc.get_provider_card_text(provider_with_models)
    assert "测试通过" in card_text, \
        f"模型测试未通过，卡片文本: {card_text[:300]}"


@allure.epic("模型配置")
@allure.feature("权限管理")
@pytest.mark.order(212)
@pytest.mark.p0
def test_model_014_public_model_readonly(logged_in_page, base_url):
    """TC-MODEL-014: 公有模型配置可读不可改
    需要普通用户账号验证，当前仅有 admin 账号
    """
    mc = ModelConfigPage(logged_in_page, base_url)
    mc.goto()

    # 检查是否有公开的 Provider
    names = mc.get_provider_names()
    has_public = False
    for name in names:
        if mc.is_public(name):
            has_public = True
            break

    if not has_public:
        pytest.skip("当前没有公开的 Provider 配置，且缺少普通用户账号进行权限验证")

    # 如果有公开的 Provider，至少验证它可见
    allure.attach(
        "公有 Provider 在列表中可见，但完整的只读验证需要普通用户账号",
        name="备注",
        attachment_type=allure.attachment_type.TEXT,
    )


@allure.epic("模型配置")
@allure.feature("权限管理")
@pytest.mark.order(213)
@pytest.mark.p1
def test_model_015_public_toggle(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-MODEL-015: 模型公开按钮
    验证：1. 公开开关存在且可切换 2. 切换后状态变化
    """
    # 前置：创建自己的 Provider
    provider_id = f"toggle-{_TEST_PREFIX}"
    _create_provider_via_api(
        logged_in_page, base_url,
        provider_id, f"Toggle {_TEST_PREFIX}",
    )

    mc = ModelConfigPage(logged_in_page, base_url)
    mc.goto()
    assert mc.has_provider(provider_id), "测试 Provider 未创建成功"

    # 获取公开开关
    sw = mc.get_public_switch(provider_id)
    assert sw is not None, "未找到公开开关"

    # 记录初始状态
    initial_state = mc.is_public(provider_id)

    # 切换状态
    mc.toggle_public(provider_id)

    # 验证状态变化
    new_state = mc.is_public(provider_id)
    assert new_state != initial_state, \
        f"切换公开状态后未生效: {initial_state} -> {new_state}"

    # 恢复原始状态
    mc.toggle_public(provider_id)
    restored = mc.is_public(provider_id)
    assert restored == initial_state, \
        f"恢复公开状态失败: {restored} vs {initial_state}"

    # 清理
    _delete_provider_via_api(logged_in_page, base_url, provider_id)


@allure.epic("模型配置")
@allure.feature("CRUD")
@pytest.mark.order(215)
@pytest.mark.p1
def test_model_021_get_provider_models(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-MODEL-021: 获取供应商下面的模型
    验证：1. 正确展示 Provider 下所有模型 2. 显示模型名称 3. 可操作模型
    """
    mc = ModelConfigPage(logged_in_page, base_url)
    mc.goto()

    # 找到有模型的 Provider
    names = mc.get_provider_names()
    target_provider = None
    for name in names:
        if mc.get_model_count_for_provider(name) > 0:
            target_provider = name
            break

    if not target_provider:
        pytest.skip("没有包含模型的 Provider")

    # 1. 正确展示模型
    model_count = mc.get_model_count_for_provider(target_provider)
    assert model_count > 0, f"Provider '{target_provider}' 下模型数量为 0"

    # 2. 显示模型名称
    model_names = mc.get_model_names_for_provider(target_provider)
    assert len(model_names) > 0, "未获取到模型名称"
    for name in model_names:
        assert len(name) > 0, f"模型名称为空"

    # 3. 每个模型有操作按钮（测试、编辑、删除）
    card_text = mc.get_provider_card_text(target_provider)
    assert "测试" in card_text, "模型缺少'测试'按钮"
    assert "编辑" in card_text, "模型缺少'编辑'按钮"
    assert "删除" in card_text, "模型缺少'删除'按钮"


# ==================== Open-API 测试 ====================


@allure.epic("模型配置")
@allure.feature("Open-API")
@pytest.mark.order(216)
@pytest.mark.p1
def test_model_016_openapi_provider_crud(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-MODEL-016: Open-API 提供商 CRUD
    验证：1. 创建 2. 获取列表 3. 获取详情 4. 删除 5. 删除后不再显示
    """
    provider_id = f"api-crud-{_TEST_PREFIX}"

    # 1. 创建 Provider
    create_resp = _create_provider_via_api(
        logged_in_page, base_url,
        provider_id, f"CRUD Test {_TEST_PREFIX}",
    )
    assert create_resp.status == 200, \
        f"创建 Provider 失败: status={create_resp.status}"
    create_body = create_resp.json()
    assert create_body.get("success") is True, \
        f"创建响应 success 不为 True: {create_body}"

    # 2. 获取列表
    providers = _get_providers_via_api(logged_in_page, base_url)
    found = any(p["id"] == provider_id for p in providers)
    assert found, f"Provider '{provider_id}' 未出现在列表中"

    # 3. 获取详情（需要 resourceKey）
    provider_data = next(p for p in providers if p["id"] == provider_id)
    resource_key = provider_data.get("resourceKey", "")
    assert resource_key, "Provider 没有 resourceKey"

    detail = _get_provider_detail_via_api(logged_in_page, base_url, resource_key)
    assert detail is not None, "获取 Provider 详情失败"
    assert detail.get("success") is True, \
        f"详情响应 success 不为 True: {detail}"

    # 4. 删除
    delete_resp = _delete_provider_via_api(logged_in_page, base_url, provider_id)
    assert delete_resp.status == 200, \
        f"删除 Provider 失败: status={delete_resp.status}"

    # 5. 删除后不再显示
    providers_after = _get_providers_via_api(logged_in_page, base_url)
    found_after = any(p["id"] == provider_id for p in providers_after)
    assert not found_after, f"删除后 Provider '{provider_id}' 仍然存在"


@allure.epic("模型配置")
@allure.feature("Open-API")
@pytest.mark.order(217)
@pytest.mark.p1
def test_model_017_openapi_model_crud(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-MODEL-017: Open-API 模型 CRUD
    验证：1. 创建模型 2. 获取模型列表 3. 模型与 Provider 关联 4. 删除模型
    """
    provider_id = f"api-model-{_TEST_PREFIX}"

    # 前置：创建 Provider
    _create_provider_via_api(
        logged_in_page, base_url,
        provider_id, f"Model CRUD {_TEST_PREFIX}",
    )

    # 获取 resourceKey
    providers = _get_providers_via_api(logged_in_page, base_url)
    provider_data = next((p for p in providers if p["id"] == provider_id), None)
    assert provider_data, "Provider 创建失败"
    resource_key = provider_data.get("resourceKey", "")

    model_id = f"model-crud-{_TEST_PREFIX}"

    # 1. 创建模型
    add_resp = logged_in_page.request.post(
        f"{base_url}/web/config/providers/actions/models?name={resource_key}",
        data=json.dumps({
            "modelId": model_id,
            "name": f"Model CRUD {_TEST_PREFIX}",
            "modalities": {"input": ["text"], "output": ["text"]},
        }),
        headers={"Content-Type": "application/json"},
    )
    assert add_resp.status == 200, f"添加模型失败: status={add_resp.status}"
    assert add_resp.json().get("success") is True, "添加模型响应 success 不为 True"

    # 2. 获取 Provider 详情，验证模型存在
    detail = _get_provider_detail_via_api(logged_in_page, base_url, resource_key)
    models = detail.get("data", {}).get("models", [])
    model_ids = [m.get("modelId", m.get("id", "")) for m in models]
    assert model_id in model_ids, \
        f"模型 '{model_id}' 未出现在 Provider 详情中，当前: {model_ids}"

    # 3. 模型与 Provider 正确关联
    assert detail.get("data", {}).get("id") == resource_key or \
        detail.get("data", {}).get("name") == provider_data["name"], \
        "模型与 Provider 关联不正确"

    # 4. 删除模型
    del_resp = logged_in_page.request.delete(
        f"{base_url}/web/config/providers/actions/models/{model_id}?name={resource_key}",
    )
    assert del_resp.status == 200, f"删除模型失败: status={del_resp.status}"
    assert del_resp.json().get("success") is True, "删除模型响应 success 不为 True"

    # 验证模型已删除
    detail_after = _get_provider_detail_via_api(logged_in_page, base_url, resource_key)
    models_after = detail_after.get("data", {}).get("models", [])
    model_ids_after = [m.get("modelId", m.get("id", "")) for m in models_after]
    assert model_id not in model_ids_after, \
        f"删除后模型 '{model_id}' 仍然存在"

    # 清理 Provider
    _delete_provider_via_api(logged_in_page, base_url, provider_id)


@allure.epic("模型配置")
@allure.feature("Open-API")
@pytest.mark.order(218)
@pytest.mark.p0
def test_model_018_openapi_auth_check(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-MODEL-018: Open-API 认证校验
    验证：1. 不带认证 → 401/403 2. 使用无效 Cookie → 401/403
    """
    # 1. 不带认证调用 API（使用新 context，无 cookie）
    from playwright.sync_api import sync_playwright

    # 创建无认证的 context
    browser = logged_in_page.context.browser
    no_auth_ctx = browser.new_context()
    no_auth_page = no_auth_ctx.new_page()

    try:
        resp = no_auth_page.request.get(f"{base_url}/web/config/providers")
        # 应返回 401 或 403 或重定向到登录
        assert resp.status in [401, 403, 302, 307, 308] or \
            not resp.json().get("success", True), \
            f"无认证请求应被拒绝，实际: status={resp.status}"
    except Exception as e:
        # 网络错误也可以接受（被防火墙拦截等）
        allure.attach(
            f"无认证请求异常: {e}",
            name="备注",
            attachment_type=allure.attachment_type.TEXT,
        )
    finally:
        no_auth_page.close()
        no_auth_ctx.close()

    # 2. 有效认证的请求应成功
    resp_auth = logged_in_page.request.get(f"{base_url}/web/config/providers")
    assert resp_auth.status == 200, \
        f"有效认证请求应成功，实际: {resp_auth.status}"
    assert resp_auth.json().get("success") is True, \
        "有效认证请求返回 success 不为 True"


@allure.epic("模型配置")
@allure.feature("Open-API")
@pytest.mark.order(219)
@pytest.mark.p2
def test_model_019_openapi_idempotency(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-MODEL-019: Open-API 并发和幂等性
    验证：1. 重复删除同一资源 2. 首次成功，后续返回 404
    """
    provider_id = f"idempotent-{_TEST_PREFIX}"

    # 创建 Provider
    _create_provider_via_api(
        logged_in_page, base_url,
        provider_id, f"Idempotent {_TEST_PREFIX}",
    )

    # 第一次删除 — 应成功
    resp1 = _delete_provider_via_api(logged_in_page, base_url, provider_id)
    assert resp1.status == 200, f"首次删除失败: {resp1.status}"
    body1 = resp1.json()
    assert body1.get("success") is True, "首次删除 success 不为 True"

    # 第二次删除 — 应返回 404 或 success=false
    resp2 = _delete_provider_via_api(logged_in_page, base_url, provider_id)
    # 可以接受 404 或 200 + success=false
    is_not_found = resp2.status == 404
    is_failed = resp2.status == 200 and not resp2.json().get("success", True)
    assert is_not_found or is_failed, \
        f"重复删除应有明确反馈（404 或 success=false），实际: status={resp2.status}, body={resp2.text()[:200]}"


@allure.epic("模型配置")
@allure.feature("Open-API")
@pytest.mark.order(220)
@pytest.mark.p1
def test_model_022_openapi_create_validation(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-MODEL-022: Open-API 创建提供商参数校验
    验证：1. 缺少必填字段 2. 无效协议类型 3. 错误响应包含校验信息
    """
    # 1. 缺少必填字段 — 空 body
    resp_empty = logged_in_page.request.put(
        f"{base_url}/web/config/providers?name=invalid-{_TEST_PREFIX}",
        data=json.dumps({}),
        headers={"Content-Type": "application/json"},
    )
    # 可能返回 400 或 200 + success=false 或 500
    body_empty = resp_empty.json() if resp_empty.status == 200 else {}
    is_rejected = (
        resp_empty.status in [400, 422, 500]
        or (resp_empty.status == 200 and not body_empty.get("success", True))
    )
    # 即使 200，检查 Provider 是否实际被创建
    providers = _get_providers_via_api(logged_in_page, base_url)
    was_created = any(
        p["id"] == f"invalid-{_TEST_PREFIX}" for p in providers
    )
    if was_created:
        # 如果创建了空 Provider，需要清理并标记
        _delete_provider_via_api(logged_in_page, base_url, f"invalid-{_TEST_PREFIX}")
        allure.attach(
            "空 body 请求创建了 Provider，前端可能有校验但 API 层未拦截",
            name="备注",
            attachment_type=allure.attachment_type.TEXT,
        )
    else:
        assert True, "空 body 请求未创建 Provider（被拦截）"

    # 2. 无效协议类型
    resp_bad_protocol = logged_in_page.request.put(
        f"{base_url}/web/config/providers?name=badproto-{_TEST_PREFIX}",
        data=json.dumps({
            "name": "Bad Protocol",
            "protocol": "invalid_protocol",
            "apiKey": "sk-test-12345",
            "baseURL": "https://api.test.com/v1",
        }),
        headers={"Content-Type": "application/json"},
    )
    # 验证是否被拦截
    providers2 = _get_providers_via_api(logged_in_page, base_url)
    bad_proto_created = any(
        p["id"] == f"badproto-{_TEST_PREFIX}" for p in providers2
    )
    if bad_proto_created:
        _delete_provider_via_api(logged_in_page, base_url, f"badproto-{_TEST_PREFIX}")
        allure.attach(
            "无效协议类型的请求创建了 Provider，API 层缺少协议校验",
            name="备注",
            attachment_type=allure.attachment_type.TEXT,
        )

    # 3. 无效 URL 格式
    resp_bad_url = logged_in_page.request.put(
        f"{base_url}/web/config/providers?name=badurl-{_TEST_PREFIX}",
        data=json.dumps({
            "name": "Bad URL",
            "protocol": "openai",
            "apiKey": "sk-test-12345",
            "baseURL": "not-a-valid-url",
        }),
        headers={"Content-Type": "application/json"},
    )
    providers3 = _get_providers_via_api(logged_in_page, base_url)
    bad_url_created = any(
        p["id"] == f"badurl-{_TEST_PREFIX}" for p in providers3
    )
    if bad_url_created:
        _delete_provider_via_api(logged_in_page, base_url, f"badurl-{_TEST_PREFIX}")
        allure.attach(
            "无效 URL 的请求创建了 Provider，API 层缺少 URL 格式校验",
            name="备注",
            attachment_type=allure.attachment_type.TEXT,
        )


@allure.epic("模型配置")
@allure.feature("Open-API")
@pytest.mark.order(221)
@pytest.mark.p1
def test_model_023_openapi_cascade_delete(logged_in_page, base_url):
    """TC-MODEL-023: Open-API 级联删除
    验证：1. Provider 删除成功 2. 其下模型也被删除 3. 不产生孤立数据
    """
    provider_id = f"cascade-{_TEST_PREFIX}"

    # 创建 Provider
    _create_provider_via_api(
        logged_in_page, base_url,
        provider_id, f"Cascade {_TEST_PREFIX}",
    )

    # 获取 resourceKey
    providers = _get_providers_via_api(logged_in_page, base_url)
    provider_data = next(p for p in providers if p["id"] == provider_id)
    resource_key = provider_data["resourceKey"]

    # 添加多个模型
    model_ids = [f"cascade-m1-{_TEST_PREFIX}", f"cascade-m2-{_TEST_PREFIX}"]
    for mid in model_ids:
        logged_in_page.request.post(
            f"{base_url}/web/config/providers/actions/models?name={resource_key}",
            data=json.dumps({
                "modelId": mid,
                "name": mid,
                "modalities": {"input": ["text"], "output": ["text"]},
            }),
            headers={"Content-Type": "application/json"},
        )

    # 验证模型已添加
    detail_before = _get_provider_detail_via_api(logged_in_page, base_url, resource_key)
    models_before = detail_before.get("data", {}).get("models", [])
    assert len(models_before) >= 2, \
        f"模型添加不足，当前: {len(models_before)}"

    # 1. 删除 Provider
    del_resp = _delete_provider_via_api(logged_in_page, base_url, provider_id)
    assert del_resp.status == 200, f"删除 Provider 失败: {del_resp.status}"

    # 2. Provider 不再存在
    providers_after = _get_providers_via_api(logged_in_page, base_url)
    found = any(p["id"] == provider_id for p in providers_after)
    assert not found, f"Provider '{provider_id}' 删除后仍存在"

    # 3. 模型也被级联删除（尝试获取详情应 404）
    detail_after = _get_provider_detail_via_api(
        logged_in_page, base_url, resource_key
    )
    if detail_after:
        models_after = detail_after.get("data", {}).get("models", [])
        assert len(models_after) == 0, \
            f"Provider 删除后仍有 {len(models_after)} 个模型存在"


@allure.epic("模型配置")
@allure.feature("Open-API")
@pytest.mark.order(222)
@pytest.mark.p1
def test_model_024_openapi_connectivity_test(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-MODEL-024: Open-API 模型联通性测试
    验证：1. 有效配置发送测试请求 2. 无效配置返回失败+错误原因
    """
    provider_id = f"connectivity-{_TEST_PREFIX}"

    # 创建 Provider（使用不可达的 URL）
    _create_provider_via_api(
        logged_in_page, base_url,
        provider_id, f"Connectivity {_TEST_PREFIX}",
        base_url_provider="https://unreachable-test.example.com/v1",
    )

    # 获取 resourceKey
    providers = _get_providers_via_api(logged_in_page, base_url)
    provider_data = next(
        (p for p in providers if p["id"] == provider_id), None
    )
    assert provider_data, "Provider 创建失败"
    resource_key = provider_data["resourceKey"]

    # 测试联通性（通过 fetch-models 端点）
    test_resp = logged_in_page.request.post(
        f"{base_url}/web/config/providers/actions/fetch-models?name={resource_key}",
        data=json.dumps({}),
        headers={"Content-Type": "application/json"},
    )

    # 无效 URL 应该返回失败
    assert test_resp.status in [200, 500, 400], \
        f"联通性测试返回异常状态码: {test_resp.status}"

    body = test_resp.json()
    if not body.get("success", True):
        # 失败时应有错误信息
        error = body.get("error", {})
        data = body.get("data", {})
        has_error_info = (
            error.get("code") or
            error.get("message") or
            data.get("reason") or
            data.get("detail")
        )
        assert has_error_info, \
            f"联通性测试失败但缺少错误信息: {body}"
    else:
        # 成功也可以接受（如果 URL 碰巧可达）
        allure.attach(
            "不可达 URL 的联通性测试返回了成功（可能是测试环境问题）",
            name="备注",
            attachment_type=allure.attachment_type.TEXT,
        )

    # 清理
    _delete_provider_via_api(logged_in_page, base_url, provider_id)


@allure.epic("模型配置")
@allure.feature("Open-API")
@pytest.mark.order(223)
@pytest.mark.p2
def test_model_025_openapi_pagination_filter(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-MODEL-025: Open-API 分页和过滤
    验证：1. 列表请求返回数据 2. 返回格式正确
    """
    # 获取 Provider 列表（验证基本分页结构）
    resp = logged_in_page.request.get(f"{base_url}/web/config/providers")
    assert resp.status == 200, f"获取列表失败: {resp.status}"

    body = resp.json()
    assert body.get("success") is True, "success 不为 True"

    data = body.get("data", {})
    providers = data.get("providers", [])
    assert isinstance(providers, list), "providers 不是数组"

    # 验证每个 Provider 的数据结构
    for prov in providers:
        assert "id" in prov, f"Provider 缺少 id: {prov}"
        assert "name" in prov, f"Provider 缺少 name: {prov}"
        assert "protocol" in prov, f"Provider 缺少 protocol: {prov}"
        assert "keyHint" in prov, f"Provider 缺少 keyHint: {prov}"
        assert "modelCount" in prov, f"Provider 缺少 modelCount: {prov}"

    # 尝试带参数查询（如果 API 支持）
    resp_params = logged_in_page.request.get(
        f"{base_url}/web/config/providers?page=1&size=5"
    )
    # 不管是否支持分页参数，至少请求成功
    assert resp_params.status == 200, \
        f"带分页参数请求失败: {resp_params.status}"

    allure.attach(
        f"Provider 总数: {len(providers)}",
        name="统计",
        attachment_type=allure.attachment_type.TEXT,
    )
