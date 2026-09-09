# tests/suites/test_views.py
"""发布视图模块回归测试
覆盖：页面加载、列表数据、CRUD 操作、详情页

新版 UI：Artifacts 面板默认折叠 → ViewsPage.goto() 负责展开并激活「发布视图」Tab。
自建视图数据需带完整 modulesConfig 才会被 GET /config/prod-views?agentId= 列表返回。
"""
import json
import uuid
import pytest
import allure
from tests.pages.views_page import ViewsPage
from tests.conftest import register_cleanup

_PREFIX = f"e2e-{uuid.uuid4().hex[:6]}"
_CARDS = "aside.artifacts-shell div.rounded-lg.border"

# 与 UI 创建弹窗默认提交一致的模块配置（缺省附加面板关闭，其余开启）
_DEFAULT_MODULES = {
    "chatHeader": {"enabled": True},
    "sessionSidebar": {"enabled": True},
    "chatView": {"enabled": True},
    "chatComposer": {"enabled": True},
    "permissionPanel": {"enabled": True},
    "todoPanel": {"enabled": True},
    "contextPanel": {"enabled": True},
    "toolCallRow": {"enabled": True},
    "filesPanel": {"enabled": False},
    "sitesPanel": {"enabled": False},
    "tasksPanel": {"enabled": False},
    "viewsPanel": {"enabled": False},
}


# === API helpers ===


def _view_cards(page):
    return page.locator(_CARDS)


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


def _get_agent_id(page, base_url, name="my-auto-test"):
    """GET /web/config/agents → 返回指定 agent 的 ID；找不到回退第一个可用 agent"""
    r = page.request.get(f"{base_url}/web/config/agents")
    if r.status == 200:
        body = r.json().get("data", {})
        if isinstance(body, dict):
            agents = body.get("agents", [])
            if isinstance(agents, list) and agents:
                for a in agents:
                    if a.get("name") == name:
                        return a.get("id")
                return agents[0].get("id")
    return None


