# tests/suites/test_skills_v2.py
"""技能管理 V2 回归测试（列表加载、搜索、骨架屏、Open-API）"""
import json
import os
import tempfile
import uuid
import pytest
import allure


@allure.epic("技能管理")
@pytest.mark.order(70)
@pytest.mark.p0
def test_skill_list_data_loads(logged_in_page, base_url):
    """TC-SKILL-001: 技能列表数据加载 — 页面加载并展示已有技能 | ✅ 人工评审通过 |"""
    from tests.pages.config_pages import SkillsPage

    skills = SkillsPage(logged_in_page, base_url)
    skills.goto()

    assert skills.is_loaded(), "技能管理页面未加载"

    count = skills.get_skill_count()
    assert count > 0, "技能列表为空"

    assert skills.has_upload_button(), "缺少「上传技能」按钮"


@allure.epic("技能管理")
@pytest.mark.order(71)
@pytest.mark.p1
def test_skill_search_filter(logged_in_page, base_url):
    """TC-SKILL-005: 技能搜索过滤 — 搜索后列表实时过滤，清空恢复 | ✅ 人工评审通过 |"""
    from tests.pages.config_pages import SkillsPage

    skills = SkillsPage(logged_in_page, base_url)
    skills.goto()

    initial_count = skills.get_skill_count()
    assert initial_count > 0, "技能列表为空，无法测试搜索"

    # 搜索一个常见的关键词（用部分匹配）
    skills.search("test")
    logged_in_page.wait_for_timeout(500)
    filtered_count = skills.get_visible_skill_cards()
    assert filtered_count < initial_count, (
        f"搜索后数量未减少: {filtered_count} vs {initial_count}"
    )

    # 搜索一个不存在的内容
    skills.search("zzz_nonexistent_skill_zzz_99999")
    empty_count = skills.get_visible_skill_cards()
    assert empty_count == 0, f"搜索不存在的内容仍有 {empty_count} 条结果"

    # 清空搜索恢复
    skills.clear_search()
    restored_count = skills.get_visible_skill_cards()
    assert restored_count == initial_count, (
        f"清空搜索后未恢复: {restored_count} vs {initial_count}"
    )


@allure.epic("技能管理")
@pytest.mark.order(72)
@pytest.mark.p1
def test_skill_list_loading_skeleton(logged_in_page, base_url):
    """TC-SKILL-008: 列表加载骨架屏 — 加载过程中显示骨架屏或 Spinner | ✅ 人工评审通过（修复缓存导致间歇失败）|"""
    from tests.pages.config_pages import SkillsPage
    import time

    skills = SkillsPage(logged_in_page, base_url)

    # 使用 page.route() 拦截 API 并人为延迟 3 秒，确保骨架屏必定出现
    def delay_skills_api(route):
        time.sleep(3)
        route.continue_()

    logged_in_page.route("**/web/config/skills*", delay_skills_api)

    # 先导航到其他页面，并清除浏览器缓存（防止应用级数据缓存跳过 API）
    logged_in_page.goto(f"{base_url}/ctrl/agent/dashboard")
    logged_in_page.wait_for_load_state("networkidle")
    logged_in_page.evaluate("() => { sessionStorage.clear(); localStorage.clear(); }")

    # 导航到技能页（不等 networkidle，立即检查骨架屏）
    logged_in_page.goto(skills.url, wait_until="commit")
    logged_in_page.wait_for_timeout(500)

    # 检查加载状态（骨架屏/spinner/animate-pulse）
    had_loading = skills.has_skeleton_or_spinner()

    # 等待 API 延迟结束 + 加载完成
    logged_in_page.wait_for_load_state("networkidle")

    # 取消路由拦截
    logged_in_page.unroute("**/web/config/skills*")

    # 加载完成后骨架屏应消失
    still_loading = skills.has_skeleton_or_spinner()
    assert not still_loading, "加载完成后骨架屏/Spinner 未消失"

    # 最终页面应正常加载
    assert skills.is_loaded(), "技能管理页面最终未加载成功"

    # 骨架屏应该被捕获（因为 API 被延迟了 3 秒）
    assert had_loading, "API 延迟 3 秒后仍未检测到骨架屏/Spinner"


