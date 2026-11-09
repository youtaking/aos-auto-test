#!/bin/sh
# main-test-sync 容器入口：计算影响面 → 调用 Claude Code 生成补丁 → 策略校验 → 校验 → 独立复核。
# 不负责 commit / push / 开 MR：那些需要 Jenkins 凭据，由 groovy 完成。
#
# 环境变量：
#   BASE_SHA / HEAD_SHA   必填，FenixAgent 的对比区间
#   TEST_REPO             AgentTest 工作副本（默认 /repo，可写）
#   FENIX_REPO            FenixAgent 源码（默认 /workspace）
#   ARTIFACT_DIR          产物目录（默认 /artifacts）
#   DRY_RUN               true/false，仅用于日志，发布在 groovy 侧
#   MAX_SYNC_TURNS        Claude Code 最大轮次（默认 40）
#
# 退出码：0 有可用补丁 10 影响面为空 11 触碰禁区 12 校验失败 13 AI 失败 14 无改动 15 复核未通过
set -eu

TEST_REPO="${TEST_REPO:-/repo}"
FENIX_REPO="${FENIX_REPO:-/workspace}"
ARTIFACT_DIR="${ARTIFACT_DIR:-/artifacts}"
MAX_SYNC_TURNS="${MAX_SYNC_TURNS:-40}"

log() { echo "[sync] $*"; }

fail_fenix_dirty() {
  echo "[sync] FenixAgent 源码出现改动（只读约束被违反）："
  git -C "$FENIX_REPO" status --porcelain | head -20
  exit 12
}

mkdir -p "$ARTIFACT_DIR"

[ -n "${BASE_SHA:-}" ] || { echo "[sync] BASE_SHA 必填"; exit 2; }
[ -n "${HEAD_SHA:-}" ] || { echo "[sync] HEAD_SHA 必填"; exit 2; }
git -C "$TEST_REPO" rev-parse --git-dir >/dev/null
git -C "$FENIX_REPO" cat-file -e "${HEAD_SHA}^{commit}"

log "test repo:  $TEST_REPO"
log "fenix repo: $FENIX_REPO"
log "range:      $(echo "$BASE_SHA" | cut -c1-8)..$(echo "$HEAD_SHA" | cut -c1-8)"

# 1. 影响面
log ">>> 计算影响面..."
if ! python -X utf8 "$TEST_REPO/sync/validate_map.py" \
  --impact "$BASE_SHA" "$HEAD_SHA" --repo "$FENIX_REPO" \
  --json-out "$ARTIFACT_DIR/impact.json" --quiet; then
  log ">>> 影响面计算失败（coverage-map 与仓库不一致）"
  exit 11
fi

EMPTY=$(python -c "import json,sys;print(json.load(open(sys.argv[1],encoding='utf-8'))['empty'])" "$ARTIFACT_DIR/impact.json")
if [ "$EMPTY" = "True" ]; then
  log ">>> 影响面为空，无需调用 AI"
  exit 10
fi

python - "$ARTIFACT_DIR/impact.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding='utf-8'))
print(f"[sync] 变更 {d['changed']} 个文件：忽略 {len(d['ignored'])}，未映射 {len(d['unmapped'])}，命中规则 {len(d['rules'])}")
print(f"[sync] 自动同步目标：unit {len(d['auto']['unit'])} / api {len(d['auto']['api'])} / e2e {len(d['auto']['e2e'])}")
if d['unmapped']:
    print('[sync] 未映射（人工关注）：')
    for f in d['unmapped']:
        print('   -', f)
if d['manual_rules']:
    print('[sync] 人工规则命中：', ', '.join(d['manual_rules']))
PY

# 2. 准备单测运行布局：unit_tests/tsconfig.json 与 bunfig.toml 依赖 ../fenix-source
ln -sfn "$FENIX_REPO" "$TEST_REPO/fenix-source"

# 3. 调用 Claude Code（密钥仅通过环境注入，不落盘）
[ -n "${ANTHROPIC_AUTH_TOKEN:-}" ] || { echo "[sync] ANTHROPIC_AUTH_TOKEN 未注入"; exit 3; }
unset ANTHROPIC_API_KEY || true

