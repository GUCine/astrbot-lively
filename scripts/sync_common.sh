#!/bin/sh
# 把 common/lively_common.py 复制到每个插件目录（AstrBot 插件各自独立安装，没法共用一个文件）
cd "$(dirname "$0")/.." || exit 1
for d in astrbot_plugin_lively_*/; do
  cp common/lively_common.py "$d"
done
echo "已同步到 $(ls -d astrbot_plugin_lively_*/ | wc -l | tr -d ' ') 个插件"
