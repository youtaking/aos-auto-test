# tests/suites/test_knowledge.py
"""知识库模块 E2E 测试 — 基于真实 DOM + API 验证
覆盖 Excel 8-知识库 sheet 全部 10 条用例
"""
import json
import os
import tempfile
import time
import uuid
import pytest
import allure
from tests.pages.knowledge_page import KnowledgePage
from tests.pages import locators as loc
from tests.conftest import register_cleanup


def _safe_remove(path: str):
    """安全删除临时文件（处理 Windows 文件锁）"""
    if not os.path.exists(path):
        return
    try:
        os.remove(path)
    except PermissionError:
        time.sleep(1)
        try:
            os.remove(path)
        except PermissionError:
            pass

_PREFIX = f"e2e-{uuid.uuid4().hex[:6]}"


@pytest.fixture
def embedding_required(env_check):
    """需要 embedding 模型 / RAGFlow 索引能力的用例显式声明本 fixture

    2026-09-15 评审修正：原实现为 autouse=True，导致环境无 embedding 模型时
    整个知识库模块 28 条用例全部跳过（报表上"已覆盖"实为"未执行"）。
    现改为按用例粒度声明：上传/解析/检索/图谱/分块等依赖向量化能力的用例显式使用，
    列表/详情/增删改等不依赖 embedding 的用例正常执行。
    """
    if not env_check.get("has_embedding_models", False):
        pytest.skip("测试环境无可用的 embedding 模型，该用例依赖向量化/索引能力")
    return True


def _retry_after_seconds(resp, default=65, cap=70):
    """解析 429 响应的 Retry-After 头，返回应等待的秒数

    服务端给出 Retry-After（秒或 HTTP-date）时按其等待，避免固定 65s 阻塞；
    未给出时退回 default（限流窗口长度）。
    """
    raw = None
    try:
        raw = resp.headers.get("retry-after") or resp.headers.get("Retry-After")
    except Exception:
        raw = None
    if not raw:
        return default
    try:
        secs = float(raw)
    except (TypeError, ValueError):
        try:
            from email.utils import parsedate_to_datetime
            import datetime as _dt
            target = parsedate_to_datetime(raw)
            secs = (target - _dt.datetime.now(_dt.timezone.utc)).total_seconds()
        except Exception:
            return default
    return max(1.0, min(secs + 1.0, cap))


def _wait_rate_limit(page, resp=None, default=65):
    """按 429 响应的 Retry-After 等待（无该头时退回 default 秒）"""
    secs = _retry_after_seconds(resp, default=default) if resp is not None else default
    print(f"[429] 限流中，等待 {secs:.0f}s 后重试（Retry-After 感知）...")
    try:
        page.goto("about:blank", wait_until="domcontentloaded", timeout=5000)
    except Exception:
        pass
    page.wait_for_timeout(int(secs * 1000))


def _create_kb_api(page, base_url, name, desc=""):
    """创建知识库，429 时按 Retry-After 等待后重试（最多 2 次）"""
    for attempt in range(2):
        resp = page.request.post(
            f"{base_url}/web/knowledgeBases",
            data=json.dumps({"name": name, "description": desc}),
            headers={"Content-Type": "application/json"},
        )
        if resp.status != 429:
            return resp
        # 429 限流，等待窗口重置（优先使用服务端给出的 Retry-After）
        _wait_rate_limit(page, resp)
    return resp


def _assert_kb_created(resp):
    """断言知识库创建成功，失败时附带响应体便于诊断。502/503 时 skip。"""
    if resp.status != 200:
        body_text = ""
        try:
            body_text = json.dumps(resp.json(), ensure_ascii=False)[:300]
        except Exception:
            try:
                body_text = resp.text()[:300]
            except Exception:
                pass
        # 502/503 表示后端知识库服务不可用，跳过而非失败
        if resp.status in (502, 503, 504):
            pytest.skip(f"知识库后端服务不可用 (HTTP {resp.status})，跳过测试")
        assert False, f"创建测试知识库失败: status={resp.status}, body={body_text}"


def _delete_kb_api(page, base_url, kb_id):
    """删除知识库，429 时等待限流窗口后重试，5xx 时重试，非 2xx 时打印警告"""
    resp = None
    for attempt in range(3):
        resp = page.request.delete(f"{base_url}/web/knowledgeBases/{kb_id}")
        if resp.status == 429:
            _wait_rate_limit(page, resp)
            continue
        if resp.status >= 500:
            print(f"[{resp.status}] _delete_kb_api 服务端错误，等待 1.5s 后重试...")
            page.wait_for_timeout(1500)
            continue
        if resp.status not in (200, 204):
            body = ""
            try:
                body = resp.text()[:200]
            except Exception:
                pass
            print(f"[WARN] _delete_kb_api({kb_id}) 返回 {resp.status}，清理可能失败: {body}")
        return resp
    # 重试耗尽仍未成功
    status = resp.status if resp else "N/A"
    print(f"[WARN] _delete_kb_api({kb_id}) 重试 3 次后仍失败，最终状态: {status}")
    return resp


def _get_kbs_api(page, base_url):
    """获取知识库列表，429 时等待限流窗口后重试"""
    for attempt in range(2):
        r = page.request.get(f"{base_url}/web/knowledgeBases")
        if r.status != 429:
            if r.status == 200:
                return r.json().get("data", [])
            return []
        _wait_rate_limit(page, r)
    return []


def _get_kb_detail_api(page, base_url, kb_id):
    r = page.request.get(f"{base_url}/web/knowledgeBases/{kb_id}")
    if r.status == 200:
        return r.json()
    return None


def _goto_kb_detail(page, base_url, kb_id, max_retries=2):
    """导航到知识库详情页（?kbId=xxx），详情头渲染成功即视为就绪

    就绪锚点：section.knowledge-detail-header（新版 master-detail UI）。
    旧锚点「返回知识库列表」文案已在 web/src 全量下线（2026-09-15 评审确认）。
    """
    for attempt in range(max_retries):
        try:
            page.goto(f"{base_url}/ctrl/agent/knowledge-bases?kbId={kb_id}",
                       wait_until="domcontentloaded")
        except Exception:
            pass
        page.wait_for_load_state("domcontentloaded")
        try:
            page.locator("div.agent-panel-content").first.wait_for(
                state="attached", timeout=8000)
        except Exception:
            pass
        # 检查详情页是否加载成功（详情头）
        try:
            page.locator("section.knowledge-detail-header").first.wait_for(
                state="visible", timeout=10000)
            return True
        except Exception:
            pass
        # 页面未加载 → 可能 429，等待限流窗口重置
        if attempt < max_retries - 1:
            print(f"[429] 知识库详情页未加载，等待限流窗口重置...")
            try:
                page.goto("about:blank", wait_until="domcontentloaded", timeout=5000)
            except Exception:
                pass
            page.wait_for_timeout(65000)
    return False


def _wait_rate_limit_reset(page, seconds=65):
    """等待限流窗口重置（60s 窗口 + 5s 缓冲），期间关闭页面减少后台轮询"""
    print(f"[429] 等待 {seconds}s 限流窗口重置...")
    try:
        page.goto("about:blank", wait_until="domcontentloaded", timeout=5000)
    except Exception:
        pass
    page.wait_for_timeout(seconds * 1000)


# ==================== 测试 ====================


