#!/bin/sh
set -e

FENIX_ROOT="/app/fenix-source-parent"
CACHE_DIR="/app/cache"
TEST_ROOT="${TEST_ROOT:-/app/tests}"
# 用 /workspace 模拟 monorepo 根目录，让 bun 正确解析 workspace:* 依赖
WORKSPACE_ROOT="/workspace"

echo "=== Unit Test Runner ==="
echo "    Source: $FENIX_ROOT (apps/server/src + packages/*)"
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
#
# 必须按根 package.json 声明的 workspaces glob（packages/*、packages/*/*）逐层枚举，
# 并保留相对路径复制：只扫 packages/* 一层会漏掉 packages/resources/*、
# packages/platform/* 下的包，bun 就会报 "@fenix/resource-xxx@workspace:* failed to resolve"。
# 不要用 packages/*/*/* 兜底——那一层会扫到各包自己的 node_modules。
# （根 glob 还声明了 apps/*，但没有任何 workspace:* 依赖指向它，故不复制。）
mkdir -p "$WORKSPACE_ROOT/packages"
for pkg_json in "$FENIX_ROOT"/packages/*/package.json "$FENIX_ROOT"/packages/*/*/package.json; do
  if [ -f "$pkg_json" ]; then
    pkg_dir=${pkg_json%/package.json}
    pkg_rel=${pkg_dir#"$FENIX_ROOT"/}
    # 读取 package.json 中的实际 name（如 @fenix/claude-code 而非 plugin-claude-code）
    pkg_json_name=$(bun -e "console.log(require('${pkg_json}').name)" 2>/dev/null || echo "")

    # 方式1：按原相对路径复制到 workspace（比 symlink 更可靠，bun 对跨 volume symlink 有兼容性问题）
    mkdir -p "$WORKSPACE_ROOT/$(dirname "$pkg_rel")"
    cp -r "$pkg_dir" "$WORKSPACE_ROOT/$pkg_rel" 2>/dev/null || ln -sfn "$pkg_dir" "$WORKSPACE_ROOT/$pkg_rel"

    # 方式2：将所有 workspace 包加到根 package.json 的 dependencies，
    # 并将其依赖也加到根 dependencies，强制 bun 安装并 hoist 所有依赖
    if [ -n "$pkg_json_name" ] && [ "$pkg_json_name" != "undefined" ]; then
      cd "$WORKSPACE_ROOT"
      bun -e "
const fs = require('fs');
const rootPkg = JSON.parse(fs.readFileSync('./package.json', 'utf8'));
const wsPkg = JSON.parse(fs.readFileSync('./$pkg_rel/package.json', 'utf8'));
if (!rootPkg.dependencies) rootPkg.dependencies = {};
// 加 workspace 包本身
rootPkg.dependencies['$pkg_json_name'] = 'workspace:*';
// 把 workspace 包的 dependencies + devDependencies 都加到 root（确保 bun hoist 到顶层 node_modules）
const wsDeps = { ...(wsPkg.dependencies || {}), ...(wsPkg.devDependencies || {}) };
const depCount = Object.keys(wsDeps).length;
for (const [name, version] of Object.entries(wsDeps)) {
  if (!rootPkg.dependencies[name]) {
    rootPkg.dependencies[name] = version;
  }
}
fs.writeFileSync('./package.json', JSON.stringify(rootPkg, null, 2));
console.log('Added $pkg_json_name + ' + depCount + ' deps');
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
# 2. 生成 tsconfig.json（@fenix/* 解析必须与被测代码一致，避免同一包加载两份导致 instanceof 失败）
#    历史坑1：曾把 @fenix/sandbox-provider 指到 ${FENIX_ROOT}/packages/...（挂载的原始源码），
#    但被测代码（FenixAgent tsconfig.base.json 无此条目）走 node_modules/workspace 拷贝
#    （/workspace/packages/sandbox-provider，entrypoint 从 FENIX_ROOT 复制的那份），两份物理
#    文件使 instanceof / toBeInstanceOf 全部失败。修复：sandbox-provider 也指到 workspace
#    拷贝 ${WORKSPACE_ROOT}/packages/sandbox-provider，与被测代码走同一份。
#    历史坑2：不能去掉 @fenix/* 通配——测试大量 import @fenix/db/*、@fenix/services/*、
#    @fenix/test-utils/* 等宿主服务端模块（不是 workspace 包），必须映射到
#    ${FENIX_ROOT}/apps/server/src/*。@fenix/chat-channel 等顶层包无对应目录，bun 会 fallback
#    到 node_modules（workspace 包）解析。
#    历史坑3：FenixAgent 于 2026-09-17（bda524de3）删除了顶层 src/，代码拆成
#    apps/server/src/（宿主）+ packages/*（业务包）。旧映射 ${FENIX_ROOT}/src/* 因此指向
#    不存在的目录，bun test 一启动就报 preload not found。现按新布局重新映射：
#      - @fenix/*      → ${FENIX_ROOT}/apps/server/src/*（db、services、test-utils 等仍在此）
#      - @src/<包>/*   → 见下，按「preload 替身登记在哪棵树」逐包决定
#    为什么 @src/<包>/* 大多指 ${WORKSPACE_ROOT} 而不是 ${FENIX_ROOT}：宿主代码内部 import
#    `@fenix/<包>/...` 会经 node_modules 落到 workspace 拷贝（bun install 建的 workspace 链接），
#    若 @src/* 指挂载的原始源码，同一个包会加载两份物理文件。多数情况无害，但只要该包用
#    「模块配置 / 端口绑定」做 DI（如 agent-runtime 的 workspaceRoot、session-event-bus-port），
#    用例装配进 A 实例、被测函数从 B 实例读取，就会「静默不生效」——测试照常通过，测的却是默认值。
#    与历史坑1 同因同解：全部指到 workspace 拷贝。
#    历史坑4（例外：identity 必须指 ${FENIX_ROOT}）：preload 的 setup-mocks.ts 位于
#    ${FENIX_ROOT}/apps/server/src/test-utils/，其中一批替身用「相对路径」登记
#      mock.module("../../../../packages/platform/identity/src/{auth/better-auth,db,config,
#                  repositories/user-config,services/system-api}")
#    相对路径经解析落在 ${FENIX_ROOT}/packages/platform/identity/src/*。mock.module 按解析后的
#    物理路径生效，若 @src/identity/* 指 workspace 拷贝，测试加载的是另一个物理文件，替身不生效
#    ——better-auth.test.ts 因此会真的去 buildAuth，撞上「应用基础设施尚未初始化」而整文件失败。
#    故 identity 包单独指回 ${FENIX_ROOT}，与替身登记的路径对齐。
#    判据：某包的内部模块若被 preload 以「相对路径」mock，该包就必须指 ${FENIX_ROOT}；
#    否则指 ${WORKSPACE_ROOT}（与 node_modules / 测试包的替身同树）。
#    为什么用 @src/ 前缀而不是包名：各 package 的 exports 只暴露 . / db / module / server /
#    web，不暴露单个 service 文件，用包名做通配会与 package 自身的 exports 抢解析。
# 注意：下面是 heredoc 生成的纯 JSON，不能写 // 注释，只能靠这里的 shell 注释说明。
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
      "@fenix/sandbox-provider": ["${WORKSPACE_ROOT}/packages/sandbox-provider/src"],
      "@fenix/sandbox-provider/*": ["${WORKSPACE_ROOT}/packages/sandbox-provider/src/*"],
      "@fenix/*": ["${FENIX_ROOT}/apps/server/src/*"],
      "@src/resource-sandbox/*": ["${WORKSPACE_ROOT}/packages/resources/sandbox/src/*"],
      "@src/resource-machine/*": ["${WORKSPACE_ROOT}/packages/resources/machine/src/*"],
      "@src/resource-prod-view/*": ["${WORKSPACE_ROOT}/packages/resources/prod-view/src/*"],
      "@src/model-management/*": ["${WORKSPACE_ROOT}/packages/resources/model-management/src/*"],
      "@src/identity/*": ["${FENIX_ROOT}/packages/platform/identity/src/*"],
      "@src/agent-runtime/*": ["${WORKSPACE_ROOT}/packages/agent-runtime/src/*"]
    }
  },
  "include": ["**/*.ts"]
}
TSEOF