# 一次性把 diff 与目标文件清单渲染进提示词：AI 无需再探索仓库，省掉每轮重复的上下文
python - "$TEST_REPO/sync/prompt.md" "$ARTIFACT_DIR/prompt.txt" \
  "$BASE_SHA" "$HEAD_SHA" "$ARTIFACT_DIR/impact.json" "$FENIX_REPO" "$TEST_REPO" <<'PY'
import json, os, re, subprocess, sys

src, dst, base, head, impact_path, fenix, repo = sys.argv[1:8]
impact = json.load(open(impact_path, encoding='utf-8'))


def git(args, cwd, limit):
    try:
        out = subprocess.run(['git', '-C', cwd] + args, capture_output=True, text=True,
                             encoding='utf-8', errors='replace', timeout=120).stdout
    except Exception:
        return ''
    if limit and len(out) > limit:
        out = out[:limit] + '\n... (已截断，剩余请自行 git diff 该路径)'
    return out


diff_stat = git(['diff', '--stat', base, head], fenix, 20000) or '(无)'

# 只取 auto 规则命中的源码路径，避免把整棵树的 diff 塞进上下文
paths = []
for rule in (impact.get('rules') or {}).values():
    if rule.get('mode') == 'auto':
        paths.extend(rule.get('files') or [])
paths = sorted(set(paths))

# 真实一周 diff 可达 1.8MB，直接整体截断会丢掉大半改动：
# 改为逐文件限额 + 总预算，小文件优先，生成物跳过，遗漏项显式列出（AI 可 Read 源码当前版本）
PER_FILE_CAP = 6000
TOTAL_CAP = 110000
SKIP_GENERATED = re.compile(
    r'(^|/)(bun\.lockb?|package-lock\.json|pnpm-lock\.yaml|yarn\.lock)$'
    r'|(^|/)(dist|build|node_modules)/'
    r'|\.snap$'
    r'|(^|/)drizzle/meta/.*\.json$'
)

if paths:
    # 不把成百上千个路径拼进 argv（Windows 会报参数过长，Linux 也有 ARG_MAX 上限），
    # 取全量改动名后按 auto 命中集合过滤
    auto_files = set(paths)
    files = [f for f in git(['diff', '--name-only', base, head], fenix, 0).splitlines()
             if f.strip() and f in auto_files]
    sized, skipped = [], []
    for f in files:
        if SKIP_GENERATED.search(f):
            skipped.append(f)
            continue
        body = git(['diff', base, head, '--', f], fenix, 0)
        if body:
            sized.append((len(body), f, body))
    sized.sort()  # 小文件优先：信息密度高，避免被生成物/大文件挤掉
    pieces, truncated, omitted, used = [], [], [], 0
    for size, f, body in sized:
        if used >= TOTAL_CAP:
            omitted.append(f)
            continue
        if size > PER_FILE_CAP:
            body = body[:PER_FILE_CAP] + '\n... (此文件 diff 已截断，请用 Read 读取 fenix-source/%s 的当前版本)' % f
            truncated.append(f)
        if used + len(body) > TOTAL_CAP:
            omitted.append(f)
            continue
        pieces.append(body)
        used += len(body)
    diff = '\n'.join(pieces) if pieces else '(无可用 diff)'
    notes = []
    if skipped:
        notes.append('已跳过生成物 %d 个：%s' % (len(skipped), ', '.join(skipped[:20])))
    if truncated:
        notes.append('已截断 %d 个（单文件超 %d 字节）：%s' % (len(truncated), PER_FILE_CAP, ', '.join(truncated[:20])))
    if omitted:
        notes.append('已省略 %d 个（超出总预算）：%s —— 需要时用 Read 读取 fenix-source 中的当前版本'
                     % (len(omitted), ', '.join(omitted[:40])))
    if notes:
        diff += '\n\n### diff 覆盖说明\n' + '\n'.join('- ' + n for n in notes)
else:
    diff = '(影响面未命中源码文件)'

# 目标既有文件清单（带行数），让 AI 一次看清要改哪些文件
targets = []
for kind in ('unit', 'api', 'e2e'):
    targets.extend((impact.get('auto') or {}).get(kind) or [])
listing = []


def count_lines(fp):
    try:
        with open(fp, encoding='utf-8', errors='replace') as fh:
            return sum(1 for _ in fh)
    except Exception:
        return 0


