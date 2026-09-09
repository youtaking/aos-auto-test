# tests/suites/test_skills_v2.py
"""技能库 V2 回归测试 — 新版两栏「技能库」页面（2026-09 DOM 全量改写）

覆盖：列表加载 / 搜索过滤 / 骨架屏 / API 列表与详情 / API 上传 / UI 删除 /
文件夹导入（含同名冲突 跳过/覆盖）/ ZIP 下载 / 作用域归属筛选 /
公开只读查看 / 公开切换 / 文本创建 / 必填校验 / 取消 / 编辑保存与取消 / 重名。

铁律遵守：只自建自销，不操作系统已有数据；删除/覆盖前校验确认弹窗含目标名；
选择器一律限定 main / catalog / dialog 容器。
"""
import json
import os
import re
import shutil
import tempfile
import time
import uuid

import allure
import pytest
import requests


def _skills_session_cookie(logged_in_page):
    """从登录上下文提取 better-auth session cookie，返回 cookie_jar dict"""
    cookies = logged_in_page.context.cookies()
    session_cookie = next(
        (c for c in cookies if c["name"].startswith("better-auth")),
        None,
    )
    assert session_cookie is not None, "未获取到登录 session cookie"
    return {session_cookie["name"]: session_cookie["value"]}


def _api_delete_skill_safe(base_url, cookie_jar, name):
    """安全删除测试技能（忽略错误）"""
    try:
        requests.delete(f"{base_url}/web/config/skills/{name}", cookies=cookie_jar, timeout=10)
    except Exception:
        pass


def _api_skill_exists(base_url, cookie_jar, name) -> bool:
    resp = requests.get(f"{base_url}/web/config/skills", cookies=cookie_jar, timeout=10)
    if resp.status_code != 200:
        return False
    return any(s.get("name") == name for s in resp.json().get("data", {}).get("skills", []))


def _api_create_skill_upload(base_url, cookie_jar, name, content):
    """通过内部上传接口预置技能（任务前置数据），返回响应"""
    manifest = json.dumps([{"skillName": name, "relativePath": "SKILL.md"}])
    return requests.post(
        f"{base_url}/web/config/skills/upload",
        files={
            "manifest": (None, manifest, "application/json"),
            "files": ("SKILL.md", content, "text/markdown"),
        },
        cookies=cookie_jar,
        timeout=15,
    )