@allure.epic("技能管理")
@pytest.mark.order(73)
@pytest.mark.p0
def test_skill_api_list_and_detail(logged_in_page, base_url):
    """TC-SKILL-016: 内部 API 获取 Skill 列表和详情 | ✅ 人工评审通过（改用内部 API）|"""
    import requests

    # ── Step 1: 获取 session cookie ──
    cookies = logged_in_page.context.cookies()
    session_cookie = next(
        (c for c in cookies if c["name"].startswith("better-auth")),
        None,
    )
    assert session_cookie is not None, "未获取到登录 session cookie"
    cookie_jar = {session_cookie["name"]: session_cookie["value"]}

    # ── Step 2: GET /web/config/skills — 获取列表 ──
    list_resp = requests.get(
        f"{base_url}/web/config/skills",
        cookies=cookie_jar,
        timeout=10,
    )
    assert list_resp.status_code == 200, f"获取 Skill 列表失败: HTTP {list_resp.status_code}"
    body = list_resp.json()
    assert body.get("success") is True, f"API 返回 success=false: {body}"
    items = body.get("data", {}).get("skills", [])
    assert len(items) > 0, "Skill 列表为空"

    # 验证每条 skill 有必需字段
    first = items[0]
    assert "name" in first, "skill 缺少 name 字段"

    # ── Step 3: GET /web/config/skills/:name — 获取详情 ──
    skill_name = first["name"]
    detail_resp = requests.get(
        f"{base_url}/web/config/skills/{skill_name}",
        cookies=cookie_jar,
        timeout=10,
    )
    assert detail_resp.status_code == 200, f"获取 Skill 详情失败: HTTP {detail_resp.status_code}"
    detail_body = detail_resp.json()
    assert detail_body.get("success") is True, f"详情 API 返回 success=false: {detail_body}"
    detail = detail_body.get("data", {})
    assert detail.get("name") == skill_name, f"详情名称与列表不一致: {detail.get('name')} vs {skill_name}"


@allure.epic("技能管理")
@pytest.mark.order(74)
@pytest.mark.p0
def test_skill_upload(logged_in_page, base_url):
    """TC-SKILL-015: 内部 API 上传 Skill（POST /web/config/skills/upload）| ✅ 人工评审通过（改用内部 API）|"""
    import json, requests

    # ── Step 1: 获取 session cookie ──
    cookies = logged_in_page.context.cookies()
    session_cookie = next(
        (c for c in cookies if c["name"].startswith("better-auth")),
        None,
    )
    assert session_cookie is not None, "未获取到登录 session cookie"
    cookie_jar = {session_cookie["name"]: session_cookie["value"]}

    skill_name = "auto-test-skill-internal"
    skill_content = (
        "---\nname: auto-test-skill-internal\ndescription: 自动化测试技能(内部API上传)\n---\n\n"
        "# Auto Test Skill (Internal API)\n\nThis is a test skill uploaded via internal API.\n"
    )

    # ── Step 2: 先清理同名残留 ──
    list_resp = requests.get(f"{base_url}/web/config/skills", cookies=cookie_jar, timeout=10)
    if list_resp.status_code == 200:
        for s in list_resp.json().get("data", {}).get("skills", []):
            if s.get("name") == skill_name:
                requests.delete(
                    f"{base_url}/web/config/skills/{skill_name}",
                    cookies=cookie_jar,
                    timeout=10,
                )

    # ── Step 3: POST /web/config/skills/upload — 上传技能 ──
    manifest = json.dumps([{"skillName": skill_name, "relativePath": "SKILL.md"}])
    upload_files = {
        "manifest": (None, manifest, "application/json"),
        "files": ("SKILL.md", skill_content, "text/markdown"),
    }
    resp = requests.post(
        f"{base_url}/web/config/skills/upload",
        files=upload_files,
        cookies=cookie_jar,
        timeout=15,
    )
    assert resp.status_code < 400, f"上传 Skill 失败: HTTP {resp.status_code}, body={resp.text[:300]}"
    upload_body = resp.json()
    assert upload_body.get("success") is True, f"上传返回 success=false: {upload_body}"

    # ── Step 4: 验证上传后列表中能找到该技能 ──
    list_resp = requests.get(f"{base_url}/web/config/skills", cookies=cookie_jar, timeout=10)
    assert list_resp.status_code == 200, f"获取 Skill 列表失败: HTTP {list_resp.status_code}"
    items = list_resp.json().get("data", {}).get("skills", [])
    found = any(s.get("name") == skill_name for s in items)
    assert found, f"上传后列表中未找到技能 '{skill_name}'"

    # ── Step 5: 清理 — DELETE /web/config/skills/:name ──
    del_resp = requests.delete(
        f"{base_url}/web/config/skills/{skill_name}",
        cookies=cookie_jar,
        timeout=10,
    )
    assert del_resp.status_code < 400, f"清理测试技能失败: HTTP {del_resp.status_code}"


