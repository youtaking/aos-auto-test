# tests/suites/test_workflow.py
"""工作流模块回归测试（适配新版架构 2026-10）

新版关键变化：
  * 列表页改为卡片式，卡片操作：打开画布 / 运行日志 / 更多操作（发布日志·调用接口·重命名·删除）
  * 编辑器是 `iframe[title='工作流画布']` 微前端，发布按钮在 iframe 内；
    控制台侧「发布」动作已于 2026-10-10 撤除，平台只读发布记录（发布日志弹窗）
  * 运行日志由 `?tab=runs` 页面改为页面级 dialog（工作流下拉 + 执行记录列表）
  * 列表/创建/删除 API 从 `/web/workflow-defs` 迁移到 `/web/workflow-v2/workflows`
"""
import json
import re
import uuid
import pytest
import allure
from tests.pages.sidebar_pages import WorkflowPage
from tests.conftest import register_cleanup


_PREFIX = f"e2e-{uuid.uuid4().hex[:6]}"

_WF_LIST = "/web/workflow-v2/workflows"


# ==================== API helpers ====================


def _wf_list(page, base_url) -> list:
    """GET /web/workflow-v2/workflows → items 列表"""
    r = page.request.get(f"{base_url}{_WF_LIST}?page=1&size=100")
    if r.status == 200:
        return r.json().get("data", {}).get("items", []) or []
    return []


def _wf_find(page, base_url, name: str):
    """按名称查找工作流（返回 v2 列表项 dict，含 id / upstreamWorkflowId）"""
    m = re.compile(rf"^{re.escape(name)}$")
    return next((it for it in _wf_list(page, base_url) if m.match(it.get("name", ""))), None)


def _wf_create(page, base_url, name: str, desc: str = "e2e test workflow") -> dict:
    """POST /web/workflow-v2/workflows → {id, upstreamWorkflowId}"""
    r = page.request.post(
        f"{base_url}{_WF_LIST}",
        data=json.dumps({"name": name, "desc": desc}),
        headers={"Content-Type": "application/json"},
    )
    if r.status in (200, 201):
        return r.json().get("data", {}) or {}
    return {}


def _wf_delete(page, base_url, local_id: str):
    """DELETE /web/workflow-v2/workflows/{id}?force=true"""
    if local_id:
        page.request.delete(f"{base_url}{_WF_LIST}/{local_id}?force=true")


# ==================== 前置检查 ====================


def _require_workflow_space(logged_in_page, base_url):
    """前置：工作流空间可用，否则 skip。

    未初始化 / 平台工作流账号不可用（503 PLATFORM_SESSION_UNAVAILABLE）时，
    列表、新建、画布全部不可用，这类用例在开头 skip。
    """
    wf = WorkflowPage(logged_in_page, base_url)
    wf.goto()
    if wf.is_space_blocked():
        pytest.skip(
            "工作流空间未初始化 / 平台工作流账号不可用(HTTP 503 "
            "PLATFORM_SESSION_UNAVAILABLE)，无法进入画布/运行日志"
        )


def _require_existing_workflow(logged_in_page, base_url) -> dict:
    """前置：列表至少有一个工作流（只读用它进编辑器，不新建不修改），返回第一项"""
    _require_workflow_space(logged_in_page, base_url)
    it = _wf_list(logged_in_page, base_url)
    if not it:
        pytest.skip("当前组织没有工作流，无法进入画布 / 运行日志")
    return it[0]