for t in sorted(set(targets)):
    p = os.path.join(repo, t)
    if os.path.isdir(p):
        for root, dirs, files in os.walk(p):
            dirs.sort()
            for f in sorted(files):
                fp = os.path.join(root, f)
                rel = os.path.relpath(fp, repo).replace('\\', '/')
                listing.append('%s  (%d 行)' % (rel, count_lines(fp)))
    elif os.path.isfile(p):
        listing.append('%s  (%d 行)' % (t, count_lines(p)))
if len(listing) > 120:
    listing = listing[:120] + ['... (更多文件已省略，需要时用 Read 按目录读取)']
target_files = '\n'.join(listing) or '(无既有目标文件，需新建)'

# 影响面里的 rules[*].files 与 diff 完全重复（一次 20 提交批次有 73KB），只保留计数；
# auto.* 是允许修改的目标清单，必须完整保留
impact_view = {
    'changed': impact.get('changed'),
    'ignored': len(impact.get('ignored') or []),
    'unmapped': impact.get('unmapped') or [],
    'manual_rules': impact.get('manual_rules') or [],
    'auto': impact.get('auto') or {},
    'rules': {k: {'mode': v.get('mode'),
                  'files': len(v.get('files') or [])}
              for k, v in (impact.get('rules') or {}).items()},
}

text = open(src, encoding='utf-8').read()
text = text.replace('{{BASE_SHA}}', base).replace('{{HEAD_SHA}}', head)
text = text.replace('{{IMPACT_JSON}}', json.dumps(impact_view, ensure_ascii=False, indent=2))
text = text.replace('{{DIFF_STAT}}', diff_stat)
text = text.replace('{{DIFF}}', diff)
text = text.replace('{{TARGET_FILES}}', target_files)
open(dst, 'w', encoding='utf-8').write(text)
print('[sync] 提示词 %d 字节（diff %d，目标清单 %d 项）' % (len(text), len(diff), len(listing)))
PY

log ">>> 调用 Claude Code（max-turns=$MAX_SYNC_TURNS）..."
set +e
cd "$TEST_REPO"
# 提示词含完整 diff，可能超过 Linux 单个参数上限（128KB），统一走 stdin
# 禁止加载任何 Skill：仓库里的技能多为本地交互式（AskUserQuestion / git pull / Playwright MCP / 实跑环境），
# 在容器里会卡住或写白名单外路径；本轮规则已全部渲染在 prompt.txt 内。
# --strict-mcp-config 防止仓库 .mcp.json 里的 Playwright MCP 在无桌面容器里启动。
timeout 2700 claude -p \
  --add-dir "$FENIX_REPO" \
  --dangerously-skip-permissions \
  --disallowedTools Skill \
  --strict-mcp-config \
  --setting-sources local \
  --max-turns "$MAX_SYNC_TURNS" \
  --max-budget-usd 3 \
  --output-format stream-json --verbose \
  < "$ARTIFACT_DIR/prompt.txt" \
  > "$ARTIFACT_DIR/claude.jsonl" 2>&1
AI_EXIT=$?
set -e
# 用量只进日志/产物，不进企微通知
python - "$ARTIFACT_DIR/claude.jsonl" <<'PY' || true
import json, sys
u, cost = None, None
for line in open(sys.argv[1], encoding='utf-8', errors='replace'):
    line = line.strip()
    if not line.startswith('{'):
        continue
    try:
        obj = json.loads(line)
    except Exception:
        continue
    if isinstance(obj, dict):
        u = obj.get('usage') or u
        cost = obj.get('total_cost_usd', cost)
if u:
    print('[sync] 生成用量：输入 %s（缓存命中 %s）/ 输出 %s / 费用 $%s' % (
        u.get('input_tokens'), u.get('cache_read_input_tokens'),
        u.get('output_tokens'), cost))
PY
log ">>> Claude Code 退出码: $AI_EXIT"
if [ "$AI_EXIT" -ne 0 ]; then
  echo "[sync] Claude Code 执行失败，尾部日志："
  tail -40 "$ARTIFACT_DIR/claude.jsonl" || true
  exit 13
fi

# AI 只允许改 AgentTest 工作副本，不许碰被测源码
check_dirty=$(git -C "$FENIX_REPO" status --porcelain || true)
[ -z "$check_dirty" ] || fail_fenix_dirty

# 4. 策略校验（白名单 / 禁区 / 改动数量上限）
log ">>> 校验改动范围..."
if ! python -X utf8 "$TEST_REPO/sync/check_policy.py" \
  --repo "$TEST_REPO" \
  --json-out "$ARTIFACT_DIR/changes.json"; then
  log ">>> 改动触碰禁区或超出允许范围（见上）"
  exit 11