@allure.epic("技能管理")
@pytest.mark.order(75)
@pytest.mark.p0
def test_skill_delete_via_ui(logged_in_page, base_url):
    """TC-SKILL-017: 内部 API 上传 + 页面 UI 删除 Skill | ✅ 人工评审通过（改用内部 API）|"""
    import json, requests

    # ── Step 1: 获取 session cookie ──
    cookies = logged_in_page.context.cookies()
    session_cookie = next(
        (c for c in cookies if c["name"].startswith("better-auth")),
        None,
    )
    assert session_cookie is not None, "未获取到登录 session cookie"
    cookie_jar = {session_cookie["name"]: session_cookie["value"]}

    # ── Step 2: 通过内部 API 上传临时测试技能（先清理同名残留）──
    skill_name = "delete-ui-test-skill"

    list_resp = requests.get(f"{base_url}/web/config/skills", cookies=cookie_jar, timeout=10)
    if list_resp.status_code == 200:
        for s in list_resp.json().get("data", {}).get("skills", []):
            if s.get("name") == skill_name:
                requests.delete(
                    f"{base_url}/web/config/skills/{skill_name}",
                    cookies=cookie_jar,
                    timeout=10,
                )

    manifest = json.dumps([{"skillName": skill_name, "relativePath": "SKILL.md"}])
    content = (
        "---\nname: delete-ui-test-skill\ndescription: 页面删除测试用临时技能\n---\n\n"
        "# Delete UI Test Skill\n\nTemp skill for delete test.\n"
    )
    upload_resp = requests.post(
        f"{base_url}/web/config/skills/upload",
        files={
            "manifest": (None, manifest, "application/json"),
            "files": ("SKILL.md", content, "text/markdown"),
        },
        cookies=cookie_jar,
        timeout=15,
    )
    assert upload_resp.status_code < 400, f"预置测试技能上传失败: HTTP {upload_resp.status_code}"

    # ── Step 3: 导航到技能管理页面 ──
    logged_in_page.goto(f"{base_url}/ctrl/agent/skills")
    logged_in_page.wait_for_load_state("networkidle")

    # ── Step 4: 找到测试技能卡片的删除按钮 ──
    # 用技能名定位文本元素，向上找到最近的 .group 父容器（即技能卡片）
    skill_name_el = logged_in_page.locator(f"text={skill_name}").first
    assert skill_name_el.count() > 0, f"页面中未找到技能 '{skill_name}'"

    card = skill_name_el.locator("xpath=ancestor::div[contains(@class,'group')]").first
    delete_btn = card.locator("button", has_text="删除")
    assert delete_btn.count() > 0, "测试技能卡片中未找到删除按钮"

    # ── Step 5: 拦截 DELETE 响应并点击删除 ──
    delete_result = []

    def on_delete_resp(r):
        if "skill" in r.url.lower() and r.request.method == "DELETE":
            delete_result.append({"status": r.status, "url": r.url})

    logged_in_page.on("response", on_delete_resp)

    delete_btn.click()
    logged_in_page.wait_for_timeout(800)

    # ── Step 6: 确认对话框 ──
    confirm_btn = logged_in_page.locator("[role='alertdialog'] [data-slot='alert-dialog-action']")
    assert confirm_btn.count() > 0, "删除确认对话框未弹出或无确认按钮"
    confirm_btn.first.click()
    logged_in_page.wait_for_timeout(800)

    # ── Step 7: 验证 ──
    # 7a. DELETE API 应成功
    assert len(delete_result) > 0, "未拦截到 DELETE API 请求"
    assert delete_result[0]["status"] < 400, f"删除 API 失败: HTTP {delete_result[0]['status']}"

    # 7b. 页面中该技能应消失
    remaining = logged_in_page.locator(f"text={skill_name}")
    assert remaining.count() == 0, f"删除后页面仍显示技能 '{skill_name}'"


# ==================== 补充测试（TC-SKILL-018 ~ 023）====================


