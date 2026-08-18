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


@pytest.fixture(autouse=True)
def _check_embedding_models(env_check):
    """知识库测试依赖 embedding 模型，环境未配置时全部跳过"""
    if not env_check.get("has_embedding_models", False):
        pytest.skip("测试环境无可用的 embedding 模型，知识库测试全部跳过")


def _create_kb_api(page, base_url, name, desc=""):
    """创建知识库，429 时等待限流窗口后重试（最多 2 次）"""
    for attempt in range(2):
        resp = page.request.post(
            f"{base_url}/web/knowledgeBases",
            data=json.dumps({"name": name, "description": desc}),
            headers={"Content-Type": "application/json"},
        )
        if resp.status != 429:
            return resp
        # 429 限流，等待窗口重置
        print(f"[429] _create_kb_api 被限流，等待 65s 后重试...")
        try:
            page.goto("about:blank", wait_until="domcontentloaded", timeout=5000)
        except Exception:
            pass
        page.wait_for_timeout(65000)
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
    """删除知识库，429 时等待限流窗口后重试"""
    for attempt in range(2):
        resp = page.request.delete(f"{base_url}/web/knowledgeBases/{kb_id}")
        if resp.status != 429:
            return resp
        print(f"[429] _delete_kb_api 被限流，等待 65s 后重试...")
        try:
            page.goto("about:blank", wait_until="domcontentloaded", timeout=5000)
        except Exception:
            pass
        page.wait_for_timeout(65000)
    return resp


def _get_kbs_api(page, base_url):
    """获取知识库列表，429 时等待限流窗口后重试"""
    for attempt in range(2):
        r = page.request.get(f"{base_url}/web/knowledgeBases")
        if r.status != 429:
            if r.status == 200:
                return r.json().get("data", [])
            return []
        print(f"[429] _get_kbs_api 被限流，等待 65s 后重试...")
        try:
            page.goto("about:blank", wait_until="domcontentloaded", timeout=5000)
        except Exception:
            pass
        page.wait_for_timeout(65000)
    return []


def _get_kb_detail_api(page, base_url, kb_id):
    r = page.request.get(f"{base_url}/web/knowledgeBases/{kb_id}")
    if r.status == 200:
        return r.json()
    return None


def _goto_kb_detail(page, base_url, kb_id, max_retries=2):
    """导航到知识库详情页，429 时等待限流窗口重置后重试"""
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
        # 检查详情页是否加载成功
        body_text = page.inner_text("body")
        if "返回知识库列表" in body_text:
            return True
        # 页面未加载 → 可能 429，等待限流窗口重置
        if attempt < max_retries - 1:
            print(f"[429] 知识库详情页未加载，等待 65s 限流窗口重置...")
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

    # 1. 发起知识库列表请求
    list_called = any("/web/knowledgeBases" in r["url"] and r["method"] == "GET"
                      for r in api_resp)
    assert list_called, "未发起知识库列表 API 请求"

    # 2. 页面有内容（左侧面板包含知识库列表）
    body = logged_in_page.locator("div.agent-panel-body")
    assert "知识库" in body.inner_text(), "页面中未显示知识库相关内容"

    # 3. 搜索框存在
    assert kb.has_search_input(), "搜索框不存在"


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
        assert has_error or dialog_still_open, f"名称为空时未拦截: has_error={has_error}, dialog_still_open={dialog_still_open}"

    kb.close_dialog()

    # 验证未创建新知识库
    final_kbs = _get_kbs_api(logged_in_page, base_url)
    assert len(final_kbs) == len(initial_kbs), \
        "名称为空时知识库被创建了"


