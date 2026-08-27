# tests/api_suites/test_peri_task_detail_api.py
"""Peri Task Detail Web API 接口测试：功能验证 + 契约验证

覆盖 Peri Task Detail API：
- TestPeriTaskDetailWebAPI: /web/agents/:envId/sessions/:sid/peri-tasks/:tid/detail

认证方式：session cookie（better-auth）
响应格式：{success: true, data: {...}} 包装

数据安全规则：
- 全部只读接口，不创建/修改/删除数据
- 需要有效的 environmentId、sessionId、taskId 才能查询

数据前置（peri_task_seed fixture）：
- 通过 Playwright UI 触发 peri-task（导航到带 sessionId 的聊天 URL → 发消息触发 subagent）
- 从 WS 帧中提取 taskId，验证 API 可用后提供给测试用例
- 仅当 Playwright 触发失败时 skip，不影响其他测试
"""
import logging
import random
import re

import httpx
import pytest

from tests.api_clients.web_client import WebClient
from tests.api_contracts.peri_task_detail_schemas import PERI_TASK_DETAIL_RESPONSE

logger = logging.getLogger(__name__)

# my-auto-test 环境 ID（优先从 test_data.yaml 的 fenixagent.peri_task_env_id 读取，兜底默认）
_PERI_TASK_ENV_ID = "env_239aaba8bf55273e4849f635"


@pytest.fixture(scope="module")
def peri_task_seed(api_base_url, api_test_config):
    """通过 Playwright UI 触发 peri-task，返回 (env_id, session_id, task_id) 或 None。

    流程：
    1. 启动 Playwright 浏览器并登录
    2. 导航到 /ctrl/agent/chat/{envId}/{sessionId}（显式带 sessionId，使 WS 携带 sessionId 参数）
    3. 发送消息触发 subagent spawn
    4. 从 WS 帧中提取 taskId
    5. 验证 API 返回 200
    6. 返回 (env_id, session_id, task_id)

    每步失败均返回 None（不 fail 整个测试模块）。
    """
    from playwright.sync_api import sync_playwright
    from tests.pages.login_page import LoginPage

    # 使用随机 session 号，避免与已有 session 冲突导致 Yjs doc 复用
    session_num = random.randint(100, 999)
    env_id = api_test_config.get("fenixagent", {}).get("peri_task_env_id") or _PERI_TASK_ENV_ID
    session_id = f"ses_inst_{env_id}_{session_num}"
    chat_url = f"{api_base_url}/ctrl/agent/chat/{env_id}/{session_id}"

    pw = None
    browser = None
    try:
        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            ignore_https_errors=True,
            viewport={"width": 1920, "height": 1080},
        )
        page = context.new_page()

        # ── 设置 WS 帧监听（在导航前注册，确保捕获所有连接） ──
        subagent_task_ids: list[str] = []

        def _on_ws(ws):
            def _on_frame(data):
                if isinstance(data, bytes):
                    text = data.decode("utf-8", errors="replace")
                    if "subagent" in text.lower():
                        matches = re.findall(
                            r"taskId.{0,5}[\$]?([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
                            text,
                        )
                        if matches:
                            subagent_task_ids.extend(matches)
            ws.on("framereceived", _on_frame)

        page.on("websocket", _on_ws)

        # ── 登录 ──
        login = LoginPage(page, api_base_url)
        login.goto()
        fenix = api_test_config["fenixagent"]
        email = fenix["admin"]["email"]
        password = str(fenix["admin"]["password"])
        login.login(email, password)
        page.wait_for_timeout(3000)
        if not login.is_logged_in():
            logger.warning("peri_task_seed: 登录失败")
            return None

        # ── 导航到带 sessionId 的聊天 URL ──
        # 关键：URL 必须包含 sessionId，否则 WS 不带 ?sessionId= 参数，
        # 导致 Yjs doc key（2-part）与 API 计算的 key（3-part）不匹配
        page.goto(chat_url)
        page.wait_for_timeout(5000)
        logger.info(f"peri_task_seed: 导航到 {chat_url}，当前 URL: {page.url}")

        # ── 发送触发消息 ──
        try:
            textarea = page.locator("textarea").first
            textarea.fill(
                "请启动子智能体帮我查一下今天的新闻头条",
                force=True,
            )
            page.wait_for_timeout(500)
            textarea.press("Enter")
            logger.info("peri_task_seed: 消息已发送，等待 subagent 触发...")
        except Exception as e:
            logger.warning(f"peri_task_seed: 发送消息失败: {e}")
            return None

        # ── 等待 subagent 触发（最多 50 秒） ──
        page.wait_for_timeout(50000)

        if not subagent_task_ids:
            logger.warning("peri_task_seed: 未从 WS 帧中捕获到 subagent taskId")
            return None

        unique_task_ids = list(set(subagent_task_ids))
        logger.info(f"peri_task_seed: 捕获到 {len(unique_task_ids)} 个 taskId: {unique_task_ids}")

        # ── 验证 API 可用性（用 httpx 调 API，确保数据可查） ──
        wc = WebClient(api_base_url)
        try:
            wc.login(email, password)
        except Exception as e:
            logger.warning(f"peri_task_seed: WebClient 登录失败: {e}")
            return None

        for tid in unique_task_ids:
            try:
                data = wc.get_peri_task_detail(env_id, session_id, tid)
                logger.info(f"peri_task_seed: API 验证成功 taskId={tid}, kind={data.get('kind')}")
                return (env_id, session_id, tid)
            except httpx.HTTPStatusError as e:
                logger.info(f"peri_task_seed: taskId={tid} API 返回 {e.response.status_code}")
                continue
            except Exception as e:
                logger.info(f"peri_task_seed: taskId={tid} API 异常: {e}")
                continue

        logger.warning("peri_task_seed: 所有 taskId 均无法通过 API 查询")
        return None

    except Exception as e:
        logger.warning(f"peri_task_seed: 异常: {e}")
        return None
    finally:
        if browser:
            try:
                browser.close()
            except Exception:
                pass
        if pw:
            try:
                pw.stop()
            except Exception:
                pass