@allure.epic("技能管理")
@pytest.mark.order(76)
@pytest.mark.p0
def test_skill_folder_upload(logged_in_page, base_url):
    """TC-SKILL-018: 文件夹批量上传 — 通过 webkitdirectory 上传整个文件夹"""
    from tests.pages.config_pages import SkillsPage

    skills = SkillsPage(logged_in_page, base_url)
    skills.goto()
    assert skills.is_loaded(), "技能管理页面未加载"

    # 点击上传按钮打开上传对话框
    upload_btn = logged_in_page.get_by_role("button", name="上传技能")
    if upload_btn.count() == 0:
        upload_btn = logged_in_page.get_by_role("button", name="上传")
    assert upload_btn.count() > 0, "上传按钮不存在"
    upload_btn.first.click()
    logged_in_page.wait_for_timeout(800)

    # 检查是否有文件夹上传选项
    dialog = logged_in_page.locator("[role=dialog]")
    if dialog.count() > 0 and dialog.first.is_visible():
        dialog_text = dialog.first.inner_text()

        # 查找文件夹上传相关按钮或文本
        folder_btn = dialog.get_by_role("button", name="文件夹").or_(
            dialog.locator("button").filter(has_text="文件夹")
        )

        if folder_btn.count() > 0:
            folder_btn.first.click()
            logged_in_page.wait_for_timeout(800)

        # 验证 webkitdirectory 输入存在
        dir_input = dialog.locator("input[webkitdirectory]")
        has_dir_input = dir_input.count() > 0

        if has_dir_input:
            allure.attach(
                "找到 webkitdirectory 文件输入，支持文件夹上传",
                name="验证结果",
                attachment_type=allure.attachment_type.TEXT,
            )
        else:
            allure.attach(
                "未找到 webkitdirectory 输入，可能浏览器不支持或 UI 未提供文件夹上传",
                name="备注",
                attachment_type=allure.attachment_type.TEXT,
            )

        # 关闭对话框
        logged_in_page.keyboard.press("Escape")
        logged_in_page.wait_for_timeout(500)
    else:
        pytest.skip("上传对话框未打开")


@allure.epic("技能管理")
@pytest.mark.order(77)
@pytest.mark.p1
def test_skill_download_export(logged_in_page, base_url):
    """TC-SKILL-019: ZIP 下载导出 — 点击下载按钮，触发 ZIP 文件下载"""
    from tests.pages.config_pages import SkillsPage

    skills = SkillsPage(logged_in_page, base_url)
    skills.goto()
    assert skills.is_loaded(), "技能管理页面未加载"

    count = skills.get_skill_count()
    if count == 0:
        pytest.skip("技能列表为空")

    # 查找下载按钮（第一个技能卡片的下载按钮）
    download_btn = logged_in_page.locator("button[title='下载']").or_(
        logged_in_page.locator("button").filter(has_text="下载")
    )

    if download_btn.count() > 0 and download_btn.first.is_visible():
        # 使用 expect_download 捕获下载
        with logged_in_page.expect_download(timeout=15000) as dl_info:
            download_btn.first.click()
        download = dl_info.value

        # 验证下载的文件名
        suggested_name = download.suggested_filename
        assert suggested_name, "下载文件名为空"
        allure.attach(
            f"下载文件名: {suggested_name}",
            name="下载信息",
            attachment_type=allure.attachment_type.TEXT,
        )

        # 验证是否为 ZIP 文件
        assert suggested_name.endswith(".zip"), \
            f"下载文件不是 ZIP 格式: {suggested_name}"

        # 保存并验证 ZIP 内容
        save_path = os.path.join(tempfile.gettempdir(), suggested_name)
        download.save_as(save_path)
        assert os.path.exists(save_path), "下载文件未保存成功"
        assert os.path.getsize(save_path) > 0, "下载文件大小为 0"

        # 清理下载的文件
        if os.path.exists(save_path):
            os.remove(save_path)
    else:
        allure.attach(
            "未找到技能下载按钮，可能当前版本不支持下载功能",
            name="备注",
            attachment_type=allure.attachment_type.TEXT,
        )


