#!/system/bin/sh
# 安装 pnpm 到 Node24 前缀（DSH 插件管理器会 spawn `pnpm add`，缺少它就会报 ENOENT）
set -eu
export PATH=/opt/node24/bin:$PATH
npm install -g pnpm@10 --no-audit --no-fund
echo "pnpm=$(pnpm -v) path=$(command -v pnpm)"