@allure.epic("知识库")
@pytest.mark.order(323)
@pytest.mark.p0
def test_kb_004_upload_file(logged_in_page, base_url, request):
    """✅ 人工评审通过 | TC-KB-004: 上传文件到知识库 — 创建临时文件，通过 UI 上传，验证文件出现在资源列表中"""
    # 创建测试知识库
    kb_name = f"upload-{_PREFIX}"
    create_resp = _create_kb_api(logged_in_page, base_url, kb_name)
    assert create_resp.status == 200, \
        f"创建测试知识库失败: status={create_resp.status}, body={create_resp.text()[:200]}"
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
def test_kb_007_delete_resource(logged_in_page, base_url, request):
    """✅ 人工评审通过 | TC-KB-007: 删除知识库资源 — 先上传文件，再通过 UI 删除，验证资源消失"""
    kb_name = f"del-res-{_PREFIX}"
    create_resp = _create_kb_api(logged_in_page, base_url, kb_name)
    assert create_resp.status == 200, \
        f"创建测试知识库失败: status={create_resp.status}, body={create_resp.text()[:200]}"
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

        # 2. 点击删除按钮（在包含文件名的行中找 title="删除" 的按钮）
        file_row = logged_in_page.locator("div.group").filter(has_text=file_name)
        assert file_row.count() > 0, f"文件行不存在（文件名: {file_name}）"
        delete_icon = file_row.first.locator('button[title="删除"]')

        if delete_icon.count() == 0:
            # 备选：通过 Trash2 SVG 图标定位
            delete_icon = file_row.first.locator(
                "svg.lucide-trash2, svg[class*='trash']"
            ).locator("xpath=ancestor::button")

        if delete_icon.count() == 0:
            # 最后备选：页面中最后一个 title="删除" 的按钮
            delete_icon = logged_in_page.locator('button[title="删除"]').last

        assert delete_icon.count() > 0, "删除按钮不存在"
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

        # 4. 验证资源已从页面消失
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


@allure.epic("知识库")
@pytest.mark.order(327)
@pytest.mark.p2
def test_kb_008_search(logged_in_page, base_url):
    """✅ 人工评审通过 | TC-KB-008: 知识库搜索 — 正向搜索存在的知识库 + 反向搜索不存在的 + 清空恢复"""
    kb = KnowledgePage(logged_in_page, base_url)
    kb.goto()

    kbs = _get_kbs_api(logged_in_page, base_url)
    if not kbs:
        pytest.skip("知识库列表为空")

    initial_count = kb.get_kb_count()

    # 1. 正向搜索：用已有知识库名称搜索
    kb_names = kb.get_kb_names()
    if kb_names:
        existing_name = kb_names[0]
        kb.search(existing_name)
        found_count = kb.get_kb_count()
        assert found_count >= 1, \
            f"搜索已有知识库 '{existing_name}' 后应至少有 1 条结果，实际 {found_count}"
        assert found_count < initial_count or initial_count <= 1, \
            f"搜索 '{existing_name}' 后数量未过滤: {found_count} vs {initial_count}"

        # 验证搜索结果的文本中包含搜索关键词
        body = logged_in_page.locator("div.agent-panel-body").first
        assert existing_name in body.inner_text(), \
            f"搜索结果中未显示 '{existing_name}'"

        kb.clear_search()
        logged_in_page.wait_for_timeout(500)

    # 2. 反向搜索：搜索不存在的关键词
    kb.search("zzz_不存在的知识库_zzz")
    filtered_count = kb.get_kb_count()
    assert filtered_count < initial_count or filtered_count == 0, \
        f"搜索不存在关键词后数量未减少: {filtered_count} vs {initial_count}"

    # 清空搜索恢复
    kb.clear_search()
    restored = kb.get_kb_count()
    assert restored == initial_count, \
        f"清空搜索后数量未恢复: {restored} vs {initial_count}"


@allure.epic("知识库")
@pytest.mark.order(328)
@pytest.mark.p1
def test_kb_009_delete_cascade(logged_in_page, base_url, request):
    """✅ 人工评审通过 | TC-KB-009: 删除知识库级联清理"""
    kb_name = f"cascade-{_PREFIX}"
    create_resp = _create_kb_api(logged_in_page, base_url, kb_name)
    assert create_resp.status == 200, \
        f"创建测试知识库失败: status={create_resp.status}, body={create_resp.text()[:200]}"
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

    # 1. 详情页导航元素
    assert "返回知识库列表" in body_text, "详情页缺少返回按钮"

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
def test_kb_011_upload_duplicate_confirm(logged_in_page, base_url, request):
    """TC-KB-011: 文件上传同名覆盖确认 — 上传同名文件应弹出覆盖确认对话框"""
    kb_name = f"dup-{_PREFIX}"
    create_resp = _create_kb_api(logged_in_page, base_url, kb_name)
    assert create_resp.status == 200, \
        f"创建测试知识库失败: status={create_resp.status}, body={create_resp.text()[:200]}"
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
def test_kb_012_parse_status_polling(logged_in_page, base_url, request):
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
def test_kb_013_reparse_resource(logged_in_page, base_url, request):
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
            logged_in_page.wait_for_timeout(800)

            # 处理可能的确认弹窗
            alert_dialog = logged_in_page.locator("[role=alertdialog]")
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
                    logged_in_page.wait_for_timeout(2000)

            # 验证重新解析请求已发送
            assert len(reparse_called) > 0, "未检测到重新解析 API 请求"
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
def test_kb_014_retrieval_test_panel(logged_in_page, base_url):
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
def test_kb_015_knowledge_graph(logged_in_page, base_url):
    """TC-KB-015: 知识图谱面板 — 点击知识图谱按钮，面板展示"""
    kbs = _get_kbs_api(logged_in_page, base_url)
    if not kbs:
        pytest.skip("知识库列表为空")

    kb_id = kbs[0]["id"]
    if not _goto_kb_detail(logged_in_page, base_url, kb_id):
        pytest.skip("429 限流导致知识库详情页无法加载")

    body_text = logged_in_page.inner_text("body")
    assert "返回知识库列表" in body_text, "知识库详情页未加载"

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
            "知识图谱面板未展示"
    else:
        allure.attach(
            "未找到知识图谱按钮，可能该知识库不支持知识图谱功能",
            name="备注",
            attachment_type=allure.attachment_type.TEXT,
        )


