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
MAX_SYNC_TURNS="${MAX_SYNC_TURNS:-30}"

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


listing_files = []
for t in sorted(set(targets)):
    p = os.path.join(repo, t)
    if os.path.isdir(p):
        for root, dirs, files in os.walk(p):
            dirs.sort()
            for f in sorted(files):
                fp = os.path.join(root, f)
                rel = os.path.relpath(fp, repo).replace('\\', '/')
                listing.append('%s  (%d 行)' % (rel, count_lines(fp)))
                listing_files.append(rel)
    elif os.path.isfile(p):
        listing.append('%s  (%d 行)' % (t, count_lines(p)))
        listing_files.append(t)
if len(listing) > 120:
    listing = listing[:120] + ['... (更多文件已省略，需要时用 Read 按目录读取)']
target_files = '\n'.join(listing) or '(无既有目标文件，需新建)'

# 既有用例名提纲：模型不必再用 grep/ls 逐个头文件里找"这个行为有没有测过"
name_re = re.compile(
    r'^\s*(?:def\s+(test_\w+)|(?:test|it|describe)\s*\(\s*["\'`]([^"\'`]{1,80})["\'`])')
OUTLINE_TOTAL = 20000
outline, outline_chars = [], 0
for rel in listing_files:
    names = []
    try:
        with open(os.path.join(repo, rel), encoding='utf-8', errors='replace') as fh:
            for line in fh:
                m = name_re.match(line)
                if m:
                    names.append(m.group(1) or m.group(2))
                if len(names) >= 8:
                    break
    except Exception:
        continue
    if not names:
        continue
    entry = '%s: %s' % (rel, ' | '.join(names))
    if outline_chars + len(entry) > OUTLINE_TOTAL:
        outline.append('... (更多用例名已省略)')
        break
    outline.append(entry)
    outline_chars += len(entry) + 1
test_outline = '\n'.join(outline) or '(无既有用例名)'

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
text = text.replace('{{TEST_OUTLINE}}', test_outline)
open(dst, 'w', encoding='utf-8').write(text)
print('[sync] 提示词 %d 字节（diff %d，目标清单 %d 项）' % (len(text), len(diff), len(listing)))
PY

# 统一的大模型调用入口：提示词走 stdin（可能超 128KB 单参数上限），用量只进日志/产物
# 禁止加载任何 Skill：仓库里的技能多为本地交互式（AskUserQuestion / git pull / Playwright MCP / 实跑环境），
# 在容器里会卡住或写白名单外路径；规则已全部渲染在提示词内。
# --strict-mcp-config 防止仓库 .mcp.json 里的 Playwright MCP 在无桌面容器里启动。
run_ai() {
  _prompt=$1; _out=$2; _turns=$3; _budget=$4; _timeout=$5
  # 记住调用方的 errexit：内部要临时关掉，返回前必须恢复，否则调用方捕获不到失败
  case $- in *e*) _was_e=1 ;; *) _was_e=0 ;; esac
  set +e
  cd "$TEST_REPO"
  timeout "$_timeout" claude -p \
    --add-dir "$FENIX_REPO" \
    --dangerously-skip-permissions \
    --disallowedTools Skill Bash Task \
    --strict-mcp-config \
    --setting-sources local \
    --max-turns "$_turns" \
    --max-budget-usd "$_budget" \
    --output-format stream-json --verbose \
    < "$_prompt" > "$_out" 2>&1
  _rc=$?
  python - "$_out" <<'PY' || true
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
  if [ "$_was_e" -eq 1 ]; then set -e; fi
  return $_rc
}

log ">>> 调用 Claude Code（max-turns=$MAX_SYNC_TURNS）..."
set +e
run_ai "$ARTIFACT_DIR/prompt.txt" "$ARTIFACT_DIR/claude.jsonl" "$MAX_SYNC_TURNS" 3 2700
AI_EXIT=$?
set -e
log ">>> Claude Code 退出码: $AI_EXIT"
if [ "$AI_EXIT" -ne 0 ]; then
  echo "[sync] Claude Code 执行失败，尾部日志："
  tail -40 "$ARTIFACT_DIR/claude.jsonl" || true
  exit 13
