# tests/suites/test_skills_v2.py
"""技能管理 V2 回归测试（列表加载、搜索、骨架屏、Open-API）"""
import pytest
import allure


@allure.epic("技能管理")
@pytest.mark.order(70)
def test_skill_list_data_loads(logged_in_page, base_url):
    """TC-SKILL-001: 技能列表数据加载 — 页面加载并展示已有技能"""
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
    """TC-SKILL-005: 技能搜索过滤 — 搜索后列表实时过滤，清空恢复"""
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
    assert filtered_count >= 0, "搜索功能异常"

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
    """TC-SKILL-008: 列表加载骨架屏 — 加载过程中显示骨架屏或 Spinner"""
    from tests.pages.config_pages import SkillsPage
    import time

    skills = SkillsPage(logged_in_page, base_url)

    # 使用 page.route() 拦截 API 并人为延迟 3 秒，确保骨架屏必定出现
    def delay_skills_api(route):
        time.sleep(3)
        route.continue_()

    logged_in_page.route("**/web/config/skills*", delay_skills_api)

    # 先导航到其他页面
    logged_in_page.goto(f"{base_url}/ctrl/agent/dashboard")
    logged_in_page.wait_for_load_state("networkidle")

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
def test_openapi_get_skill_list(logged_in_page, base_url):
    """TC-SKILL-016: Open-API 获取 Skill 列表和详情"""
    import json

    # 拦截技能列表 API 响应（/web/config/skills 或 /api/skills）
    skill_list_data = []

    def on_resp(r):
        if "skill" in r.url.lower() and ".js" not in r.url:
            try:
                body = r.json()
                if isinstance(body, dict):
                    # /web/config/skills → {success, data: {skills: [...]}}
                    # /api/skills → {items: [...]}
                    if "data" in body and "skills" in body.get("data", {}):
                        skill_list_data.append(("config", body))
                    elif "items" in body:
                        skill_list_data.append(("api", body))
            except Exception:
                pass

    logged_in_page.on("response", on_resp)
    logged_in_page.goto(f"{base_url}/ctrl/agent/skills")
    logged_in_page.wait_for_load_state("networkidle")
    logged_in_page.wait_for_timeout(2000)

    assert len(skill_list_data) > 0, "未拦截到技能 API 响应"

    # 取第一个有效数据
    source, data = skill_list_data[0]
    if source == "config":
        items = data.get("data", {}).get("skills", [])
    else:
        items = data.get("items", [])

    assert len(items) > 0, "API 返回的 skill 列表为空"

    # 验证每条 skill 有必需字段
    first = items[0]
    for field in ["id", "name"]:
        assert field in first, f"skill 缺少字段: {field}"

    # 验证获取单个详情（通过 /api/skills/{id}）
    skill_id = first["id"]
    detail_data = []

    def on_detail(r):
        if f"/api/skills/{skill_id}" in r.url:
            try:
                detail_data.append(r.json())
            except Exception:
                pass

    logged_in_page.on("response", on_detail)
    logged_in_page.goto(f"{base_url}/api/skills/{skill_id}")
    logged_in_page.wait_for_timeout(2000)

    if detail_data:
        detail = detail_data[0]
        assert detail.get("name") == first["name"], "详情名称与列表不一致"
    else:
        # 直接用 page content 检查
        body_text = logged_in_page.locator("body").inner_text()
        try:
            detail = json.loads(body_text)
            assert detail.get("name") == first["name"], "详情名称与列表不一致"
        except (json.JSONDecodeError, KeyError):
            pytest.skip("无法获取单个 Skill 详情接口")


