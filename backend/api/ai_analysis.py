# backend/api/ai_analysis.py
"""AI 分析 API：LLM 分析报告 → 生成 Bug → 推送禅道"""
import json
import httpx
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.db.config import get_async_session
from backend.db.models import TestRun, TestResult, LLMConfig, ZentaoConfig
from backend.schemas.common import ApiResponse
from pydantic import BaseModel

router = APIRouter()

# ── 报告文件存储目录 ───────────────────────────────────────────────
REPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "ai_reports"


def _ensure_reports_dir():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _write_report_files(run_id: int, report_md: str, bugs: list[dict], model: str) -> str:
    """将报告写入文件，返回报告 ID（时间戳目录名）"""
    _ensure_reports_dir()
    report_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    # 处理同一秒内的并发：加后缀避免覆盖
    report_dir = REPORTS_DIR / report_id
    suffix = 1
    while report_dir.exists():
        report_id = datetime.now().strftime("%Y%m%d_%H%M%S") + f"_{suffix}"
        report_dir = REPORTS_DIR / report_id
        suffix += 1
    report_dir.mkdir(parents=True)

    (report_dir / "report.md").write_text(report_md, encoding="utf-8")
    (report_dir / "bugs.json").write_text(
        json.dumps(bugs, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    meta = {
        "run_id": run_id,
        "llm_model": model,
        "created_at": datetime.now().isoformat(),
    }
    (report_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report_id


def _read_report_files(report_id: str) -> dict | None:
    """读取单份报告，不存在则返回 None"""
    report_dir = REPORTS_DIR / report_id
    if not report_dir.exists():
        return None
    try:
        meta = json.loads((report_dir / "meta.json").read_text(encoding="utf-8"))
        report_md = (report_dir / "report.md").read_text(encoding="utf-8")
        bugs = json.loads((report_dir / "bugs.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    return {
        "id": report_id,
        "run_id": meta.get("run_id", 0),
        "report_md": report_md,
        "bugs": bugs,
        "llm_model": meta.get("llm_model", ""),
        "created_at": meta.get("created_at", ""),
    }


def _list_all_reports() -> list[dict]:
    """列出所有已保存的报告（按时间倒序）"""
    _ensure_reports_dir()
    items = []
    for d in REPORTS_DIR.iterdir():
        if not d.is_dir():
            continue
        data = _read_report_files(d.name)
        if data:
            items.append(data)
    items.sort(key=lambda x: x["created_at"], reverse=True)
    return items


def _delete_report_dir(report_id: str) -> bool:
    """删除报告目录，成功返回 True"""
    import shutil
    report_dir = REPORTS_DIR / report_id
    if not report_dir.exists():
        return False
    shutil.rmtree(report_dir)
    return True

# ── 第一步：分析报告 ──────────────────────────────────────────────

ANALYZE_PROMPT = """你是一个资深测试工程师。请分析以下测试运行数据，生成一份 Markdown 格式的分析报告。

报告要求包含以下章节：
## 总体概况
简要总结本次运行的整体情况（总数、通过率、失败数等）。
## 失败分析
对失败用例进行分类归纳，分析可能的根因和关联关系。如无失败则说明全部通过。
## 性能分析
点评耗时最长的用例，给出性能优化建议。
## 风险评估
评估当前版本的质量风险等级（高/中/低），说明理由。
## 建议与结论
给出后续行动建议，包括优先修复项和回归测试建议。

请直接输出 Markdown 内容，不要包裹在代码块中。

## 测试运行数据

"""

# ── 第二步：从报告生成 Bug ──────────────────────────────────────────

GENERATE_BUGS_PROMPT = """你是一个资深测试工程师。请根据以下测试分析报告，为每个需要提交 Bug 的失败问题生成 Bug 单。

## 规则
- 只为确实有 Bug 的失败用例生成，不要为正常行为或环境问题生成
- 严重程度：P0（核心流程/阻塞性）、P1（重要功能）、P2（次要功能/体验问题）
- 如果报告指出无失败或无需提交 Bug，返回空数组 []

## 输出格式（严格 JSON 数组）

```json
[
  {
    "title": "Bug 标题（简明扼要描述问题现象）",
    "severity": "P0/P1/P2",
    "module": "所属模块",
    "steps": ["复现步骤1", "复现步骤2"],
    "expected": "期望结果",
    "actual": "实际结果",
    "error_detail": "错误详情（如报告中有）"
  }
]
```

## 测试分析报告

"""


class BugItem(BaseModel):
    title: str
    severity: str = "P1"
    module: str = ""
    steps: list[str] = []
    expected: str = ""
    actual: str = ""
    error_detail: str = ""


class AnalysisRequest(BaseModel):
    run_id: int


class GenerateBugsRequest(BaseModel):
    report_md: str


# ── 辅助函数 ─────────────────────────────────────────────────────

def _strip_codeblock(content: str) -> str:
    """去除 markdown 代码块包裹"""
    content = content.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()
    return content


async def _call_llm(llm, system: str, user: str, max_tokens: int = 4000) -> str:
    """调用 LLM，返回原始文本"""
    async with httpx.AsyncClient(timeout=120) as client:
        url = f"{llm.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {llm.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": llm.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.3,
            "max_tokens": max_tokens,
        }
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    return data["choices"][0]["message"]["content"]


def _build_run_summary(run: TestRun, results: list) -> str:
    """构造运行摘要文本"""
    failed = [r for r in results if r.status in ("failed", "error")]
    lines = [f"运行 #{run.id}，共 {run.total} 条用例，通过 {run.passed} 条，失败 {run.failed} 条，跳过 {run.skipped} 条。\n"]
    if failed:
        lines.append("=== 失败用例 ===")
        for r in failed:
            lines.append(f"失败用例: {r.suite_name} / {r.case_name}")
            if r.error_message:
                lines.append(f"错误信息: {r.error_message[:500]}")
            if r.stack_trace:
                lines.append(f"堆栈: {r.stack_trace[:300]}")
            lines.append("")
    else:
        lines.append("本次运行全部通过，无失败用例。")

    sorted_by_duration = sorted(results, key=lambda r: r.duration_ms, reverse=True)[:5]
    lines.append("\n=== 最慢用例 Top 5 ===")
    for r in sorted_by_duration:
        lines.append(f"{r.suite_name}/{r.case_name}: {r.duration_ms}ms")
    return "\n".join(lines)


# ── 端点：第一步 分析报告 ─────────────────────────────────────────

@router.post("/ai/analyze", response_model=ApiResponse)
async def analyze_report(body: AnalysisRequest, db: AsyncSession = Depends(get_async_session)):
    """调用 LLM 分析测试运行，返回 Markdown 分析报告"""
    llm_result = await db.execute(select(LLMConfig).where(LLMConfig.is_active == 1))
    llm = llm_result.scalar_one_or_none()
    if not llm:
        return ApiResponse(success=False, error="未配置激活的 LLM，请先在设置中添加并激活 LLM 配置")

    run = await db.get(TestRun, body.run_id)
    if not run:
        return ApiResponse(success=False, error="运行记录不存在")

    result = await db.execute(
        select(TestResult).where(TestResult.run_id == body.run_id).order_by(TestResult.id)
    )
    results = result.scalars().all()
    summary = _build_run_summary(run, results)

    try:
        content = await _call_llm(
            llm,
            system="你是一个测试分析专家。请直接输出 Markdown 格式的分析报告，不要包裹在代码块中。",
            user=ANALYZE_PROMPT + summary,
            max_tokens=4000,
        )
        # 去除可能的代码块包裹
        report_md = content.strip()
        if report_md.startswith("```markdown"):
            report_md = report_md[11:]
            report_md = report_md.rsplit("```", 1)[0].strip()
        elif report_md.startswith("```"):
            report_md = report_md[3:]
            report_md = report_md.rsplit("```", 1)[0].strip()

        return ApiResponse(data={"report": report_md, "run_id": body.run_id})

    except httpx.HTTPStatusError as e:
        return ApiResponse(success=False, error=f"LLM API 请求失败: {e.response.status_code} - {e.response.text[:200]}")
    except Exception as e:
        return ApiResponse(success=False, error=f"分析失败: {str(e)}")


# ── 端点：第二步 从报告生成 Bug ───────────────────────────────────

@router.post("/ai/generate-bugs", response_model=ApiResponse)
async def generate_bugs(body: GenerateBugsRequest, db: AsyncSession = Depends(get_async_session)):
    """根据分析报告，调用 LLM 生成 Bug 列表"""
    llm_result = await db.execute(select(LLMConfig).where(LLMConfig.is_active == 1))
    llm = llm_result.scalar_one_or_none()
    if not llm:
        return ApiResponse(success=False, error="未配置激活的 LLM，请先在设置中添加并激活 LLM 配置")

    if not body.report_md.strip():
        return ApiResponse(success=False, error="报告内容为空")

    try:
        content = await _call_llm(
            llm,
            system="你是一个测试分析专家。请严格按照 JSON 数组格式返回 Bug 列表，不要包含其他文字。",
            user=GENERATE_BUGS_PROMPT + body.report_md,
            max_tokens=4000,
        )
        parsed = json.loads(_strip_codeblock(content))
        bugs = parsed if isinstance(parsed, list) else parsed.get("bugs", [])
        return ApiResponse(data={"bugs": bugs})

    except httpx.HTTPStatusError as e:
        return ApiResponse(success=False, error=f"LLM API 请求失败: {e.response.status_code} - {e.response.text[:200]}")
    except json.JSONDecodeError:
        return ApiResponse(success=False, error=f"LLM 返回格式异常，无法解析 JSON: {content[:200]}")
    except Exception as e:
        return ApiResponse(success=False, error=f"生成 Bug 失败: {str(e)}")


# ── 端点：上传报告文件 ────────────────────────────────────────────

@router.post("/ai/upload-report", response_model=ApiResponse)
async def upload_report(file: UploadFile = File(...)):
    """上传之前下载的 AI 分析报告 JSON 文件，恢复报告+Bug 数据"""
    try:
        raw = await file.read()
        data = json.loads(raw.decode("utf-8"))
        report_md = data.get("report", "")
        bugs = data.get("bugs", [])
        run_id = data.get("run_id", None)
        return ApiResponse(data={"report": report_md, "bugs": bugs, "run_id": run_id})
    except json.JSONDecodeError:
        return ApiResponse(success=False, error="文件格式错误，不是有效的 JSON 报告文件")
    except Exception as e:
        return ApiResponse(success=False, error=f"上传失败: {str(e)}")


# ── 端点：保存到文件 ──────────────────────────────────────────────

class SaveReportRequest(BaseModel):
    run_id: int
    report_md: str
    bugs: list[BugItem]


@router.post("/ai/save-report", response_model=ApiResponse)
async def save_report(body: SaveReportRequest):
    """保存 AI 分析报告到文件"""
    # 获取当前激活的 LLM 模型名称（可选，失败不影响保存）
    model_name = ""
    try:
        from backend.db.config import async_session
        async with async_session() as db:
            llm_result = await db.execute(select(LLMConfig).where(LLMConfig.is_active == 1))
            llm = llm_result.scalar_one_or_none()
            model_name = llm.model if llm else ""
    except Exception:
        pass

    bugs_data = [b.model_dump() for b in body.bugs]
    report_id = _write_report_files(body.run_id, body.report_md, bugs_data, model_name)
    return ApiResponse(data={"id": report_id, "message": "报告已保存"})


# ── 端点：历史报告 CRUD ──────────────────────────────────────────

@router.get("/ai/reports", response_model=ApiResponse)
async def list_reports():
    """获取所有已保存的 AI 分析报告"""
    items = []
    for data in _list_all_reports():
        items.append({
            "id": data["id"],
            "run_id": data["run_id"],
            "run_status": "",
            "run_total": 0,
            "run_passed": 0,
            "run_failed": 0,
            "report_md": data["report_md"],
            "bugs": data["bugs"],
            "llm_model": data["llm_model"],
            "created_at": data["created_at"],
        })
    return ApiResponse(data=items)


@router.get("/ai/reports/{report_id}", response_model=ApiResponse)
async def get_report(report_id: str):
    """获取单份 AI 分析报告"""
    data = _read_report_files(report_id)
    if not data:
        return ApiResponse(success=False, error="报告不存在")
    return ApiResponse(data={
        "id": data["id"],
        "run_id": data["run_id"],
        "run_status": "",
        "run_total": 0,
        "run_passed": 0,
        "run_failed": 0,
        "report_md": data["report_md"],
        "bugs": data["bugs"],
        "llm_model": data["llm_model"],
        "created_at": data["created_at"],
    })


@router.delete("/ai/reports/{report_id}", response_model=ApiResponse)
async def delete_report(report_id: str):
    """删除已保存的 AI 分析报告"""
    if not _delete_report_dir(report_id):
        return ApiResponse(success=False, error="报告不存在")
    return ApiResponse(data={"message": "已删除"})


# ── 端点：推送 Bug 到禅道 ────────────────────────────────────────

class PushZentaoRequest(BaseModel):
    bugs: list[BugItem]


@router.post("/ai/push-zentao", response_model=ApiResponse)
async def push_to_zentao(body: PushZentaoRequest, db: AsyncSession = Depends(get_async_session)):
    """推送 Bug 到禅道"""
    zt_result = await db.execute(select(ZentaoConfig).where(ZentaoConfig.is_active == 1))
    zt = zt_result.scalar_one_or_none()
    if not zt:
        return ApiResponse(success=False, error="未配置激活的禅道，请先在设置中添加并激活禅道配置")

    base = zt.base_url.rstrip("/")

    async with httpx.AsyncClient(timeout=30) as client:
        # 先用账号密码获取 Token
        try:
            token_resp = await client.post(
                f"{base}/api.php/v1/tokens",
                json={"account": zt.username, "password": zt.password},
            )
            token_resp.raise_for_status()
            token = token_resp.json().get("token", "")
            if not token:
                return ApiResponse(success=False, error="禅道登录失败，未获取到 Token，请检查账号密码")
        except Exception as e:
            return ApiResponse(success=False, error=f"禅道登录失败: {str(e)[:200]}")

        headers = {"Token": token, "Content-Type": "application/json"}
        pushed = 0
        errors = []

        for bug in body.bugs:
            try:
                severity_map = {"P0": 1, "P1": 2, "P2": 3, "P3": 4}
                zt_severity = severity_map.get(bug.severity, 3)

                steps_html = "<p>[步骤]</p>"
                for i, s in enumerate(bug.steps, 1):
                    steps_html += f"<p>{i}. {s}</p>"
                steps_html += f"<p></p><p>[结果]</p><p>{bug.actual}</p>"
                steps_html += f"<p></p><p>[期望]</p><p>{bug.expected}</p>"

                zentao_bug = {
                    "product": zt.product_id,
                    "title": bug.title,
                    "severity": zt_severity,
                    "pri": zt_severity,
                    "type": "codeerror",
                    "steps": steps_html,
                    "openedBuild": ["trunk"],
                }
                resp = await client.post(f"{base}/api.php/v1/bugs", json=zentao_bug, headers=headers)
                resp.raise_for_status()
                pushed += 1
            except Exception as e:
                errors.append(f"{bug.title}: {str(e)[:100]}")

    return ApiResponse(data={"pushed": pushed, "errors": errors})