# 2b. 生成 bunfig.toml（preload setup-globals + setup-mocks，确保 mock.module() 生效）
#     preload 路径必须与 FenixAgent 根 bunfig.toml 一致：test-utils 随 src/ 一起迁到了
#     apps/server/src/test-utils/，不再位于仓库根 src/ 下。
echo ">>> Generating bunfig.toml..."
cat > "$WORKSPACE_ROOT/tests/bunfig.toml" << BFEOF
[test]
root = "."
preload = ["${FENIX_ROOT}/apps/server/src/test-utils/setup-globals.ts", "${FENIX_ROOT}/apps/server/src/test-utils/setup-mocks.ts"]
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

  # 诊断：列出 workspace 包（显示相对路径 + package.json name；必须覆盖两级，
  # 否则 packages/resources/* 这类包在日志里不可见，出问题很难定位）
  echo "    Workspace packages:"
  for pkg in "$WORKSPACE_ROOT/packages"/*/ "$WORKSPACE_ROOT/packages"/*/*/; do
    if [ -f "${pkg}package.json" ]; then
      dir_name=${pkg#"$WORKSPACE_ROOT"/}
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
  bun install 2>&1 | tail -20
  INSTALL_EXIT=$?
  set -e

  if [ $INSTALL_EXIT -ne 0 ]; then
    echo "    WARNING: bun install with lockfile failed (exit $INSTALL_EXIT)"
    echo "    Retrying without lockfile..."
    rm -f bun.lock bun.lockb
    set +e
    bun install 2>&1 | tail -20
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