fi

git -C "$TEST_REPO" status --porcelain > "$ARTIFACT_DIR/status.txt" || true

FILE_COUNT=$(python -c "import json,sys;print(len(json.load(open(sys.argv[1],encoding='utf-8'))['files']))" "$ARTIFACT_DIR/changes.json")
log ">>> AI 改动文件数: $FILE_COUNT"
if [ "$FILE_COUNT" -eq 0 ]; then
  log ">>> 无改动，结束"
  exit 14
fi

# 5. 校验：py 收集 + ts 单测
UNIT_FILES=$(python -c "import json,sys;print('\n'.join(json.load(open(sys.argv[1],encoding='utf-8'))['unit']))" "$ARTIFACT_DIR/changes.json")
PY_FILES=$(python -c "import json,sys;print('\n'.join(json.load(open(sys.argv[1],encoding='utf-8'))['python']))" "$ARTIFACT_DIR/changes.json")

if [ -n "$PY_FILES" ]; then
  log ">>> pytest --collect-only..."
  PY_FAIL=0
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    # 退出码 5 = 没收集到用例（Page Object / client 等非测试文件），不算失败
    set +e
    python -X utf8 -m pytest --collect-only -q "$f"
    rc=$?
    set -e
    [ "$rc" -eq 0 ] || [ "$rc" -eq 5 ] || PY_FAIL=1
  done <<EOF
$PY_FILES
EOF
  [ "$PY_FAIL" -eq 0 ] || { echo "[sync] pytest 收集失败"; exit 12; }
fi