def _make_temp_import_root(skill_name: str, content: str) -> str:
    """创建「文件夹导入」用临时根目录：root/{skill_name}/SKILL.md"""
    root = tempfile.mkdtemp(prefix="skill-import-")
    skill_dir = os.path.join(root, skill_name)
    os.makedirs(skill_dir, exist_ok=True)
    with open(os.path.join(skill_dir, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write(content)
    return root


def _wait_skill_gone(skills, name: str, timeout: float = 10000):
    """轮询等待目录中技能消失（删除后列表刷新有延迟）"""
    deadline = time.time() + timeout / 1000
    while time.time() < deadline:
        if not skills.has_skill(name, timeout=1500):
            return True
        skills.page.wait_for_timeout(300)
    return False


@allure.epic("技能管理")
@pytest.mark.order(70)
@pytest.mark.p0
def test_skill_list_data_loads(logged_in_page, base_url):
    """TC-SKILL-001: 技能库列表加载 — 两栏目录+详情正常展示，工具栏按钮齐全"""
    from tests.pages.config_pages import SkillsPage

    skills = SkillsPage(logged_in_page, base_url)
    skills.goto()

    assert skills.is_loaded(), "技能库页面未加载（未出现技能目录）"

    count = skills.get_skill_count()
    if count == 0:
        pytest.skip("技能列表为空，环境无技能数据")
    assert count > 0, "技能列表为空"

    # 顶栏应有 导入 / 添加 Skill（限定 main，防侧边栏同名）
    main = skills._main()
    assert main.get_by_role("button", name="导入", exact=True).count() > 0, "缺少「导入」按钮"
    assert main.get_by_role("button", name="添加 Skill", exact=True).count() > 0, "缺少「添加 Skill」按钮"
    # 筛选区：搜索框 + 三个作用域分段按钮（全部N/本组织N/公开N）
    assert main.get_by_placeholder("搜索 Skill").count() > 0, "缺少搜索框"
    for scope in ("全部", "本组织", "公开"):
        seg = main.get_by_role("button", name=re.compile(f"^{scope}\\d+$"))
        assert seg.count() > 0, f"缺少作用域分段按钮 {scope}"


@allure.epic("技能管理")
@pytest.mark.order(71)
@pytest.mark.p1
def test_skill_search_filter(logged_in_page, base_url):
    """TC-SKILL-005: 技能搜索过滤 — 目录实时过滤，清空恢复全部"""
    from tests.pages.config_pages import SkillsPage

    skills = SkillsPage(logged_in_page, base_url)
    skills.goto()
    assert skills.is_loaded(), "技能库页面未加载"

    initial_count = skills.get_skill_count()
    if initial_count == 0:
        pytest.skip("技能列表为空，无法测试搜索")

    names = skills.get_skill_names()
    assert len(names) > 0, "目录中无技能名可测"
    first_name = names[0]

    # 搜索真实技能名 → 应至少匹配 1 条且不增多
    skills.search(first_name)
    filtered_count = skills.get_skill_count()
    assert filtered_count >= 1, f"搜索真实名称 '{first_name}' 后目录为空"
    assert filtered_count <= initial_count, f"搜索后数量不应超过初始: {filtered_count} > {initial_count}"

    # 搜索不存在内容 → 目录应为 0
    skills.search("zzznonexist999")
    assert skills.get_skill_count() == 0, "搜索不存在内容后目录未清空"

    # 清空搜索 → 恢复初始数量
    skills.clear_search()
    restored = skills.get_skill_count()
    for _ in range(10):
        if restored >= initial_count:
            break
        skills.page.wait_for_timeout(500)
        restored = skills.get_skill_count()
    assert restored == initial_count, f"清空搜索后未恢复初始数量: {restored} vs {initial_count}"


@allure.epic("技能管理")
@pytest.mark.order(72)
@pytest.mark.p1
def test_skill_list_loading_skeleton(logged_in_page, base_url):
    """TC-SKILL-008: 列表加载门控 — API 未返回时目录不渲染（不闪现陈旧/空列表），数据就绪后才出现

    实测（2026-09 headless）：`.animate-pulse` 骨架仅随列表解析的瞬间闪烁约 0.2s，
    无法作为持续加载态断言；稳定契约是「API 未返回前 catalog 不渲染」。
    """
    from tests.pages.config_pages import SkillsPage

    skills = SkillsPage(logged_in_page, base_url)

    # 拦截技能列表 API 并人为延迟 3s
    def delay_skills_api(route):
        time.sleep(3)
        route.continue_()

    logged_in_page.route("**/web/config/skills*", delay_skills_api)
    logged_in_page.goto(skills.url, wait_until="domcontentloaded")

    # 延迟窗口内（请求尚未返回）：目录不得提前渲染
    logged_in_page.wait_for_timeout(1200)
    assert skills._catalog().count() == 0, "技能 API 未返回时目录不应渲染"

    logged_in_page.unroute("**/web/config/skills*")

    # 数据就绪后：目录渲染、页面加载完成
    try:
        skills._catalog().first.wait_for(state="visible", timeout=15000)
    except Exception:
        pass
    assert skills.is_loaded(), "技能库页面最终未加载"


@allure.epic("技能管理")
@pytest.mark.order(73)
@pytest.mark.p0
def test_skill_api_list_and_detail(logged_in_page, base_url):
    """TC-SKILL-016: 内部 API 获取 Skill 列表和详情"""
    cookie_jar = _skills_session_cookie(logged_in_page)

    # GET /web/config/skills — 列表
    list_resp = requests.get(f"{base_url}/web/config/skills", cookies=cookie_jar, timeout=10)
    assert list_resp.status_code == 200, f"获取 Skill 列表失败: HTTP {list_resp.status_code}"
    body = list_resp.json()
    assert body.get("success") is True, f"API 返回 success=false: {body}"
    items = body.get("data", {}).get("skills", [])
    assert len(items) > 0, "Skill 列表为空"
    assert "name" in items[0], "skill 缺少 name 字段"

    # GET /web/config/skills/:name — 详情
    skill_name = items[0]["name"]
    detail_resp = requests.get(
        f"{base_url}/web/config/skills/{skill_name}", cookies=cookie_jar, timeout=10
    )
    assert detail_resp.status_code == 200, f"获取 Skill 详情失败: HTTP {detail_resp.status_code}"
    detail_body = detail_resp.json()
    assert detail_body.get("success") is True, f"详情 API 返回 success=false: {detail_body}"
    detail = detail_body.get("data", {})
    assert detail.get("name") == skill_name, (
        f"详情名称与列表不一致: {detail.get('name')} vs {skill_name}"
    )
    assert "content" in detail, "详情缺少 content 字段"


@allure.epic("技能管理")
@pytest.mark.order(74)
@pytest.mark.p0
def test_skill_upload(logged_in_page, base_url):
    """TC-SKILL-015: 内部 API 上传 Skill（POST /web/config/skills/upload）"""
    cookie_jar = _skills_session_cookie(logged_in_page)

    skill_name = "auto-test-skill-internal"
    skill_content = (
        "---\nname: auto-test-skill-internal\ndescription: 自动化测试技能(内部API上传)\n---\n\n"
        "# Auto Test Skill (Internal API)\n\nThis is a test skill uploaded via internal API.\n"
    )

    # 先清理同名残留
    resp = requests.get(f"{base_url}/web/config/skills", cookies=cookie_jar, timeout=10)
    if resp.status_code == 200:
        for s in resp.json().get("data", {}).get("skills", []):
            if s.get("name") == skill_name:
                _api_delete_skill_safe(base_url, cookie_jar, skill_name)

    manifest = json.dumps([{"skillName": skill_name, "relativePath": "SKILL.md"}])
    upload_resp = requests.post(
        f"{base_url}/web/config/skills/upload",
        files={
            "manifest": (None, manifest, "application/json"),
            "files": ("SKILL.md", skill_content, "text/markdown"),
        },
        cookies=cookie_jar,
        timeout=15,
    )
    assert upload_resp.status_code < 400, (
        f"上传 Skill 失败: HTTP {upload_resp.status_code}, body={upload_resp.text[:300]}"
    )
    assert upload_resp.json().get("success") is True, f"上传返回 success=false: {upload_resp.text[:300]}"

    # 上传后列表中应能找到
    assert _api_skill_exists(base_url, cookie_jar, skill_name), (
        f"上传后列表中未找到技能 '{skill_name}'"
    )

    # 清理
    _api_delete_skill_safe(base_url, cookie_jar, skill_name)


@allure.epic("技能管理")
@pytest.mark.order(75)
@pytest.mark.p0
def test_skill_delete_via_ui(logged_in_page, base_url):
    """TC-SKILL-017: API 预置 + UI 删除技能（自建自销，确认弹窗校验目标名）"""
    from tests.pages.config_pages import SkillsPage

    cookie_jar = _skills_session_cookie(logged_in_page)
    skill_name = f"e2e-ui-del-{uuid.uuid4().hex[:8]}"
    content = (
        "---\n"
        f"name: {skill_name}\n"
        "description: UI 删除测试技能\n"
        "---\n\n"
        "# Delete UI Test Skill"
    )
    upload_resp = _api_create_skill_upload(base_url, cookie_jar, skill_name, content)
    assert upload_resp.status_code < 400, f"预置删除测试技能失败: HTTP {upload_resp.status_code}"
    assert _api_skill_exists(base_url, cookie_jar, skill_name), "预置技能未生效"

    skills = SkillsPage(logged_in_page, base_url)
    skills.goto()
    assert skills.is_loaded(), "技能库页面未加载"
    assert skills.reload(), "刷新后技能页面未加载"
    assert skills.has_skill(skill_name), f"预置技能 '{skill_name}' 未出现在目录"

    # 选中 → owner（页脚应有删除）→ 删除
    assert skills.select_skill(skill_name), "无法选中预置技能"
    assert skills.is_owner(skill_name), "预置技能应属于本账号（可编辑）"
    skills.delete_skill(skill_name)  # 内部已断言 确认弹窗含目标名

    # 目录中消失（reload 拿服务端权威状态）
    assert skills.reload(), "删除后刷新失败"
    assert not skills.has_skill(skill_name, timeout=5000), f"删除后目录仍显示技能 '{skill_name}'"
    assert not _api_skill_exists(base_url, cookie_jar, skill_name), "删除后 API 仍返回该技能"


@allure.epic("技能管理")
@pytest.mark.order(76)
@pytest.mark.p0
def test_skill_folder_upload(logged_in_page, base_url):
    """TC-SKILL-018: 文件夹批量导入 — 导入目录识别子技能并成功建入"""
    from tests.pages.config_pages import SkillsPage

    cookie_jar = _skills_session_cookie(logged_in_page)
    skill_name = f"e2e-folder-{uuid.uuid4().hex[:8]}"
    content = (
        "# Folder Import Skill\n\n"
        f"skill: {skill_name}\n"
        "通过文件夹导入创建。"
    )
    root = _make_temp_import_root(skill_name, content)
    try:
        skills = SkillsPage(logged_in_page, base_url)
        skills.goto()
        assert skills.is_loaded(), "技能库页面未加载"

        skills.open_import_dialog()
        assert skills.is_import_dialog_open(), "上传技能弹窗未打开"
        skills.select_import_folder(root)
        skills.click_import_start()

        toast_text = skills.get_last_toast_text()
        assert "已导入 1 个技能" in toast_text, f"导入成功 toast 未出现: {toast_text}"
        assert not skills.is_import_dialog_open(), "导入成功后上传弹窗应关闭"

        # 目录出现新技能，且详情含导入内容
        assert skills.has_skill(skill_name), f"导入后目录未出现技能 '{skill_name}'"
        assert skills.select_skill(skill_name), "无法选中导入的技能"
        article = skills.article_text(skill_name)
        assert skill_name in article, "导入技能详情未展示其内容"

        # 清理：UI 删除自建导入的技能
        skills.delete_skill(skill_name)
        assert skills.reload(), "删除后刷新失败"
        assert not skills.has_skill(skill_name, timeout=5000), "清理后技能仍存在"
    finally:
        shutil.rmtree(root, ignore_errors=True)


@allure.epic("技能管理")
@pytest.mark.order(77)
@pytest.mark.p1
def test_skill_download_export(logged_in_page, base_url):
    """TC-SKILL-019: ZIP 下载导出 — 下载自建技能，文件名为 {name}.zip"""
    from tests.pages.config_pages import SkillsPage

    cookie_jar = _skills_session_cookie(logged_in_page)
    skill_name = f"e2e-dl-{uuid.uuid4().hex[:8]}"
    content = (
        "---\n"
        f"name: {skill_name}\n"
        "description: 下载测试技能\n"
        "---\n\n"
        "# Download Test Skill"
    )
    upload_resp = _api_create_skill_upload(base_url, cookie_jar, skill_name, content)
    assert upload_resp.status_code < 400, f"预置下载测试技能失败: HTTP {upload_resp.status_code}"
    try:
        skills = SkillsPage(logged_in_page, base_url)
        skills.goto()
        assert skills.is_loaded(), "技能库页面未加载"
        assert skills.reload(), "刷新后技能页面未加载"
        assert skills.has_skill(skill_name), f"预置技能 '{skill_name}' 未出现在目录"

        assert skills.select_skill(skill_name), "无法选中技能"
        download = skills.download_skill(skill_name)
        assert download.suggested_filename == f"{skill_name}.zip", (
            f"下载文件名异常: {download.suggested_filename}"
        )
        save_path = os.path.join(tempfile.gettempdir(), download.suggested_filename)
        download.save_as(save_path)
        assert os.path.exists(save_path), "下载文件未保存成功"
        assert os.path.getsize(save_path) > 0, "下载文件大小为 0"
        os.remove(save_path)
    finally:
        _api_delete_skill_safe(base_url, cookie_jar, skill_name)


@allure.epic("技能管理")
@pytest.mark.order(78)
@pytest.mark.p1
def test_skill_scope_filter(logged_in_page, base_url):
    """TC-SKILL-020: 归属筛选（全部/本组织/公开）— 目录数量与分段计数一致，公开目录全带公开徽标"""
    from tests.pages.config_pages import SkillsPage

    skills = SkillsPage(logged_in_page, base_url)
    skills.goto()
    assert skills.is_loaded(), "技能库页面未加载"

    main = skills._main()
    all_count = skills.get_skill_count()
    if all_count == 0:
        pytest.skip("技能列表为空")

    def parse_scope_num(label: str) -> int:
        btn = main.get_by_role("button", name=re.compile(f"^{label}\\d+$")).first
        btn.wait_for(state="visible", timeout=5000)
        txt = btn.inner_text()
        m = re.search(r"(\d+)$", txt)
        assert m, f"分段按钮文案无数量: {txt}"
        return int(m.group(1))

    def wait_count(n: int, timeout: float = 8000):
        deadline = time.time() + timeout / 1000
        while time.time() < deadline:
            if skills.get_skill_count() == n:
                return True
            skills.page.wait_for_timeout(300)
        return False

    # 公开：目录数量与按钮计数一致，且每项都带「公开」徽标
    skills.click_scope("公开")
    pub_num = parse_scope_num("公开")
    if pub_num == 0:
        pytest.skip("环境中无公开技能")
    assert wait_count(pub_num), f"公开作用域目录数 {skills.get_skill_count()} != {pub_num}"
    for name in skills.get_skill_names():
        item_text = skills._catalog_item(name).first.inner_text()
        assert "公开" in item_text, f"公开作用域下 '{name}' 缺少公开徽标"

    # 本组织：目录数量与按钮计数一致
    skills.click_scope("本组织")
    org_num = parse_scope_num("本组织")
    if org_num > 0:
        assert wait_count(org_num), f"本组织作用域目录数 {skills.get_skill_count()} != {org_num}"
        assert main.get_by_role("button", name=re.compile("^全部\\d+$")).first.get_attribute(
            "aria-pressed"
        ) != "true", "切到本组织后「全部」仍为按下态"

    # 切回全部恢复
    skills.click_scope("全部")
    assert wait_count(all_count), "切回全部后目录数未恢复初始"


@allure.epic("技能管理")
@pytest.mark.order(79)
@pytest.mark.p1
def test_skill_public_toggle(logged_in_page, base_url):
    """TC-SKILL-021: 公开/私密切换 — 自建技能设公开→再切回私有"""
    from tests.pages.config_pages import SkillsPage

    cookie_jar = _skills_session_cookie(logged_in_page)
    skill_name = f"e2e-pub-{uuid.uuid4().hex[:8]}"
    content = (
        "---\n"
        f"name: {skill_name}\n"
        "description: 公开切换测试技能\n"
        "---\n\n"
        "# Public Toggle Skill"
    )
    upload_resp = _api_create_skill_upload(base_url, cookie_jar, skill_name, content)
    assert upload_resp.status_code < 400, f"预置公开切换技能失败: HTTP {upload_resp.status_code}"
    try:
        skills = SkillsPage(logged_in_page, base_url)
        skills.goto()
        assert skills.is_loaded(), "技能库页面未加载"
        assert skills.reload(), "刷新后技能页面未加载"
        assert skills.has_skill(skill_name), f"预置技能 '{skill_name}' 未出现在目录"

        assert skills.select_skill(skill_name), "无法选中技能"
        assert not skills.is_public(skill_name), "新建私有技能不应显示为公开"

        # 设为公开 → 页脚按钮变 设为私有
        skills.toggle_public(skill_name)
        assert skills.is_public(skill_name), "设为公开后未变为公开状态"
        detail = requests.get(
            f"{base_url}/web/config/skills/{skill_name}", cookies=cookie_jar, timeout=10
        ).json()
        assert detail.get("data", {}).get("resourceAccess", {}).get("publicReadable") is True, (
            "API 中 publicReadable 未变为 true"
        )

        # 切回私有 → 恢复
        skills.toggle_public(skill_name)
        assert not skills.is_public(skill_name), "切回私有后仍为公开状态"
        detail2 = requests.get(
            f"{base_url}/web/config/skills/{skill_name}", cookies=cookie_jar, timeout=10
        ).json()
        assert detail2.get("data", {}).get("resourceAccess", {}).get("publicReadable") is False, (
            "API 中 publicReadable 未恢复 false"
        )
    finally:
        _api_delete_skill_safe(base_url, cookie_jar, skill_name)


@allure.epic("技能管理")
@pytest.mark.order(80)
@pytest.mark.p2
def test_skill_readonly_public_view(logged_in_page, base_url):
    """TC-SKILL-022: 公开分享技能只读查看 — 非 owner 仅 查看+下载，无管理按钮"""
    from tests.pages.config_pages import SkillsPage

    skills = SkillsPage(logged_in_page, base_url)
    skills.goto()
    assert skills.is_loaded(), "技能库页面未加载"

    # 只看公开作用域（他组织公开技能为只读）
    skills.click_scope("公开")
    names = skills.get_skill_names()
    if not names:
        pytest.skip("环境中无公开技能")

    readonly_name = None
    for name in names:
        try:
            skills.select_skill(name)
            if not skills.is_owner(name):  # header 无「编辑」→ 只读
                readonly_name = name
                break
        except Exception:
            continue
    if readonly_name is None:
        pytest.skip("公开作用域内未找到只读技能（均为本账号 owner）")

    main = skills._main()
    # header 是「查看」而非「编辑」
    assert main.get_by_role("button", name="查看", exact=True).count() > 0, (
        f"只读技能 '{readonly_name}' header 无「查看」"
    )
    assert main.get_by_role("button", name="编辑", exact=True).count() == 0, (
        f"只读技能 '{readonly_name}' 不应有「编辑」"
    )
    # 页脚仅 [下载]，无 [删除]/[设为公开或私有]
    assert main.get_by_role("button", name="下载", exact=True).count() > 0, "只读技能无「下载」"
    assert main.get_by_role("button", name="删除", exact=True).count() == 0, (
        f"只读技能 '{readonly_name}' 不应有「删除」"
    )
    assert main.get_by_role("button", name=re.compile("^设为(公开|私有)$")).count() == 0, (
        f"只读技能 '{readonly_name}' 不应有公开切换按钮"
    )
    # 详情含 技能指令(SKILL.md 渲染)
    article = skills.article_text(readonly_name)
    assert "技能指令" in article, "只读技能详情缺少 SKILL.md 渲染区"


@allure.epic("技能管理")
@pytest.mark.order(81)
@pytest.mark.p1
@pytest.mark.no_page_error_check  # 上传同名冲突后端返回 409，会打 console.error
def test_skill_upload_conflict_handling(logged_in_page, base_url):
    """TC-SKILL-023: 文件夹导入同名冲突 — 覆盖策略替换内容 / 跳过策略保留原内容"""
    from tests.pages.config_pages import SkillsPage

    cookie_jar = _skills_session_cookie(logged_in_page)
    skill_name = f"e2e-conf-{uuid.uuid4().hex[:8]}"
    seed_content = (
        "---\n"
        f"name: {skill_name}\n"
        "description: 冲突测试技能\n"
        "---\n\n"
        "# Conflict Skill\n\nORIGINAL-SEED"
    )
    upload_resp = _api_create_skill_upload(base_url, cookie_jar, skill_name, seed_content)
    assert upload_resp.status_code < 400, f"预置冲突测试技能失败: HTTP {upload_resp.status_code}"
    try:
        skills = SkillsPage(logged_in_page, base_url)
        skills.goto()
        assert skills.is_loaded(), "技能库页面未加载"

        def detail_content() -> str:
            r = requests.get(
                f"{base_url}/web/config/skills/{skill_name}", cookies=cookie_jar, timeout=10
            )
            return r.json().get("data", {}).get("content", "")

        # ── 覆盖分支：导入含 V2 的同名目录，选「覆盖已有技能」→ 内容替换为 V2 ──
        root_over = _make_temp_import_root(skill_name, f"# V2\n\nOVERWRITE-V2-MARKER-{skill_name}")
        try:
            skills.open_import_dialog()
            assert skills.is_import_dialog_open(), "上传技能弹窗未打开"
            skills.select_import_folder(root_over)
            skills.click_import_start()
            assert skills.has_upload_conflict(skill_name), "同名导入未触发冲突检测"
            skills.resolve_upload_conflict(skill_name, "overwrite")  # 内部断言覆盖确认弹窗含目标名
            toast_text = skills.get_last_toast_text()
            assert "已导入 1 个技能" in toast_text, f"覆盖导入 toast 异常: {toast_text}"
            assert f"OVERWRITE-V2-MARKER-{skill_name}" in detail_content(), "覆盖后内容未替换为 V2"
        finally:
            shutil.rmtree(root_over, ignore_errors=True)

        # ── 跳过分支：再导入含 V3 的同名目录，选「跳过冲突项」→ 内容仍为 V2 ──
        root_skip = _make_temp_import_root(skill_name, f"# V3\n\nSKIP-V3-MARKER-{skill_name}")
        try:
            skills.open_import_dialog()
            assert skills.is_import_dialog_open(), "第二次上传技能弹窗未打开"
            skills.select_import_folder(root_skip)
            skills.click_import_start()
            assert skills.has_upload_conflict(skill_name), "第二次同名导入未触发冲突"
            skills.resolve_upload_conflict(skill_name, "skip")
            toast_text = skills.get_last_toast_text()
            assert "跳过 1 个冲突技能" in toast_text, f"跳过导入 toast 异常: {toast_text}"
            content_after_skip = detail_content()
            assert f"OVERWRITE-V2-MARKER-{skill_name}" in content_after_skip, (
                "跳过冲突后原内容不应被覆盖为 V3"
            )
            assert "SKIP-V3-MARKER" not in content_after_skip, "跳过冲突后 V3 内容不应写入"
        finally:
            shutil.rmtree(root_skip, ignore_errors=True)
    finally:
        _api_delete_skill_safe(base_url, cookie_jar, skill_name)


@allure.epic("技能管理")
@pytest.mark.order(82)
@pytest.mark.p1
def test_skills_edit_entry_and_locked_name(logged_in_page, base_url):
    """技能编辑入口 — owner 详情可打开编辑弹窗，名称 disabled 且字段已回填"""
    from tests.pages.config_pages import SkillsPage

    cookie_jar = _skills_session_cookie(logged_in_page)
    skill_name = f"e2e-edt-{uuid.uuid4().hex[:8]}"
    content = (
        "---\n"
        f"name: {skill_name}\n"
        "description: 编辑入口测试技能\n"
        "---\n\n"
        "# Edit Entry Skill"
    )
    upload_resp = _api_create_skill_upload(base_url, cookie_jar, skill_name, content)
    assert upload_resp.status_code < 400, f"预置技能失败: HTTP {upload_resp.status_code}"
    try:
        skills = SkillsPage(logged_in_page, base_url)
        skills.goto()
        assert skills.is_loaded(), "技能库页面未加载"
        assert skills.reload(), "刷新后技能页面未加载"
        assert skills.has_skill(skill_name), f"预置技能 '{skill_name}' 未出现在目录"

        assert skills.select_skill(skill_name), "无法选中技能"
        assert skills.is_owner(skill_name), "本账号技能应可编辑"

        skills.open_edit(skill_name)
        assert skills.is_edit_dialog_open(), "编辑弹窗未打开"
        assert skills.is_name_disabled(), "编辑时名称输入框应 disabled（不可改）"
        fields = skills.edit_field_values()
        assert fields["name"] == skill_name, f"编辑弹窗名称未回填: {fields['name']}"
        assert "编辑入口测试技能" in fields["description"], "编辑弹窗描述未回填"
        assert "Edit Entry Skill" in fields["content"], "编辑弹窗内容未回填"

        skills.cancel_dialog()
        assert not skills.is_dialog_open(), "取消后编辑弹窗应关闭"
    finally:
        _api_delete_skill_safe(base_url, cookie_jar, skill_name)


@allure.epic("技能管理")
@pytest.mark.order(83)
@pytest.mark.p2
def test_skills_detail_pane(logged_in_page, base_url):
    """技能详情栏 — 选中技能后展示名称/Skill 徽标/描述/SKILL.md 渲染区/归属徽标"""
    from tests.pages.config_pages import SkillsPage

    skills = SkillsPage(logged_in_page, base_url)
    skills.goto()
    assert skills.is_loaded(), "技能库页面未加载"

    names = skills.get_skill_names()
    if not names:
        pytest.skip("技能列表为空，无法测试详情")
    name = names[0]

    title = skills.select_skill(name)
    assert name in title, f"详情标题与所选不一致: '{title}' vs '{name}'"

    article = skills.article_text(name)
    assert "技能指令" in article, "详情缺少「技能指令」区块"
    assert "SKILL.md" in article, "详情缺少 SKILL.md 标识"
    # 底部徽标：公开/未公开 二选一
    assert ("未公开" in article) or ("公开" in article), "详情缺少公开/未公开徽标"


@allure.epic("技能管理")
@pytest.mark.order(84)
@pytest.mark.p0
def test_skill_create_text_mode_via_ui(logged_in_page, base_url, request):
    """TC-SKILL-003: 文本模式创建技能 — 新建→填表→保存→toast+目录出现+API 落库"""
    from tests.pages.config_pages import SkillsPage

    cookie_jar = _skills_session_cookie(logged_in_page)
    unique_name = f"e2e-create-{uuid.uuid4().hex[:8]}"
    content = (
        "---\n"
        f"name: {unique_name}\n"
        "description: 自动化文本创建测试技能\n"
        "---\n\n"
        "# 文本创建测试技能\n\n通过 UI 手动创建技能，验证完整创建流程。"
    )
    request.addfinalizer(lambda: _api_delete_skill_safe(base_url, cookie_jar, unique_name))

    skills = SkillsPage(logged_in_page, base_url)
    skills.goto()
    assert skills.is_loaded(), "技能库页面未加载"

    skills.open_create_dialog()
    assert skills.is_create_dialog_open(), "新建技能弹窗未打开"
    skills.fill_create_form(unique_name, description="自动化文本创建测试技能", content=content)
    skills.save_dialog()

    toast_text = skills.get_last_toast_text()
    assert "技能已创建" in toast_text, f"创建成功 toast 未出现: {toast_text}"
    assert not skills.is_dialog_open(), "创建成功后弹窗应关闭"

    assert skills.has_skill(unique_name), f"创建后目录未出现技能 '{unique_name}'"
    title = skills.select_skill(unique_name)
    assert unique_name in title, "详情标题未展示新建技能名"
    assert skills.is_owner(unique_name), "新建技能应属于本账号"
    # SKILL.md 的 front-matter name 不渲染进正文；断言标题含名 + 正文含描述与 Markdown 内容
    article = skills.article_text(unique_name)
    assert "自动化文本创建测试技能" in article, "新建技能详情未展示描述"
    assert "通过 UI 手动创建技能" in article, "新建技能详情未展示 SKILL.md 内容"

    # API 侧确认已创建（独立于 UI 渲染）
    assert _api_skill_exists(base_url, cookie_jar, unique_name), f"API 列表中未找到 '{unique_name}'"


@allure.epic("技能管理")
@pytest.mark.order(85)
@pytest.mark.p1
def test_skill_validation_empty_name(logged_in_page, base_url):
    """TC-SKILL-021: 空名称提交 → toast「名称不能为空」，未创建"""
    from tests.pages.config_pages import SkillsPage

    skills = SkillsPage(logged_in_page, base_url)
    skills.goto()
    assert skills.is_loaded(), "技能库页面未加载"

    skills.open_create_dialog()
    assert skills.is_create_dialog_open(), "新建技能弹窗未打开"
    skills.fill_create_form("", content="内容正常填写")
    skills.save_dialog()

    toast_text = skills.get_last_toast_text()
    assert "名称不能为空" in toast_text, f"名称校验 toast 未出现: {toast_text}"
    assert skills.is_create_dialog_open(), "校验失败后新建弹窗应保持打开"

    skills.cancel_dialog()
    assert not skills.is_dialog_open(), "取消后新建弹窗应关闭"


@allure.epic("技能管理")
@pytest.mark.order(86)
@pytest.mark.p1
def test_skill_validation_empty_content(logged_in_page, base_url):
    """TC-SKILL-022: 内容空提交 → toast「内容不能为空」，未创建"""
    from tests.pages.config_pages import SkillsPage

    skills = SkillsPage(logged_in_page, base_url)
    skills.goto()
    assert skills.is_loaded(), "技能库页面未加载"

    name = f"e2e-validate-{uuid.uuid4().hex[:8]}"
    skills.open_create_dialog()
    assert skills.is_create_dialog_open(), "新建技能弹窗未打开"
    skills.fill_create_form(name, content="")
    skills.save_dialog()

    toast_text = skills.get_last_toast_text()
    assert "内容不能为空" in toast_text, f"内容校验 toast 未出现: {toast_text}"
    assert skills.is_create_dialog_open(), "校验失败后新建弹窗应保持打开"
    assert not skills.has_skill(name, timeout=3000), "内容为空时不应创建技能"

    skills.cancel_dialog()
    assert not skills.is_dialog_open(), "取消后新建弹窗应关闭"


@allure.epic("技能管理")
@pytest.mark.order(87)
@pytest.mark.p2
def test_skill_create_cancel(logged_in_page, base_url):
    """TC-SKILL-024: 创建弹窗取消 — 填部分字段后取消，不创建"""
    from tests.pages.config_pages import SkillsPage

    skills = SkillsPage(logged_in_page, base_url)
    skills.goto()
    assert skills.is_loaded(), "技能库页面未加载"

    cancel_name = f"e2e-cancel-{uuid.uuid4().hex[:8]}"
    skills.open_create_dialog()
    assert skills.is_create_dialog_open(), "新建技能弹窗未打开"
    skills.fill_create_form(cancel_name, content="不会被保存")
    skills.cancel_dialog()

    assert not skills.is_dialog_open(), "取消后弹窗应关闭"
    assert not skills.has_skill(cancel_name, timeout=3000), "取消后不应创建技能"


@allure.epic("技能管理")
@pytest.mark.order(88)
@pytest.mark.p1
def test_skill_edit_save_and_cancel(logged_in_page, base_url):
    """TC-SKILL-004: 编辑保存生效 / 编辑取消不保存（API 侧校验描述）"""
    from tests.pages.config_pages import SkillsPage

    cookie_jar = _skills_session_cookie(logged_in_page)
    unique_name = f"e2e-edit-{uuid.uuid4().hex[:8]}"
    content = (
        "---\n"
        f"name: {unique_name}\n"
        "description: 初始描述\n"
        "---\n\n"
        "# 编辑测试技能"
    )
    upload_resp = _api_create_skill_upload(base_url, cookie_jar, unique_name, content)
    assert upload_resp.status_code < 400, f"预置编辑测试技能失败: HTTP {upload_resp.status_code}"
    try:
        skills = SkillsPage(logged_in_page, base_url)
        skills.goto()
        assert skills.is_loaded(), "技能库页面未加载"
        assert skills.reload(), "刷新后技能页面未加载"
        assert skills.has_skill(unique_name), f"预置技能 '{unique_name}' 未出现在目录"

        def api_description() -> str:
            r = requests.get(
                f"{base_url}/web/config/skills/{unique_name}", cookies=cookie_jar, timeout=10
            )
            return r.json().get("data", {}).get("description", "")

        # ── 编辑：改描述并保存 → 静默关闭，API 描述更新 ──
        assert skills.select_skill(unique_name), "无法选中技能"
        assert skills.is_owner(unique_name), "本账号技能应可编辑"
        skills.open_edit(unique_name)
        assert skills.is_edit_dialog_open(), "编辑弹窗未打开"
        skills.set_edit_field(description="编辑后的描述-已保存")
        skills.save_dialog()
        assert not skills.is_dialog_open(), "保存后编辑弹窗应关闭"
        assert api_description() == "编辑后的描述-已保存", "保存后描述未更新"

        # ── 编辑：再改描述但取消 → 描述不变 ──
        skills.open_edit(unique_name)
        assert skills.is_edit_dialog_open(), "第二次编辑弹窗未打开"
        fields = skills.edit_field_values()
        assert fields["description"] == "编辑后的描述-已保存", "编辑弹窗未回填已保存的描述"
        skills.set_edit_field(description="不应保存的描述")
        skills.cancel_dialog()
        assert not skills.is_dialog_open(), "取消后编辑弹窗应关闭"
        assert api_description() == "编辑后的描述-已保存", "取消编辑后描述不应变化"
    finally:
        _api_delete_skill_safe(base_url, cookie_jar, unique_name)


@allure.epic("技能管理")
@pytest.mark.order(89)
@pytest.mark.p1
@pytest.mark.no_page_error_check  # 重名创建后端返回 409，会打 console.error
def test_skill_duplicate_name(logged_in_page, base_url):
    """TC-SKILL-023: 重复名称创建 → toast「保存失败」，同名技能仍只有 1 个"""
    from tests.pages.config_pages import SkillsPage

    cookie_jar = _skills_session_cookie(logged_in_page)
    unique_name = f"e2e-dup-{uuid.uuid4().hex[:8]}"
    content = (
        "---\n"
        f"name: {unique_name}\n"
        "description: 重名测试技能\n"
        "---\n\n"
        "# 重名测试技能"
    )
    upload_resp = _api_create_skill_upload(base_url, cookie_jar, unique_name, content)
    assert upload_resp.status_code < 400, f"预置同名技能失败: HTTP {upload_resp.status_code}"
    try:
        skills = SkillsPage(logged_in_page, base_url)
        skills.goto()
        assert skills.is_loaded(), "技能库页面未加载"
        assert skills.reload(), "刷新后技能页面未加载"
        assert skills.has_skill(unique_name), f"预置技能 '{unique_name}' 未出现在目录"

        # 手动创建同名技能 → 应 409 冲突，toast 保存失败
        skills.open_create_dialog()
        assert skills.is_create_dialog_open(), "新建技能弹窗未打开"
        skills.fill_create_form(unique_name, content="同名内容")
        skills.save_dialog()

        toast_text = skills.get_last_toast_text()
        assert "保存失败" in toast_text, f"重复名称未提示保存失败: {toast_text}"
        assert skills.is_create_dialog_open(), "创建失败后弹窗应保持打开"
        skills.cancel_dialog()

        # API 侧确认仍只有 1 个同名技能
        resp = requests.get(f"{base_url}/web/config/skills", cookies=cookie_jar, timeout=10)
        assert resp.status_code == 200
        names = [s.get("name") for s in resp.json().get("data", {}).get("skills", [])]
        assert names.count(unique_name) == 1, (
            f"重名创建后同名技能数应为 1，实际 {names.count(unique_name)}"
        )
    finally:
        _api_delete_skill_safe(base_url, cookie_jar, unique_name)
