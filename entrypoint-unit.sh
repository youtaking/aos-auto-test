#!/bin/sh
set -e

FENIX_SRC="/app/fenix-source-parent/src"
FENIX_ROOT="/app/fenix-source-parent"
CACHE_DIR="/app/cache"
TEST_ROOT="${TEST_ROOT:-/app/tests}"
# 用 /workspace 模拟 monorepo 根目录，让 bun 正确解析 workspace:* 依赖
WORKSPACE_ROOT="/workspace"

echo "=== Unit Test Runner ==="
echo "    Source: $FENIX_SRC"
echo "    Tests:  $TEST_ROOT"
echo "    Cache:  $CACHE_DIR"
echo "    Workspace: $WORKSPACE_ROOT"

# 1. 搭建 workspace 结构（bun install 必须在 workspace 根目录运行）
echo ">>> Setting up workspace structure..."
mkdir -p "$WORKSPACE_ROOT"
cp "$FENIX_ROOT/package.json" "$WORKSPACE_ROOT/package.json"

# 复制 lockfile（bun.lockb 或 bun.lock）
LOCK_NAME=""
if [ -f "$FENIX_ROOT/bun.lockb" ]; then
  LOCK_NAME="bun.lockb"
elif [ -f "$FENIX_ROOT/bun.lock" ]; then
  LOCK_NAME="bun.lock"
fi
[ -n "$LOCK_NAME" ] && cp "$FENIX_ROOT/$LOCK_NAME" "$WORKSPACE_ROOT/$LOCK_NAME"

# 创建 workspace 包的软链（指向真实包目录，让 bun 能解析 workspace:* 依赖及其源码）
# 注意：bun 对 symlink 解析有时不可靠（尤其在 Docker 跨 volume 时），
# 所以同时预创建 node_modules 条目作为双保险
mkdir -p "$WORKSPACE_ROOT/packages"
for pkg_dir in "$FENIX_ROOT/packages"/*/; do
  if [ -f "${pkg_dir}package.json" ]; then
    pkg_dir_name=$(basename "$pkg_dir")
    # 读取 package.json 中的实际 name（如 @fenix/claude-code 而非 plugin-claude-code）
    pkg_json_name=$(bun -e "console.log(require('${pkg_dir}package.json').name)" 2>/dev/null || echo "")

    # 方式1：复制到 packages/（比 symlink 更可靠，bun 对跨 volume symlink 有兼容性问题）
    cp -r "${pkg_dir%/}" "$WORKSPACE_ROOT/packages/$pkg_dir_name" 2>/dev/null || ln -sfn "${pkg_dir%/}" "$WORKSPACE_ROOT/packages/$pkg_dir_name"

    # 方式2：将所有 workspace 包加到根 package.json 的 dependencies，
    # 强制 bun 安装并 hoist 所有依赖（解决 pino 等包没被 hoist 的问题）
    if [ -n "$pkg_json_name" ] && [ "$pkg_json_name" != "undefined" ]; then
      cd "$WORKSPACE_ROOT"
      bun -e "
const fs = require('fs');
const pkg = JSON.parse(fs.readFileSync('./package.json', 'utf8'));
if (!pkg.dependencies) pkg.dependencies = {};
pkg.dependencies['$pkg_json_name'] = 'workspace:*';
fs.writeFileSync('./package.json', JSON.stringify(pkg, null, 2));
console.log('Added $pkg_json_name to root dependencies');
" || echo "    WARNING: Failed to add $pkg_json_name to root dependencies"
      cd - > /dev/null
    fi
  fi
done

# 将测试文件放入 workspace（作为 workspace 的一个包）
mkdir -p "$WORKSPACE_ROOT/tests"
if [ -d "$TEST_ROOT" ] && [ "$(ls -A "$TEST_ROOT" 2>/dev/null)" ]; then
  cp -r "$TEST_ROOT"/* "$WORKSPACE_ROOT/tests/" 2>/dev/null || true
  echo "    Copied tests from $TEST_ROOT ($(find "$TEST_ROOT" -name '*.test.ts' | wc -l) test files)"
else
  echo "    WARNING: TEST_ROOT=$TEST_ROOT is empty or does not exist!"
fi
# 2. 生成 tsconfig.json（@fenix/* → FenixAgent src/*）
echo ">>> Generating tsconfig.json..."
cat > "$WORKSPACE_ROOT/tests/tsconfig.json" << TSEOF
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ES2022",
    "moduleResolution": "bundler",
    "baseUrl": ".",
    "types": ["bun"],
    "strict": true,
    "paths": {
      "@fenix/sandbox-provider": ["${FENIX_ROOT}/packages/sandbox-provider/src"],
      "@fenix/sandbox-provider/*": ["${FENIX_ROOT}/packages/sandbox-provider/src/*"],
      "@fenix/*": ["${FENIX_SRC}/*"]
    }
  },
  "include": ["**/*.ts"]
}
TSEOF

# 2b. 生成 bunfig.toml（preload setup-globals + setup-mocks，确保 mock.module() 生效）
echo ">>> Generating bunfig.toml..."
cat > "$WORKSPACE_ROOT/tests/bunfig.toml" << BFEOF
[test]
root = "."
preload = ["${FENIX_SRC}/test-utils/setup-globals.ts", "${FENIX_SRC}/test-utils/setup-mocks.ts"]
BFEOF

# 3. 安装依赖（从 workspace 根目录运行，正确解析 workspace:* 依赖）
echo ">>> Installing dependencies..."
NEED_INSTALL=true
CACHE_LOCK_NAME=""
if [ -f "$CACHE_DIR/bun.lockb" ]; then
  CACHE_LOCK_NAME="bun.lockb"