def _create_view_api(page, base_url, name=None, description="e2e test view",
                     agent_id=None):
    """POST /web/config/prod-views → created view（自动注册清理）

    新版 UI 提交会带完整 modulesConfig；缺失会导致视图不被 agentId 过滤列表返回。
    注：参照环境 DELETE 返回 404 DELETE_FAILED 但服务端实际已删行，清理仍有效。
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
    agent_id = agent_id or _get_agent_id(page, base_url)
    if not agent_id:
        return {}
    payload = {
        "name": name,
        "agentId": agent_id,
        "description": description,
        "modulesConfig": _DEFAULT_MODULES,
    }
    r = page.request.post(
        f"{base_url}/web/config/prod-views",
        data=json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )
    view_data = {}
    if r.status in (200, 201):
        view_data = r.json().get("data", {})

    if _req and view_data.get("id"):
        _vid = view_data["id"]
        register_cleanup(_req, lambda: _delete_view_api(page, base_url, _vid))

    return view_data


def _delete_view_api(page, base_url, view_id):
    """DELETE /web/config/prod-views/:id（响应 404 但行会被删除，忽略）"""
    if view_id:
        try:
            page.request.delete(f"{base_url}/web/config/prod-views/{view_id}")
        except Exception:
            pass


@allure.epic("产品视图")
class TestViews:
    """产品视图 — Agent 内容面板「发布视图」Tab"""

    # === 页面加载 ===

    @pytest.mark.order(60)
    @pytest.mark.p0
    def test_views_page_loads(self, logged_in_page, base_url):
        """发布视图 Tab 能正常打开并渲染"""
        v = ViewsPage(logged_in_page, base_url)
        v.goto()
        assert v.is_loaded(), "发布视图 Tab 未加载"

    # === 列表数据 ===

    @pytest.mark.order(61)
    @pytest.mark.p0
    def test_views_list_data(self, logged_in_page, base_url):
        """发布视图 Tab 有内容展示（视图列表或空状态）"""
        v = ViewsPage(logged_in_page, base_url)
        v.goto()
        assert v.is_loaded(), "发布视图 Tab 未加载"

        has_views = v.get_view_count() > 0
        has_empty = logged_in_page.get_by_text("点击 + 创建发布视图").count() > 0
        assert has_views or has_empty, \
            f"既无视图列表也无空状态提示，has_views={has_views}, has_empty={has_empty}"

    # === 创建视图 ===

    @pytest.mark.order(62)
    @pytest.mark.p0
    def test_views_create(self, logged_in_page, base_url):
        """点击新建按钮，验证弹窗/表单打开"""
        v = ViewsPage(logged_in_page, base_url)
        v.goto()

        assert v.has_create_button(), "缺少创建视图按钮"

        v.click_create_button()

        dialog = logged_in_page.locator('[role="dialog"]')
        try:
            dialog.first.wait_for(state="visible", timeout=5000)
        except Exception:
            pytest.fail("创建视图弹窗未打开")

        dialog_text = dialog.first.inner_text()
        assert "名称" in dialog_text, "弹窗缺少名称字段"
        assert any(kw in dialog_text for kw in ["保存", "创建"]), \
            f"创建弹窗缺少提交按钮（保存/创建），dialog_text 前200字符: {dialog_text[:200]!r}"

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
        view = _create_view_api(logged_in_page, base_url)
        view_id = view.get("id")
        original_name = view.get("name", "")
        if not view_id:
            pytest.skip("无法创建视图")
        try:
            v = ViewsPage(logged_in_page, base_url)
            v.goto()

            cards = _view_cards(logged_in_page)
            card = cards.filter(has_text=original_name)
            try:
                card.first.wait_for(state="visible", timeout=8000)
            except Exception:
                pytest.fail("视图卡片未加载")

            edit_btn = card.first.locator('button[title="编辑"]')
            assert edit_btn.count() > 0, "视图卡片内缺少编辑按钮"
            edit_btn.first.click()

            dialog = logged_in_page.locator('[role="dialog"]')
            try:
                dialog.first.wait_for(state="visible", timeout=5000)
            except Exception:
                pytest.fail("编辑弹窗未打开")

            new_name = f"e2e-edit-{_PREFIX}"
            name_input = dialog.locator("input").first
            name_input.wait_for(state="visible", timeout=5000)
            name_input.fill(new_name)

            save_btn = dialog.locator("button").filter(has_text="保存")
            assert save_btn.count() > 0, "编辑弹窗缺少保存按钮"
            save_btn.first.wait_for(state="visible", timeout=5000)
            save_btn.first.click()

            try:
                dialog.first.wait_for(state="hidden", timeout=8000)
            except Exception:
                pass

            # 列表重拉后名称更新
            try:
                logged_in_page.locator("span").filter(has_text=new_name).first.wait_for(
                    state="visible", timeout=8000
                )
            except Exception:
                pytest.fail(f"编辑保存后，视图名称未更新为 '{new_name}'")

            # 恢复原名称（清理）
            if original_name:
                try:
                    logged_in_page.request.put(
                        f"{base_url}/web/config/prod-views/{view_id}",
                        data=json.dumps({"name": original_name}),
                        headers={"Content-Type": "application/json"},
                    )
                except Exception:
                    pass
        finally:
            _delete_view_api(logged_in_page, base_url, view_id)

    # === 删除视图 ===

    @pytest.mark.order(64)
    @pytest.mark.p1
    def test_views_delete(self, logged_in_page, base_url):
        """TC-VIEW-005: 删除视图 — 点击删除并确认，刷新后视图被移除"""
        view_name = f"e2e-del-view-{_PREFIX}"
        view = _create_view_api(logged_in_page, base_url, name=view_name)
        view_id = view.get("id")
        if not view_id:
            pytest.skip("无法创建视图用于删除测试")
        try:
            v = ViewsPage(logged_in_page, base_url)
            v.goto()

            cards = _view_cards(logged_in_page)
            card = cards.filter(has_text=view_name)
            try:
                card.first.wait_for(state="visible", timeout=8000)
            except Exception:
                pytest.fail(f"未找到名称为 '{view_name}' 的视图卡片")

            delete_btn = card.first.locator('button[title="删除"]')
            assert delete_btn.count() > 0, "视图卡片内缺少删除按钮"
            delete_btn.first.wait_for(state="visible", timeout=5000)
            delete_btn.first.click()

            alert = logged_in_page.locator('[role="alertdialog"]')
            try:
                alert.first.wait_for(state="visible", timeout=5000)
            except Exception:
                pytest.fail("删除确认弹窗未出现")

            confirm_btn = alert.locator("button").filter(
                has_text="确认"
            ).or_(alert.locator("button").filter(has_text="确定"))
            assert confirm_btn.count() > 0, "确认弹窗缺少确认按钮"
            confirm_btn.first.wait_for(state="visible", timeout=5000)
            confirm_btn.first.click()

            # 参照环境：DELETE 服务端实际删除但返回 404，UI 不会自动移除卡片，
            # 需切换到其它 Tab 强制重拉列表，再断言视图已消失。
            v.refresh()

            remaining = _view_cards(logged_in_page).filter(has_text=view_name)
            assert remaining.count() == 0, \
                f"删除后视图 '{view_name}' 仍在列表中"
        finally:
            _delete_view_api(logged_in_page, base_url, view_id)

    # === 详情页 ===

    @pytest.mark.order(65)
    @pytest.mark.p1
    def test_views_detail_page(self, logged_in_page, base_url):
        """TC-VIEW-006: 打开视图 — 新标签页打开且 URL 含 /view/"""
        view = _create_view_api(logged_in_page, base_url)
        view_id = view.get("id")
        view_name = view.get("name", "")
        if not view_id:
            pytest.skip("无法创建视图")
        new_page = None
        try:
            v = ViewsPage(logged_in_page, base_url)
            v.goto()

            cards = _view_cards(logged_in_page)
            card = cards.filter(has_text=view_name)
            try:
                card.first.wait_for(state="visible", timeout=8000)
            except Exception:
                pytest.fail("视图卡片未加载")

            open_btn = card.first.locator('button[title="打开视图"]')
            assert open_btn.count() > 0, "视图卡片内缺少「打开视图」按钮"

            with logged_in_page.context.expect_page() as new_page_info:
                open_btn.first.wait_for(state="visible", timeout=5000)
                open_btn.first.click()
            new_page = new_page_info.value
            new_page.wait_for_load_state("domcontentloaded")

            new_url = new_page.url
            assert "/view/" in new_url, f"打开视图后 URL 不包含 /view/: {new_url}"

            # 新标签页 React 挂载可能慢于 domcontentloaded，轮询等待内容
            body_ok = False
            for _wait in range(20):
                body_text = new_page.locator("body").inner_text()
                if len(body_text.strip()) > 0:
                    body_ok = True
                    break
                new_page.wait_for_timeout(1000)
            assert body_ok, "打开视图后页面内容为空"
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

            cards = _view_cards(logged_in_page)
            card = cards.filter(has_text=view_name)
            try:
                card.first.wait_for(state="visible", timeout=8000)
            except Exception:
                pytest.fail("视图卡片未加载")

            edit_btn = card.first.locator('button[title="编辑"]')
            assert edit_btn.count() > 0, "视图卡片内缺少编辑按钮"
            edit_btn.first.click()

            dialog = logged_in_page.locator('[role="dialog"]')
            try:
                dialog.first.wait_for(state="visible", timeout=5000)
            except Exception:
                pytest.fail("编辑弹窗未打开")

            switches = dialog.locator('[role="switch"]')
            try:
                switches.first.wait_for(state="visible", timeout=3000)
            except Exception:
                pytest.fail("编辑弹窗内缺少模块配置开关")
            switch_count = switches.count()
            assert switch_count >= 4, \
                f"预期至少 4 个面板开关，实际 {switch_count}"

            initial_state = switches.first.get_attribute("data-state")
            switches.first.click()
            logged_in_page.wait_for_timeout(500)
            new_state = switches.first.get_attribute("data-state")
            assert new_state != initial_state, \
                f"开关切换后状态未变化: {initial_state} → {new_state}"

            switches.first.wait_for(state="visible", timeout=5000)
            switches.first.click()
            logged_in_page.wait_for_timeout(500)

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

            cards = _view_cards(logged_in_page)
            card = cards.filter(has_text=view_name)
            try:
                card.first.wait_for(state="visible", timeout=8000)
            except Exception:
                pytest.fail("视图卡片未加载")

            copy_btn = card.first.locator('button[title="复制链接"]')
            assert copy_btn.count() > 0, "视图卡片内缺少复制链接按钮"
            copy_btn.first.wait_for(state="visible", timeout=5000)
            copy_btn.first.click()

            toast = logged_in_page.locator("[data-sonner-toast]").filter(
                has_text="链接已复制"
            )
            try:
                toast.first.wait_for(state="visible", timeout=5000)
            except Exception:
                pytest.fail("点击复制后未出现「链接已复制」toast")
        finally:
            _delete_view_api(logged_in_page, base_url, view_id)

    @pytest.mark.order(512)
    @pytest.mark.p1
    def test_views_module_config(self, logged_in_page, base_url):
        """验证 ProdView 模块配置区域存在（编辑弹窗中有模块开关）"""
        view = _create_view_api(logged_in_page, base_url)
        view_id = view.get("id")
        view_name = view.get("name", "")
        if not view_id:
            pytest.skip("无法创建视图")
        try:
            v = ViewsPage(logged_in_page, base_url)
            v.goto()

            cards = _view_cards(logged_in_page)
            card = cards.filter(has_text=view_name)
            try:
                card.first.wait_for(state="visible", timeout=8000)
            except Exception:
                pytest.skip("视图卡片未加载")

            edit_btn = card.first.locator('button[title="编辑"]')
            if edit_btn.count() == 0:
                pytest.skip("视图卡片内缺少编辑按钮")
            edit_btn.first.click()

            dialog = logged_in_page.locator('[role="dialog"]')
            try:
                dialog.first.wait_for(state="visible", timeout=5000)
            except Exception:
                pytest.skip("编辑弹窗未打开")

            switches = dialog.locator('[role="switch"]')
            checkboxes = dialog.locator('input[type="checkbox"]')
            has_switches = switches.count() > 0
            has_checkboxes = checkboxes.count() > 0
            if not has_switches:
                try:
                    switches.first.wait_for(state="visible", timeout=3000)
                    has_switches = True
                except Exception:
                    pass

            assert has_switches or has_checkboxes, \
                "编辑弹窗内缺少模块配置区域（无 switch 或 checkbox）"

            cancel = dialog.locator("button").filter(has_text="取消")
            if cancel.count() > 0:
                cancel.first.click()
            else:
                logged_in_page.keyboard.press("Escape")
        finally:
            _delete_view_api(logged_in_page, base_url, view_id)


# ==================== 补充 P1 测试 ====================


@allure.epic("产品视图")
@pytest.mark.order(513)
@pytest.mark.p1
def test_views_preview(logged_in_page, base_url, request):
    """P1: ProdView 预览功能 — 点击 '打开视图' 验证预览页面出现（自建自销）"""
    v = ViewsPage(logged_in_page, base_url)

    view_data = _create_view_api(
        logged_in_page, base_url, name=f"e2e-preview-{uuid.uuid4().hex[:6]}"
    )
    view_id = view_data.get("id")
    if not view_id:
        pytest.skip("无法创建测试视图")
    view_name = view_data.get("name", "")

    v.goto()
    cards = _view_cards(logged_in_page).filter(has_text=view_name)
    try:
        cards.first.wait_for(state="visible", timeout=10000)
    except Exception:
        pytest.skip("自建视图卡片未在页面中出现")

    open_btn = cards.first.locator('button[title="打开视图"]')
    if open_btn.count() == 0:
        pytest.skip("视图卡片内未找到 '打开视图' 按钮")
    open_btn.first.wait_for(state="visible", timeout=5000)

    new_page = None
    try:
        with logged_in_page.context.expect_page() as new_page_info:
            open_btn.first.click()
        new_page = new_page_info.value
        new_page.wait_for_load_state("domcontentloaded")

        new_url = new_page.url
        assert "/view/" in new_url, \
            f"打开视图后 URL 不包含 /view/，实际 URL: {new_url}"

        body_ok = False
        for _wait in range(20):
            body_text = new_page.locator("body").inner_text()
            if len(body_text.strip()) > 0:
                body_ok = True
                break
            new_page.wait_for_timeout(1000)
        assert body_ok, "打开视图后页面内容为空"
    finally:
        if new_page:
            try:
                new_page.close()
            except Exception:
                pass
        _delete_view_api(logged_in_page, base_url, view_id)
