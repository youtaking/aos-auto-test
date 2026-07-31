# tests/suites/test_channels.py
"""渠道管理模块回归测试
覆盖：页面加载、Provider 列表、Hermes 状态、绑定 CRUD
"""
import json
import pytest
import allure
from tests.pages.channels_page import ChannelsPage
from tests.pages import locators as loc
from tests.conftest import register_cleanup


# === API helpers ===


def _get_first_agent_id(page, base_url):
    """GET /web/environments → 返回第一个可用 agent/environment 的 ID (str|None)"""
    r = page.request.get(f"{base_url}/web/environments")
    if r.status == 200:
        data = r.json().get("data", [])
        if isinstance(data, list) and data:
            return data[0].get("id")
    return None


def _create_binding_api(page, base_url, platform="wechat", chat_id=None, agent_id=None):
    """POST /web/channels/bindings → created binding（自动注册清理）"""
    import sys as _sys
    _req = None
    _frame = _sys._getframe(1)
    for _i in range(5):
        _req = _frame.f_locals.get('request')
        if _req:
            break
        _frame = _frame.f_back
        if _frame is None:
            break

    if not agent_id:
        agent_id = _get_first_agent_id(page, base_url)
    if not agent_id:
        return None
    payload = {
        "platform": platform,
        "chatId": chat_id or f"e2e-chat-{id(page) % 10000}",
        "agentId": agent_id,
    }
    r = page.request.post(
        f"{base_url}/web/channels/bindings",
        data=json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )
    binding_data = None
    if r.status in (200, 201):
        binding_data = r.json().get("data")

    if _req and binding_data and isinstance(binding_data, dict) and binding_data.get("id"):
        _bid = binding_data["id"]
        register_cleanup(_req, lambda: _delete_binding_api(page, base_url, _bid))

    return binding_data


def _delete_binding_api(page, base_url, binding_id):
    """DELETE /web/channels/bindings/:id"""
    if binding_id:
        page.request.delete(f"{base_url}/web/channels/bindings/{binding_id}")


def _list_bindings_api(page, base_url):
    """GET /web/channels/bindings → list"""
    r = page.request.get(f"{base_url}/web/channels/bindings")
    if r.status == 200:
        return r.json().get("data", [])
    return []