elif [ -f "$CACHE_DIR/bun.lock" ]; then
  CACHE_LOCK_NAME="bun.lock"
fi

if [ -n "$LOCK_NAME" ] && [ -n "$CACHE_LOCK_NAME" ]; then
  if cmp -s "$FENIX_ROOT/$LOCK_NAME" "$CACHE_DIR/$CACHE_LOCK_NAME"; then
    if [ -d "$CACHE_DIR/node_modules" ] && [ "$(ls -A $CACHE_DIR/node_modules 2>/dev/null)" ]; then
      echo "    Lockfile unchanged, using cached node_modules..."
      cp -r "$CACHE_DIR/node_modules" "$WORKSPACE_ROOT/node_modules"
      NEED_INSTALL=false
    fi
  fi
elif [ -z "$LOCK_NAME" ] && [ -d "$CACHE_DIR/node_modules" ] && [ "$(ls -A $CACHE_DIR/node_modules 2>/dev/null)" ]; then
  echo "    No lockfile, using cached node_modules..."
  cp -r "$CACHE_DIR/node_modules" "$WORKSPACE_ROOT/node_modules"
  NEED_INSTALL=false
fi

if [ "$NEED_INSTALL" = "true" ]; then
  echo "    Lockfile changed or no cache, running bun install in workspace root..."
  cd "$WORKSPACE_ROOT"

  # 诊断：列出 workspace 包（显示目录名 + package.json name）
  echo "    Workspace packages:"
  for pkg in "$WORKSPACE_ROOT/packages"/*/; do
    if [ -f "${pkg}package.json" ]; then
      dir_name=$(basename "$pkg")
      json_name=$(bun -e "console.log(require('${pkg}package.json').name || '?')" 2>/dev/null || echo "parse_error")
      is_link=$( [ -L "${pkg%/}" ] && echo "symlink" || echo "copy" )
      echo "      $dir_name → $json_name ($is_link)"
    fi
  done

  # 诊断：显示 root package.json 中的 workspace:* 依赖
  echo "    Root workspace:* deps:"
  bun -e "
const pkg = require('./package.json');
const deps = pkg.dependencies || {};
Object.entries(deps).filter(([k,v]) => v === 'workspace:*').forEach(([k,v]) => console.log('      ' + k + ' -> ' + v));
" 2>/dev/null || echo "      (failed to read)"

  set +e
  bun install --no-save 2>&1 | tail -20
  INSTALL_EXIT=$?
  set -e

  if [ $INSTALL_EXIT -ne 0 ]; then
    echo "    WARNING: bun install with lockfile failed (exit $INSTALL_EXIT)"
    echo "    Retrying without lockfile..."
    rm -f bun.lock bun.lockb
    set +e
    bun install --no-save 2>&1 | tail -20
    INSTALL_EXIT=$?
    set -e
  fi

  if [ $INSTALL_EXIT -ne 0 ]; then
    echo "    ERROR: bun install failed after retry (exit $INSTALL_EXIT)"
    echo "    bun version: $(bun --version)"
    echo "    package.json workspaces: $(bun -e "console.log(JSON.stringify(require('./package.json').workspaces) || 'N/A')" 2>/dev/null || echo "parse failed")"
    echo "    Workspace packages found:"
    ls -la "$WORKSPACE_ROOT/packages/" 2>/dev/null || echo "    (none)"
    exit 1
  fi
  # 更新缓存（供下次使用）
  rm -rf "$CACHE_DIR/node_modules"
  cp -r "$WORKSPACE_ROOT/node_modules" "$CACHE_DIR/node_modules"
  # 保存实际生成的锁文件
  if [ -f "$WORKSPACE_ROOT/bun.lockb" ]; then
    cp "$WORKSPACE_ROOT/bun.lockb" "$CACHE_DIR/bun.lockb"
  elif [ -f "$WORKSPACE_ROOT/bun.lock" ]; then
    cp "$WORKSPACE_ROOT/bun.lock" "$CACHE_DIR/bun.lock"
  fi
  echo "    Dependencies installed and cache updated."
else
  echo "    Dependencies ready (from cache)."
fi

# 4. 软链 node_modules 到源码目录（bun 从 /app/fenix-source-parent/src/ 解析 import 时需要）
if [ ! -e "$FENIX_ROOT/node_modules" ]; then
  ln -s "$WORKSPACE_ROOT/node_modules" "$FENIX_ROOT/node_modules"
  echo "    Symlinked node_modules → $WORKSPACE_ROOT/node_modules"
fi

# 5. 运行测试
echo ">>> Running bun test..."
mkdir -p "$WORKSPACE_ROOT/tests/results"
cd "$WORKSPACE_ROOT/tests"

# bun test --reporter=junit 必须配 --reporter-outfile
set +e
bun test --reporter=junit --reporter-outfile=results/unit-junit.xml
TEST_EXIT=$?
set -e

# 将结果复制回 /app/tests/results（供 Jenkins 读取）
mkdir -p /app/tests/results
cp -f results/unit-junit.xml /app/tests/results/unit-junit.xml 2>/dev/null || true

if [ -s results/unit-junit.xml ]; then
    echo ">>> junit XML written: $(wc -c < results/unit-junit.xml) bytes"
else
    echo "    WARNING: junit XML is empty or missing!"
fi

echo ">>> Test exit code: $TEST_EXIT"
exit $TEST_EXIT
