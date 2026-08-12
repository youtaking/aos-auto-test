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
mkdir -p "$WORKSPACE_ROOT/packages"
for pkg_dir in "$FENIX_ROOT/packages"/*/; do
  if [ -f "${pkg_dir}package.json" ]; then
    pkg_name=$(basename "$pkg_dir")
    # 软链到真实包目录（包含 src/、package.json 等），确保 workspace 包源码可正常导入
    ln -sfn "${pkg_dir%/}" "$WORKSPACE_ROOT/packages/$pkg_name"
  fi
done

# 将测试文件放入 workspace（作为 workspace 的一个包）
mkdir -p "$WORKSPACE_ROOT/tests"
cp -r "$TEST_ROOT"/* "$WORKSPACE_ROOT/tests/"
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
  set +e
  bun install --no-save 2>&1 | tail -10
  INSTALL_EXIT=$?
  set -e
  if [ $INSTALL_EXIT -ne 0 ]; then
    echo "    ERROR: bun install failed (exit $INSTALL_EXIT)"
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