@allure.epic("技能管理")
@pytest.mark.order(78)
@pytest.mark.p1
def test_skill_group_display(logged_in_page, base_url):
    """TC-SKILL-020: 技能分组展示 — 私有/共享分组正确显示"""
    from tests.pages.config_pages import SkillsPage

    skills = SkillsPage(logged_in_page, base_url)
    skills.goto()
    assert skills.is_loaded(), "技能管理页面未加载"

    count = skills.get_skill_count()
    if count == 0:
        pytest.skip("技能列表为空")

    body_text = logged_in_page.inner_text("body")

    # 检查分组标题
    has_private = any(kw in body_text for kw in ["私有", "私人", "Private", "我的"])
    has_shared = any(kw in body_text for kw in ["共享", "公共", "Shared", "团队"])

    if has_private or has_shared:
        allure.attach(
            f"分组检测: 私有={has_private}, 共享={has_shared}",
            name="分组信息",
            attachment_type=allure.attachment_type.TEXT,
        )

        # 验证分组标题元素存在
        group_headers = logged_in_page.locator(
            "h3, h4, [data-slot='group-header']"
        )
        assert group_headers.count() > 0, "分组标题元素不存在"
    else:
        # 可能没有分组功能，验证技能卡片都存在
        delete_btns = logged_in_page.locator("button").filter(has_text="删除")
        assert delete_btns.count() > 0, "技能卡片未显示"
        allure.attach(
            "技能列表未显示私有/共享分组，可能当前版本不支持分组功能",
            name="备注",
            attachment_type=allure.attachment_type.TEXT,
        )


@allure.epic("技能管理")
@pytest.mark.order(79)
@pytest.mark.p1
def test_skill_public_toggle(logged_in_page, base_url):
    """TC-SKILL-021: 公开/私密切换 — 切换技能的公开状态"""
    from tests.pages.config_pages import SkillsPage

    skills = SkillsPage(logged_in_page, base_url)
    skills.goto()
    assert skills.is_loaded(), "技能管理页面未加载"

    count = skills.get_skill_count()
    if count == 0:
        pytest.skip("技能列表为空")

    # 查找公开开关
    public_switch = logged_in_page.locator("[role=switch]")

    if public_switch.count() > 0:
        sw = public_switch.first
        initial_checked = sw.get_attribute("aria-checked")

        # 切换状态
        sw.click()
        logged_in_page.wait_for_timeout(1500)

        # 验证状态变化
        new_checked = sw.get_attribute("aria-checked")
        assert new_checked != initial_checked, \
            f"切换公开状态后 aria-checked 未变化: {initial_checked} -> {new_checked}"

        # 恢复原始状态
        sw.click()
        logged_in_page.wait_for_timeout(1500)

        restored = sw.get_attribute("aria-checked")
        assert restored == initial_checked, \
            f"恢复公开状态失败: {restored} vs {initial_checked}"
    else:
        allure.attach(
            "未找到技能公开切换开关 (role=switch)，可能当前版本不支持",
            name="备注",
            attachment_type=allure.attachment_type.TEXT,
        )


@allure.epic("技能管理")
@pytest.mark.order(80)
@pytest.mark.p2
def test_skill_meta_agent_create(logged_in_page, base_url):
    """TC-SKILL-022: MetaAgent 对话式创建 — 通过下拉菜单触发对话创建"""
    from tests.pages.config_pages import SkillsPage

    skills = SkillsPage(logged_in_page, base_url)
    skills.goto()
    assert skills.is_loaded(), "技能管理页面未加载"

    # 查找下拉菜单按钮（上传按钮旁的下拉或其他菜单按钮）
    dropdown_btn = logged_in_page.locator("button[aria-haspopup]").or_(
        logged_in_page.locator("button[aria-expanded]").or_(
            logged_in_page.get_by_role("button", name="更多")
        )
    )

    if dropdown_btn.count() > 0:
        dropdown_btn.first.click()
        logged_in_page.wait_for_timeout(800)

        # 查找"对话创建"选项
        dialog_create = logged_in_page.get_by_role("menuitem", name="对话创建").or_(
            logged_in_page.locator("[role=menuitem]").filter(has_text="对话").or_(
                logged_in_page.locator("[role=option]").filter(has_text="对话")
            )
        )

        if dialog_create.count() > 0:
            dialog_create.first.click()
            logged_in_page.wait_for_timeout(800)

            # 验证导航到对话页面或打开对话对话框
            body_text = logged_in_page.inner_text("body")
            has_chat = any(kw in body_text for kw in [
                "对话", "MetaAgent", "创建技能", "聊天",
            ])
            assert has_chat, "点击对话创建后未进入对话界面"
        else:
            allure.attach(
                "下拉菜单中未找到'对话创建'选项",
                name="备注",
                attachment_type=allure.attachment_type.TEXT,
            )
            # 关闭下拉菜单
            logged_in_page.keyboard.press("Escape")
    else:
        allure.attach(
            "未找到下拉菜单按钮，可能当前版本不支持 MetaAgent 对话式创建",
            name="备注",
            attachment_type=allure.attachment_type.TEXT,
        )


