# tests/suites/test_views.py
"""产品视图模块回归测试
覆盖：页面加载、列表数据、CRUD 操作、详情页
"""
import json
import uuid
import pytest
import allure
from tests.pages.views_page import ViewsPage
from tests.pages import locators as loc
from tests.conftest import register_cleanup


_PREFIX = f"e2e-{uuid.uuid4().hex[:6]}"


# === API helpers ===


def _list_views_api(page, base_url):
    """GET /web/config/prod-views → list of views"""
    r = page.request.get(f"{base_url}/web/config/prod-views")
    if r.status == 200:
        body = r.json()
        data = body.get("data", [])
        if isinstance(data, dict):
            return data.get("items", [])
        return data
    return []


def _get_first_agent_id(page, base_url):
    """GET /web/config/agents → 返回第一个可用 agent ID（用于创建视图的必填字段 agentId）"""
    r = page.request.get(f"{base_url}/web/config/agents")
    if r.status == 200:
        body = r.json().get("data", {})
        if isinstance(body, dict):
            agents = body.get("agents", [])
            if isinstance(agents, list) and agents:
                return agents[0].get("id")
    return None


def _create_view_api(page, base_url, name=None, description="e2e test view"):
    """POST /web/config/prod-views → created view（自动注册清理）

    源码 schema (CreateProdViewSchema):
      name (必填), agentId (必填, UUID), description?, modulesConfig?
    """
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

    name = name or f"e2e-view-{_PREFIX}"
    agent_id = _get_first_agent_id(page, base_url)
    if not agent_id:
        return {}
    payload = {
        "name": name,
        "agentId": agent_id,
        "description": description,
    }
    r = page.request.post(
        f"{base_url}/web/config/prod-views",
        data=json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )
    view_data = {}
    if r.status in (200, 201):
        body = r.json()
        view_data = body.get("data", {})

    if _req and view_data.get("id"):
        _vid = view_data["id"]
        register_cleanup(_req, lambda: _delete_view_api(page, base_url, _vid))

    return view_data


def _delete_view_api(page, base_url, view_id):
    """DELETE /web/config/prod-views/:id"""
    if view_id:
        page.request.delete(f"{base_url}/web/config/prod-views/{view_id}")


def _get_or_create_view(page, base_url):
    """获取第一个视图 ID，若无则创建一个。返回 (view_id, created_flag)"""
    views = _list_views_api(page, base_url)
    if views:
        return views[0].get("id"), False
    view = _create_view_api(page, base_url)
    return view.get("id"), True


