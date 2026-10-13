# ci/vendor

CI 构建期需要、但**不能**改在被测仓库里的东西放这里。

## hindsight-marketplace

上游 [vectorize-io/hindsight](https://github.com/vectorize-io/hindsight) 的 marketplace 清单与
`claude-code` 集成插件副本（38 个文件 / 249KB；上游 marketplace 里还有 `zcode` 集成，用不到，未预置）。
当前对应 commit 见 `hindsight-marketplace.upstream.txt`。

**为什么需要它**

被测应用镜像里有一行 `peri plugin marketplace add vectorize-io/hindsight`（`Dockerfile`，peri 引擎预装）：

- peri 对 marketplace 的 `git clone` 硬编码 30s 超时（`peri-middlewares/src/plugin/marketplace/fetch.rs` 里的 `tokio::time::timeout`）；
- 而上游仓库主干树就有 225MB（含 30MB 的 `openapi-generator-cli.jar` 与十几张 5~6MB 文档截图）；
- 实测：直连下载该仓库归档约 90s（2.6MB/s），走 gh-proxy 更慢（约 12KB/s）——30s 内不可能拉完。

于是构建稳定失败（`PR-Pipeline-build` #191 / #192 / #194 全都挂在这一步）：

```
Error: 无法拉取 marketplace: Git 操作失败: clone 超时: deadline has elapsed
```

被测仓库（`HuangPuStar/FenixAgent`）是**只读**的，不能改它的 Dockerfile，所以由**本仓库的流水线**在
`docker build` 之前把这份 249KB 副本注入构建上下文，并把那一行改写成「本地目录源」——只改本次构建
上下文里的副本，不动被测仓库：

```bash
# docs/jenkins-pipeline-build.groovy / docs/jenkins-pipeline-script.groovy 的 Build Image 阶段
if [ -d ../autotest/ci/vendor/hindsight-marketplace ]; then
    mkdir -p docker/vendor
    cp -r ../autotest/ci/vendor/hindsight-marketplace docker/vendor/
    sed -i 's|^RUN peri plugin marketplace add vectorize-io/hindsight.*|COPY docker/vendor/hindsight-marketplace/ /root/.claude/plugins/marketplaces/hindsight/\nRUN peri plugin marketplace add /root/.claude/plugins/marketplaces/hindsight|' Dockerfile
fi
```

**COPY 的目标路径不能改**：`plugin install` 解析 marketplace 里 `./xxx` 这类相对插件路径时，是从
`~/.claude/plugins/marketplaces/<marketplace>/` 下找的（peri 见 `peri-middlewares/src/plugin/installer/install.rs`，
ccb / Claude Code 同理）。目录不落在 `marketplaces/hindsight/` 下，`plugin install` 会报「插件未找到」。

**用到的地方**

- `docs/jenkins-pipeline-build.groovy` → job `PR-Pipeline-build`
- `docs/jenkins-pipeline-script.groovy` → job `PR-Pipeline-FenixAgent`

若被测应用哪天自己修好了（Dockerfile 里不再有那行 clone），流水线会打印 NOTE 并跳过改写。

**刷新**

```bash
bash ci/vendor/refresh-hindsight-marketplace.sh                  # 用脚本内固定 commit
HINDSIGHT_COMMIT=main bash ci/vendor/refresh-hindsight-marketplace.sh
HINDSIGHT_ARCHIVE=/path/to/repo.tar.gz bash ci/vendor/refresh-hindsight-marketplace.sh
```

刷新后请提交 `ci/vendor/` 的改动。