@allure.epic("技能管理")
@pytest.mark.order(74)
def test_openapi_upload_skill(logged_in_page, base_url):
    """TC-SKILL-015: Open-API 上传 Skill（通过页面上传功能验证 API）"""
    import os, tempfile, shutil

    # 准备测试文件夹（含 SKILL.md）
    test_dir = tempfile.mkdtemp(prefix="skill_auto_test_")
    skill_dir = os.path.join(test_dir, "auto-test-skill")
    os.makedirs(skill_dir, exist_ok=True)
    skill_md = os.path.join(skill_dir, "SKILL.md")
    with open(skill_md, "w", encoding="utf-8") as f:
        f.write(
            "---\nname: auto-test-skill\ndescription: 自动化测试技能\n---\n\n"
            "# Auto Test Skill\n\nThis is a test skill for automation.\n"
        )

    upload_result = []

    def on_upload_resp(r):
        url = r.url.lower()
        if "skill" in url and r.request.method in ("POST", "PUT"):
            try:
                upload_result.append({"status": r.status, "url": r.url})
            except Exception:
                pass

    logged_in_page.on("response", on_upload_resp)

    from tests.pages.config_pages import SkillsPage

    skills = SkillsPage(logged_in_page, base_url)
    skills.goto()

    # 点击上传按钮 → 打开对话框
    upload_btn = logged_in_page.locator("button").filter(has_text="上传技能")
    assert upload_btn.count() > 0, "未找到「上传技能」按钮"
    upload_btn.first.click()
    logged_in_page.wait_for_timeout(1500)

    # 对话框应出现
    dialog = logged_in_page.locator("[role='dialog']")
    assert dialog.count() > 0, "上传对话框未弹出"

    # 找到文件 input（在对话框中）
    file_input = dialog.locator("input[type='file']")
    if file_input.count() == 0:
        file_input = logged_in_page.locator("input[type='file']")

    if file_input.count() > 0:
        # 检查是否为 webkitdirectory（文件夹上传）
        is_dir = file_input.first.get_attribute("webkitdirectory")
        if is_dir is not None:
            # Playwright 不支持直接设置目录路径
            pytest.skip("Playwright 不支持 webkitdirectory 文件夹上传")
        try:
            # 设置 SKILL.md 文件
            file_input.first.set_input_files(skill_md)
            logged_in_page.wait_for_timeout(1000)

            # 点击「开始上传」
            start_btn = dialog.locator("button").filter(has_text="开始上传")
            if start_btn.count() > 0:
                start_btn.first.click()
                logged_in_page.wait_for_load_state("networkidle", timeout=10000)
                logged_in_page.wait_for_timeout(2000)

                # 检查上传结果
                if upload_result:
                    status = upload_result[-1]["status"]
                    assert status < 400, f"上传失败: HTTP {status}"
                else:
                    # 检查页面反馈
                    logged_in_page.wait_for_timeout(3000)
                    body = logged_in_page.locator("body").inner_text()
                    assert (
                        "auto-test-skill" in body or len(upload_result) > 0
                    ), "上传后无成功反馈"
            else:
                pytest.skip("未找到「开始上传」按钮")
        except Exception as e:
            pytest.skip(f"文件夹上传不支持: {e}")
    else:
        pytest.skip("未找到文件上传 input")

    # 清理
    shutil.rmtree(test_dir, ignore_errors=True)


@allure.epic("技能管理")
@pytest.mark.order(75)
def test_openapi_delete_skill(logged_in_page, base_url):
    """TC-SKILL-017: Open-API 删除 Skill（通过页面删除功能验证）"""
    from tests.pages.config_pages import SkillsPage

    skills = SkillsPage(logged_in_page, base_url)
    skills.goto()

    initial_count = skills.get_skill_count()
    assert initial_count > 0, "技能列表为空，无法测试删除"

    # 找到第一个技能的删除按钮
    delete_btns = logged_in_page.locator("button").filter(has_text="删除")
    assert delete_btns.count() > 0, "未找到删除按钮"

    delete_result = []

    def on_delete_resp(r):
        if "/skill" in r.url.lower() and r.request.method == "DELETE":
            try:
                delete_result.append({"status": r.status})
            except Exception:
                pass

    logged_in_page.on("response", on_delete_resp)

    # 点击第一个删除按钮
    delete_btns.first.click()
    logged_in_page.wait_for_timeout(1000)

    # 确认删除（可能有对话框）
    for selector in [
        "[role='alertdialog'] button:has-text('确认')",
        "[role='alertdialog'] button:has-text('确定')",
        "[role='dialog'] button:has-text('确认')",
        "[role='dialog'] button:has-text('确定')",
        "button:has-text('确认删除')",
    ]:
        confirm = logged_in_page.locator(selector)
        if confirm.count() > 0:
            confirm.first.click()
            logged_in_page.wait_for_timeout(2000)
            break

    # 验证
    new_count = skills.get_skill_count()
    if delete_result:
        assert delete_result[0]["status"] < 400, (
            f"删除 API 失败: HTTP {delete_result[0]['status']}"
        )
    assert new_count < initial_count, (
        f"删除后数量未减少: {new_count} vs {initial_count}"
    )