if [ -n "$UNIT_FILES" ]; then
  # 单测 import 的被测源码需要 FenixAgent 根依赖；node_modules 由 .gitignore 屏蔽，不会污染只读校验
  log ">>> 安装 FenixAgent 依赖（bun install）..."
  cd "$FENIX_REPO"
  set +e
  bun install --frozen-lockfile >/dev/null 2>&1 || \
    BUN_CONFIG_REGISTRY=https://registry.npmmirror.com bun install --no-save >/dev/null 2>&1 || \
    bun install --no-save >/dev/null 2>&1
  WS_INSTALL=$?
  set -e
  [ "$WS_INSTALL" -eq 0 ] || { echo "[sync] FenixAgent 依赖安装失败"; exit 12; }
  # 兜底路径的 bun install 可能改写锁文件，恢复后只读校验才不会被误判
  git -C "$FENIX_REPO" checkout -- bun.lock bun.lockb 2>/dev/null || true

  log ">>> bun install + bun test..."
  cd "$TEST_REPO/unit_tests"
  set +e
  bun install --frozen-lockfile >/dev/null 2>&1 || \
    BUN_CONFIG_REGISTRY=https://registry.npmmirror.com bun install >/dev/null 2>&1 || \
    bun install >/dev/null 2>&1
  INSTALL_EXIT=$?
  set -e
  # bun install 可能改写锁文件，恢复仓库状态
  git -C "$TEST_REPO" checkout -- unit_tests/bun.lock 2>/dev/null || true
  git -C "$TEST_REPO" checkout -- unit_tests/bun.lockb 2>/dev/null || true
  [ "$INSTALL_EXIT" -eq 0 ] || { echo "[sync] unit_tests bun install 失败"; exit 12; }

  UNIT_FAIL=0
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    rel=${f#"$TEST_REPO"/}
    rel=${rel#unit_tests/}
    bun test "./$rel" || UNIT_FAIL=1
  done <<EOF
$UNIT_FILES
EOF
  cd "$TEST_REPO"
  [ "$UNIT_FAIL" -eq 0 ] || { echo "[sync] 单测失败"; exit 12; }

  check_dirty=$(git -C "$FENIX_REPO" status --porcelain || true)
  [ -z "$check_dirty" ] || fail_fenix_dirty
fi

# 6. 独立复核（Maker/Checker 分离）
log ">>> 独立复核（sync-reviewer）..."
if [ -f "$TEST_REPO/sync/reviewer.md" ]; then
  REVIEW_SPEC=$(cat "$TEST_REPO/sync/reviewer.md")
else
  REVIEW_SPEC="检查范围是否落在白名单、有无恒真断言、异常断言是否完整、skip 是否只在用例开头、写操作是否自建自清、单测是否覆盖五类、API 四类产物是否一致、E2E 选择器是否有源码依据、baseline 是否已更新。"
fi
cd "$TEST_REPO"

# 复核只喂改动本身（已跟踪文件的 diff + 新增文件全文），不探索仓库
python - "$TEST_REPO" "$ARTIFACT_DIR/review-diff.txt" <<'PY'
import os, subprocess, sys

repo, dst = sys.argv[1:3]


def run(args):
    return subprocess.run(['git', '-C', repo] + args, capture_output=True, text=True,
                          encoding='utf-8', errors='replace').stdout


parts = ['### 已跟踪文件改动（git diff HEAD）', run(['diff', '--stat', 'HEAD']), run(['diff', 'HEAD'])]
parts.append('### 新增文件全文')
for rel in run(['ls-files', '--others', '--exclude-standard']).splitlines():
    fp = os.path.join(repo, rel)
    if not os.path.isfile(fp):
        continue
    try:
        if os.path.getsize(fp) > 400000:
            parts.append('--- b/%s (过大，省略)' % rel)
            continue
        body = open(fp, encoding='utf-8', errors='replace').read()
    except Exception:
        continue
    parts.append('--- /dev/null\n+++ b/%s\n%s' % (rel, body))

text = '\n'.join(parts)
if len(text) > 120000:
    text = text[:120000] + '\n... (改动全文已截断，未展示的改动可 Read 对应文件)'
open(dst, 'w', encoding='utf-8').write(text)
print('[sync] 复核材料 %d 字节' % len(text))
PY

{
  printf '你是独立的 sync-reviewer（Checker），与生成补丁的 Maker 分离。严格按下面的检查项审查本轮改动（本次对齐 HEAD_SHA=%s）。改动内容已完整附在最后，只审查这些改动，禁止浏览测试仓库其他文件、禁止执行 git 命令、禁止修改任何文件；仅当核对 E2E 选择器依据时，可 Read fenix-source 中对应的组件源码。全部检查项通过则输出 APPROVE，否则输出 REJECT 并逐条说明。最后一行只输出一个词：APPROVE 或 REJECT。\n\n' "$HEAD_SHA"
  printf '%s\n\n' "$REVIEW_SPEC"
  cat "$ARTIFACT_DIR/review-diff.txt"
} > "$ARTIFACT_DIR/review-prompt.txt"

set +e
timeout 600 claude -p \
  --add-dir "$FENIX_REPO" \
  --dangerously-skip-permissions \
  --disallowedTools Skill \
  --strict-mcp-config \
  --setting-sources local \
  --max-turns 6 \
  --max-budget-usd 1 \
  --output-format json \
  < "$ARTIFACT_DIR/review-prompt.txt" \
  > "$ARTIFACT_DIR/review.json" 2> "$ARTIFACT_DIR/review.stderr.txt"
REVIEW_EXIT=$?
set -e
if [ "$REVIEW_EXIT" -ne 0 ]; then
  echo "[sync] 复核执行失败，尾部日志："
  tail -40 "$ARTIFACT_DIR/review.json" || true
  exit 15
fi
VERDICT=$(python -c "
import json,sys
r = ''
# 输出里可能夹带 CLI 告警行，逐行找可解析且带 result 的对象
for line in open(sys.argv[1], encoding='utf-8', errors='replace'):
    line = line.strip()
    if not line.startswith('{'):
        continue
    try:
        obj = json.loads(line)
    except Exception:
        continue
    if isinstance(obj, dict) and 'result' in obj:
        r = obj.get('result') or ''
parts = r.split()
print(parts[-1] if parts else '')
" "$ARTIFACT_DIR/review.json" 2>/dev/null || echo "")
case "$VERDICT" in
  APPROVE*) log ">>> 复核通过" ;;
  *) echo "[sync] 复核未通过: $VERDICT"; exit 15 ;;
esac

log ">>> 再跑一次映射校验..."
if ! python -X utf8 "$TEST_REPO/sync/validate_map.py" --quiet; then
  log ">>> 映射校验失败"
  exit 11
fi

git -C "$TEST_REPO" diff --stat > "$ARTIFACT_DIR/diff-stat.txt" || true
log ">>> 同步补丁已就绪（DRY_RUN=${DRY_RUN:-true}）"
cat "$ARTIFACT_DIR/diff-stat.txt" || true
exit 0
