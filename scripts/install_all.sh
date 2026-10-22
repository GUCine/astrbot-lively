#!/bin/sh
# 把擬真群友（lively）插件從 GitHub clone 到 AstrBot 的 data/plugins/。
# 用法：./scripts/install_all.sh <AstrBot 的 data 目錄> [插件短名 ...]
#   不列插件就裝全部 12 個；已經存在的目錄跳過（要更新請進目錄 git pull）
set -e
DATA=${1:?用法：$0 <AstrBot 的 data 目錄> [gate bond ...]}
shift
[ -d "$DATA/plugins" ] || { echo "找不到 $DATA/plugins，請確認是 AstrBot 的 data 目錄"; exit 1; }
ALL="gate billing bond comic evolve memtier panel proactive qzone report social voice"
for s in ${*:-$ALL}; do
  n=astrbot_plugin_lively_$s
  if [ -d "$DATA/plugins/$n" ]; then
    echo "跳過 $n（已存在）"
  else
    git clone --depth 1 "https://github.com/GUCine/$n.git" "$DATA/plugins/$n"
  fi
done
echo "完成。重啟 AstrBot 後到 WebUI 填 astrbot_plugin_lively_gate 的配置。"