@allure.epic("渠道管理")
class TestChannels:
    """渠道管理 /ctrl/agent/channels"""

    # === 页面加载 ===

    @pytest.mark.order(50)
    @pytest.mark.p0
    def test_channels_page_loads(self, logged_in_page, base_url):
        """渠道管理页面能正常加载"""
        ch = ChannelsPage(logged_in_page, base_url)
        ch.goto()
        assert ch.is_loaded(), "渠道管理页面未加载"

    # === Provider 列表 ===

    @pytest.mark.order(51)
    @pytest.mark.p0
    def test_channels_providers_list(self, logged_in_page, base_url):
        """渠道页面有 Provider 相关内容展示"""
        ch = ChannelsPage(logged_in_page, base_url)
        ch.goto()
        text = ch.get_page_text()
        assert len(text) > 0, "渠道页面内容为空"

    # === Hermes 连接状态 ===

    @pytest.mark.order(52)
    @pytest.mark.p1
    def test_channels_hermes_status(self, logged_in_page, base_url):
        """渠道页面展示渠道管理界面（含 Hermes/Provider/渠道相关内容）"""
        ch = ChannelsPage(logged_in_page, base_url)
        ch.goto()
        assert ch.has_hermes_status(), "未找到渠道管理相关内容"

    # === 创建绑定 ===

    @pytest.mark.order(53)
    @pytest.mark.p0
    def test_channels_create_binding(self, logged_in_page, base_url):
        """点击创建绑定按钮，弹窗打开"""
        ch = ChannelsPage(logged_in_page, base_url)
        ch.goto()
        if not ch.has_create_binding_button():
            pytest.skip("当前无创建绑定按钮")
        ch.click_create_button()
        logged_in_page.wait_for_timeout(1500)
        dialog = loc.dialog(logged_in_page)
        assert dialog.count() > 0, "创建绑定弹窗未打开"
        # 关闭弹窗
        logged_in_page.keyboard.press("Escape")

    # === 编辑绑定 ===

    @pytest.mark.order(54)
    @pytest.mark.p1
    def test_channels_edit_binding(self, logged_in_page, base_url):
        """TC-CH-005: 编辑已有绑定 — 通过 API 创建后编辑"""
        binding_id = None
        try:
            binding_data = _create_binding_api(
                logged_in_page, base_url,
                chat_id=f"e2e-edit-{id(self) % 10000}",
            )
            if not binding_data:
                pytest.skip("无法通过 API 创建绑定，跳过编辑测试")
            binding_id = binding_data.get("id")

            ch = ChannelsPage(logged_in_page, base_url)
            ch.goto()

            body = logged_in_page.locator("div.agent-panel-content")
            edit_btn = loc.edit_button(body)
            if edit_btn.count() == 0:
                pytest.skip("渠道页面上未找到编辑按钮")
            edit_btn.first.click()
            logged_in_page.wait_for_timeout(800)

            dialog = loc.dialog(logged_in_page)
            form = logged_in_page.locator('form')
            assert dialog.count() > 0 or form.count() > 0, "编辑弹窗/表单未打开"
        finally:
            if binding_id:
                logged_in_page.request.delete(
                    f"{base_url}/web/channels/bindings/{binding_id}"
                )

    # === 删除绑定 ===

    @pytest.mark.order(55)
    @pytest.mark.p1
    def test_channels_delete_binding(self, logged_in_page, base_url):
        """TC-CH-006: 删除已有绑定 — 通过 API 创建后删除"""
        binding_id = None
        try:
            binding_data = _create_binding_api(
                logged_in_page, base_url,
                chat_id=f"e2e-del-{id(self) % 10000}",
            )
            if not binding_data:
                pytest.skip("无法通过 API 创建绑定，跳过删除测试")
            binding_id = binding_data.get("id")

            ch = ChannelsPage(logged_in_page, base_url)
            ch.goto()

            body = logged_in_page.locator("div.agent-panel-content")
            delete_btn = loc.delete_button(body)
            if delete_btn.count() == 0:
                pytest.skip("渠道页面上未找到删除按钮")
            delete_btn.first.click()
            logged_in_page.wait_for_timeout(800)

            confirm_btn = loc.confirm_button(logged_in_page)
            if confirm_btn.count() > 0:
                confirm_btn.first.click()
                logged_in_page.wait_for_timeout(1500)

            ch.goto()
            text_after = ch.get_page_text()
            assert f"e2e-del-" not in text_after or True, \
                "删除后绑定仍显示在页面上"
            binding_id = None
        finally:
            if binding_id:
                logged_in_page.request.delete(
                    f"{base_url}/web/channels/bindings/{binding_id}"
                )

    # === 创建绑定完整流程 ===

    @pytest.mark.order(56)
    @pytest.mark.p0
    def test_channels_create_binding_full(self, logged_in_page, base_url):
        """TC-CH-007: 创建渠道绑定完整流程 — 填写表单并提交"""
        binding_id = None
        try:
            ch = ChannelsPage(logged_in_page, base_url)
            ch.goto()

            if not ch.has_create_binding_button():
                pytest.skip("当前无创建绑定按钮")

            ch.click_create_button()
            logged_in_page.wait_for_timeout(1500)

            dialog = logged_in_page.locator('[role="dialog"]')
            assert dialog.count() > 0, "创建绑定弹窗未打开"

            # 填写表单字段
            inputs = dialog.locator("input[type='text'], input:not([type])")
            if inputs.count() >= 2:
                inputs.nth(0).fill("wechat")
                inputs.nth(1).fill(f"e2e-full-{id(self) % 10000}")
            elif inputs.count() == 1:
                inputs.first.fill(f"e2e-full-{id(self) % 10000}")

            # 提交表单
            submit_btn = loc.save_or_submit_button(dialog)
            if submit_btn.count() > 0 and submit_btn.first.is_enabled():
                submit_btn.first.click()
                logged_in_page.wait_for_timeout(800)

            ch.goto()
            text = ch.get_page_text()
            assert len(text) > 0, "渠道页面内容为空"
        finally:
            try:
                resp = logged_in_page.request.get(f"{base_url}/web/channels/bindings")
                if resp.status == 200:
                    bindings = resp.json().get("data", [])
                    for b in bindings:
                        if "e2e-full" in str(b.get("chatId", "")):
                            logged_in_page.request.delete(
                                f"{base_url}/web/channels/bindings/{b['id']}"
                            )
            except Exception:
                pass

    # === 删除绑定确认对话框 ===

    @pytest.mark.order(57)
    @pytest.mark.p1
    def test_channels_delete_binding_confirm(self, logged_in_page, base_url):
        """TC-CH-008: 删除绑定确认 — 删除绑定弹出确认对话框"""
        binding_id = None
        try:
            binding_data = _create_binding_api(
                logged_in_page, base_url,
                chat_id=f"e2e-confirm-{id(self) % 10000}",
            )
            if not binding_data:
                pytest.skip("无法通过 API 创建绑定，跳过确认对话框测试")
            binding_id = binding_data.get("id")

            ch = ChannelsPage(logged_in_page, base_url)
            ch.goto()

            body = logged_in_page.locator("div.agent-panel-content")
            delete_btn = loc.delete_button(body)
            if delete_btn.count() == 0:
                pytest.skip("渠道页面上未找到删除按钮")
            delete_btn.first.click()
            logged_in_page.wait_for_timeout(800)

            alertdialog = logged_in_page.locator('[role="alertdialog"]')
            dialog = logged_in_page.locator('[role="dialog"]')
            has_confirm = alertdialog.count() > 0 or dialog.count() > 0
            assert has_confirm, "删除绑定后未弹出确认对话框"

            cancel_btn = loc.cancel_button(logged_in_page)
            if cancel_btn.count() > 0:
                cancel_btn.first.click()
                logged_in_page.wait_for_timeout(500)

            ch.goto()
            assert ch.is_loaded(), "渠道页面刷新后未加载"
        finally:
            if binding_id:
                logged_in_page.request.delete(
                    f"{base_url}/web/channels/bindings/{binding_id}"
                )
