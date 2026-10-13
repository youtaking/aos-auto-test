#!/usr/bin/env bash
# 刷新镜像预置的 hindsight marketplace 副本：docker/vendor/hindsight-marketplace/
#
# 背景
#   上游 vectorize-io/hindsight 的主干树就有 225MB（含 30MB 的 openapi-generator-cli.jar
#   与十几张 5~6MB 的文档截图），而 peri 对 marketplace 的 git clone 硬编码 30s 超时
#   （peri-middlewares/src/plugin/marketplace/fetch.rs 里的 tokio::time::timeout），
#   所以在容器构建里跑 `peri plugin marketplace add vectorize-io/hindsight` 必然报
#   "无法拉取 marketplace: Git 操作失败: clone 超时: deadline has elapsed"。
#   这里只把插件真正用到的子集（约 250KB）预置在本仓库，由流水线注入构建上下文并把 Dockerfile
#   那一行改成本地目录源（peri 的 MarketplaceSource::Directory，全程不联网）；详见 ci/vendor/README.md。
#
# 用法
#   bash docker/vendor/refresh-hindsight-marketplace.sh                    # 用脚本内固定 commit
#   HINDSIGHT_COMMIT=<sha|分支> bash docker/vendor/refresh-hindsight-marketplace.sh
#   HINDSIGHT_ARCHIVE=/path/to/repo.tar.gz bash docker/vendor/refresh-hindsight-marketplace.sh
#       # 复用已下载的归档，跳过下载
#
# 刷新后请提交 docker/vendor/ 下的改动。
set -euo pipefail

REPO="vectorize-io/hindsight"
# 固定到 commit，保证 CI 构建可复现；跟进上游时用 HINDSIGHT_COMMIT 覆盖。
COMMIT="${HINDSIGHT_COMMIT:-12f2d54f643baddacb98cd547c89b1a50c5c3dcc}"
# 只保留 claude-code 集成（文档/截图/其它语言客户端都不需要）；
# marketplace 清单单独取，因为它在仓库根的 .claude-plugin/ 下。
KEEP=("hindsight-integrations/claude-code")
MANIFEST_PATTERN="*/.claude-plugin/marketplace.json"
# 与 Jenkins 流水线同源的 GitHub 镜像：先直连（通常最快），失败再逐个回退。
MIRRORS=("" "https://gh-proxy.com" "https://ghfast.top" "https://mirror.ghproxy.com" "https://ghproxy.net")

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${HERE}/hindsight-marketplace"
TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT

ARCHIVE_URL="https://github.com/${REPO}/archive/${COMMIT}.tar.gz"
ARCHIVE="${HINDSIGHT_ARCHIVE:-${TMP}/repo.tar.gz}"

echo ">>> 目标：docker/vendor/hindsight-marketplace/（上游 ${REPO}@${COMMIT}）"

if [ -n "${HINDSIGHT_ARCHIVE:-}" ]; then
    echo ">>> 复用本地归档：${ARCHIVE}"
    [ -f "${ARCHIVE}" ] || { echo "ERROR: 找不到 ${ARCHIVE}" >&2; exit 1; }
else
    echo ">>> 下载归档（约 180MB，直连 1~3 分钟）..."
    downloaded=0
    for mirror in "${MIRRORS[@]}"; do
        url="${mirror:+${mirror}/}${ARCHIVE_URL}"
        echo "    Trying: ${url}"
        if curl --fail -SL --progress-bar --connect-timeout 10 --max-time 1800 "${url}" -o "${ARCHIVE}" \
            && tar tzf "${ARCHIVE}" >/dev/null 2>&1; then
            echo "    OK (proxy: ${mirror:-direct})"
            downloaded=1
            break
        fi
        echo "    失败，换下一个镜像..."
    done
    if [ "${downloaded}" != "1" ]; then
        echo "ERROR: 所有镜像都下载失败" >&2
        exit 1
    fi
fi

echo ">>> 解出需要的子目录..."
# 注意：只用文件级 pattern。GNU tar 匹配到目录成员时会连整棵子树一起取，
# 若再叠一个 "*/.claude-plugin/*" 这类文件 pattern，tar 会因为重复匹配报
# "Not found in archive" 并以非 0 退出（误导性的报错）。
patterns=("${MANIFEST_PATTERN}")
for keep in "${KEEP[@]}"; do
    patterns+=("*/${keep}/*")
done
rm -rf "${DEST}"
mkdir -p "${DEST}"
tar xzf "${ARCHIVE}" -C "${DEST}" --strip-components=1 --wildcards "${patterns[@]}"

echo ">>> 校验..."
MANIFEST="${DEST}/.claude-plugin/marketplace.json"
PLUGIN_DIR="${DEST}/hindsight-integrations/claude-code"
[ -f "${MANIFEST}" ] || { echo "ERROR: 缺少 ${MANIFEST}" >&2; exit 1; }
[ -d "${PLUGIN_DIR}" ] || { echo "ERROR: 缺少插件目录 ${PLUGIN_DIR}" >&2; exit 1; }
[ -f "${PLUGIN_DIR}/.claude-plugin/plugin.json" ] || {
    echo "ERROR: 缺少 ${PLUGIN_DIR}/.claude-plugin/plugin.json" >&2; exit 1; }

# 0=合法 JSON，1=JSON 非法，2=环境里没有可用的校验工具
validate_json() {
    local tool out
    if command -v jq >/dev/null 2>&1; then
        if out="$(jq empty "${MANIFEST}" 2>&1)"; then return 0; fi
        echo "    jq: ${out}" >&2
        return 1
    fi
    for tool in python3 python; do
        command -v "${tool}" >/dev/null 2>&1 || continue
        # 跳过 Windows 商店占位符这类“存在但不可用”的 shim
        "${tool}" -c 'pass' >/dev/null 2>&1 || continue
        if out="$("${tool}" -c 'import json,sys;json.load(open(sys.argv[1],encoding="utf-8"))' "${MANIFEST}" 2>&1)"; then
            return 0
        fi
        echo "    ${tool}: $(printf '%s' "${out}" | tail -1)" >&2
        return 1
    done
    return 2
}

if validate_json; then
    echo "    marketplace.json 是合法 JSON"
else
    rc=$?
    if [ "${rc}" = "1" ]; then
        echo "ERROR: ${MANIFEST} 不是合法 JSON" >&2
        exit 1
    fi
    echo "    (跳过 JSON 校验：环境里没有可用的 jq/python)"
fi
grep -q '"source": "\./hindsight-integrations' "${MANIFEST}" \
    && echo "    marketplace.json 的插件 source 仍是相对路径（./hindsight-integrations/...）" \
    || echo "    提示：插件 source 已不再是 ./hindsight-integrations/...，请确认 COPY 的目录结构是否仍匹配"

printf 'repo=%s\ncommit=%s\n' "${REPO}" "${COMMIT}" > "${HERE}/hindsight-marketplace.upstream.txt"

echo ">>> 完成：$(find "${DEST}" -type f | wc -l | tr -d ' ') 个文件，$(du -sh "${DEST}" | cut -f1)"
echo "    上游记录：docker/vendor/hindsight-marketplace.upstream.txt"