@allure.epic("产品视图")
class TestViews:
    """产品视图 /ctrl/agent/views"""

    # === 页面加载 ===

    @pytest.mark.order(60)
    @pytest.mark.p0
    def test_views_page_loads(self, logged_in_page, base_url):
        """产品视图页面能正常加载"""
        v = ViewsPage(logged_in_page, base_url)
        v.goto()
        assert v.is_loaded(), "产品视图页面未加载"

    # === 列表数据 ===

    @pytest.mark.order(61)
    @pytest.mark.p0
    def test_views_list_data(self, logged_in_page, base_url):
        """产品视图页面有内容展示"""
        v = ViewsPage(logged_in_page, base_url)
        v.goto()

        # 全量回归：发布视图 tab 内容可能未加载，重新点击 tab 激活（最多 4 轮）
        for _retry in range(4):
            has_title = logged_in_page.get_by_role("button", name="发布视图").count() > 0
            has_views = v.get_view_count() > 0
            has_empty = logged_in_page.get_by_text("点击 + 创建发布视图").count() > 0
            if has_title and (has_views or has_empty):
                break
            # 重新点击「发布视图」tab
            tab_btn = logged_in_page.get_by_role("button", name="发布视图")
            if tab_btn.count() > 0:
                tab_btn.first.click(force=True)
                logged_in_page.wait_for_timeout(1500)
            else:
                # tab 按钮都找不到，面板可能折叠了，goto 重试
                v.goto()
                logged_in_page.wait_for_timeout(1000)

        assert has_title, "缺少「发布视图」Tab"
        assert has_views or has_empty, "既没有视图列表也没有空状态提示"

    # === 创建视图 ===

    @pytest.mark.order(62)
    @pytest.mark.p0
    def test_views_create(self, logged_in_page, base_url):
        """点击新建按钮，验证弹窗/表单打开"""
        v = ViewsPage(logged_in_page, base_url)
        v.goto()

        # 必须有创建按钮
        assert v.has_create_button(), "缺少创建视图按钮"

        v.click_create_button()

        # 验证弹窗打开
        dialog = logged_in_page.locator('[role="dialog"]')
        try:
            dialog.first.wait_for(state="visible", timeout=5000)
        except Exception:
            pytest.fail("创建视图弹窗未打开")

        # 验证弹窗内容
        dialog_text = dialog.first.inner_text()
        assert "名称" in dialog_text, "弹窗缺少名称字段"
        assert "保存" in dialog_text or "创建" in dialog_text, "弹窗缺少提交按钮"

        # 关闭弹窗
        cancel = dialog.locator("button").filter(has_text="取消")
        if cancel.count() > 0:
            cancel.first.wait_for(state="visible", timeout=5000)
            cancel.first.click()
        else:
            logged_in_page.keyboard.press("Escape")

    # === 编辑视图 ===

    @pytest.mark.order(63)
    @pytest.mark.p1
    def test_views_edit(self, logged_in_page, base_url):
        """TC-VIEW-004: 编辑视图 — 修改名称并验证保存生效"""
        # 前置：通过 API 创建视图
        view = _create_view_api(logged_in_page, base_url)
        view_id = view.get("id")
        original_name = view.get("name", "")
        if not view_id:
            pytest.skip("无法创建视图")
        try:
            v = ViewsPage(logged_in_page, base_url)
            v.goto()

            # 等待视图卡片加载
            cards = logged_in_page.locator("div.rounded-lg.border")
            try:
                cards.first.wait_for(state="visible", timeout=5000)
            except Exception:
                pytest.fail("视图卡片未加载")

            # 定位当前视图的卡片（按名称匹配）
            card = cards.filter(has_text=original_name)
            if card.count() == 0:
                card = cards  # fallback 到第一个
            first_card = card.first

            # 点击编辑按钮（Pencil 图标）
            edit_btn = first_card.locator("button").filter(
                has=logged_in_page.locator("svg.lucide-pencil")
            )
            assert edit_btn.count() > 0, "视图卡片内缺少编辑按钮"
            edit_btn.first.click()

            # 验证编辑弹窗打开
            dialog = logged_in_page.locator('[role="dialog"]')
            try:
                dialog.first.wait_for(state="visible", timeout=5000)
            except Exception:
                pytest.fail("编辑弹窗未打开")

            # 修改名称
            new_name = f"e2e-edit-{_PREFIX}"
            name_input = dialog.locator("input").first
            name_input.wait_for(state="visible", timeout=5000)
            name_input.fill(new_name)

            # 点击保存
            save_btn = dialog.locator("button").filter(has_text="保存")
            assert save_btn.count() > 0, "编辑弹窗缺少保存按钮"
            save_btn.first.wait_for(state="visible", timeout=5000)
            save_btn.first.click()

            # 等待弹窗关闭（保存完成）
            try:
                dialog.first.wait_for(state="hidden", timeout=8000)
            except Exception:
                pass

            # 验证名称已更新 — 页面上能找到新名称
            try:
                logged_in_page.locator("span").filter(has_text=new_name).first.wait_for(
                    state="visible", timeout=5000
                )
            except Exception:
                pytest.fail(f"编辑保存后，视图名称未更新为 '{new_name}'")

            # 通过 API 恢复原名称（清理）
            if original_name:
                logged_in_page.request.put(
                    f"{base_url}/web/config/prod-views/{view_id}",
                    data=json.dumps({"name": original_name}),
                    headers={"Content-Type": "application/json"},
                )
        finally:
            _delete_view_api(logged_in_page, base_url, view_id)

    # === 删除视图 ===

    @pytest.mark.order(64)
    @pytest.mark.p1
    def test_views_delete(self, logged_in_page, base_url):
        """TC-VIEW-005: 删除视图 — 点击删除按钮并确认，验证视图被移除"""
        # 前置：API 创建临时视图
        view_name = f"e2e-del-view-{_PREFIX}"
        view = _create_view_api(logged_in_page, base_url, name=view_name)
        view_id = view.get("id")
        if not view_id:
            pytest.skip("无法创建视图用于删除测试")
        try:
            v = ViewsPage(logged_in_page, base_url)
            v.goto()

            # 全量回归：发布视图 tab 内容可能未加载，重新点击 tab 激活
            for _retry in range(4):
                cards = logged_in_page.locator("div.rounded-lg.border")
                # 确认当前是「发布视图」tab（有标题或有视图卡片或空状态）
                has_title = logged_in_page.get_by_text("发布视图").count() > 0
                has_cards = cards.count() > 0
                has_empty = logged_in_page.get_by_text("暂无发布视图").count() > 0
                if has_title and (has_cards or has_empty):
                    break
                tab_btn = logged_in_page.get_by_role("button", name="发布视图")
                if tab_btn.count() > 0:
                    tab_btn.first.click(force=True)
                    logged_in_page.wait_for_timeout(1500)
                else:
                    v.goto()
                    logged_in_page.wait_for_timeout(1000)

            # 等待视图卡片加载
            cards = logged_in_page.locator("div.rounded-lg.border")
            try:
                cards.first.wait_for(state="visible", timeout=8000)
            except Exception:
                pytest.fail("视图卡片未加载")

            initial_count = cards.count()

            # 定位目标视图卡片（API 刚创建，UI 可能未刷新，轮询等待）
            card = cards.filter(has_text=view_name)
            if card.count() == 0:
                for _poll in range(6):
                    logged_in_page.wait_for_timeout(1500)
                    cards = logged_in_page.locator("div.rounded-lg.border")
                    card = cards.filter(has_text=view_name)
                    if card.count() > 0:
                        break
                else:
                    pytest.fail(f"未找到名称为 '{view_name}' 的视图卡片（已轮询等待）")

            # 点击删除按钮（Trash2 图标 + "删除"文字）
            delete_btn = card.first.locator("button").filter(
                has=logged_in_page.locator("svg.lucide-trash-2")
            )
            assert delete_btn.count() > 0, "视图卡片内缺少删除按钮"
            delete_btn.first.wait_for(state="visible", timeout=5000)
            delete_btn.first.click()

            # 确认弹窗出现（ConfirmDialog → alertdialog）
            alert = logged_in_page.locator('[role="alertdialog"]')
            try:
                alert.first.wait_for(state="visible", timeout=5000)
            except Exception:
                pytest.fail("删除确认弹窗未出现")

            # 点击确认
            confirm_btn = alert.locator("button").filter(
                has_text="确认"
            ).or_(alert.locator("button").filter(has_text="确定"))
            assert confirm_btn.count() > 0, "确认弹窗缺少确认按钮"
            confirm_btn.first.wait_for(state="visible", timeout=5000)
            confirm_btn.first.click()

            # 等待弹窗关闭 + 列表刷新
            try:
                alert.first.wait_for(state="hidden", timeout=8000)
            except Exception:
                pass

            # 验证视图已被移除（按名称查找不到）
            logged_in_page.wait_for_timeout(1000)
            remaining = logged_in_page.locator("div.rounded-lg.border").filter(
                has_text=view_name
            )
            assert remaining.count() == 0, \
                f"删除后视图 '{view_name}' 仍在列表中"
            view_id = None  # 已被 UI 删除
        finally:
            if view_id:
                _delete_view_api(logged_in_page, base_url, view_id)

    # === 详情页 ===

    @pytest.mark.order(65)
    @pytest.mark.p1
    def test_views_detail_page(self, logged_in_page, base_url):
        """TC-VIEW-006: 打开视图 — 点击卡片上的「打开视图」按钮，验证新标签页打开"""
        view = _create_view_api(logged_in_page, base_url)
        view_id = view.get("id")
        view_name = view.get("name", "")
        if not view_id:
            pytest.skip("无法创建视图")
        new_page = None
        try:
            v = ViewsPage(logged_in_page, base_url)
            v.goto()

            # 等待视图卡片加载
            cards = logged_in_page.locator("div.rounded-lg.border")
            try:
                cards.first.wait_for(state="visible", timeout=5000)
            except Exception:
                pytest.fail("视图卡片未加载")

            # 定位目标视图卡片
            card = cards.filter(has_text=view_name)
            if card.count() == 0:
                card = cards
            first_card = card.first

            # 点击「打开视图」按钮（ExternalLink 图标）
            open_btn = first_card.locator("button").filter(
                has=logged_in_page.locator("svg.lucide-external-link")
            )
            assert open_btn.count() > 0, "视图卡片内缺少「打开视图」按钮"

            # 点击后会打开新标签页
            with logged_in_page.context.expect_page() as new_page_info:
                open_btn.first.wait_for(state="visible", timeout=5000)
                open_btn.first.click()
            new_page = new_page_info.value
            new_page.wait_for_load_state("domcontentloaded")

            # 验证新标签页 URL 包含 /view/
            new_url = new_page.url
            assert "/view/" in new_url, f"打开视图后 URL 不包含 /view/: {new_url}"

            # 等待页面渲染（ProdViewPage 需要 API 加载）
            header = new_page.locator("div.agent-panel-layout")
            try:
                header.first.wait_for(state="visible", timeout=10000)
            except Exception:
                pass

            # 等待文本渲染完成
            try:
                new_page.locator("span.font-medium").first.wait_for(
                    state="visible", timeout=5000
                )
            except Exception:
                pass

            # 验证页面有内容（header 含视图名称或 "FenixAgent"）
            body_text = new_page.locator("body").inner_text()
            assert len(body_text.strip()) > 0, "打开视图后页面内容为空"
        finally:
            if new_page:
                try:
                    new_page.close()
                except Exception:
                    pass
            _delete_view_api(logged_in_page, base_url, view_id)

    # === 新增测试 ===

    @pytest.mark.order(510)
    @pytest.mark.p1
    def test_view_module_config_switches(self, logged_in_page, base_url):
        """TC-VIEW-007: 模块配置开关 — 编辑弹窗中有面板开关且可切换"""
        view = _create_view_api(logged_in_page, base_url)
        view_id = view.get("id")
        view_name = view.get("name", "")
        if not view_id:
            pytest.skip("无法创建视图")
        try:
            v = ViewsPage(logged_in_page, base_url)
            v.goto()

            # 等待视图卡片加载
            cards = logged_in_page.locator("div.rounded-lg.border")
            try:
                cards.first.wait_for(state="visible", timeout=5000)
            except Exception:
                pytest.fail("视图卡片未加载")

            # 定位卡片，点击编辑按钮（Pencil 图标）
            card = cards.filter(has_text=view_name)
            if card.count() == 0:
                card = cards
            edit_btn = card.first.locator("button").filter(
                has=logged_in_page.locator("svg.lucide-pencil")
            )
            assert edit_btn.count() > 0, "视图卡片内缺少编辑按钮"
            edit_btn.first.evaluate("el => el.click()")

            # 验证编辑弹窗打开
            dialog = logged_in_page.locator('[role="dialog"]')
            try:
                dialog.first.wait_for(state="visible", timeout=5000)
            except Exception:
                pytest.fail("编辑弹窗未打开")

            # 验证模块开关存在（应有 4 个面板开关）
            switches = dialog.locator('[role="switch"]')
            try:
                switches.first.wait_for(state="visible", timeout=3000)
            except Exception:
                pytest.fail("编辑弹窗内缺少模块配置开关")
            switch_count = switches.count()
            assert switch_count >= 4, \
                f"预期至少 4 个面板开关，实际 {switch_count}"

            # 切换第一个开关，验证状态变化
            initial_state = switches.first.get_attribute("data-state")
            switches.first.click()
            logged_in_page.wait_for_timeout(500)
            new_state = switches.first.get_attribute("data-state")
            assert new_state != initial_state, \
                f"开关切换后状态未变化: {initial_state} → {new_state}"

            # 切回原状态
            switches.first.wait_for(state="visible", timeout=5000)
            switches.first.click()
            logged_in_page.wait_for_timeout(500)

            # 关闭弹窗
            cancel = dialog.locator("button").filter(has_text="取消")
            if cancel.count() > 0:
                cancel.first.click()
            else:
                logged_in_page.keyboard.press("Escape")
        finally:
            _delete_view_api(logged_in_page, base_url, view_id)

    @pytest.mark.order(511)
    @pytest.mark.p2
    def test_view_copy_link(self, logged_in_page, base_url):
        """TC-VIEW-008: 复制链接 — 点击复制按钮，验证 toast 提示"""
        view = _create_view_api(logged_in_page, base_url)
        view_id = view.get("id")
        view_name = view.get("name", "")
        if not view_id:
            pytest.skip("无法创建视图")
        try:
            v = ViewsPage(logged_in_page, base_url)
            v.goto()

            # 等待视图卡片加载
            cards = logged_in_page.locator("div.rounded-lg.border")
            try:
                cards.first.wait_for(state="visible", timeout=5000)
            except Exception:
                pytest.fail("视图卡片未加载")

            # 定位卡片，找复制按钮（Copy 图标 + "复制链接"文字）
            card = cards.filter(has_text=view_name)
            if card.count() == 0:
                card = cards
            copy_btn = card.first.locator("button").filter(
                has=logged_in_page.locator("svg.lucide-copy")
            )
            assert copy_btn.count() > 0, "视图卡片内缺少复制链接按钮"
            copy_btn.first.wait_for(state="visible", timeout=5000)
            copy_btn.first.click()

            # 验证 toast 出现"链接已复制"
            toast = logged_in_page.locator("[data-sonner-toast]").filter(
                has_text="链接已复制"
            )
            try:
                toast.first.wait_for(state="visible", timeout=5000)
            except Exception:
                pytest.fail("点击复制后未出现「链接已复制」toast")
        finally:
            _delete_view_api(logged_in_page, base_url, view_id)
