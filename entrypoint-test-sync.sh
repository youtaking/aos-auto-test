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
#   MAX_SYNC_TURNS        Claude Code 最大轮次（默认 45）
#
# 退出码：0 有可用补丁 10 影响面为空 11 触碰禁区 12 校验失败 13 AI 失败 14 无改动 15 复核未通过
set -eu

TEST_REPO="${TEST_REPO:-/repo}"
FENIX_REPO="${FENIX_REPO:-/workspace}"
ARTIFACT_DIR="${ARTIFACT_DIR:-/artifacts}"
MAX_SYNC_TURNS="${MAX_SYNC_TURNS:-45}"

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

python - "$TEST_REPO/sync/prompt.md" "$ARTIFACT_DIR/prompt.txt" \
  "$BASE_SHA" "$HEAD_SHA" "$ARTIFACT_DIR/impact.json" <<'PY'
import json, sys
src, dst, base, head, impact_path = sys.argv[1:6]
impact = json.load(open(impact_path, encoding='utf-8'))
text = open(src, encoding='utf-8').read()
text = text.replace('{{BASE_SHA}}', base).replace('{{HEAD_SHA}}', head)
text = text.replace('{{IMPACT_JSON}}', json.dumps(impact, ensure_ascii=False, indent=2))
open(dst, 'w', encoding='utf-8').write(text)
PY

log ">>> 调用 Claude Code（max-turns=$MAX_SYNC_TURNS）..."
set +e
cd "$TEST_REPO"
timeout 2700 claude -p "$(cat "$ARTIFACT_DIR/prompt.txt")" \
  --add-dir "$FENIX_REPO" \
  --dangerously-skip-permissions \
  --max-turns "$MAX_SYNC_TURNS" \
  --output-format stream-json --verbose \
  > "$ARTIFACT_DIR/claude.jsonl" 2>&1
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

# 4. 策略校验（白名单 / 禁区 / 改动数量上限）
log ">>> 校验改动范围..."
python -X utf8 "$TEST_REPO/sync/check_policy.py" \
  --repo "$TEST_REPO" \
  --json-out "$ARTIFACT_DIR/changes.json"

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
    python -X utf8 -m pytest --collect-only -q "$f" || PY_FAIL=1
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
set +e
timeout 900 claude -p "你是独立的 sync-reviewer（Checker），与生成补丁的 Maker 分离。严格按下面的检查项审查当前仓库（$TEST_REPO）未提交的改动（本次对齐 HEAD_SHA=$HEAD_SHA）。只允许只读操作，不要修改任何文件。全部检查项通过则输出 APPROVE，否则输出 REJECT 并逐条说明。最后一行只输出一个词：APPROVE 或 REJECT。

$REVIEW_SPEC" \
  --add-dir "$FENIX_REPO" \
  --dangerously-skip-permissions \
  --max-turns 20 \
  --output-format json \
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
python -X utf8 "$TEST_REPO/sync/validate_map.py" --quiet

git -C "$TEST_REPO" diff --stat > "$ARTIFACT_DIR/diff-stat.txt" || true
log ">>> 同步补丁已就绪（DRY_RUN=${DRY_RUN:-true}）"
cat "$ARTIFACT_DIR/diff-stat.txt" || true
exit 0