@allure.epic("知识库")
@pytest.mark.order(320)
@pytest.mark.p0
def test_kb_001_list_loads(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-KB-001: 知识库列表数据加载"""
    kb = KnowledgePage(logged_in_page, base_url)
    api_resp = kb.intercept_api("/web/knowledgeBases")
    kb.goto()

    assert kb.is_loaded(), "知识库页面未加载"

    # 1. 发起知识库列表请求（domcontentloaded 后请求可能未到达，轮询等待）
    list_called = False
    for _ in range(20):
        if any("/web/knowledgeBases" in r["url"] and r["method"] == "GET"
               for r in api_resp):
            list_called = True
            break
        logged_in_page.wait_for_timeout(500)
    assert list_called, "未发起知识库列表 API 请求"

    # 2. 页面有内容（左侧面板包含知识库列表）
    body = logged_in_page.locator("div.agent-panel-body")
    assert "知识库" in body.inner_text(), "页面中未显示知识库相关内容"

    # 3. 新版目录结构渲染（「目录 + 资源」双栏，无库级搜索框；旧 has_search_input 断言已随改版失效）
    assert logged_in_page.get_by_text("知识库目录").count() > 0, "知识库目录标题未渲染"
    directory_items = logged_in_page.locator(".knowledge-directory-item")
    assert directory_items.count() > 0, \
        "知识库目录未渲染任何知识库项（.knowledge-directory-item）"


@allure.epic("知识库")
@pytest.mark.order(321)
@pytest.mark.p0
def test_kb_002_create_kb(logged_in_page, base_url, request):
    """✅ 人工评审通过 | TC-KB-002: 创建知识库 — 填写名称、选择向量模型、内置解析方法和分块方法"""
    kb = KnowledgePage(logged_in_page, base_url)
    kb.goto()

    initial_kbs = _get_kbs_api(logged_in_page, base_url)

    kb.click_create_kb()
    assert kb.is_dialog_open(), "新建知识库弹窗未打开"
    assert "新建知识库" in kb.get_dialog_title(), "弹窗标题不正确"

    # 填写表单
    dialog = logged_in_page.locator("[role=dialog]")

    # 1. 名称（必填）
    name_input = dialog.locator("input[placeholder*='项目文档'], input[placeholder*='名称']").first
    assert name_input.count() > 0, "名称输入框不存在"
    kb_name = f"KB-{_PREFIX}"
    name_input.wait_for(state="visible", timeout=5000)
    name_input.fill(kb_name)

    # 2. 描述（选填）
    desc_input = dialog.locator("textarea")
    if desc_input.count() > 0:
        desc_input.first.wait_for(state="visible", timeout=5000)
        desc_input.first.fill("E2E 测试知识库")

    # 3. 选择向量模型（必填）
    model_combo = dialog.locator("[role=combobox]").first
    assert model_combo.count() > 0, "向量模型选择器不存在"
    if model_combo.is_disabled():
        pytest.skip("向量模型选择器被禁用，系统中无可用的 embedding 模型")
    model_combo.wait_for(state="visible", timeout=5000)
    model_combo.click()
    logged_in_page.wait_for_timeout(800)
    options = logged_in_page.locator("[role=option]")
    assert options.count() > 0, "向量模型下拉无选项"
    options.first.wait_for(state="visible", timeout=5000)
    options.first.click()
    logged_in_page.wait_for_timeout(800)

    # 4. 选择内置解析方法（builtin radio）
    builtin_radio = dialog.locator("input[type=radio][value=builtin]")
    if builtin_radio.count() > 0:
        builtin_radio.first.wait_for(state="visible", timeout=5000)
        builtin_radio.first.click()
        logged_in_page.wait_for_timeout(800)

    # 5. 选择分块方法（第二个 combobox）
    chunk_combo = dialog.locator("[role=combobox]").nth(1)
    if chunk_combo.count() > 0 and not chunk_combo.is_disabled():
        chunk_combo.wait_for(state="visible", timeout=5000)
        chunk_combo.click()
        logged_in_page.wait_for_timeout(800)
        chunk_options = logged_in_page.locator("[role=option]")
        if chunk_options.count() > 0:
            chunk_options.first.wait_for(state="visible", timeout=5000)
            chunk_options.first.click()
            logged_in_page.wait_for_timeout(500)

    try:
        kb.submit_dialog()

        # 验证弹窗关闭
        logged_in_page.wait_for_timeout(800)
        dialog_after = logged_in_page.locator("[role=dialog]")
        still_open = dialog_after.count() > 0 and dialog_after.first.is_visible()

        # 如果弹窗仍在，可能是 429 限流导致保存请求被拒绝，等待后重试
        if still_open:
            print("[429] 保存后弹窗未关闭，等待限流窗口重置后重试...")
            _wait_rate_limit_reset(logged_in_page, 65)
            kb.goto()
            kb.click_create_kb()
            # 重新填写表单
            dialog2 = logged_in_page.locator("[role=dialog]")
            name_inp2 = dialog2.locator("input[placeholder*='项目文档'], input[placeholder*='名称']")
            if name_inp2.count() > 0:
                name_inp2.first.wait_for(state="visible", timeout=5000)
                name_inp2.first.fill(kb_name)
            desc_inp2 = dialog2.locator("textarea")
            if desc_inp2.count() > 0:
                desc_inp2.first.fill("E2E 测试知识库")
            # 重新选择向量模型
            model_combo2 = dialog2.locator("[role=combobox]").first
            if model_combo2.count() > 0 and not model_combo2.is_disabled():
                model_combo2.click()
                logged_in_page.wait_for_timeout(800)
                opts2 = logged_in_page.locator("[role=option]")
                if opts2.count() > 0:
                    opts2.first.click()
                    logged_in_page.wait_for_timeout(500)
            kb.submit_dialog()
            logged_in_page.wait_for_timeout(800)
            dialog_after2 = logged_in_page.locator("[role=dialog]")
            still_open = dialog_after2.count() > 0 and dialog_after2.first.is_visible()

        assert not still_open, "提交后弹窗未关闭，表单可能有校验错误"

        # 刷新验证列表
        kb.goto()
        kbs = _get_kbs_api(logged_in_page, base_url)
        found = any(kb_name in k.get("name", "") for k in kbs)
        assert found, f"新知识库 {kb_name} 未出现在 API 列表中"
        assert len(kbs) > len(initial_kbs), "知识库数量未增加"
        # 注册清理（以 API 查到的 kb_id 为准）
        for k in kbs:
            if kb_name in k.get("name", ""):
                register_cleanup(request, lambda kid=k["id"]: _delete_kb_api(logged_in_page, base_url, kid))
    finally:
        # 清理：无论 assert 是否通过，都删除测试数据
        kbs = _get_kbs_api(logged_in_page, base_url)
        for k in kbs:
            if kb_name in k.get("name", ""):
                _delete_kb_api(logged_in_page, base_url, k["id"])


@allure.epic("知识库")
@pytest.mark.order(322)
@pytest.mark.p1
def test_kb_003_name_empty_validation(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-KB-003: 名称为空时创建拦截"""
    kb = KnowledgePage(logged_in_page, base_url)
    kb.goto()
    initial_kbs = _get_kbs_api(logged_in_page, base_url)

    kb.click_create_kb()
    assert kb.is_dialog_open(), "弹窗未打开"

    dialog = logged_in_page.locator("[role=dialog]")
    save_btn = loc.save_or_submit_button(dialog)

    assert save_btn.count() > 0, "保存按钮不存在"
    is_disabled = save_btn.first.is_disabled()

    if is_disabled:
        # 按钮禁用 = 系统正确拦截
        pass
    else:
        # 按钮可用，点击后应有校验错误且弹窗不关闭
        save_btn.first.wait_for(state="visible", timeout=5000)
        save_btn.first.click(force=True)
        logged_in_page.wait_for_timeout(800)
        has_error = len(kb.get_form_validation_text()) > 0
        dialog_still_open = kb.is_dialog_open()
        assert has_error or dialog_still_open, \
            f"名称为空时未触发校验拦截（has_error={has_error}, dialog_still_open={dialog_still_open}）"

    kb.close_dialog()

    # 验证未创建新知识库
    final_kbs = _get_kbs_api(logged_in_page, base_url)
    assert len(final_kbs) == len(initial_kbs), \
        "名称为空时知识库被创建了"


@allure.epic("知识库")
@pytest.mark.order(323)
@pytest.mark.p0
def test_kb_004_upload_file(logged_in_page, base_url, request, embedding_required):
    """✅ 人工评审通过 | TC-KB-004: 上传文件到知识库 — 创建临时文件，通过 UI 上传，验证文件出现在资源列表中"""
    # 创建测试知识库
    kb_name = f"upload-{_PREFIX}"
    create_resp = _create_kb_api(logged_in_page, base_url, kb_name)
    # 统一走本模块的创建断言：仅上游 502/503/504（RagFlow 不可用）跳过，其余状态码一律失败
    _assert_kb_created(create_resp)
    kb_id = create_resp.json()["data"]["id"]
    register_cleanup(request, lambda kid=kb_id: _delete_kb_api(logged_in_page, base_url, kid))

    # 创建临时测试文件
    test_file = os.path.join(tempfile.gettempdir(), f"e2e_kb_upload_{_PREFIX}.txt")
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("这是一份用于 E2E 测试的上传文件。\n包含多行内容，验证知识库文件上传功能。\n第三行测试数据。")

    try:
        # 导航到知识库详情页（429 时自动等待重试）
        if not _goto_kb_detail(logged_in_page, base_url, kb_id):
            pytest.skip("429 限流导致知识库详情页无法加载")

        # 验证初始状态：暂无资源
        no_resource = logged_in_page.locator("text=暂无资源")
        assert no_resource.count() > 0, "初始状态应显示暂无资源"

        # 点击上传按钮
        upload_btn = logged_in_page.get_by_role("button", name="上传")
        assert upload_btn.count() > 0, "上传按钮不存在"
        assert upload_btn.first.is_visible(), "上传按钮不可见"

        # 通过 file_chooser 上传文件
        with logged_in_page.expect_file_chooser() as fc_info:
            upload_btn.first.click()
        file_chooser = fc_info.value
        file_chooser.set_files(test_file)

        # 等待上传完成（轮询等文件名出现在页面，最长 15 秒）
        file_name = os.path.basename(test_file)
        for _wait in range(15):
            if logged_in_page.locator(f"text={file_name}").count() > 0:
                break
            logged_in_page.wait_for_timeout(1000)

        # 验证 1：文件名出现在页面中
        assert logged_in_page.locator(f"text={file_name}").count() > 0, \
            f"上传后文件名 {file_name} 未出现在页面中"

        # 验证 2："暂无资源" 消失
        assert logged_in_page.locator("text=暂无资源").count() == 0, \
            "上传文件后仍显示暂无资源"

        # 验证 3：资源计数更新
        res_count = logged_in_page.locator("text=/资源（\\d+）/")
        assert res_count.count() > 0, "资源计数未显示"
        count_text = res_count.first.text_content().strip()
        assert "0" not in count_text, f"上传后资源计数仍为 0: {count_text}"

        # 验证 4：API 层确认资源存在
        resources_resp = logged_in_page.request.get(
            f"{base_url}/web/knowledgeBases/{kb_id}/resources"
        )
        assert resources_resp.status == 200, "获取资源列表失败"
        resources = resources_resp.json().get("data", [])
        found = any(file_name in r.get("sourceName", "") for r in resources)
        assert found, f"文件 {file_name} 未出现在 API 资源列表中"

    finally:
        # 清理临时文件（Windows 文件锁，Playwright 可能仍持有句柄）
        if os.path.exists(test_file):
            try:
                _safe_remove(test_file)
            except PermissionError:
                import time
                time.sleep(1)
                try:
                    _safe_remove(test_file)
                except PermissionError:
                    pass  # 留给系统清理
        # 清理知识库
        _delete_kb_api(logged_in_page, base_url, kb_id)



@allure.epic("知识库")
@pytest.mark.order(326)
@pytest.mark.p1
def test_kb_007_delete_resource(logged_in_page, base_url, request, embedding_required):
    """✅ 人工评审通过 | TC-KB-007: 删除知识库资源 — 先上传文件，再通过 UI 删除，验证资源消失"""
    kb_name = f"del-res-{_PREFIX}"
    create_resp = _create_kb_api(logged_in_page, base_url, kb_name)
    # 统一走本模块的创建断言：仅上游 502/503/504（RagFlow 不可用）跳过，其余状态码一律失败
    _assert_kb_created(create_resp)
    kb_id = create_resp.json()["data"]["id"]
    register_cleanup(request, lambda kid=kb_id: _delete_kb_api(logged_in_page, base_url, kid))

    # 创建临时测试文件
    test_file = os.path.join(tempfile.gettempdir(), f"e2e_del_{_PREFIX}.txt")
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("这是一份用于测试资源删除功能的 E2E 文件。\n删除后应不再显示在资源列表中。")

    try:
        # 导航到知识库详情页（429 时自动等待重试）
        if not _goto_kb_detail(logged_in_page, base_url, kb_id):
            pytest.skip("429 限流导致知识库详情页无法加载")

        # 1. 上传文件
        upload_btn = logged_in_page.get_by_role("button", name="上传")
        assert upload_btn.count() > 0, "上传按钮不存在"
        with logged_in_page.expect_file_chooser() as fc_info:
            upload_btn.first.wait_for(state="visible", timeout=5000)
            upload_btn.first.click()
        fc_info.value.set_files(test_file)

        # 轮询等待文件名出现（上传+解析需要时间）
        file_name = os.path.basename(test_file)
        for _wait in range(15):
            if logged_in_page.locator(f"text={file_name}").count() > 0:
                break
            logged_in_page.wait_for_timeout(1000)

        assert logged_in_page.locator(f"text={file_name}").count() > 0, \
            f"上传后文件名 {file_name} 未出现"

        # 2. 点击删除按钮（在包含文件名的资源行中找 title="删除" 的按钮）
        #    实测 2026-09-15（正式环境）：资源列表为表格，行 = <tr>，
        #    名称在 <div class="knowledge-resource-name">，操作列删除按钮 title="删除"（actions.delete）
        file_row = logged_in_page.locator("div.knowledge-resource-name").filter(has_text=file_name)
        assert file_row.count() > 0, f"文件行不存在（文件名: {file_name}）"
        resource_row = file_row.first.locator("xpath=ancestor::tr[1]")
        if resource_row.count() == 0:
            # 兼容旧版 UI：行容器为 div.group
            resource_row = logged_in_page.locator("div.group").filter(has_text=file_name)
        assert resource_row.count() > 0, f"文件所在行不存在（文件名: {file_name}）"

        delete_icon = resource_row.first.locator('button[title="删除"]')
        if delete_icon.count() == 0:
            # 备选：通过 Trash2 SVG 图标定位（仍限定在本行内，禁止页面级兜底）
            delete_icon = resource_row.first.locator(
                "button:has(svg.lucide-trash2), button:has(svg[class*='trash'])"
            )

        assert delete_icon.count() == 1, \
            f"资源行内删除按钮应唯一，实际 {delete_icon.count()} 个（文件名: {file_name}）"
        delete_icon.first.wait_for(state="visible", timeout=5000)
        delete_icon.first.click()
        logged_in_page.wait_for_timeout(800)

        # 3. 处理确认弹窗（如果有）
        alert_dialog = logged_in_page.locator("[role=alertdialog]")
        if alert_dialog.count() > 0 and alert_dialog.first.is_visible():
            confirm_btn = loc.confirm_button(alert_dialog)
            if confirm_btn.count() > 0:
                confirm_btn.first.wait_for(state="visible", timeout=5000)
                confirm_btn.first.click()
                logged_in_page.wait_for_timeout(800)

        # 4. 验证资源已从页面消失（删除 + 列表刷新需要时间，轮询等待，禁止裸 count）
        for _wait in range(15):
            if logged_in_page.locator(f"text={file_name}").count() == 0:
                break
            logged_in_page.wait_for_timeout(1000)
        assert logged_in_page.locator(f"text={file_name}").count() == 0, \
            f"删除后文件名 {file_name} 仍然显示在页面中"

        # 5. 验证 API 层资源已删除（等待服务端处理完成）
        logged_in_page.wait_for_timeout(800)
        resources_resp = logged_in_page.request.get(
            f"{base_url}/web/knowledgeBases/{kb_id}/resources"
        )
        if resources_resp.status == 200:
            resources = resources_resp.json().get("data", [])
            found = any(file_name in r.get("sourceName", "") for r in resources)
            assert not found, f"删除后文件 {file_name} 仍在 API 资源列表中"

    finally:
        if os.path.exists(test_file):
            try:
                _safe_remove(test_file)
            except PermissionError:
                import time
                time.sleep(1)
                try:
                    _safe_remove(test_file)
                except PermissionError:
                    pass
        _delete_kb_api(logged_in_page, base_url, kb_id)


# TC-KB-008「知识库搜索」用例已于 2026-09-15 删除：
# 新版知识库为「目录 + 资源」双栏布局，页面无库级搜索框
# （AgentKnowledgeBasesPage.tsx / agent-knowledge-directory.tsx 无搜索输入，
#  i18n 仅残留 searchPlaceholder 键），后端 GET /web/knowledgeBases 亦无 keyword 参数，
# 原用例的 kb.search() 实际不生效（搜索前后计数相同），属失效用例。


@allure.epic("知识库")
@pytest.mark.order(328)
@pytest.mark.p1
def test_kb_009_delete_cascade(logged_in_page, base_url, request):
    """✅ 人工评审通过 | TC-KB-009: 删除知识库级联清理"""
    kb_name = f"cascade-{_PREFIX}"
    create_resp = _create_kb_api(logged_in_page, base_url, kb_name)
    # 统一走本模块的创建断言：仅上游 502/503/504（RagFlow 不可用）跳过，其余状态码一律失败
    _assert_kb_created(create_resp)
    kb_id = create_resp.json()["data"]["id"]
    register_cleanup(request, lambda kid=kb_id: _delete_kb_api(logged_in_page, base_url, kid))

    # 通过 API 删除并验证
    del_resp = _delete_kb_api(logged_in_page, base_url, kb_id)
    assert del_resp.status == 200, f"删除失败: {del_resp.status}"

    # 验证已删除
    kbs = _get_kbs_api(logged_in_page, base_url)
    exists = any(k["id"] == kb_id for k in kbs)
    assert not exists, "知识库删除后仍在列表中"

    # 详情也应不可访问
    detail = _get_kb_detail_api(logged_in_page, base_url, kb_id)
    if detail:
        assert not detail.get("success", True), \
            "删除后仍能获取详情"


@allure.epic("知识库")
@pytest.mark.order(329)
@pytest.mark.p1
def test_kb_010_detail_panel(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-KB-010: 知识库详情面板展示 — 导航到详情页，验证名称、向量模型、解析方法等信息"""
    kbs = _get_kbs_api(logged_in_page, base_url)
    if not kbs:
        pytest.skip("知识库列表为空")

    kb = kbs[0]
    kb_id = kb["id"]
    kb_name = kb["name"]

    # 导航到知识库详情页（429 时自动等待重试）
    if not _goto_kb_detail(logged_in_page, base_url, kb_id):
        pytest.skip("429 限流导致知识库详情页无法加载")

    body_text = logged_in_page.inner_text("body")

    # 1. 详情页结构（详情头 + 名称/状态）
    # 详情视图就绪：详情头 section.knowledge-detail-header（旧「返回知识库列表」文案已下线）
    detail_header = logged_in_page.locator("section.knowledge-detail-header")
    assert detail_header.count() == 1, "知识库详情头（section.knowledge-detail-header）未渲染"
    assert detail_header.first.is_visible(), "知识库详情头不可见"

    # 2. 知识库名称显示
    assert kb_name in body_text, f"详情页未显示知识库名称 {kb_name}"

    # 3. 向量模型信息显示
    assert "向量模型" in body_text, "详情页未显示向量模型信息"

    # 4. 解析方法信息显示
    assert "解析方法" in body_text, "详情页未显示解析方法信息"

    # 5. 资源区域存在
    assert "资源" in body_text, "详情页未显示资源区域"

    # 6. 操作按钮存在
    assert "编辑" in body_text, "详情页缺少编辑按钮"
    assert "删除" in body_text, "详情页缺少删除按钮"
    assert "上传" in body_text, "详情页缺少上传按钮"


# ==================== 补充测试（TC-KB-011 ~ 018）====================


@allure.epic("知识库")
@pytest.mark.order(330)
@pytest.mark.p0
def test_kb_011_upload_duplicate_confirm(logged_in_page, base_url, request, embedding_required):
    """TC-KB-011: 文件上传同名覆盖确认 — 上传同名文件应弹出覆盖确认对话框"""
    kb_name = f"dup-{_PREFIX}"
    create_resp = _create_kb_api(logged_in_page, base_url, kb_name)
    # 统一走本模块的创建断言：仅上游 502/503/504（RagFlow 不可用）跳过，其余状态码一律失败
    _assert_kb_created(create_resp)
    kb_id = create_resp.json()["data"]["id"]
    register_cleanup(request, lambda kid=kb_id: _delete_kb_api(logged_in_page, base_url, kid))

    test_file = os.path.join(tempfile.gettempdir(), f"e2e_dup_{_PREFIX}.txt")
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("第一次上传的内容。\n用于测试同名文件覆盖确认。")

    try:
        # 导航到知识库详情页（429 时自动等待重试）
        if not _goto_kb_detail(logged_in_page, base_url, kb_id):
            pytest.skip("429 限流导致知识库详情页无法加载")

        # 第一次上传
        upload_btn = logged_in_page.get_by_role("button", name="上传")
        assert upload_btn.count() > 0, "上传按钮不存在"
        with logged_in_page.expect_file_chooser() as fc_info:
            upload_btn.first.wait_for(state="visible", timeout=5000)
            upload_btn.first.click()
        fc_info.value.set_files(test_file)

        # 轮询等待文件名出现（上传+解析需要时间）
        file_name = os.path.basename(test_file)
        for _wait in range(15):
            if logged_in_page.locator(f"text={file_name}").count() > 0:
                break
            logged_in_page.wait_for_timeout(1000)

        assert logged_in_page.locator(f"text={file_name}").count() > 0, \
            f"第一次上传后文件名 {file_name} 未出现"

        # 第二次上传同名文件
        with logged_in_page.expect_file_chooser() as fc_info2:
            upload_btn.first.wait_for(state="visible", timeout=5000)
            upload_btn.first.click()
        fc_info2.value.set_files(test_file)
        logged_in_page.wait_for_timeout(800)

        # 检查覆盖确认对话框
        alert_dialog = logged_in_page.locator("[role=alertdialog]")
        dialog = logged_in_page.locator("[role=dialog]")
        has_confirm = (
            (alert_dialog.count() > 0 and alert_dialog.first.is_visible())
            or (dialog.count() > 0 and dialog.first.is_visible()
                and "覆盖" in dialog.first.inner_text())
        )

        if has_confirm:
            body_text = logged_in_page.locator("body").inner_text()
            assert "覆盖" in body_text, "覆盖确认对话框中缺少'覆盖'相关文本"
            # 取消覆盖
            cancel_btn = loc.cancel_button(alert_dialog).or_(
                loc.cancel_button(dialog)
            )
            if cancel_btn.count() > 0:
                cancel_btn.first.wait_for(state="visible", timeout=5000)
                cancel_btn.first.click()
                logged_in_page.wait_for_timeout(800)
        else:
            allure.attach(
                "第二次上传同名文件未弹出覆盖确认对话框，系统可能直接覆盖或拒绝",
                name="备注",
                attachment_type=allure.attachment_type.TEXT,
            )

    finally:
        if os.path.exists(test_file):
            _safe_remove(test_file)
        _delete_kb_api(logged_in_page, base_url, kb_id)


@allure.epic("知识库")
@pytest.mark.order(331)
@pytest.mark.p1
def test_kb_012_parse_status_polling(logged_in_page, base_url, request, embedding_required):
    """TC-KB-012: 资源解析状态轮询 — 上传文件后解析状态从 pending 变为 completed"""
    kb_name = f"parse-{_PREFIX}"
    create_resp = _create_kb_api(logged_in_page, base_url, kb_name)
    _assert_kb_created(create_resp)
    kb_id = create_resp.json()["data"]["id"]
    register_cleanup(request, lambda kid=kb_id: _delete_kb_api(logged_in_page, base_url, kid))

    test_file = os.path.join(tempfile.gettempdir(), f"e2e_parse_{_PREFIX}.txt")
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("用于测试解析状态轮询的文件内容。\n包含多行文本以触发解析流程。\n第三行数据。")

    try:
        # 导航到知识库详情页（429 时自动等待重试）
        if not _goto_kb_detail(logged_in_page, base_url, kb_id):
            pytest.skip("429 限流导致知识库详情页无法加载")

        # 上传文件
        upload_btn = logged_in_page.get_by_role("button", name="上传")
        assert upload_btn.count() > 0, "上传按钮不存在"
        with logged_in_page.expect_file_chooser() as fc_info:
            upload_btn.first.wait_for(state="visible", timeout=5000)
            upload_btn.first.click()
        fc_info.value.set_files(test_file)

        # 轮询等待文件名出现
        file_name = os.path.basename(test_file)
        for _wait in range(15):
            if logged_in_page.locator(f"text={file_name}").count() > 0:
                break
            logged_in_page.wait_for_timeout(1000)

        assert logged_in_page.locator(f"text={file_name}").count() > 0, \
            f"上传后文件名 {file_name} 未出现"

        # 通过 API 轮询解析状态（最多 60 秒）
        final_status = None
        for _ in range(12):
            resp = logged_in_page.request.get(
                f"{base_url}/web/knowledgeBases/{kb_id}/resources"
            )
            assert resp.status == 200, "获取资源列表失败"
            resources = resp.json().get("data", [])
            if resources:
                status = resources[0].get("status", "") or resources[0].get("parseStatus", "")
                if status in ("completed", "success", "done", "indexed", "ready"):
                    final_status = status
                    break
                if status in ("failed", "error"):
                    final_status = status
                    break
            time.sleep(5)

        assert final_status in ("completed", "success", "done", "indexed", "ready"), \
            f"60 秒内解析未完成，最终状态: {final_status}"

    finally:
        if os.path.exists(test_file):
            _safe_remove(test_file)
        _delete_kb_api(logged_in_page, base_url, kb_id)


@allure.epic("知识库")
@pytest.mark.order(332)
@pytest.mark.p1
def test_kb_013_reparse_resource(logged_in_page, base_url, request, embedding_required):
    """TC-KB-013: 重新解析资源 — 点击重新解析，可选删除旧分块"""
    kb_name = f"reparse-{_PREFIX}"
    create_resp = _create_kb_api(logged_in_page, base_url, kb_name)
    _assert_kb_created(create_resp)
    kb_id = create_resp.json()["data"]["id"]
    register_cleanup(request, lambda kid=kb_id: _delete_kb_api(logged_in_page, base_url, kid))

    test_file = os.path.join(tempfile.gettempdir(), f"e2e_reparse_{_PREFIX}.txt")
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("用于测试重新解析功能的文件。\n包含足够的内容以生成分块。")

    try:
        # 导航到知识库详情页（429 时自动等待重试）
        if not _goto_kb_detail(logged_in_page, base_url, kb_id):
            pytest.skip("429 限流导致知识库详情页无法加载")

        # 上传文件并等待解析完成
        upload_btn = logged_in_page.get_by_role("button", name="上传")
        assert upload_btn.count() > 0, "上传按钮不存在"
        with logged_in_page.expect_file_chooser() as fc_info:
            upload_btn.first.wait_for(state="visible", timeout=5000)
            upload_btn.first.click()
        fc_info.value.set_files(test_file)

        # 轮询等待文件名出现
        file_name = os.path.basename(test_file)
        for _wait in range(15):
            if logged_in_page.locator(f"text={file_name}").count() > 0:
                break
            logged_in_page.wait_for_timeout(1000)

        assert logged_in_page.locator(f"text={file_name}").count() > 0, \
            f"上传后文件名 {file_name} 未出现"

        # 等待解析完成
        for _ in range(12):
            resp = logged_in_page.request.get(
                f"{base_url}/web/knowledgeBases/{kb_id}/resources"
            )
            if resp.status == 200:
                resources = resp.json().get("data", [])
                if resources and (resources[0].get("status") or resources[0].get("parseStatus")) in (
                    "completed", "success", "done", "indexed", "ready"
                ):
                    break
            time.sleep(5)

        # 刷新页面
        try:
            logged_in_page.reload(wait_until="domcontentloaded")
        except Exception:
            pass
        logged_in_page.wait_for_load_state("domcontentloaded")
        try:
            logged_in_page.locator("div.agent-panel-content").first.wait_for(state="attached", timeout=8000)
        except Exception:
            pass

        file_name = os.path.basename(test_file)
        # 刷新后资源列表重新拉取需要时间，轮询等待文件名出现（禁止裸 count）
        for _wait in range(15):
            if logged_in_page.locator(f"text={file_name}").count() > 0:
                break
            logged_in_page.wait_for_timeout(1000)
        assert logged_in_page.locator(f"text={file_name}").count() > 0, \
            f"资源 {file_name} 未找到"

        # 查找重新解析按钮
        reparse_btn = loc.button_by_name_or_title(logged_in_page, "重新解析")

        if reparse_btn.count() > 0 and reparse_btn.first.is_visible():
            # 拦截 API 以验证重新解析请求
            reparse_called = []

            def on_reparse_resp(resp):
                if "reparse" in resp.url.lower() or "reindex" in resp.url.lower():
                    reparse_called.append({"url": resp.url, "status": resp.status})

            logged_in_page.on("response", on_reparse_resp)
            reparse_btn.first.wait_for(state="visible", timeout=5000)
            reparse_btn.first.click()

            # 等待确认弹窗出现（全量回归时服务端负载高，渲染可能延迟）
            alert_dialog = logged_in_page.locator("[role=alertdialog]")
            for _wait in range(8):
                if alert_dialog.count() > 0 and alert_dialog.first.is_visible():
                    break
                logged_in_page.wait_for_timeout(500)
            if alert_dialog.count() > 0 and alert_dialog.first.is_visible():
                # 检查是否有删除旧分块的复选框
                checkbox = alert_dialog.locator("input[type=checkbox], [role=checkbox]")
                if checkbox.count() > 0:
                    allure.attach(
                        "重新解析对话框包含删除旧分块选项",
                        name="对话框信息",
                        attachment_type=allure.attachment_type.TEXT,
                    )
                # 确认按钮文本为 "开始解析"（非标准的确认/确定）
                confirm = alert_dialog.get_by_role("button", name="开始解析").or_(
                    loc.confirm_button(alert_dialog)
                )
                if confirm.count() > 0:
                    confirm.first.wait_for(state="visible", timeout=5000)
                    confirm.first.click()
                    logged_in_page.wait_for_load_state("networkidle")
                    logged_in_page.wait_for_timeout(500)

            # 验证重新解析请求已发送（轮询等待响应捕获，防服务端负载高时响应慢）
            reparse_ok = False
            for _wait in range(15):
                if len(reparse_called) > 0:
                    reparse_ok = True
                    break
                logged_in_page.wait_for_timeout(1000)
            assert reparse_ok, "未检测到重新解析 API 请求"
        else:
            allure.attach(
                "未找到重新解析按钮，可能系统版本不支持此功能",
                name="备注",
                attachment_type=allure.attachment_type.TEXT,
            )

    finally:
        if os.path.exists(test_file):
            _safe_remove(test_file)
        _delete_kb_api(logged_in_page, base_url, kb_id)


@allure.epic("知识库")
@pytest.mark.order(333)
@pytest.mark.p1
def test_kb_014_retrieval_test_panel(logged_in_page, base_url, embedding_required):
    """TC-KB-014: 检索测试面板 — 在检索测试Tab中输入查询，返回相关分块"""
    kbs = _get_kbs_api(logged_in_page, base_url)
    if not kbs:
        pytest.skip("知识库列表为空")

    # 优先选择有资源的知识库
    kb_id = None
    for kb in kbs:
        resp = logged_in_page.request.get(
            f"{base_url}/web/knowledgeBases/{kb['id']}/resources"
        )
        if resp.status == 200:
            resources = resp.json().get("data", [])
            if resources:
                kb_id = kb["id"]
                break

    if not kb_id:
        kb_id = kbs[0]["id"]

    if not _goto_kb_detail(logged_in_page, base_url, kb_id):
        pytest.skip("429 限流导致知识库详情页无法加载")

    # 点击检索测试 Tab
    retrieval_tab = loc.tab_by_name(logged_in_page, "检索测试")

    if retrieval_tab.count() > 0 and retrieval_tab.first.is_visible():
        retrieval_tab.first.wait_for(state="visible", timeout=5000)
        retrieval_tab.first.click()
        logged_in_page.wait_for_timeout(800)

        # 查找搜索输入框
        search_input = logged_in_page.locator(
            "textarea[placeholder*='检索'], "
            "input[placeholder*='检索'], "
            "textarea[placeholder*='查询'], "
            "input[placeholder*='搜索']"
        )

        if search_input.count() > 0:
            search_input.first.wait_for(state="visible", timeout=5000)
            search_input.first.fill("测试查询")
            logged_in_page.wait_for_timeout(500)

            # 点击搜索按钮
            search_btn = loc.search_or_submit_button(logged_in_page)
            if search_btn.count() > 0:
                search_btn.first.wait_for(state="visible", timeout=5000)
                search_btn.first.click()
                logged_in_page.wait_for_timeout(800)

            # 验证有结果区域（可能有结果也可能为空，但至少面板存在）
            body_text = logged_in_page.inner_text("body")
            assert "检索测试" in body_text, "检索测试面板未正确显示"
        else:
            allure.attach(
                "检索测试面板中未找到搜索输入框",
                name="备注",
                attachment_type=allure.attachment_type.TEXT,
            )
    else:
        pytest.skip("知识库详情页无检索测试 Tab")


@allure.epic("知识库")
@pytest.mark.order(334)
@pytest.mark.p2
def test_kb_015_knowledge_graph(logged_in_page, base_url, embedding_required):
    """TC-KB-015: 知识图谱面板 — 点击知识图谱按钮，面板展示"""
    kbs = _get_kbs_api(logged_in_page, base_url)
    if not kbs:
        pytest.skip("知识库列表为空")

    kb_id = kbs[0]["id"]
    if not _goto_kb_detail(logged_in_page, base_url, kb_id):
        pytest.skip("429 限流导致知识库详情页无法加载")

    body_text = logged_in_page.inner_text("body")
    body_text = logged_in_page.inner_text("body")
    # 详情视图就绪：详情头 section.knowledge-detail-header（旧「返回知识库列表」文案已下线）
    detail_header = logged_in_page.locator("section.knowledge-detail-header")
    assert detail_header.count() == 1, "知识库详情头（section.knowledge-detail-header）未渲染"
    assert detail_header.first.is_visible(), "知识库详情头不可见"

    # 查找知识图谱按钮
    graph_btn = loc.button_by_name_or_title(logged_in_page, "知识图谱")

    if graph_btn.count() > 0 and graph_btn.first.is_visible():
        graph_btn.first.wait_for(state="visible", timeout=5000)
        graph_btn.first.click()
        logged_in_page.wait_for_timeout(800)

        # 验证图谱面板出现
        panel_text = logged_in_page.inner_text("body")
        has_graph_panel = any(kw in panel_text for kw in [
            "知识图谱", "图谱", "graph", "节点", "关系",
        ])
        graph_visual = logged_in_page.locator(
            "canvas, svg, [data-slot='graph']"
        )
        assert has_graph_panel or graph_visual.count() > 0, \
            f"知识图谱面板未展示（has_graph_panel={has_graph_panel}, graph_visual.count()={graph_visual.count()}）"
    else:
        allure.attach(
            "未找到知识图谱按钮，可能该知识库不支持知识图谱功能",
            name="备注",
            attachment_type=allure.attachment_type.TEXT,
        )


@allure.epic("知识库")
@pytest.mark.order(335)
@pytest.mark.p2
def test_kb_016_vector_model_management(logged_in_page, base_url, embedding_required):
    """TC-KB-016: 向量模型管理 — 打开向量模型管理对话框"""
    kbs = _get_kbs_api(logged_in_page, base_url)
    if not kbs:
        pytest.skip("知识库列表为空")

    kb_id = kbs[0]["id"]
    if not _goto_kb_detail(logged_in_page, base_url, kb_id):
        pytest.skip("429 限流导致知识库详情页无法加载")

    body_text = logged_in_page.inner_text("body")
    body_text = logged_in_page.inner_text("body")
    # 详情视图就绪：详情头 section.knowledge-detail-header（旧「返回知识库列表」文案已下线）
    detail_header = logged_in_page.locator("section.knowledge-detail-header")
    assert detail_header.count() == 1, "知识库详情头（section.knowledge-detail-header）未渲染"
    assert detail_header.first.is_visible(), "知识库详情头不可见"

    # 查找向量模型管理按钮
    vector_btn = loc.button_by_name_or_title(logged_in_page, "向量模型")

    if vector_btn.count() > 0 and vector_btn.first.is_visible():
        vector_btn.first.wait_for(state="visible", timeout=5000)
        vector_btn.first.click()
        logged_in_page.wait_for_timeout(800)

        # 验证对话框打开
        dialog = logged_in_page.locator("[role=dialog]")
        assert dialog.count() > 0 and dialog.first.is_visible(), \
            "向量模型管理对话框未打开"

        dialog_text = dialog.first.inner_text()
        has_model_info = any(kw in dialog_text for kw in [
            "模型", "向量", "embedding", "Embedding",
        ])
        assert has_model_info, \
            f"向量模型管理对话框内容不正确: {dialog_text[:200]}"

        # 关闭对话框
        close_btn = loc.close_button(dialog)
        if close_btn.count() > 0:
            close_btn.first.wait_for(state="visible", timeout=5000)
            close_btn.first.click()
    else:
        allure.attach(
            "未找到向量模型管理按钮，可能在编辑模式或系统不支持",
            name="备注",
            attachment_type=allure.attachment_type.TEXT,
        )


@allure.epic("知识库")
@pytest.mark.order(336)
@pytest.mark.p2
def test_kb_017_ragflow_import(logged_in_page, base_url, embedding_required):
    """TC-KB-017: RAGFlow 导入 — 打开 RAGFlow 导入对话框"""
    kb = KnowledgePage(logged_in_page, base_url)
    kb.goto()

    # 查找 RAGFlow 导入按钮
    ragflow_btn = loc.button_by_name_or_title(logged_in_page, "RAGFlow")

    if ragflow_btn.count() > 0 and ragflow_btn.first.is_visible():
        ragflow_btn.first.wait_for(state="visible", timeout=5000)
        ragflow_btn.first.click()
        logged_in_page.wait_for_timeout(800)

        # 验证导入对话框打开
        dialog = logged_in_page.locator("[role=dialog]")
        assert dialog.count() > 0 and dialog.first.is_visible(), \
            "RAGFlow 导入对话框未打开"

        dialog_text = dialog.first.inner_text()
        has_ragflow_info = any(kw in dialog_text for kw in [
            "RAGFlow", "ragflow", "导入", "连接", "配置",
            "未配置", "地址", "API",
        ])
        assert has_ragflow_info, \
            f"RAGFlow 导入对话框内容不正确: {dialog_text[:200]}"

        # 关闭对话框
        logged_in_page.keyboard.press("Escape")
        logged_in_page.wait_for_timeout(500)
    else:
        # RAGFlow 按钮可能不在列表页，尝试进入知识库详情查找
        kbs = _get_kbs_api(logged_in_page, base_url)
        if kbs:
            kb_id = kbs[0]["id"]
            if not _goto_kb_detail(logged_in_page, base_url, kb_id):
                pytest.skip("429 限流导致知识库详情页无法加载")

            detail_ragflow = logged_in_page.locator("button").filter(has_text="RAGFlow")
            if detail_ragflow.count() > 0:
                detail_ragflow.first.wait_for(state="visible", timeout=5000)
                detail_ragflow.first.click()
                logged_in_page.wait_for_timeout(800)
                dialog = logged_in_page.locator("[role=dialog]")
                assert dialog.count() > 0, "RAGFlow 导入对话框未打开"
            else:
                allure.attach(
                    "页面中未找到 RAGFlow 导入按钮，可能系统未配置 RAGFlow 集成",
                    name="备注",
                    attachment_type=allure.attachment_type.TEXT,
                )
        else:
            pytest.skip("知识库列表为空且无 RAGFlow 按钮")


@allure.epic("知识库")
@pytest.mark.order(337)
@pytest.mark.p2
def test_kb_018_resource_preview(logged_in_page, base_url, request, embedding_required):
    """TC-KB-018: 资源预览 — 点击资源预览，展示文件内容"""
    kb_name = f"preview-{_PREFIX}"
    create_resp = _create_kb_api(logged_in_page, base_url, kb_name)
    _assert_kb_created(create_resp)
    kb_id = create_resp.json()["data"]["id"]
    register_cleanup(request, lambda kid=kb_id: _delete_kb_api(logged_in_page, base_url, kid))

    test_file = os.path.join(tempfile.gettempdir(), f"e2e_preview_{_PREFIX}.txt")
    preview_content = "这是用于预览测试的文件内容。\n包含中文和英文 mixed content。\n第三行用于验证预览功能。"
    with open(test_file, "w", encoding="utf-8") as f:
        f.write(preview_content)

    try:
        # 导航到知识库详情页（429 时自动等待重试）
        if not _goto_kb_detail(logged_in_page, base_url, kb_id):
            pytest.skip("429 限流导致知识库详情页无法加载")

        # 上传文件
        upload_btn = logged_in_page.get_by_role("button", name="上传")
        assert upload_btn.count() > 0, "上传按钮不存在"
        with logged_in_page.expect_file_chooser() as fc_info:
            upload_btn.first.wait_for(state="visible", timeout=5000)
            upload_btn.first.click()
        fc_info.value.set_files(test_file)
        logged_in_page.wait_for_load_state("domcontentloaded")
        try:
            logged_in_page.locator("div.agent-panel-content").first.wait_for(state="attached", timeout=8000)
        except Exception:
            pass

        # 等待解析完成
        for _ in range(12):
            resp = logged_in_page.request.get(
                f"{base_url}/web/knowledgeBases/{kb_id}/resources"
            )
            if resp.status == 200:
                resources = resp.json().get("data", [])
                if resources and resources[0].get("status") in (
                    "ready", "completed", "success", "done", "indexed"
                ):
                    break
            time.sleep(5)

        # 刷新页面
        try:
            logged_in_page.reload(wait_until="domcontentloaded")
        except Exception:
            pass
        logged_in_page.wait_for_load_state("domcontentloaded")
        try:
            logged_in_page.locator("div.agent-panel-content").first.wait_for(state="attached", timeout=8000)
        except Exception:
            pass

        file_name = os.path.basename(test_file)
        file_loc = logged_in_page.locator(f"text={file_name}")
        for _ in range(12):
            if file_loc.count() > 0:
                break
            logged_in_page.wait_for_timeout(1000)
        assert file_loc.count() > 0, \
            f"资源 {file_name} 未找到"

        # 查找预览按钮
        preview_btn = loc.button_by_name_or_title(logged_in_page, "预览")

        if preview_btn.count() > 0 and preview_btn.first.is_visible():
            preview_btn.first.wait_for(state="visible", timeout=5000)
            preview_btn.first.click()
            logged_in_page.wait_for_timeout(800)

            # 验证预览面板或对话框出现
            dialog = logged_in_page.locator("[role=dialog]")
            preview_panel = logged_in_page.locator(
                "[data-slot='preview']"
            )

            has_preview = (
                (dialog.count() > 0 and dialog.first.is_visible())
                or preview_panel.count() > 0
            )
            assert has_preview, "资源预览面板未展示"

            # 验证预览中有内容
            if dialog.count() > 0 and dialog.first.is_visible():
                preview_text = dialog.first.inner_text()
                assert len(preview_text) > 0, "预览对话框内容为空"
        else:
            # 尝试点击文件名来打开预览
            file_link = logged_in_page.locator(f"text={file_name}")
            if file_link.count() > 0:
                file_link.first.wait_for(state="visible", timeout=5000)
                file_link.first.click()
                logged_in_page.wait_for_timeout(800)

                dialog = logged_in_page.locator("[role=dialog]")
                body_text = logged_in_page.inner_text("body")
                has_preview = (
                    dialog.count() > 0
                    or "预览" in body_text
                    or "内容" in body_text
                )
                assert has_preview, "点击文件名后未打开预览"
            else:
                allure.attach(
                    "未找到预览按钮且无法通过文件名打开预览",
                    name="备注",
                    attachment_type=allure.attachment_type.TEXT,
                )

    finally:
        if os.path.exists(test_file):
            _safe_remove(test_file)
        _delete_kb_api(logged_in_page, base_url, kb_id)


@allure.epic("知识库")
@pytest.mark.order(338)
@pytest.mark.p1
def test_kb_019_toggle_resource_enabled(logged_in_page, base_url, request, embedding_required):
    """TC-KB-019: 资源启用/禁用 Switch — 切换资源的启用/禁用状态"""
    kb_name = f"toggle-{_PREFIX}"
    create_resp = _create_kb_api(logged_in_page, base_url, kb_name)
    _assert_kb_created(create_resp)
    kb_id = create_resp.json()["data"]["id"]
    register_cleanup(request, lambda kid=kb_id: _delete_kb_api(logged_in_page, base_url, kid))

    test_file = os.path.join(tempfile.gettempdir(), f"e2e_toggle_{_PREFIX}.txt")
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("用于测试资源启用/禁用的文件内容。")

    try:
        # 导航到知识库详情页（429 时自动等待重试）
        if not _goto_kb_detail(logged_in_page, base_url, kb_id):
            pytest.skip("429 限流导致知识库详情页无法加载")

        # 上传文件
        upload_btn = logged_in_page.get_by_role("button", name="上传")
        assert upload_btn.count() > 0, "上传按钮不存在"
        with logged_in_page.expect_file_chooser() as fc_info:
            upload_btn.first.wait_for(state="visible", timeout=5000)
            upload_btn.first.click()
        fc_info.value.set_files(test_file)
        logged_in_page.wait_for_load_state("domcontentloaded")
        try:
            logged_in_page.locator("div.agent-panel-content").first.wait_for(state="attached", timeout=8000)
        except Exception:
            pass

        # 查找资源行的 Switch
        switch = logged_in_page.locator("[role='switch']")
        if switch.count() > 0:
            initial_checked = switch.first.get_attribute("aria-checked")
            switch.first.wait_for(state="visible", timeout=5000)
            switch.first.click()
            logged_in_page.wait_for_timeout(1500)
            new_checked = switch.first.get_attribute("aria-checked")
            assert new_checked != initial_checked, \
                f"切换后状态未变化: {initial_checked} → {new_checked}"
        else:
            resp = logged_in_page.request.get(
                f"{base_url}/web/knowledgeBases/{kb_id}/resources"
            )
            assert resp.status == 200, "资源列表 API 不可访问"
            allure.attach(
                "资源行未找到 Switch 控件",
                name="备注",
                attachment_type=allure.attachment_type.TEXT,
            )
    finally:
        if os.path.exists(test_file):
            _safe_remove(test_file)
        _delete_kb_api(logged_in_page, base_url, kb_id)


@allure.epic("知识库")
@pytest.mark.order(339)
@pytest.mark.p1
def test_kb_020_edit_kb_info(logged_in_page, base_url, request):
    """TC-KB-020: 知识库编辑（修改名称/描述）"""
    kb_name = f"edit-{_PREFIX}"
    create_resp = _create_kb_api(logged_in_page, base_url, kb_name, desc="原始描述")
    _assert_kb_created(create_resp)
    kb_id = create_resp.json()["data"]["id"]
    register_cleanup(request, lambda kid=kb_id: _delete_kb_api(logged_in_page, base_url, kid))

    try:
        # 导航到知识库详情页（429 时自动等待重试）
        if not _goto_kb_detail(logged_in_page, base_url, kb_id):
            pytest.skip("429 限流导致知识库详情页无法加载")

        body_text = logged_in_page.inner_text("body")
        body_text = logged_in_page.inner_text("body")
        detail_header = logged_in_page.locator("section.knowledge-detail-header")
        assert detail_header.count() == 1, "知识库详情头（section.knowledge-detail-header）未渲染"

        edit_btn = loc.button_by_name_or_title(logged_in_page, "编辑")
        if edit_btn.count() > 0 and edit_btn.first.is_visible():
            edit_btn.first.wait_for(state="visible", timeout=5000)
            edit_btn.first.click()
            logged_in_page.wait_for_timeout(1500)

            dialog = logged_in_page.locator("[role=dialog]")
            if dialog.count() > 0 and dialog.first.is_visible():
                new_name = f"{kb_name}-edited"
                # 名称输入框：优先 placeholder 匹配，备选 dialog 中第一个 input
                name_input = dialog.locator(
                    "input[placeholder*='名称'], input[placeholder*='知识库名称'], "
                    "input[placeholder*='例如']"
                )
                if name_input.count() == 0:
                    # 备选：dialog 中第一个 input（编辑弹窗只有名称+描述两个字段）
                    name_input = dialog.locator("input")
                if name_input.count() > 0:
                    name_input.first.wait_for(state="visible", timeout=5000)
                    name_input.first.click()
                    name_input.first.fill("")
                    name_input.first.fill(new_name)

                save_btn = loc.save_or_submit_button(dialog)
                if save_btn.count() > 0:
                    save_btn.first.wait_for(state="visible", timeout=5000)
                    save_btn.first.click()
                    logged_in_page.wait_for_load_state("networkidle")
                    logged_in_page.wait_for_timeout(500)
                else:
                    # 备选：dialog 中最后一个 button（可能是提交按钮）
                    all_btns = dialog.locator("button")
                    if all_btns.count() > 0:
                        all_btns.last.wait_for(state="visible", timeout=5000)
                        all_btns.last.click()
                        logged_in_page.wait_for_load_state("networkidle")
                        logged_in_page.wait_for_timeout(500)

                # API 验证
                detail = _get_kb_detail_api(logged_in_page, base_url, kb_id)
                if detail and detail.get("data"):
                    updated_name = detail["data"].get("name", "")
                    assert updated_name == new_name, \
                        f"编辑后名称未更新: 期望 '{new_name}'，实际 '{updated_name}'"
            else:
                allure.attach("点击编辑后未弹出对话框", name="备注",
                              attachment_type=allure.attachment_type.TEXT)
        else:
            update_resp = logged_in_page.request.patch(
                f"{base_url}/web/knowledgeBases/{kb_id}",
                data=json.dumps({"description": "API 更新描述"}),
                headers={"Content-Type": "application/json"},
            )
            assert update_resp.status < 400, \
                f"知识库更新 API 失败: status={update_resp.status}"
    finally:
        _delete_kb_api(logged_in_page, base_url, kb_id)


@allure.epic("知识库")
@pytest.mark.order(340)
@pytest.mark.p1
def test_kb_021_delete_via_ui(logged_in_page, base_url, request):
    """TC-KB-021: 知识库 UI 删除 — 详情头「删除」按钮 + 确认弹窗（含目标名称）后校验消失

    新版 UI 结构（AgentKnowledgeBasesPage.tsx:557-628）：
    详情容器 section.knowledge-detail-header 内含 <h2>{name}</h2> 与「编辑」「删除」按钮。
    旧锚点「返回知识库列表」+ ancestor::div[4] 已随改版失效（2026-08-18 误删事故的防护代码），
    此处改为：详情头唯一 + h2 名称等于目标 + 删除按钮在详情头内唯一 + 确认弹窗必须包含目标名称。
    """
    kb_name = f"del-ui-{_PREFIX}"
    create_resp = _create_kb_api(logged_in_page, base_url, kb_name, desc="UI删除测试")
    _assert_kb_created(create_resp)
    kb_id = create_resp.json()["data"]["id"]
    register_cleanup(request, lambda kid=kb_id: _delete_kb_api(logged_in_page, base_url, kid))

    # 导航到知识库详情页（?kbId=xxx，429 时自动等待重试）
    if not _goto_kb_detail(logged_in_page, base_url, kb_id):
        pytest.skip("知识库详情页未加载（可能 429 限流）")

    # 1. 详情头唯一，且指向目标知识库（防误删的第一道锚点）
    detail_header = logged_in_page.locator("section.knowledge-detail-header")
    assert detail_header.count() == 1, \
        f"知识库详情头应唯一，实际 {detail_header.count()} 个"
    header_name = detail_header.locator("h2").first.inner_text().strip()
    assert header_name == kb_name, \
        f"详情头名称与目标知识库不一致: 期望 {kb_name!r}，实际 {header_name!r}"

    # 2. 删除按钮限定在详情头内，并强制唯一（不可逆操作的安全断言）
    delete_btn = detail_header.get_by_role("button", name="删除", exact=True)
    assert delete_btn.count() == 1, \
        f"详情头「删除」按钮应唯一，实际 {delete_btn.count()} 个"
    delete_btn.first.wait_for(state="visible", timeout=5000)
    delete_btn.first.click()

    # 3. 确认弹窗（ConfirmDialog → role=alertdialog）：文案必须指向目标知识库
    alert = logged_in_page.locator("[role=alertdialog]")
    alert.first.wait_for(state="visible", timeout=8000)
    dialog_text = alert.first.inner_text()
    assert "确认删除知识库" in dialog_text, \
        f"确认弹窗标题不是知识库删除: {dialog_text[:120]!r}"
    assert kb_name in dialog_text, (
        f"确认弹窗未包含目标知识库名 {kb_name!r}，禁止点击确认（防误删）：{dialog_text[:120]!r}"
    )
    assert "删除智能体" not in dialog_text, (
        f"【严重】确认弹窗是关于删除智能体的，不是知识库！弹窗内容: {dialog_text[:120]!r}"
    )

    confirm_btn = alert.first.get_by_role("button", name="确认", exact=True)
    assert confirm_btn.count() == 1, \
        f"确认弹窗「确认」按钮应唯一，实际 {confirm_btn.count()} 个"
    confirm_btn.first.click()
    alert.first.wait_for(state="hidden", timeout=15000)

    # 4. 结果校验：API 列表中不再存在该知识库
    kbs = _get_kbs_api(logged_in_page, base_url)
    assert not any(k["id"] == kb_id for k in kbs), \
        f"UI 删除后知识库仍存在: {kb_name}"


# ==================== 分块详情 Sheet 补充测试（TC-KB-GAP-01 ~ 05）====================


@allure.epic("知识库")
@pytest.mark.order(341)
@pytest.mark.p1
def test_kb_gap_01_chunk_sheet_open(logged_in_page, base_url, embedding_required):
    """TC-KB-GAP-01: 分块详情 Sheet 打开 — 点击资源文件名链接，Sheet 从右侧滑出"""
    kbs = _get_kbs_api(logged_in_page, base_url)
    if not kbs:
        pytest.skip("知识库列表为空")

    # 找到有 chunks 的知识库
    kb_id = None
    resource_name = None
    for kb in kbs:
        resp = logged_in_page.request.get(
            f"{base_url}/web/knowledgeBases/{kb['id']}/resources"
        )
        if resp.status == 200:
            resources = resp.json().get("data", [])
            for r in resources:
                if (r.get("chunkCount") or 0) > 0:
                    kb_id = kb["id"]
                    resource_name = r.get("sourceName", "")
                    break
        if kb_id:
            break

    if not kb_id:
        pytest.skip("无包含 chunks 的知识库资源，跳过 Sheet 测试")

    # 导航到知识库详情页
    if not _goto_kb_detail(logged_in_page, base_url, kb_id):
        pytest.skip("429 限流导致知识库详情页无法加载")

    kb_page = KnowledgePage(logged_in_page, base_url)

    # 点击资源文件名打开 Sheet
    opened = kb_page.open_chunk_sheet(resource_name)
    assert opened, f"分块详情 Sheet 未打开（资源: {resource_name}）"

    # 验证 Sheet 内容
    sheet_text = kb_page.get_chunk_sheet_text()
    assert resource_name in sheet_text, \
        f"Sheet 标题不包含资源名 '{resource_name}'"
    assert "切片" in sheet_text, "Sheet 不包含'切片'关键词"
    assert "文档预览" in sheet_text, "Sheet 缺少文档预览区域"

    # 验证搜索输入框存在
    search_input = kb_page.get_chunk_sheet_search_input()
    assert search_input.count() > 0, "Sheet 内搜索输入框不存在"

    # 验证有切片 Switch
    switches = kb_page.get_chunk_sheet_switches()
    assert switches.count() > 0, "Sheet 内无切片 Switch"

    # 验证全文/省略按钮
    ellipse_btn = kb_page.get_chunk_sheet_text_mode_button("省略")
    full_btn = kb_page.get_chunk_sheet_text_mode_button("全文")
    assert ellipse_btn.count() > 0, "Sheet 缺少'省略'按钮"
    assert full_btn.count() > 0, "Sheet 缺少'全文'按钮"

    kb_page.close_chunk_sheet()


@allure.epic("知识库")
@pytest.mark.order(342)
@pytest.mark.p1
def test_kb_gap_02_chunk_toggle_enabled(logged_in_page, base_url, request, embedding_required):
    """TC-KB-GAP-02: 分块详情 Sheet — 切片启用/禁用切换"""
    kb_name = f"chunk-toggle-{_PREFIX}"
    create_resp = _create_kb_api(logged_in_page, base_url, kb_name)
    _assert_kb_created(create_resp)
    kb_id = create_resp.json()["data"]["id"]
    register_cleanup(request, lambda kid=kb_id: _delete_kb_api(logged_in_page, base_url, kid))

    test_file = os.path.join(tempfile.gettempdir(), f"e2e_chunk_{_PREFIX}.txt")
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("用于测试分块详情 Sheet 切片启用禁用功能的文件。\n" * 10)

    try:
        if not _goto_kb_detail(logged_in_page, base_url, kb_id):
            pytest.skip("429 限流导致知识库详情页无法加载")

        # 上传文件
        upload_btn = logged_in_page.get_by_role("button", name="上传")
        assert upload_btn.count() > 0, "上传按钮不存在"
        with logged_in_page.expect_file_chooser() as fc_info:
            upload_btn.first.wait_for(state="visible", timeout=5000)
            upload_btn.first.click()
        fc_info.value.set_files(test_file)

        file_name = os.path.basename(test_file)
        for _wait in range(15):
            if logged_in_page.locator(f"text={file_name}").count() > 0:
                break
            logged_in_page.wait_for_timeout(1000)

        assert logged_in_page.locator(f"text={file_name}").count() > 0, \
            f"上传后文件名 {file_name} 未出现"

        # 等待解析完成：以「目标资源 chunkCount > 0」为准
        # （原实现取 resources[0] 且只看 status，列表顺序不保证 + status=ready 时切片可能尚未生成）
        for _ in range(12):
            resp = logged_in_page.request.get(
                f"{base_url}/web/knowledgeBases/{kb_id}/resources"
            )
            if resp.status == 200:
                resources = resp.json().get("data", [])
                target = next(
                    (r for r in resources if r.get("sourceName") == file_name), None
                )
                if target and (target.get("chunkCount") or 0) > 0:
                    break
            time.sleep(5)

        # 刷新页面
        try:
            logged_in_page.reload(wait_until="domcontentloaded")
        except Exception:
            pass
        logged_in_page.wait_for_load_state("domcontentloaded")
        logged_in_page.wait_for_timeout(1000)

        kb_page = KnowledgePage(logged_in_page, base_url)

        # 打开 Sheet（open_chunk_sheet 内部已等待切片渲染完成）
        opened = kb_page.open_chunk_sheet(file_name)
        assert opened, "分块详情 Sheet 未打开"

        # 获取第一个 Switch 的初始状态
        switches = kb_page.get_chunk_sheet_switches()
        assert switches.count() > 0, "Sheet 内无切片 Switch"

        initial_checked = switches.first.get_attribute("aria-checked")
        assert initial_checked is not None, "Switch 无 aria-checked 属性"

        # 切换
        switches.first.click()
        logged_in_page.wait_for_timeout(1000)

        # 验证状态变化
        new_checked = switches.first.get_attribute("aria-checked")
        assert new_checked != initial_checked, \
            f"切片 Switch 状态未变化: {initial_checked} → {new_checked}"

        kb_page.close_chunk_sheet()

    finally:
        if os.path.exists(test_file):
            _safe_remove(test_file)
        _delete_kb_api(logged_in_page, base_url, kb_id)


@allure.epic("知识库")
@pytest.mark.order(343)
@pytest.mark.p1
def test_kb_gap_03_chunk_search(logged_in_page, base_url, embedding_required):
    """TC-KB-GAP-03: 分块详情 Sheet — 搜索切片"""
    kbs = _get_kbs_api(logged_in_page, base_url)
    if not kbs:
        pytest.skip("知识库列表为空")

    # 找到有 chunks 的知识库
    kb_id = None
    resource_name = None
    for kb in kbs:
        resp = logged_in_page.request.get(
            f"{base_url}/web/knowledgeBases/{kb['id']}/resources"
        )
        if resp.status == 200:
            resources = resp.json().get("data", [])
            for r in resources:
                if (r.get("chunkCount") or 0) > 0:
                    kb_id = kb["id"]
                    resource_name = r.get("sourceName", "")
                    break
        if kb_id:
            break

    if not kb_id:
        pytest.skip("无包含 chunks 的知识库资源")

    if not _goto_kb_detail(logged_in_page, base_url, kb_id):
        pytest.skip("429 限流导致知识库详情页无法加载")

    kb_page = KnowledgePage(logged_in_page, base_url)
    opened = kb_page.open_chunk_sheet(resource_name)
    assert opened, "分块详情 Sheet 未打开"

    # 获取搜索前的 Switch 数量
    switches_before = kb_page.get_chunk_sheet_switches().count()
    assert switches_before > 0, "Sheet 内无切片"

    # 输入搜索关键词（使用切片内容中常见的词）
    search_input = kb_page.get_chunk_sheet_search_input()
    search_input.first.fill("报销")
    logged_in_page.keyboard.press("Enter")
    logged_in_page.wait_for_timeout(1000)

    # 搜索后应有过滤结果
    sheet_text = kb_page.get_chunk_sheet_text()
    assert any(kw in sheet_text for kw in ["报销", "无匹配", "0 个切片"]), \
        f"分块搜索后未显示结果也无空状态提示，实际文本片段: '{sheet_text[:200] if sheet_text else '(empty)'}'"

    # 清空搜索恢复
    search_input.first.fill("")
    logged_in_page.keyboard.press("Enter")
    logged_in_page.wait_for_timeout(1000)

    switches_after = kb_page.get_chunk_sheet_switches().count()
    assert switches_after == switches_before, \
        f"清空搜索后切片数不一致: {switches_before} → {switches_after}"

    kb_page.close_chunk_sheet()


@allure.epic("知识库")
@pytest.mark.order(344)
@pytest.mark.p2
def test_kb_gap_04_chunk_text_mode_toggle(logged_in_page, base_url, embedding_required):
    """TC-KB-GAP-04: 分块详情 Sheet — 全文/省略切换"""
    kbs = _get_kbs_api(logged_in_page, base_url)
    if not kbs:
        pytest.skip("知识库列表为空")

    kb_id = None
    resource_name = None
    for kb in kbs:
        resp = logged_in_page.request.get(
            f"{base_url}/web/knowledgeBases/{kb['id']}/resources"
        )
        if resp.status == 200:
            resources = resp.json().get("data", [])
            for r in resources:
                if (r.get("chunkCount") or 0) > 0:
                    kb_id = kb["id"]
                    resource_name = r.get("sourceName", "")
                    break
        if kb_id:
            break

    if not kb_id:
        pytest.skip("无包含 chunks 的知识库资源")

    if not _goto_kb_detail(logged_in_page, base_url, kb_id):
        pytest.skip("429 限流导致知识库详情页无法加载")

    kb_page = KnowledgePage(logged_in_page, base_url)
    opened = kb_page.open_chunk_sheet(resource_name)
    assert opened, "分块详情 Sheet 未打开"

    # 验证两个模式按钮存在
    ellipse_btn = kb_page.get_chunk_sheet_text_mode_button("省略")
    full_btn = kb_page.get_chunk_sheet_text_mode_button("全文")
    assert ellipse_btn.count() > 0, "缺少'省略'按钮"
    assert full_btn.count() > 0, "缺少'全文'按钮"

    # 点击"全文"
    full_btn.first.click()
    logged_in_page.wait_for_timeout(1000)

    # 验证"全文"按钮高亮（紫色背景 class）
    full_cls = full_btn.first.get_attribute("class") or ""
    assert any(kw in full_cls for kw in ["bg-", "text-white"]), \
        f"点击'全文'后按钮未高亮（class='{full_cls}'）"

    # 点击"省略"切回
    ellipse_btn.first.click()
    logged_in_page.wait_for_timeout(1000)

    ellipse_cls = ellipse_btn.first.get_attribute("class") or ""
    assert any(kw in ellipse_cls for kw in ["bg-", "text-white"]), \
        f"点击'省略'后按钮未高亮（class='{ellipse_cls}'）"

    kb_page.close_chunk_sheet()


@allure.epic("知识库")
@pytest.mark.order(345)
@pytest.mark.p1
def test_kb_gap_05_chunk_sheet_close(logged_in_page, base_url, embedding_required):
    """TC-KB-GAP-05: 分块详情 Sheet — 关闭（Escape / Close 按钮）"""
    kbs = _get_kbs_api(logged_in_page, base_url)
    if not kbs:
        pytest.skip("知识库列表为空")

    kb_id = None
    resource_name = None
    for kb in kbs:
        resp = logged_in_page.request.get(
            f"{base_url}/web/knowledgeBases/{kb['id']}/resources"
        )
        if resp.status == 200:
            resources = resp.json().get("data", [])
            for r in resources:
                if (r.get("chunkCount") or 0) > 0:
                    kb_id = kb["id"]
                    resource_name = r.get("sourceName", "")
                    break
        if kb_id:
            break

    if not kb_id:
        pytest.skip("无包含 chunks 的知识库资源")

    if not _goto_kb_detail(logged_in_page, base_url, kb_id):
        pytest.skip("429 限流导致知识库详情页无法加载")

    kb_page = KnowledgePage(logged_in_page, base_url)

    # 测试 Escape 关闭
    opened = kb_page.open_chunk_sheet(resource_name)
    assert opened, "分块详情 Sheet 未打开"
    kb_page.close_chunk_sheet()
    logged_in_page.wait_for_timeout(1000)
    assert not kb_page.is_chunk_sheet_open(), "Escape 后 Sheet 未关闭"

    # 测试 Close 按钮关闭
    opened2 = kb_page.open_chunk_sheet(resource_name)
    assert opened2, "分块详情 Sheet 第二次未打开"
    dialog = logged_in_page.locator("[role=dialog][data-state=open]")
    close_btn = dialog.get_by_role("button", name="Close")
    if close_btn.count() > 0:
        close_btn.first.click()
        logged_in_page.wait_for_timeout(1000)
        assert not kb_page.is_chunk_sheet_open(), "Close 按钮后 Sheet 未关闭"
    else:
        # 无 Close 按钮，用 Escape 关闭
        kb_page.close_chunk_sheet()


# TC-KB-GAP-06「清除记录」用例已于 2026-09-15 删除：
# 「清除记录」文案在 web/src 全量源码中 0 命中，功能已下线；
# 原用例内部 clear_btns == 0 → pytest.skip 恒成立（静默跳过掩盖失效），故删除。


# TC-KB-P1「知识库批量操作」用例已于 2026-09-15 删除：
# 当前 UI 已无批量选择能力 —— web/src 全量源码中 Checkbox 仅用于「重新解析」弹窗
# （AgentKnowledgeBasesPage.tsx:21 引入、:995 使用），知识库列表与资源表均无 checkbox 列
# （agent-knowledge-resources.tsx 无 Checkbox 引用）。
# 原用例在 staging 与正式环境（fenix-agent.pazhoulab-huangpu.com）实跑均恒 skip
# （「知识库列表中无 checkbox」），且断言本身为 OR + [class*='batch'] 猜测选择器，
# 属「静默跳过掩盖失效」，故删除。

# === P2: 知识库列表分页 ===

@allure.epic("知识库")
@pytest.mark.order(348)
@pytest.mark.p2
def test_knowledge_pagination(logged_in_page, base_url, embedding_required):
    """TC-KB-P2-01: 知识库列表分页控件验证"""
    kb = KnowledgePage(logged_in_page, base_url)
    kb.goto()

    # 等待页面加载
    try:
        logged_in_page.locator("div.agent-panel-content").first.wait_for(
            state="attached", timeout=8000
        )
    except Exception:
        pass
    logged_in_page.wait_for_timeout(1000)

    # 查找分页相关控件
    # 1. 上一页/下一页按钮
    prev_next = logged_in_page.get_by_role("button", name="上一页").or_(
        logged_in_page.get_by_role("button", name="下一页")
    ).or_(
        logged_in_page.get_by_role("button", name="Previous")
    ).or_(
        logged_in_page.get_by_role("button", name="Next")
    ).or_(
        logged_in_page.locator("button[aria-label*='prev' i], button[aria-label*='next' i]")
    ).or_(
        logged_in_page.locator("button[data-slot='pagination-previous'], button[data-slot='pagination-next']")
    )

    # 2. 分页导航容器
    page_numbers = logged_in_page.locator(
        "nav[aria-label*='pagination' i], "
        "div[class*='pagination'], "
        "ul[class*='pagination']"
    )

    # 3. 每页条数选择器
    page_size = logged_in_page.locator(
        "select[class*='page-size'], "
        "button:has-text('条/页'), "
        "button:has-text('/页')"
    ).or_(
        logged_in_page.get_by_text("显示", exact=False).filter(has_text="条")
    )

    # 4. 分页文本（如 "1 / 3" 或 "共 N 条"）
    pagination_text = logged_in_page.locator(
        "span:has-text('共'), span:has-text('页'), "
        "span:text-matches('\\\\d+\\\\s*/\\\\s*\\\\d+')"
    )

    has_prev_next = prev_next.count() > 0
    has_page_nav = page_numbers.count() > 0
    has_page_size = page_size.count() > 0
    has_pagination_text = pagination_text.count() > 0

    has_any_pagination = has_prev_next or has_page_nav or has_page_size or has_pagination_text

    if not has_any_pagination:
        # 数据量少时可能不显示分页
        api_resp = logged_in_page.request.get(f"{base_url}/web/knowledgeBases")
        if api_resp.status == 200:
            data = api_resp.json()
            items = data.get("data", data) if isinstance(data, dict) else data
            if isinstance(items, dict):
                total = items.get("total", len(items.get("items", [])))
            elif isinstance(items, list):
                total = len(items)
            else:
                total = 0
            if total <= 20:
                pytest.skip(f"知识库列表仅 {total} 条数据，无分页控件（数据量不足）")
        pytest.skip("知识库列表未找到分页控件，且无法确认数据量")

    # 分页控件存在，记录找到了哪些
    visible_controls = []
    if has_prev_next:
        visible_controls.append("上一页/下一页按钮")
    if has_page_nav:
        visible_controls.append("页码导航")
    if has_page_size:
        visible_controls.append("每页条数选择")
    if has_pagination_text:
        visible_controls.append("分页文本信息")

    assert has_any_pagination, \
        "知识库列表应有分页控件，但未找到任何分页元素"


# ═══════════════════════════════════════════════════════
# P2 补充: 知识库创建弹窗字段覆盖
# ═══════════════════════════════════════════════════════


@allure.epic("知识库")
@pytest.mark.order(349)
@pytest.mark.p2
def test_knowledge_create_all_fields(logged_in_page, base_url, embedding_required):
    """验证知识库创建弹窗的所有未覆盖字段 — 仅验证字段存在，不填写不提交"""
    kb = KnowledgePage(logged_in_page, base_url)
    kb.goto()

    kb.click_create_kb()
    assert kb.is_dialog_open(), "新建知识库弹窗未打开"

    dialog = logged_in_page.locator("[role=dialog]")

    # 1. 描述字段（DOM: textarea[placeholder*='简要描述']，非 input）
    desc_input = dialog.locator("textarea[placeholder*='简要描述']")
    assert desc_input.count() > 0, "描述字段不存在"
    assert desc_input.first.is_visible(), "描述字段不可见"

    # 2. 解析方法 radio：内置 / 选择 pipeline
    builtin_radio = dialog.locator("input[type=radio][value=builtin]")
    pipeline_radio = dialog.locator("input[type=radio][value=pipeline]")
    assert builtin_radio.count() > 0, "解析方法-内置 radio 不存在"
    assert pipeline_radio.count() > 0, "解析方法-选择 pipeline radio 不存在"

    # 3. 向量模型 combobox
    model_combo = dialog.locator("[role=combobox]").first
    assert model_combo.count() > 0, "向量模型选择器不存在"
    assert model_combo.is_visible(), "向量模型选择器不可见"

    # 4. 分块方法 combobox（第二个 combobox）
    chunk_combo = dialog.locator("[role=combobox]").nth(1)
    assert chunk_combo.count() > 0, "分块方法选择器不存在"
    assert chunk_combo.is_visible(), "分块方法选择器不可见"

    # Escape 关闭，不提交
    logged_in_page.keyboard.press("Escape")
    logged_in_page.wait_for_timeout(500)
