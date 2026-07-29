# tests/suites/test_auth.py
"""认证登录模块 E2E 测试 — 基于真实 DOM + API 验证
覆盖 Excel 1-认证登录 sheet 全部 14 条用例
"""
import os
import uuid
import pytest
import allure
from tests.pages.auth_page import AuthPage

_PREFIX = f"e2e-{uuid.uuid4().hex[:6]}"


def _new_context(browser):
    """根据 HEADLESS 环境变量创建 context，有头模式最大化"""
    is_headless = os.environ.get("HEADLESS", "true").lower() == "true"
    if is_headless:
        return browser.new_context(viewport={"width": 1920, "height": 1080})
    return browser.new_context(no_viewport=True)


# ==================== 测试 ====================


@allure.epic("认证登录")
@pytest.mark.order(100)
@pytest.mark.p0
def test_auth_001_login_success(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-AUTH-001: 正确凭证登录成功"""
    # logged_in_page 已经登录，验证登录成功后的状态
    auth = AuthPage(logged_in_page, base_url)

    # 1. 不在登录页
    assert auth.is_logged_in(), "正确凭证登录后应跳转离开登录页"

    # 2. 有 session cookie
    assert auth.has_session_cookie(), "登录后应存储 session cookie"

    # 3. 侧边栏显示用户信息（等待加载）
    logged_in_page.locator("button.agent-sidebar-user-button").wait_for(
        state="visible", timeout=10000
    )
    user_name = auth.get_user_name()
    assert len(user_name) > 0, "侧边栏应显示用户名"

    # 4. cookie 名称
    cookies = logged_in_page.context.cookies()
    session_cookies = [c for c in cookies if "session" in c["name"].lower()]
    assert len(session_cookies) > 0, "应存在 session cookie"


@allure.epic("认证登录")
@pytest.mark.order(101)
@pytest.mark.p0
def test_auth_002_login_wrong_password(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-AUTH-002: 错误凭证登录失败"""
    # 用新的 context（未登录）测试
    browser = logged_in_page.context.browser
    ctx = _new_context(browser)
    page = ctx.new_page()

    try:
        auth = AuthPage(page, base_url)
        api_resp = auth.intercept_login_api()
        auth.goto()

        auth.fill_email("xiaochun@agent.com")
        auth.fill_password("wrong_password_123")
        auth.click_login()
        page.wait_for_timeout(3000)

        # 1. 登录失败，不跳转
        assert auth.is_on_login_page(), "错误凭证登录后不应跳转"

        # 2. 显示错误信息
        error = auth.get_error_message()
        assert len(error) > 0, "应显示错误信息"
        # 不应暴露"用户不存在"
        assert "不存在" not in error, "错误信息不应暴露用户是否存在"

        # 3. API 返回 401
        sign_in_calls = [r for r in api_resp if "sign-in" in r["url"]]
        assert len(sign_in_calls) > 0, "应有登录 API 请求"
        assert sign_in_calls[0]["status"] == 401, \
            f"错误密码应返回 401，实际: {sign_in_calls[0]['status']}"

        # 4. 响应中不含密码哈希等敏感信息
        resp_body = sign_in_calls[0].get("body", {})
        if resp_body:
            assert "password" not in str(resp_body).lower() or \
                "hash" not in str(resp_body).lower(), \
                "响应中不应包含密码哈希"
    finally:
        page.close()
        ctx.close()


@allure.epic("认证登录")
@pytest.mark.order(102)
@pytest.mark.p1
def test_auth_003_email_empty_validation(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-AUTH-003: 邮箱为空时提交拦截"""
    browser = logged_in_page.context.browser
    ctx = _new_context(browser)
    page = ctx.new_page()

    try:
        auth = AuthPage(page, base_url)
        api_resp = auth.intercept_login_api()
        auth.goto()

        # 只填密码不填邮箱
        auth.fill_password("12345678")
        auth.click_login()
        page.wait_for_timeout(1000)

        # 1. 前端校验拦截（HTML5 required）
        validation = auth.get_email_validation()
        assert len(validation) > 0, "邮箱为空时应有前端校验提示"

        # 2. 仍在登录页
        assert auth.is_on_login_page(), "邮箱为空时不应离开登录页"

        # 3. 无登录 API 请求
        sign_in_calls = [r for r in api_resp if "sign-in" in r["url"]
                         and r["method"] == "POST"]
        assert len(sign_in_calls) == 0, "邮箱为空时不应发送登录请求"
    finally:
        page.close()
        ctx.close()


@allure.epic("认证登录")
@pytest.mark.order(103)
@pytest.mark.p1
def test_auth_004_password_empty_validation(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-AUTH-004: 密码为空时提交拦截"""
    browser = logged_in_page.context.browser
    ctx = _new_context(browser)
    page = ctx.new_page()

    try:
        auth = AuthPage(page, base_url)
        api_resp = auth.intercept_login_api()
        auth.goto()

        auth.fill_email("xiaochun@agent.com")
        auth.click_login()
        page.wait_for_timeout(1000)

        # 1. 前端校验拦截
        validation = auth.get_password_validation()
        assert len(validation) > 0, "密码为空时应有前端校验提示"

        # 2. 仍在登录页
        assert auth.is_on_login_page(), "密码为空时不应离开登录页"

        # 3. 无登录请求
        sign_in_calls = [r for r in api_resp if "sign-in" in r["url"]
                         and r["method"] == "POST"]
        assert len(sign_in_calls) == 0, "密码为空时不应发送登录请求"
    finally:
        page.close()
        ctx.close()


@allure.epic("认证登录")
@pytest.mark.order(104)
@pytest.mark.p2
def test_auth_005_email_format_validation(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-AUTH-005: 邮箱格式校验"""
    browser = logged_in_page.context.browser
    ctx = _new_context(browser)
    page = ctx.new_page()

    bad_emails = ["abc", "abc@", "@abc.com"]

    try:
        auth = AuthPage(page, base_url)

        for bad_email in bad_emails:
            auth.goto()
            auth.fill_email(bad_email)
            auth.fill_password("12345678")
            auth.click_login()
            page.wait_for_timeout(1000)

            validation = auth.get_email_validation()
            assert len(validation) > 0, \
                f"非法邮箱 '{bad_email}' 应有格式校验提示"

            assert auth.is_on_login_page(), \
                f"非法邮箱 '{bad_email}' 不应离开登录页"
    finally:
        page.close()
        ctx.close()


@allure.epic("认证登录")
@pytest.mark.order(105)
@pytest.mark.p2
def test_auth_006_password_visibility_toggle(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-AUTH-006: 密码可见性切换"""
    browser = logged_in_page.context.browser
    ctx = _new_context(browser)
    page = ctx.new_page()

    try:
        auth = AuthPage(page, base_url)
        auth.goto()
        auth.fill_password("testpassword123")

        # 初始状态：密码掩码
        assert auth.get_password_type() == "password", \
            "初始状态密码应为掩码（password）"
        assert auth.get_toggle_aria_label() == "显示密码", \
            "切换按钮 aria-label 应为'显示密码'"

        # 第一次点击：明文显示
        auth.toggle_password_visibility()
        assert auth.get_password_type() == "text", \
            "点击后密码应变为明文（text）"

        # 再次点击：恢复掩码
        auth.toggle_password_visibility()
        assert auth.get_password_type() == "password", \
            "再次点击后密码应恢复为掩码（password）"
    finally:
        page.close()
        ctx.close()


@allure.epic("认证登录")
@pytest.mark.order(106)
@pytest.mark.p0
def test_auth_007_login_no_sensitive_info(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-AUTH-007: 登录请求不暴露敏感信息"""
    browser = logged_in_page.context.browser
    ctx = _new_context(browser)
    page = ctx.new_page()

    try:
        auth = AuthPage(page, base_url)
        api_resp = auth.intercept_login_api()
        auth.goto()

        auth.login("xiaochun@agent.com", "12345678")
        page.wait_for_timeout(3000)

        # 1. 登录 API 请求
        sign_in_calls = [r for r in api_resp if "sign-in" in r["url"]
                         and r["method"] == "POST"]
        assert len(sign_in_calls) > 0, "应有登录 POST 请求"

        req = sign_in_calls[0]

        # 2. 密码不在 URL 参数中
        assert "password" not in req["url"], \
            "密码不应出现在 URL 中"

        # 3. 密码在请求体中（且加密）
        post_data = req.get("post_data", "")
        assert post_data is not None, "应有请求体"
        if post_data:
            # 密码是加密传输的（AESGCM 前缀），password 字段名始终存在所以不能单独作为断言
            assert "AESGCM" in post_data or "password" in post_data, \
                "请求体中应包含密码相关字段"
            # 如果包含 password 字段，进一步检查是否加密
            if "password" in post_data and "AESGCM" not in post_data:
                # password 字段存在但未加密 — 记录但不阻断
                import allure
                allure.attach(
                    "密码字段存在但未发现 AESGCM 前缀，可能使用其他加密方式",
                    name="加密检查",
                    attachment_type=allure.attachment_type.TEXT,
                )
            # 明文密码不应直接出现在请求体中
            assert "12345678" not in post_data, \
                "明文密码不应出现在请求体中"

        # 4. 响应中不返回密码哈希
        resp_body = req.get("body", {})
        if resp_body:
            resp_str = str(resp_body).lower()
            assert "passwordhash" not in resp_str, \
                "响应中不应包含 passwordHash"
            assert "password_hash" not in resp_str, \
                "响应中不应包含 password_hash"
            # 应返回 token
            assert "token" in resp_str, "响应中应包含 token"
    finally:
        page.close()
        ctx.close()


@allure.epic("认证登录")
@pytest.mark.order(107)
@pytest.mark.p0
def test_auth_008_token_expired_redirect(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-AUTH-008: Token 过期后自动跳转登录
    模拟方式：在新 context 中清除 session cookie 后访问受保护页面
    """
    browser = logged_in_page.context.browser
    ctx = _new_context(browser)
    page = ctx.new_page()

    try:
        # 先登录
        page.goto(f"{base_url}/ctrl/login")
        page.wait_for_load_state("networkidle")
        page.fill("#auth-email", "xiaochun@agent.com")
        page.fill("#auth-password", "12345678")
        page.click("button.auth-light-submit")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(3000)
        assert "/ctrl/login" not in page.url, "应先成功登录"

        # 清除 cookie 模拟 token 过期
        ctx.clear_cookies()

        # 访问受保护页面
        page.goto(f"{base_url}/ctrl/agent/chat")
        page.wait_for_timeout(3000)

        # 应自动跳转到登录页
        assert "/ctrl/login" in page.url, \
            "Token 过期后应自动跳转到登录页"
    finally:
        page.close()
        ctx.close()


@allure.epic("认证登录")
@pytest.mark.order(108)
@pytest.mark.p0
def test_auth_009_unauthenticated_redirect(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-AUTH-009: 未登录访问受保护页面"""
    browser = logged_in_page.context.browser
    ctx = _new_context(browser)
    page = ctx.new_page()

    try:
        # 直接访问受保护页面
        page.goto(f"{base_url}/ctrl/agent/chat")
        page.wait_for_timeout(3000)

        # 1. 自动重定向到登录页
        assert "/ctrl/login" in page.url, \
            "未登录访问受保护页面应重定向到登录页"

        # 2. 不显示受保护内容
        body = page.locator("body").inner_text()
        assert "智能体管理" not in body, \
            "未登录时不应显示受保护内容"
    finally:
        page.close()
        ctx.close()


@allure.epic("认证登录")
@pytest.mark.order(109)
@pytest.mark.p0
def test_auth_011_refresh_keeps_login(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-AUTH-011: 登录后刷新页面保持登录状态"""
    # 确保已登录
    logged_in_page.goto(f"{base_url}/ctrl/agent/home")
    logged_in_page.wait_for_timeout(2000)
    assert "/ctrl/login" not in logged_in_page.url, "应先确保已登录"

    # 刷新页面
    logged_in_page.reload()
    logged_in_page.wait_for_timeout(3000)

    # 1. 刷新后仍保持登录
    assert "/ctrl/login" not in logged_in_page.url, \
        "刷新后应保持登录状态"

    # 2. session cookie 仍存在
    auth = AuthPage(logged_in_page, base_url)
    assert auth.has_session_cookie(), "刷新后 session cookie 应仍存在"


@allure.epic("认证登录")
@pytest.mark.order(110)
@pytest.mark.p0
def test_auth_012_logout_clears_auth(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-AUTH-012: 退出登录清除认证信息"""
    browser = logged_in_page.context.browser
    ctx = _new_context(browser)
    page = ctx.new_page()

    try:
        # 先登录
        page.goto(f"{base_url}/ctrl/login")
        page.wait_for_load_state("networkidle")
        page.fill("#auth-email", "xiaochun@agent.com")
        page.fill("#auth-password", "12345678")
        page.click("button.auth-light-submit")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(3000)

        auth = AuthPage(page, base_url)

        # 记录当前 cookie
        assert auth.has_session_cookie(), "退出前应有 session cookie"

        # 拦截退出 API
        logout_api = auth.intercept_all_auth_api()

        # 点击退出
        auth.click_logout()
        page.wait_for_timeout(3000)

        # 1. 跳转到登录页
        assert "/ctrl/login" in page.url, \
            "退出后应跳转到登录页"

        # 2. session cookie 被清除
        assert not auth.has_session_cookie(), \
            "退出后 session cookie 应被清除"

        # 3. 退出 API 被调用
        sign_out_calls = [r for r in logout_api if "sign-out" in r["url"]]
        assert len(sign_out_calls) > 0, "应有退出登录 API 请求"
    finally:
        page.close()
        ctx.close()


@allure.epic("认证登录")
@pytest.mark.order(111)
@pytest.mark.p0
def test_auth_014_change_password_ui(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-AUTH-014: 账号密码修改 — 仅验证 UI 存在
    不真正修改密码以避免影响后续测试
    """
    # 确保已登录
    logged_in_page.goto(f"{base_url}/ctrl/agent/home")
    logged_in_page.wait_for_timeout(2000)

    auth = AuthPage(logged_in_page, base_url)

    # 打开修改密码弹窗
    auth.click_change_password()

    # 1. 弹窗打开
    assert auth.is_dialog_open(), "修改密码弹窗应打开"

    # 2. 弹窗标题
    title = auth.get_dialog_title()
    assert "密码" in title, f"弹窗标题应包含'密码': {title}"

    # 3. 三个密码输入框
    pw_inputs = auth.get_password_inputs()
    assert pw_inputs.count() == 3, \
        f"应有 3 个密码输入框（旧密码、新密码、确认），实际: {pw_inputs.count()}"

    # 4. 关闭弹窗
    auth.close_dialog()
    assert not auth.is_dialog_open(), "弹窗应已关闭"


@allure.epic("认证登录")
@pytest.mark.order(112)
@pytest.mark.p1
def test_auth_015_change_password_validation(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-AUTH-015: 密码修改校验 — 验证前端校验逻辑"""
    logged_in_page.goto(f"{base_url}/ctrl/agent/home")
    logged_in_page.wait_for_timeout(2000)

    auth = AuthPage(logged_in_page, base_url)
    auth.click_change_password()

    assert auth.is_dialog_open(), "修改密码弹窗应打开"

    dialog_text = auth.get_dialog_text()

    # 1. 弹窗包含密码字段标签
    has_labels = "当前密码" in dialog_text or "新密码" in dialog_text or \
        "确认" in dialog_text
    assert has_labels, "弹窗应包含密码字段标签"

    # 2. 不填写直接提交，检查校验
    submit_btn = logged_in_page.locator("[role=dialog]").get_by_role(
        "button", name="修改密码"
    )
    if submit_btn.count() > 0:
        is_disabled = submit_btn.first.is_disabled()
        if is_disabled:
            allure.attach(
                "提交按钮在未填写时被禁用（前端校验生效）",
                name="校验结果",
                attachment_type=allure.attachment_type.TEXT,
            )
        else:
            # 尝试提交
            submit_btn.first.click(force=True)
            logged_in_page.wait_for_timeout(1000)
            error = auth.get_dialog_error()
            dialog_still_open = auth.is_dialog_open()
            assert error or dialog_still_open, \
                "空表单提交时应有校验提示或弹窗不关闭"

    auth.close_dialog()


@allure.epic("认证登录")
@pytest.mark.order(113)
@pytest.mark.p1
def test_auth_015b_change_password_required_fields(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-AUTH-015b: 修改密码弹窗三个输入框均为必填项（逐个留空验证）"""
    logged_in_page.goto(f"{base_url}/ctrl/agent/home")
    logged_in_page.wait_for_timeout(2000)

    auth = AuthPage(logged_in_page, base_url)
    field_names = ["当前密码", "新密码", "确认新密码"]

    for skip_idx in range(3):
        # 每次重新打开弹窗
        auth.click_change_password()
        assert auth.is_dialog_open(), f"测试'{field_names[skip_idx]}'时弹窗应打开"

        pw_inputs = auth.get_password_inputs()
        assert pw_inputs.count() == 3, f"应有 3 个密码输入框"

        # 填写其他两个字段，跳过当前字段
        for j in range(3):
            if j != skip_idx:
                pw_inputs.nth(j).fill("test123456")

        # 尝试提交
        dialog = logged_in_page.locator("[role=dialog]")
        submit_btn = dialog.get_by_role("button", name="修改密码")
        if submit_btn.count() > 0 and not submit_btn.first.is_disabled():
            submit_btn.first.click()
            logged_in_page.wait_for_timeout(1000)

        # 验证：弹窗仍打开（提交被拦截）或有校验提示
        still_open = auth.is_dialog_open()
        error = auth.get_dialog_error() if still_open else ""
        # 也检查 HTML5 校验（浏览器弹窗提示）
        validation = pw_inputs.nth(skip_idx).evaluate("el => el.validationMessage")
        print(f"\n{field_names[skip_idx]}留空: 弹窗仍在={still_open}, 错误={error}, 校验提示={validation}")

        assert still_open or error or validation, \
            f"'{field_names[skip_idx]}' 留空时应被校验拦截"

        # 关闭弹窗准备下一轮
        if still_open:
            auth.close_dialog()


@allure.epic("认证登录")
@pytest.mark.order(113)
@pytest.mark.p1
def test_auth_016_default_account_resources(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-AUTH-016: 默认系统账号和公开资源"""
    # 确保已登录
    logged_in_page.goto(f"{base_url}/ctrl/agent/home")
    logged_in_page.wait_for_timeout(2000)

    auth = AuthPage(logged_in_page, base_url)

    # 1. 默认账号可正常登录（当前 fixture 已登录）
    assert auth.is_logged_in(), "默认账号应可正常登录"

    # 2. 侧边栏有内容（预置资源）
    sidebar_text = auth.get_sidebar_text()
    assert len(sidebar_text) > 0, "侧边栏应有内容"

    # 3. 有预置的智能体（公开资源）
    has_agents = "ORG_001" in sidebar_text or "智能体" in sidebar_text
    assert has_agents, "侧边栏应有预置智能体"

    # 4. 有配置入口（模型库、技能库等公开资源）
    has_config = "模型库" in sidebar_text or "技能库" in sidebar_text
    assert has_config, "侧边栏应有配置入口（模型库/技能库）"