fi

# AI 只允许改 AgentTest 工作副本，不许碰被测源码
check_dirty=$(git -C "$FENIX_REPO" status --porcelain || true)
[ -z "$check_dirty" ] || fail_fenix_dirty

# 4~6. 策略校验 → 校验 → 独立复核；任一失败时带报错自动修复一次（SYNC_RETRY_LIMIT）
ATTEMPT=0
RETRY_LIMIT="${SYNC_RETRY_LIMIT:-1}"
WS_INSTALLED=0
UT_INSTALLED=0
CHECK_LOG=""
FAIL_LOG=""

read_changes() {
  UNIT_FILES=$(python -c "import json,sys;print('\n'.join(json.load(open(sys.argv[1],encoding='utf-8'))['unit']))" "$ARTIFACT_DIR/changes.json")
  PY_FILES=$(python -c "import json,sys;print('\n'.join(json.load(open(sys.argv[1],encoding='utf-8'))['python']))" "$ARTIFACT_DIR/changes.json")
}

# 校验输出同时落盘：失败时作为自动修复的输入
run_checks() {
  CHECK_LOG="$ARTIFACT_DIR/checks-$ATTEMPT.log"
  FAIL_LOG="$ARTIFACT_DIR/checks-fail.log"
  : > "$CHECK_LOG"
  : > "$FAIL_LOG"
  read_changes

if [ -n "$PY_FILES" ]; then
  log ">>> pytest --collect-only..."
  PY_FAIL=0
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    # 退出码 5 = 没收集到用例（Page Object / client 等非测试文件），不算失败
    set +e
    python -X utf8 -m pytest --collect-only -q "$f" >> "$CHECK_LOG" 2>&1
    rc=$?
    set -e
    [ "$rc" -eq 0 ] || [ "$rc" -eq 5 ] || PY_FAIL=1
  done <<EOF
$PY_FILES
EOF
  if [ "$PY_FAIL" -ne 0 ]; then
    echo "[sync] pytest 收集失败"
    tail -n 40 "$CHECK_LOG" >> "$FAIL_LOG" || true
    tail -n 40 "$CHECK_LOG" || true
    return 1
  fi
fi

if [ -n "$UNIT_FILES" ]; then
  # 单测 import 的被测源码需要 FenixAgent 根依赖；node_modules 由 .gitignore 屏蔽，不会污染只读校验
  if [ "$WS_INSTALLED" -eq 0 ]; then
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
    WS_INSTALLED=1
  fi

  if [ "$UT_INSTALLED" -eq 0 ]; then
    log ">>> 安装 unit_tests 依赖（bun install）..."
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
    UT_INSTALLED=1
  fi

  log ">>> bun test..."
  UNIT_FAIL=0
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    rel=${f#"$TEST_REPO"/}
    rel=${rel#unit_tests/}
    set +e
    bun test "./$rel" > "$CHECK_LOG.part" 2>&1
    rc=$?
    set -e
    cat "$CHECK_LOG.part" >> "$CHECK_LOG"
    cat "$CHECK_LOG.part"
    if [ "$rc" -ne 0 ]; then
      UNIT_FAIL=1
      # 只留失败文件的输出，避免重试提示词被大量通过用例挤掉
      printf '\n### %s\n' "$rel" >> "$FAIL_LOG"
      tail -n 80 "$CHECK_LOG.part" >> "$FAIL_LOG"
    fi
  done <<EOF
$UNIT_FILES
EOF
  cd "$TEST_REPO"
  if [ "$UNIT_FAIL" -ne 0 ]; then
    echo "[sync] 单测失败"
    return 1
  fi

  check_dirty=$(git -C "$FENIX_REPO" status --porcelain || true)
  [ -z "$check_dirty" ] || fail_fenix_dirty
fi
  return 0
}

# 独立复核（Maker/Checker 分离）：0=APPROVE，1=REJECT，2=执行失败
run_review() {
# 记住调用方的 errexit：内部要临时关掉，返回前必须恢复，否则调用方捕获不到 REJECT
case $- in *e*) _re_e=1 ;; *) _re_e=0 ;; esac
set +e
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

BASELINE_SHA=$(python -X utf8 -c "import json,sys;print(json.load(open(sys.argv[1],encoding='utf-8')).get('main_sha',''))" "$TEST_REPO/sync/baseline.json" 2>/dev/null || echo "")

{
  printf '你是独立的 sync-reviewer（Checker），与生成补丁的 Maker 分离。严格按下面的检查项审查本轮改动（本次对齐 HEAD_SHA=%s）。改动内容已完整附在最后，只审查这些改动，禁止浏览测试仓库其他文件、禁止执行 git 命令、禁止修改任何文件；仅当核对 E2E 选择器依据时，可 Read fenix-source 中对应的组件源码。全部检查项通过则输出 APPROVE，否则输出 REJECT 并逐条说明。最后一行只输出一个词：APPROVE 或 REJECT。\n\n' "$HEAD_SHA"
  printf '基线状态：sync/baseline.json 的 main_sha = %s；本轮 HEAD_SHA = %s。若两者相等，说明基线已对齐，本轮不需要改动 baseline.json，不得以“未改动 baseline”为由 REJECT。\n\n' "${BASELINE_SHA:-未知}" "$HEAD_SHA"
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
if [ "$REVIEW_EXIT" -ne 0 ]; then
  echo "[sync] 复核执行失败，尾部日志："
  tail -40 "$ARTIFACT_DIR/review.json" || true
  if [ "$_re_e" -eq 1 ]; then set -e; fi
  return 2
fi
VERDICT=$(python - "$ARTIFACT_DIR/review.json" "$ARTIFACT_DIR/review-result.txt" <<'PY'
import json, sys
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
# 复核全文供自动修复使用
open(sys.argv[2], 'w', encoding='utf-8').write(r)
parts = r.split()
print(parts[-1] if parts else '')
PY
) || VERDICT=""
case "$VERDICT" in
  APPROVE*) log ">>> 复核通过"; _verdict_rc=0 ;;
  *) echo "[sync] 复核未通过: $VERDICT"; _verdict_rc=1 ;;