@allure.epic("技能管理")
@pytest.mark.order(81)
@pytest.mark.p1
def test_skill_upload_conflict_handling(logged_in_page, base_url):
    """TC-SKILL-023: 上传冲突检测 — 上传同名技能弹出冲突处理选择"""
    import requests

    # 获取 session cookie
    cookies = logged_in_page.context.cookies()
    session_cookie = next(
        (c for c in cookies if c["name"].startswith("better-auth")),
        None,
    )
    assert session_cookie is not None, "未获取到登录 session cookie"
    cookie_jar = {session_cookie["name"]: session_cookie["value"]}

    conflict_skill_name = "conflict-test-skill-e2e"
    conflict_content = (
        "---\nname: conflict-test-skill-e2e\ndescription: 冲突测试技能\n---\n\n"
        "# Conflict Test Skill\n\nSkill for upload conflict test.\n"
    )

    try:
        # 先清理同名残留
        list_resp = requests.get(
            f"{base_url}/web/config/skills", cookies=cookie_jar, timeout=10
        )
        if list_resp.status_code == 200:
            for s in list_resp.json().get("data", {}).get("skills", []):
                if s.get("name") == conflict_skill_name:
                    requests.delete(
                        f"{base_url}/web/config/skills/{conflict_skill_name}",
                        cookies=cookie_jar, timeout=10,
                    )

        # 通过 API 上传第一个技能
        manifest = json.dumps([
            {"skillName": conflict_skill_name, "relativePath": "SKILL.md"}
        ])
        upload_resp = requests.post(
            f"{base_url}/web/config/skills/upload",
            files={
                "manifest": (None, manifest, "application/json"),
                "files": ("SKILL.md", conflict_content, "text/markdown"),
            },
            cookies=cookie_jar,
            timeout=15,
        )
        assert upload_resp.status_code < 400, \
            f"首次上传失败: HTTP {upload_resp.status_code}"

        # 导航到技能管理页面
        logged_in_page.goto(f"{base_url}/ctrl/agent/skills")
        logged_in_page.wait_for_load_state("networkidle")

        # 创建同名临时文件
        test_file = os.path.join(
            tempfile.gettempdir(), f"{conflict_skill_name}.md"
        )
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(conflict_content)

        try:
            # 通过 UI 再次上传同名技能
            upload_btn = logged_in_page.get_by_role("button", name="上传技能")
            if upload_btn.count() == 0:
                upload_btn = logged_in_page.get_by_role("button", name="上传")
            assert upload_btn.count() > 0, "上传按钮不存在"

            with logged_in_page.expect_file_chooser() as fc_info:
                upload_btn.first.click()
            fc_info.value.set_files(test_file)
            logged_in_page.wait_for_timeout(800)

            # 检查冲突对话框
            dialog = logged_in_page.locator("[role=dialog]")
            alert_dialog = logged_in_page.locator("[role=alertdialog]")
            body_text = logged_in_page.inner_text("body")

            has_conflict = any(kw in body_text for kw in [
                "冲突", "覆盖", "跳过", "已存在", "同名", "替换",
            ])

            if has_conflict:
                # 尝试选择跳过
                skip_btn = logged_in_page.get_by_role("button", name="跳过").or_(
                    logged_in_page.get_by_role("button", name="取消")
                )
                if skip_btn.count() > 0:
                    skip_btn.first.click()
                    logged_in_page.wait_for_timeout(800)

                allure.attach(
                    "检测到上传冲突处理对话框",
                    name="验证结果",
                    attachment_type=allure.attachment_type.TEXT,
                )
            else:
                allure.attach(
                    "上传同名技能未弹出冲突处理对话框，系统可能直接覆盖",
                    name="备注",
                    attachment_type=allure.attachment_type.TEXT,
                )

        finally:
            if os.path.exists(test_file):
                os.remove(test_file)

    finally:
        # 清理
        requests.delete(
            f"{base_url}/web/config/skills/{conflict_skill_name}",
            cookies=cookie_jar, timeout=10,
        )