@allure.epic("工作流")
class TestWorkflow:
    """工作流 /ctrl/agent/workflow"""

    # ==================== 列表页 ====================

    @pytest.mark.order(70)
    @pytest.mark.p0
    def test_workflow_page_loads(self, logged_in_page, base_url):
        """工作流页面能正常加载"""
        wf = WorkflowPage(logged_in_page, base_url)
        wf.goto()
        assert wf.is_loaded(), "工作流页面未加载"

    @pytest.mark.order(71)
    @pytest.mark.p0
    def test_workflow_list_data(self, logged_in_page, base_url):
        """工作流列表有数据，或明确的空间不可用说明态"""
        wf = WorkflowPage(logged_in_page, base_url)
        wf.goto()
        assert wf.is_loaded(), "工作流页面未加载"

        if wf.is_space_blocked():
            body = logged_in_page.locator("body").inner_text()
            assert "工作流" in body, "空间不可用态页面缺少说明文案"
            return

        count = wf.get_workflow_count()
        api_items = _wf_list(logged_in_page, base_url)
        if count == 0:
            body = logged_in_page.locator("body").inner_text()
            assert ("暂无" in body) or ("还没有工作流" in body) or (len(api_items) == 0), \
                f"列表无卡片但页面也无空状态提示，API 却返回 {len(api_items)} 条"
        else:
            assert count == len(api_items), \
                f"卡片数({count}) 与 API 返回数({len(api_items)}) 不一致"

    @pytest.mark.order(72)
    @pytest.mark.p0
    def test_workflow_create_dialog(self, logged_in_page, base_url):
        """点击「新建工作流」打开创建弹窗，字段完整（名称/描述/创建并打开）"""
        wf = WorkflowPage(logged_in_page, base_url)
        wf.goto()
        if not wf.has_create_button():
            pytest.skip("当前无可用「新建工作流」按钮（空间未初始化 / 平台账号不可用）")

        logged_in_page.get_by_role("button", name="新建工作流").click()
        dialog = logged_in_page.get_by_role("dialog")
        dialog.wait_for(state="visible", timeout=8000)

        assert dialog.locator("#workflow-create-name").count() == 1, \
            "创建弹窗缺少名称输入框 #workflow-create-name"
        assert dialog.locator("#workflow-create-desc").count() == 1, \
            "创建弹窗缺少描述输入框 #workflow-create-desc"
        assert dialog.get_by_role("button", name="创建并打开").count() == 1, \
            "创建弹窗缺少「创建并打开」按钮"

        dialog.get_by_role("button", name="取消").click()
        logged_in_page.wait_for_timeout(500)

    @pytest.mark.order(73)
    @pytest.mark.p1
    def test_workflow_list_refresh(self, logged_in_page, base_url):
        """「刷新列表」按钮可点击，刷新后列表卡片数不变且无报错"""
        _require_workflow_space(logged_in_page, base_url)
        wf = WorkflowPage(logged_in_page, base_url)
        wf.goto()
        before = wf.get_workflow_count()
        wf.refresh_list()
        after = wf.get_workflow_count()
        assert after == before, f"刷新后卡片数变化：{before} → {after}"

    @pytest.mark.order(74)
    @pytest.mark.p1
    def test_workflow_list_pagination(self, logged_in_page, base_url):
        """列表底部分页文本形如「共 N 条」，且与卡片数/API 总数一致"""
        _require_workflow_space(logged_in_page, base_url)
        wf = WorkflowPage(logged_in_page, base_url)
        wf.goto()
        pag = wf.get_pagination_text()
        assert re.search(r"共\s*\d+\s*条", pag), f"未找到分页文本（共 N 条），实际: {pag!r}"
        total = int(re.search(r"(\d+)", pag).group(1))
        assert total == len(_wf_list(logged_in_page, base_url)), \
            f"分页总数({total}) 与 API 返回数不一致"

    # ==================== 编辑器画布（iframe 微前端） ====================

    @pytest.mark.order(75)
    @pytest.mark.p0
    def test_workflow_editor_canvas(self, logged_in_page, base_url):
        """TC-WF-004: 进入编辑器，iframe 画布握手完成并渲染出画布根节点"""
        it = _require_existing_workflow(logged_in_page, base_url)
        wf = WorkflowPage(logged_in_page, base_url)
        wf.open_canvas_by_id(it["upstreamWorkflowId"])

        assert "/workflow/" in logged_in_page.url and "/edit" in logged_in_page.url, \
            f"未进入编辑器: {logged_in_page.url}"
        assert logged_in_page.locator(WorkflowPage.CANVAS_IFRAME).count() == 1, \
            "未找到画布 iframe（iframe[title='工作流画布']）"
        assert wf.canvas_frame().locator("[data-testid='sdk.workflow.canvas']").count() > 0, \
            "画布 iframe 内未渲染出 sdk.workflow.canvas"
        assert wf.canvas_frame().locator("[data-testid='sdk.workflow.canvas.node']").count() >= 2, \
            "画布内节点数不足 2（至少应有 开始 / 结束 两个节点）"

    @pytest.mark.order(76)
    @pytest.mark.p1
    def test_workflow_add_node(self, logged_in_page, base_url):
        """TC-WF-005: 画布暴露「添加节点」入口与节点面板"""
        it = _require_existing_workflow(logged_in_page, base_url)
        wf = WorkflowPage(logged_in_page, base_url)
        wf.open_canvas_by_id(it["upstreamWorkflowId"])

        assert wf.has_add_node_button(), \
            "画布工具栏未找到「添加节点」按钮 (workflow.detail.toolbar.add-node)"
        assert wf.node_type_card_count() > 0, \
            "左侧节点面板没有可添加的节点类型卡片"

    @pytest.mark.order(77)
    @pytest.mark.p1
    def test_workflow_save_draft(self, logged_in_page, base_url):
        """TC-WF-006: 画布自动保存（已自动保存标签）+ 发布入口可见"""
        it = _require_existing_workflow(logged_in_page, base_url)
        wf = WorkflowPage(logged_in_page, base_url)
        wf.open_canvas_by_id(it["upstreamWorkflowId"])

        tag = wf.autosave_tag()
        tag.first.wait_for(state="visible", timeout=15000)
        assert re.search(r"已自动保存", tag.first.inner_text()), \
            f"未显示「已自动保存」标签，实际: {tag.first.inner_text()!r}"
        assert wf.has_publish_button(), "画布内未找到发布按钮"

    @pytest.mark.order(78)
    @pytest.mark.p1
    def test_workflow_publish(self, logged_in_page, base_url):
        """TC-WF-007: 发布入口 — 画布内发布按钮可见且可用

        控制台侧发布动作已撤除（发布在上游画布完成）；这里校验平台侧
        仍提供发布入口（iframe 内的「发布」按钮）。
        """
        it = _require_existing_workflow(logged_in_page, base_url)
        wf = WorkflowPage(logged_in_page, base_url)
        wf.open_canvas_by_id(it["upstreamWorkflowId"])

        pub = wf.canvas_frame().get_by_test_id("workflow-base-publish-button")
        pub.first.wait_for(state="visible", timeout=15000)
        assert pub.first.inner_text().strip() == "发布", \
            f"发布按钮文案异常: {pub.first.inner_text()!r}"
        assert pub.first.is_enabled(), "发布按钮处于禁用状态"

    @pytest.mark.order(79)
    @pytest.mark.p1
    def test_workflow_versions(self, logged_in_page, base_url):
        """TC-WF-008: 发布记录 — 卡片菜单「发布日志」弹窗 + publish-records API"""
        _require_workflow_space(logged_in_page, base_url)
        wf = WorkflowPage(logged_in_page, base_url)
        wf.goto()
        name = _wf_list(logged_in_page, base_url)[0]["name"]

        # 1) UI: 卡片菜单 → 发布日志 → 弹窗展示「上游当前版本」
        wf.open_publish_log(name)
        dlg = wf.publish_log_dialog()
        dlg.first.wait_for(state="visible", timeout=8000)
        text = dlg.first.inner_text()
        assert name in text, f"发布日志弹窗标题未包含工作流名 '{name}': {text[:120]}"
        assert "上游当前版本" in text, "发布日志弹窗缺少「上游当前版本」区块"
        logged_in_page.get_by_role("button", name="Close").click()
        logged_in_page.wait_for_timeout(500)

        # 2) API: publish-records 返回 {current, records, actions}
        it = _wf_find(logged_in_page, base_url, name)
        r = logged_in_page.request.get(
            f"{base_url}{_WF_LIST}/{it['id']}/publish-records"
        )
        assert r.status == 200, f"发布记录接口异常: HTTP {r.status}"
        data = r.json().get("data", {})
        assert "current" in data and "publishedVersion" in data["current"], \
            f"发布记录响应缺少 current.publishedVersion: {str(data)[:150]}"
        assert isinstance(data.get("records"), list), "发布记录 records 字段不是数组"
        assert isinstance(data.get("actions"), list), "发布记录 actions 字段不是数组"

    # ==================== 运行日志（页面级 dialog） ====================

    @pytest.mark.order(80)
    @pytest.mark.p0
    def test_workflow_run_execute(self, logged_in_page, base_url):
        """TC-WF-009: 卡片「运行日志」按钮打开运行日志弹窗"""
        it = _require_existing_workflow(logged_in_page, base_url)
        wf = WorkflowPage(logged_in_page, base_url)
        wf.goto()
        wf.open_run_logs(it["name"])

        dialog = wf.run_log_dialog()
        dialog.first.wait_for(state="visible", timeout=8000)
        assert "运行记录来自上游工作流引擎" in dialog.first.inner_text(), \
            "运行日志弹窗说明文案缺失，可能不是运行日志弹窗"

    @pytest.mark.order(81)
    @pytest.mark.p1
    def test_workflow_run_logs(self, logged_in_page, base_url):
        """点击「全部运行日志」，弹窗含工作流下拉 + 执行记录区（列表或空态）"""
        _require_workflow_space(logged_in_page, base_url)
        wf = WorkflowPage(logged_in_page, base_url)
        wf.goto()
        wf.open_all_run_logs()

        dialog = wf.run_log_dialog()
        dialog.first.wait_for(state="visible", timeout=8000)
        assert dialog.first.get_by_role("heading", name="执行记录").count() == 1, \
            "运行日志弹窗缺少「执行记录」标题"
        assert dialog.first.get_by_role("combobox").count() == 1, \
            "运行日志弹窗缺少工作流下拉框"
        text = dialog.first.inner_text()
        assert ("该工作流还没有运行记录" in text) or ("运行中" in text) or ("成功" in text) \
            or ("失败" in text), "执行记录区既无空状态提示也无状态行"
        logged_in_page.get_by_role("button", name="Close").click()

    @pytest.mark.order(82)
    @pytest.mark.p1
    def test_workflow_runs_filter_tabs(self, logged_in_page, base_url):
        """TC-WF-GAP-04: 运行日志弹窗工作流下拉可选项完整（全部工作流 + 各工作流）"""
        _require_workflow_space(logged_in_page, base_url)
        wf = WorkflowPage(logged_in_page, base_url)
        wf.goto()
        names = [it["name"] for it in _wf_list(logged_in_page, base_url)]
        wf.open_all_run_logs()

        dialog = wf.run_log_dialog()
        dialog.first.wait_for(state="visible", timeout=8000)
        combo = dialog.first.get_by_role("combobox")
        options = [o.strip() for o in combo.locator("option").all_inner_texts()]
        assert "全部工作流" in options, f"下拉缺少「全部工作流」选项: {options}"
        for name in names:
            assert name in options, f"下拉缺少工作流选项 '{name}': {options}"

        # 选择第一个具体工作流，列表区仍正常（不报错、仍有内容）
        combo.select_option(label=names[0])
        logged_in_page.wait_for_timeout(1500)
        assert dialog.first.get_by_role("heading", name="执行记录").count() == 1, \
            "切换工作流后执行记录区消失"
        logged_in_page.get_by_role("button", name="Close").click()

    @pytest.mark.order(83)
    @pytest.mark.p1
    def test_workflow_runs_search(self, logged_in_page, base_url):
        """TC-WF-GAP-05: 运行日志按工作流过滤 — 切到指定工作流后说明/列表随之刷新"""
        _require_workflow_space(logged_in_page, base_url)
        wf = WorkflowPage(logged_in_page, base_url)
        wf.goto()
        names = [it["name"] for it in _wf_list(logged_in_page, base_url)]
        assert names, "列表无工作流，无法验证运行日志过滤"
        wf.open_all_run_logs()

        dialog = wf.run_log_dialog()
        dialog.first.wait_for(state="visible", timeout=8000)
        combo = dialog.first.get_by_role("combobox")

        combo.select_option(label=names[0])
        logged_in_page.wait_for_timeout(1500)
        after_first = dialog.first.inner_text()

        combo.select_option(label="全部工作流")
        logged_in_page.wait_for_timeout(1500)
        after_all = dialog.first.inner_text()

        # 两次筛选都应保持弹窗结构完整（有效状态），且内容随选择变化
        for txt in (after_first, after_all):
            assert dialog.first.get_by_role("heading", name="执行记录").count() == 1
        assert (after_first != after_all) or ("该工作流还没有运行记录" in after_first), \
            "切换工作流后弹窗内容完全未变化，筛选可能未生效"
        logged_in_page.get_by_role("button", name="Close").click()

    @pytest.mark.order(84)
    @pytest.mark.p1
    def test_workflow_runs_refresh(self, logged_in_page, base_url):
        """TC-WF-GAP-06: 列表「刷新列表」后页面无报错，卡片与分页仍正常"""
        _require_workflow_space(logged_in_page, base_url)
        wf = WorkflowPage(logged_in_page, base_url)
        wf.goto()
        before = wf.get_workflow_count()
        wf.refresh_list()
        assert wf.is_loaded(), "刷新后页面失去就绪标识"
        assert wf.get_workflow_count() == before, "刷新后卡片数变化"
        assert re.search(r"共\s*\d+\s*条", wf.get_pagination_text()), "刷新后分页文本缺失"

    # ==================== 卡片菜单功能 ====================

    @pytest.mark.order(85)
    @pytest.mark.p1
    def test_workflow_api_info(self, logged_in_page, base_url):
        """卡片菜单「调用接口」弹窗展示 run 调用地址与鉴权说明"""
        _require_workflow_space(logged_in_page, base_url)
        wf = WorkflowPage(logged_in_page, base_url)
        wf.goto()
        name = _wf_list(logged_in_page, base_url)[0]["name"]

        wf.open_api_info(name)
        dialog = logged_in_page.locator("[role=dialog]").filter(
            has=logged_in_page.get_by_role("heading", name=re.compile(r"^调用接口"))
        )
        dialog.first.wait_for(state="visible", timeout=8000)
        text = dialog.first.inner_text()
        assert name in text, f"调用接口弹窗未包含工作流名 '{name}'"
        assert re.search(r"/api/workflow-v2/workflows/[^/]+/run", text), \
            f"调用接口弹窗未展示 run 调用地址: {text[:200]}"
        assert "Authorization: Bearer" in text, "调用接口弹窗缺少鉴权说明"
        logged_in_page.get_by_role("button", name="Close").click()

    @pytest.mark.order(86)
    @pytest.mark.p0
    def test_workflow_create_rename_delete(self, logged_in_page, base_url, request):
        """TC-WF-LIFE: 通过 UI 创建 → 重命名 → 删除（自建自销）

        数据安全：只在**本用例自建**的工作流上做重命名与删除；
        删除前校验确认弹窗包含目标名称。
        """
        _require_workflow_space(logged_in_page, base_url)
        wf = WorkflowPage(logged_in_page, base_url)
        wf.goto()

        name = f"e2e-wf-{_PREFIX}"
        renamed = f"{name}-r"

        upstream_id = wf.create_workflow(name, description="E2E 自建自销用例")
        assert upstream_id, "通过 UI 创建后未跳转到编辑器"

        # 注册 API 兜底清理
        local = _wf_find(logged_in_page, base_url, name)
        assert local, f"创建后 API 列表中找不到 '{name}'"
        register_cleanup(request, lambda: _wf_delete(logged_in_page, base_url, local["id"]))

        # 回列表，验证可见
        wf.goto()
        assert wf.has_workflow(name), f"创建的工作流 '{name}' 未出现在列表中"

        # 重命名
        wf.rename(name, renamed)
        wf.refresh_list()
        assert wf.has_workflow(renamed), f"重命名后 '{renamed}' 不在列表中"
        assert not wf.has_workflow(name), f"重命名后旧名 '{name}' 仍在列表中"

        # 删除
        wf.delete_workflow(renamed)
        wf.refresh_list()
        assert not wf.has_workflow(renamed), f"删除后 '{renamed}' 仍在列表中"

    # ==================== 画布进阶 ====================

    @pytest.mark.order(87)
    @pytest.mark.p0
    def test_workflow_canvas_editor(self, logged_in_page, base_url):
        """TC-WF-012: 画布工具栏（缩放/自动布局/小地图/注释）齐备"""
        it = _require_existing_workflow(logged_in_page, base_url)
        wf = WorkflowPage(logged_in_page, base_url)
        wf.open_canvas_by_id(it["upstreamWorkflowId"])
        frame = wf.canvas_frame()

        for tid in (
            "workflow.detail.toolbar.zoom",
            "workflow.detail.toolbar.auto-layout",
            "workflow.detail.toolbar.minimap-switch",
            "workflow.detail.controls.comment",
        ):
            assert frame.get_by_test_id(tid).count() == 1, f"画布工具栏缺少 {tid}"

    @pytest.mark.order(88)
    @pytest.mark.p1
    def test_workflow_canvas_backend_calls(self, logged_in_page, base_url):
        """画布握手：进入编辑器会向 /workflow-canvas/bff 发起会话与画布读取请求"""
        it = _require_existing_workflow(logged_in_page, base_url)
        calls = []

        def on_request(req):
            if "/workflow-canvas/bff/" in req.url:
                calls.append(req.url)

        logged_in_page.on("request", on_request)
        try:
            wf = WorkflowPage(logged_in_page, base_url)
            wf.open_canvas_by_id(it["upstreamWorkflowId"])
        finally:
            logged_in_page.remove_listener("request", on_request)

        assert calls, "进入画布后未观察到任何 /workflow-canvas/bff 请求，微前端可能未握手"

    @pytest.mark.order(89)
    @pytest.mark.p1
    def test_workflow_node_config(self, logged_in_page, base_url):
        """TC-WF-GAP-01: 点击画布节点，展开该节点的配置表单"""
        it = _require_existing_workflow(logged_in_page, base_url)
        wf = WorkflowPage(logged_in_page, base_url)
        wf.open_canvas_by_id(it["upstreamWorkflowId"])

        wf.click_canvas_node(0)
        form = wf.node_config_form()
        form.first.wait_for(state="visible", timeout=10000)
        assert form.count() == 1, f"节点配置表单匹配 {form.count()} 个，预期唯一"
        text = form.first.inner_text().strip()
        assert text, "节点配置表单内容为空"
        assert form.first.locator("input, textarea, select").count() > 0, \
            "节点配置表单内没有任何可编辑控件"

    @pytest.mark.order(90)
    @pytest.mark.p1
    def test_workflow_title_edit(self, logged_in_page, base_url):
        """TC-WF-GAP-02: 画布标题「编辑」按钮打开工作流名称/描述表单（不保存）"""
        it = _require_existing_workflow(logged_in_page, base_url)
        wf = WorkflowPage(logged_in_page, base_url)
        wf.open_canvas_by_id(it["upstreamWorkflowId"])
        frame = wf.canvas_frame()

        wf.title_edit_button().first.click()
        logged_in_page.wait_for_timeout(1200)
        name_box = frame.locator("textarea[placeholder='请输入工作流名称']")
        name_box.wait_for(state="visible", timeout=8000)
        assert name_box.input_value().strip() == it["name"], \
            f"标题编辑表单名称回填不正确: {name_box.input_value()!r}"
        assert frame.locator("textarea[placeholder*='让大模型理解']").count() == 1, \
            "标题编辑表单缺少描述输入框"

        # 取消，避免修改既有工作流
        frame.get_by_role("button", name="取消").click()
        logged_in_page.wait_for_timeout(600)

    @pytest.mark.order(91)
    @pytest.mark.p1
    def test_workflow_run_params_dialog(self, logged_in_page, base_url):
        """TC-WF-017: 画布「试运行」按钮展开试运行输入面板（不实际运行）"""
        it = _require_existing_workflow(logged_in_page, base_url)
        wf = WorkflowPage(logged_in_page, base_url)
        wf.open_canvas_by_id(it["upstreamWorkflowId"])
        frame = wf.canvas_frame()

        run_btn = wf.run_button()
        run_btn.first.wait_for(state="visible", timeout=10000)
        wf.click_run()

        assert frame.get_by_text("试运行输入").count() > 0, \
            "点击试运行后未出现「试运行输入」面板"
        assert frame.get_by_text("JSON模式").count() > 0, \
            "试运行面板缺少「JSON模式」开关"