esac
if [ "$_re_e" -eq 1 ]; then set -e; fi
return $_verdict_rc
}

# 把失败详情回喂给生成器，只修最小范围；已改文件在 /repo 里可直接 Read
build_fix_prompt() {
  python - "$TEST_REPO" "$ARTIFACT_DIR" "$1" "$2" <<'PY'
import json, os, sys
repo, art, kind, detail_path = sys.argv[1:5]
changed = json.load(open(os.path.join(art, 'changes.json'), encoding='utf-8')).get('files') or []
detail = open(detail_path, encoding='utf-8', errors='replace').read() if os.path.exists(detail_path) else ''
if kind == 'checks':
    if len(detail) > 14000:
        detail = '... (前部已截断)\n' + detail[-14000:]
    header = '上一轮改动没有通过自动化校验。下面是校验输出，请只修正这些失败。'
else:
    if len(detail) > 14000:
        detail = detail[:14000] + '\n... (已截断)'
    header = '独立复核（sync-reviewer）判定 REJECT。下面是复核意见，请只修正被指出的问题。'

prompt = """# 任务：修复上一轮测试同步补丁

%s

上一轮你已经修改了下面这些文件（位于 /repo，当前内容已包含你的改动）：
%s

被测源码只读挂载在 /workspace，仓库内的 fenix-source 也可见。可用工具：Read / Glob / Grep / Write / Edit（Bash 已禁用）。

## 失败详情
%s

## 硬约束（违反即整轮作废）
- 只能写：unit_tests/、tests/api_suites/、tests/api_clients/、tests/api_contracts/、tests/suites/、tests/pages/、tests/fixtures/、docs/手工用例/、sync/baseline.json
- 只做最小修正：不要重写已通过的部分，不要新增无关文件，不要删除有依据的既有断言
- 禁止恒真断言；异常用例必须同时断言 status_code 与 error.code；skip 只能放在用例开头
- 写操作必须自建数据并 try/finally 清理，禁止修改或删除已存在数据
- 单测断言必须是具体值，内联副本必须与当前源码逐段一致
- 不要运行 bun/pytest（由流水线执行）；不要 commit/push
直接修改文件，不要输出计划。
""" % (header, '\n'.join('- ' + f for f in changed) or '(无)', detail)
open(os.path.join(art, 'fix-prompt.txt'), 'w', encoding='utf-8').write(prompt)
print('[sync] 修复提示词 %d 字节（kind=%s，改动文件 %d）' % (len(prompt), kind, len(changed)))
PY
}