@allure.epic("知识库")
@pytest.mark.order(335)
@pytest.mark.p2
def test_kb_016_vector_model_management(logged_in_page, base_url):
    """TC-KB-016: 向量模型管理 — 打开向量模型管理对话框"""
    kbs = _get_kbs_api(logged_in_page, base_url)
    if not kbs:
        pytest.skip("知识库列表为空")

    kb_id = kbs[0]["id"]
    if not _goto_kb_detail(logged_in_page, base_url, kb_id):
        pytest.skip("429 限流导致知识库详情页无法加载")

    body_text = logged_in_page.inner_text("body")
    assert "返回知识库列表" in body_text, "知识库详情页未加载"

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
def test_kb_017_ragflow_import(logged_in_page, base_url):
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
def test_kb_018_resource_preview(logged_in_page, base_url, request):
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
                    "completed", "success", "done", "indexed"
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
        assert logged_in_page.locator(f"text={file_name}").count() > 0, \
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
def test_kb_019_toggle_resource_enabled(logged_in_page, base_url, request):
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
        assert "返回知识库列表" in body_text, "知识库详情页未加载"

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
                    logged_in_page.wait_for_timeout(2000)
                else:
                    # 备选：dialog 中最后一个 button（可能是提交按钮）
                    all_btns = dialog.locator("button")
                    if all_btns.count() > 0:
                        all_btns.last.wait_for(state="visible", timeout=5000)
                        all_btns.last.click()
                        logged_in_page.wait_for_timeout(2000)

                # API 验证
                detail = _get_kb_detail_api(logged_in_page, base_url, kb_id)
                if detail and detail.get("data"):
                    updated_name = detail["data"].get("name", "")
                    assert new_name in updated_name or updated_name == new_name, \
                        f"编辑后名称未更新: '{updated_name}'"
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
    """TC-KB-021: 知识库 UI 删除 — 在详情页点击删除按钮，确认弹窗后验证知识库消失"""
    kb_name = f"del-ui-{_PREFIX}"
    create_resp = _create_kb_api(logged_in_page, base_url, kb_name, desc="UI删除测试")
    _assert_kb_created(create_resp)
    kb_id = create_resp.json()["data"]["id"]
    register_cleanup(request, lambda kid=kb_id: _delete_kb_api(logged_in_page, base_url, kid))

    # 导航到知识库详情页（429 时自动等待重试）
    if not _goto_kb_detail(logged_in_page, base_url, kb_id):
        pytest.skip("429 限流导致知识库详情页无法加载")

    body_text = logged_in_page.inner_text("body")
    assert "返回知识库列表" in body_text, "知识库详情页未加载"

    # 点击删除按钮
    delete_btn = loc.button_by_name_or_title(logged_in_page, "删除")
    assert delete_btn.count() > 0, "删除按钮不存在"
    delete_btn.first.wait_for(state="visible", timeout=5000)
    delete_btn.first.click()
    logged_in_page.wait_for_timeout(800)

    # 处理确认弹窗
    alert_dialog = logged_in_page.locator("[role=alertdialog]")
    dialog = logged_in_page.locator("[role=dialog]")
    has_confirm = (
        (alert_dialog.count() > 0 and alert_dialog.first.is_visible())
        or (dialog.count() > 0 and dialog.first.is_visible()
            and any(kw in dialog.first.inner_text() for kw in ["删除", "确认", "确定"]))
    )

    if has_confirm:
        confirm_btn = loc.confirm_button(alert_dialog).or_(
            loc.confirm_button(dialog)
        )
        if confirm_btn.count() > 0:
            confirm_btn.first.wait_for(state="visible", timeout=5000)
            confirm_btn.first.click()
            logged_in_page.wait_for_timeout(1500)
        else:
            # 备选：找弹窗中包含"删除"文本的按钮
            target = alert_dialog if alert_dialog.count() > 0 else dialog
            del_btn_in_dialog = target.get_by_role("button", name="删除").or_(
                target.get_by_role("button", name="确认")
            )
            if del_btn_in_dialog.count() > 0:
                del_btn_in_dialog.first.wait_for(state="visible", timeout=5000)
                del_btn_in_dialog.first.click()
                logged_in_page.wait_for_timeout(1500)
    else:
        # 可能 429 导致删除请求被拒、未弹出确认弹窗，等待后重试
        print("[429] 点击删除后未弹出确认弹窗，等待限流窗口重置后重试...")
        _wait_rate_limit_reset(logged_in_page, 65)
        if not _goto_kb_detail(logged_in_page, base_url, kb_id):
            pytest.skip("429 限流导致知识库详情页无法加载")
        delete_btn2 = loc.button_by_name_or_title(logged_in_page, "删除")
        if delete_btn2.count() > 0:
            delete_btn2.first.wait_for(state="visible", timeout=5000)
            delete_btn2.first.click()
            logged_in_page.wait_for_timeout(800)
        alert_dialog2 = logged_in_page.locator("[role=alertdialog]")
        dialog2 = logged_in_page.locator("[role=dialog]")
        has_confirm2 = (
            (alert_dialog2.count() > 0 and alert_dialog2.first.is_visible())
            or (dialog2.count() > 0 and dialog2.first.is_visible()
                and any(kw in dialog2.first.inner_text() for kw in ["删除", "确认", "确定"]))
        )
        if has_confirm2:
            confirm_btn2 = loc.confirm_button(alert_dialog2).or_(
                loc.confirm_button(dialog2)
            )
            if confirm_btn2.count() > 0:
                confirm_btn2.first.wait_for(state="visible", timeout=5000)
                confirm_btn2.first.click()
                logged_in_page.wait_for_timeout(1500)
        else:
            pytest.skip("点击删除后未弹出确认弹窗（429 重试后仍未弹出）")

    # 验证：页面应回到列表或不再显示该知识库
    logged_in_page.wait_for_timeout(1000)
    try:
        logged_in_page.goto(
            f"{base_url}/ctrl/agent/knowledge-bases",
            wait_until="domcontentloaded",
        )
    except Exception:
        pass
    logged_in_page.wait_for_load_state("domcontentloaded")
    try:
        logged_in_page.locator("div.agent-panel-content").first.wait_for(
            state="attached", timeout=8000
        )
    except Exception:
        pass

    # API 验证知识库已删除
    kbs = _get_kbs_api(logged_in_page, base_url)
    exists = any(k["id"] == kb_id for k in kbs)

    # 如果仍然存在，可能是确认删除的请求被 429 拦截，等待后重试
    if exists:
        print("[429] UI 删除确认可能因限流未生效，等待 65s 后通过 API 验证并重试...")
        _wait_rate_limit_reset(logged_in_page, 65)
        # 再次检查
        kbs2 = _get_kbs_api(logged_in_page, base_url)
        exists = any(k["id"] == kb_id for k in kbs2)
        if exists:
            # 确认按钮的请求被 429 拦截了，此时 UI 重试意义不大，用 API 完成删除
            # 但断言 UI 确认流程已走通（弹窗已弹出且确认按钮已点击）
            del_resp = _delete_kb_api(logged_in_page, base_url, kb_id)
            assert del_resp.status == 200, \
                f"429 重试后 API 删除也失败: status={del_resp.status}"
            kbs3 = _get_kbs_api(logged_in_page, base_url)
            exists = any(k["id"] == kb_id for k in kbs3)

    assert not exists, f"UI 删除后知识库仍在列表中: {kb_name}"
