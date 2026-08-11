#!/bin/sh
set -e

FENIX_SRC="/app/fenix-source-parent/src"
FENIX_ROOT="/app/fenix-source-parent"
CACHE_DIR="/app/cache"

echo "=== Unit Test Runner ==="
echo "    Source: $FENIX_SRC"
echo "    Tests:  /app/tests"
echo "    Cache:  $CACHE_DIR"

# 1. 生成 tsconfig.json（@fenix/* → FenixAgent src/*）
echo ">>> Generating tsconfig.json..."
cat > /app/tests/tsconfig.json << TSEOF
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

# 1b. 生成 bunfig.toml（preload setup-globals + setup-mocks，确保 mock.module() 生效）
echo ">>> Generating bunfig.toml..."
cat > /app/tests/bunfig.toml << BFEOF
[test]
root = "."
preload = ["${FENIX_SRC}/test-utils/setup-globals.ts", "${FENIX_SRC}/test-utils/setup-mocks.ts"]
BFEOF

# 2. 安装依赖（优先使用预装缓存）
echo ">>> Installing dependencies..."
if [ -f "$FENIX_ROOT/package.json" ]; then
  cp "$FENIX_ROOT/package.json" /app/tests/package.json

  # 检查 lockfile 是否与缓存一致（支持 bun.lockb 和 bun.lock 两种格式）
  NEED_INSTALL=true

  # 确定实际使用的锁文件名称
  LOCK_NAME=""
  if [ -f "$FENIX_ROOT/bun.lockb" ]; then
    LOCK_NAME="bun.lockb"
  elif [ -f "$FENIX_ROOT/bun.lock" ]; then
    LOCK_NAME="bun.lock"
  fi

  CACHE_LOCK_NAME=""
  if [ -f "$CACHE_DIR/bun.lockb" ]; then
    CACHE_LOCK_NAME="bun.lockb"
  elif [ -f "$CACHE_DIR/bun.lock" ]; then
    CACHE_LOCK_NAME="bun.lock"
  fi

  if [ -n "$LOCK_NAME" ] && [ -n "$CACHE_LOCK_NAME" ]; then
    cp "$FENIX_ROOT/$LOCK_NAME" "/app/tests/$LOCK_NAME"
    if cmp -s "$FENIX_ROOT/$LOCK_NAME" "$CACHE_DIR/$CACHE_LOCK_NAME"; then
      echo "    Lockfile unchanged, using cached node_modules..."
      cp -r "$CACHE_DIR/node_modules" /app/tests/node_modules
      NEED_INSTALL=false
    fi
  elif [ -z "$LOCK_NAME" ] && [ -d "$CACHE_DIR/node_modules" ] && [ "$(ls -A $CACHE_DIR/node_modules 2>/dev/null)" ]; then
    echo "    No lockfile, using cached node_modules..."
    cp -r "$CACHE_DIR/node_modules" /app/tests/node_modules
    NEED_INSTALL=false
  fi

  if [ "$NEED_INSTALL" = "true" ]; then
    echo "    Lockfile changed or no cache, running bun install..."
    cd /app/tests && bun install --no-save 2>&1 | tail -3
    # 更新缓存（供下次使用）
    rm -rf "$CACHE_DIR/node_modules"
    cp -r /app/tests/node_modules "$CACHE_DIR/node_modules"
    # 保存实际生成的锁文件
    if [ -f /app/tests/bun.lockb ]; then
      cp /app/tests/bun.lockb "$CACHE_DIR/bun.lockb"
    elif [ -f /app/tests/bun.lock ]; then
      cp /app/tests/bun.lock "$CACHE_DIR/bun.lock"
    fi
    echo "    Dependencies installed and cache updated."
  else
    echo "    Dependencies ready (from cache)."
  fi
else
  echo "    WARNING: No package.json found at $FENIX_ROOT, skipping bun install."
fi

# 3. 运行测试
echo ">>> Running bun test..."
mkdir -p /app/tests/results
cd /app/tests

# bun test --reporter=junit 必须配 --reporter-outfile
set +e
bun test --reporter=junit --reporter-outfile=results/unit-junit.xml
TEST_EXIT=$?
set -e

if [ -s results/unit-junit.xml ]; then
    echo ">>> junit XML written: $(wc -c < results/unit-junit.xml) bytes"
else
    echo "    WARNING: junit XML is empty or missing!"
fi

echo ">>> Test exit code: $TEST_EXIT"
exit $TEST_EXIT
