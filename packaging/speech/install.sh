#!/bin/sh
# 在 Linux 显卡主机上安装 Liber Speech 插件。需要 Docker 与 NVIDIA Container Toolkit。
set -eu
cd "$(dirname "$0")"
if ! command -v docker >/dev/null 2>&1; then
  echo "未找到 docker。请先安装 Docker Engine 与 NVIDIA Container Toolkit。" >&2
  exit 1
fi
docker compose up -d --build
echo ""
echo "Liber Speech 已监听 5555。"
echo "本机 LiberAstra 的 Base URL：http://127.0.0.1:5555"
hostname -I 2>/dev/null | awk '{for (i = 1; i <= NF; i++) printf "其它主机上的 LiberAstra 填：http://%s:5555\n", $i}'
