#!/bin/sh
set -e

FENIX_SRC="/app/fenix-source-parent/src"
FENIX_ROOT="/app/fenix-source-parent"

echo "=== Unit Test Runner ==="
echo "    Source: $FENIX_SRC"
echo "    Tests:  /app/tests"

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
      "@fenix/*": ["${FENIX_SRC}/*"]
    }
  },
  "include": ["**/*.ts"]
}
TSEOF

# 2. 安装依赖（从 FenixAgent 的 package.json 获取外部依赖）
echo ">>> Installing dependencies..."
if [ -f "$FENIX_ROOT/package.json" ]; then
  cp "$FENIX_ROOT/package.json" /app/tests/package.json
  # 如果有 lockfile 也复制
  [ -f "$FENIX_ROOT/bun.lockb" ] && cp "$FENIX_ROOT/bun.lockb" /app/tests/bun.lockb
  cd /app/tests && bun install --no-save 2>&1 | tail -3
  echo "    Dependencies installed."
else
  echo "    WARNING: No package.json found at $FENIX_ROOT, skipping bun install."
fi

# 3. 运行测试
echo ">>> Running bun test..."
mkdir -p /app/tests/results
cd /app/tests
bun test --reporter=junit --reporter-outfile=results/unit-junit.xml
