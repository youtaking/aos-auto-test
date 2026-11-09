# Jenkins 自定义镜像部署指南

## 为什么需要自定义镜像

Jenkins 容器重建（宿主机重启、1Panel 升级）会丢失：
- Python 3（Pipeline 脚本 JSON 解析依赖）
- Docker Compose（Pipeline 部署 PR 环境依赖）
- 代理环境变量（可能带入死代理导致网络不通）

自定义镜像将依赖烘焙进去，重建后无需手动修复。

## 构建镜像

```bash
cd docs/jenkins
docker build -t jenkins-custom:2.568.1 -f Dockerfile.jenkins .
```

## 1Panel 配置

在 1Panel 中将 Jenkins 应用镜像替换为 `jenkins-custom:2.568.1`：

1. 进入 1Panel → 应用商店 → Jenkins → 设置
2. 镜像标签改为 `jenkins-custom:2.568.1`
3. **删除所有代理环境变量**（HTTP_PROXY、HTTPS_PROXY、NO_PROXY），避免网络问题
4. 确认数据卷挂载 `/opt/1panel/apps/jenkins/jenkins/data:/var/jenkins_home`

## 容器重建后检查清单

如果容器被重建，执行以下验证：

```bash
# 1. 确认工具可用
docker exec 1Panel-jenkins-goqR python3 --version
docker exec 1Panel-jenkins-goqR docker-compose --version

# 2. 确认网络正常（无代理干扰）
docker exec 1Panel-jenkins-goqR curl -s -o /dev/null -w "%{http_code}" https://github.com

# 3. 确认 Docker 网络
docker inspect 1Panel-jenkins-goqR --format='{{json .NetworkSettings.Networks}}' | python3 -c "import sys,json; print(list(json.load(sys.stdin).keys()))"
# 应输出包含 "1panel-network"

# 4. 如果网络不对，修复：
docker network disconnect bridge 1Panel-jenkins-goqR 2>/dev/null
docker network connect 1panel-network 1Panel-jenkins-goqR
```

## Pipeline 脚本关键配置

以下配置已持久化在 Git 仓库的 Groovy 文件中：

| 配置 | 文件 | 说明 |
|------|------|------|
| GitHub 直连优先 | `jenkins-pipeline-build.groovy` L102 | `for proxy in "" $proxies` |
| 关闭限流 | `jenkins-pipeline-build.groovy` L372-373 | `NODE_ENV: test` + `BUN_TEST: "1"` |

## 已知问题

- **apt-get 端口 80 被屏蔽**：容器内无法直接用 apt 安装软件，Dockerfile 使用清华镜像源
- **GitHub 下载慢**：Pipeline 已改为直连优先，实测 25 秒下载 8MB
- **Bun build 死代码消除**：`bun build --target=bun` 会在构建时消除 `NODE_ENV === "test"` 判断，必须用 `BUN_TEST` 环境变量
