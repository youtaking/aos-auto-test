# tests/suites/test_skills_v2.py
"""技能管理 V2 回归测试（列表加载、搜索、骨架屏、Open-API）"""
import pytest
import allure


@allure.epic("技能管理")
@pytest.mark.order(70)
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
    logged_in_page.wait_for_timeout(1000)

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
    logged_in_page.wait_for_timeout(2000)

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
    logged_in_page.wait_for_timeout(1000)

    # ── Step 6: 确认对话框 ──
    confirm_btn = logged_in_page.locator("[role='alertdialog'] [data-slot='alert-dialog-action']")
    assert confirm_btn.count() > 0, "删除确认对话框未弹出或无确认按钮"
    confirm_btn.first.click()
    logged_in_page.wait_for_timeout(3000)

    # ── Step 7: 验证 ──
    # 7a. DELETE API 应成功
    assert len(delete_result) > 0, "未拦截到 DELETE API 请求"
    assert delete_result[0]["status"] < 400, f"删除 API 失败: HTTP {delete_result[0]['status']}"

    # 7b. 页面中该技能应消失
    remaining = logged_in_page.locator(f"text={skill_name}")
    assert remaining.count() == 0, f"删除后页面仍显示技能 '{skill_name}'"