while :; do
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
  if ! run_checks; then
    if [ "$ATTEMPT" -ge "$RETRY_LIMIT" ]; then
      echo "[sync] 校验失败，自动修复次数已用尽"
      exit 12
    fi
    ATTEMPT=$((ATTEMPT + 1))
    log ">>> 校验未通过，第 $ATTEMPT 次自动修复（上限 $RETRY_LIMIT）..."
    # 失败输出为空时退回完整日志尾部，保证重试拿到上下文
    [ -s "$FAIL_LOG" ] || tail -n 200 "$CHECK_LOG" > "$FAIL_LOG" || true
    build_fix_prompt checks "$FAIL_LOG"
    set +e
    run_ai "$ARTIFACT_DIR/fix-prompt.txt" "$ARTIFACT_DIR/claude-fix-$ATTEMPT.jsonl" 12 1.5 1800
    FIX_EXIT=$?
    set -e
    if [ "$FIX_EXIT" -ne 0 ]; then
      echo "[sync] 自动修复执行失败，尾部日志："
      tail -40 "$ARTIFACT_DIR/claude-fix-$ATTEMPT.jsonl" || true
      exit 13
    fi
    check_dirty=$(git -C "$FENIX_REPO" status --porcelain || true)
    [ -z "$check_dirty" ] || fail_fenix_dirty
    continue
  fi

  # 6. 独立复核（Maker/Checker 分离）
  set +e
  run_review
  REVIEW_RC=$?
  set -e
  case "$REVIEW_RC" in
    0) break ;;
    2) exit 15 ;;
    *)
      if [ "$ATTEMPT" -ge "$RETRY_LIMIT" ]; then
        echo "[sync] 复核未通过，自动修复次数已用尽"
        exit 15
      fi
      ATTEMPT=$((ATTEMPT + 1))
      log ">>> 复核未通过，第 $ATTEMPT 次自动修复（上限 $RETRY_LIMIT）..."
      build_fix_prompt review "$ARTIFACT_DIR/review-result.txt"
      set +e
      run_ai "$ARTIFACT_DIR/fix-prompt.txt" "$ARTIFACT_DIR/claude-fix-$ATTEMPT.jsonl" 12 1.5 1800
      FIX_EXIT=$?
      set -e
      if [ "$FIX_EXIT" -ne 0 ]; then
        echo "[sync] 自动修复执行失败，尾部日志："
        tail -40 "$ARTIFACT_DIR/claude-fix-$ATTEMPT.jsonl" || true
        exit 13
      fi
      check_dirty=$(git -C "$FENIX_REPO" status --porcelain || true)
      [ -z "$check_dirty" ] || fail_fenix_dirty
      ;;
  esac
done

log ">>> 再跑一次映射校验..."
if ! python -X utf8 "$TEST_REPO/sync/validate_map.py" --quiet; then
  log ">>> 映射校验失败"
  exit 11
fi

git -C "$TEST_REPO" diff --stat > "$ARTIFACT_DIR/diff-stat.txt" || true
log ">>> 同步补丁已就绪（DRY_RUN=${DRY_RUN:-true}）"
cat "$ARTIFACT_DIR/diff-stat.txt" || true
exit 0