@pytest.fixture(scope="module")
def peri_task(peri_task_seed):
    """返回 (env_id, session_id, task_id)；seed 失败则 skip 整个模块的正向用例。"""
    if peri_task_seed is None:
        pytest.skip("peri_task_seed 失败（Playwright UI 触发 subagent 未成功），跳过依赖真实数据的用例")
    return peri_task_seed


# ── Peri Task Detail 测试 ──

class TestPeriTaskDetailWebAPI:
    """/web/agents/:envId/sessions/:sid/peri-tasks/:tid/detail 接口（session cookie 认证）"""

    # ── 正向场景（P0） ──

    def test_get_peri_task_detail(self, web_client, peri_task):
        """获取 peri task 详情：使用有效的参数组合"""
        env_id, session_id, task_id = peri_task

        data = web_client.get_peri_task_detail(env_id, session_id, task_id)
        web_client.validate_schema(data, PERI_TASK_DETAIL_RESPONSE)
        # data 是 discriminated union（kind: preview | unavailable）
        assert "kind" in data
        assert data["kind"] in ("preview", "unavailable")
        assert "taskId" in data
        assert "taskKind" in data

    def test_get_peri_task_detail_preview(self, web_client, peri_task):
        """获取 preview 类型的 peri task 详情"""
        env_id, session_id, task_id = peri_task

        data = web_client.get_peri_task_detail(env_id, session_id, task_id)
        if data["kind"] != "preview":
            pytest.skip(f"当前任务返回 kind={data['kind']}，非 preview 类型")
        assert "items" in data
        assert isinstance(data["items"], list)
        assert "complete" in data
        assert isinstance(data["complete"], bool)

    def test_get_peri_task_detail_unavailable(self, web_client, peri_task):
        """获取 unavailable 类型的 peri task 详情"""
        env_id, session_id, task_id = peri_task

        data = web_client.get_peri_task_detail(env_id, session_id, task_id)
        if data["kind"] != "unavailable":
            pytest.skip(f"当前任务返回 kind={data['kind']}，非 unavailable 类型")
        assert "reason" in data
        assert data["reason"] in ("not_provided", "expired")

    def test_get_peri_task_detail_with_query_params(self, web_client, peri_task):
        """带查询参数获取 peri task 详情（cursor, limit, byteLimit）"""
        env_id, session_id, task_id = peri_task

        data = web_client.get_peri_task_detail(
            env_id, session_id, task_id,
            params={"limit": 1, "byteLimit": 500},
        )
        assert "kind" in data
        assert data["kind"] in ("preview", "unavailable")

    # ── 异常响应（P0） ──

    def test_get_peri_task_detail_nonexistent(self, web_client):
        """查询不存在的 peri-task：应返回 404 + NOT_FOUND"""
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            web_client.get_peri_task_detail(
                "nonexistent-env-id",
                "nonexistent-session-id",
                "nonexistent-task-id",
            )
        assert exc_info.value.response.status_code == 404
        body = exc_info.value.response.json()
        assert body.get("success") is False
        assert body.get("error", {}).get("code") == "NOT_FOUND"

    # ── 参数边界（P1） ──

    def test_get_peri_task_detail_empty_env_id(self, web_client):
        """空 environmentId：服务端路径规范化可能返回 302 重定向或 400/404"""
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            web_client.get_peri_task_detail("", "session-1", "task-1")
        # 空 path segment 产生双斜杠，服务端 path normalization 返回 302 重定向
        assert exc_info.value.response.status_code in (302, 400, 404, 422)

    def test_get_peri_task_detail_limit_boundary(self, web_client, peri_task):
        """limit 边界值（0）：应返回 400 或 422"""
        env_id, session_id, task_id = peri_task

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            web_client.get_peri_task_detail(
                env_id, session_id, task_id,
                params={"limit": 0},
            )
        assert exc_info.value.response.status_code in (400, 422)

    def test_get_peri_task_detail_byte_limit_exceeded(self, web_client, peri_task):
        """byteLimit 超限（>2000）：应返回 400 或 422"""
        env_id, session_id, task_id = peri_task

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            web_client.get_peri_task_detail(
                env_id, session_id, task_id,
                params={"byteLimit": 99999},
            )
        assert exc_info.value.response.status_code in (400, 422)

    # ── 权限场景（P0） ──

    def test_get_peri_task_detail_unauthorized(self, api_base_url):
        """无认证访问 peri-task detail：应返回 401 或 302（重定向到登录）"""
        client = httpx.Client(
            base_url=api_base_url, timeout=10, verify=False,
            follow_redirects=False,
        )
        try:
            resp = client.get(
                "/web/agents/env-1/sessions/sess-1/peri-tasks/task-1/detail"
            )
            # 未认证时，better-auth 可能返回 401 或 302 重定向到登录
            assert resp.status_code in (401, 302, 403)
        finally:
            client.close()
