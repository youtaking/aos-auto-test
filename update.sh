#!/bin/bash
# update.sh — autotest 一键更新脚本（在 Linux 服务器上执行）
# 用法：./update.sh
# 作用：拉取最新代码 → 重建有改动的镜像 → 重启 backend 同步用例 → 健康检查
set -euo pipefail

cd "$(dirname "$0")"

echo "==> [1/4] 拉取最新代码"
git pull

echo "==> [2/4] 重建有改动的镜像并启动"
docker compose up -d --build

echo "==> [3/4] 重启 backend 触发用例自动发现"
docker compose restart backend

echo "==> [4/4] 健康检查"
for i in $(seq 1 15); do
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 http://localhost:8111/api/health || echo 000)
    if [ "$code" = "200" ]; then
        echo "    后端 /api/health → 200 OK"
        break
    fi
    if [ "$i" = "15" ]; then
        echo "    后端健康检查失败（最后状态码: $code），请查看 docker compose logs backend"
        exit 1
    fi
    echo "    等待后端就绪 (${i}/15)..."
    sleep 3
done

echo "==> 更新完成，当前容器状态："
docker compose ps
