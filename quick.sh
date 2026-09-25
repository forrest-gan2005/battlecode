#!/bin/zsh
# 快速 A/B：5 张代表性地图各打先后手两局，共 10 局。
# default / schooltime / trauma 有传送门，devil 是海草迷宫，big_empty 是 64x64 上限。
# 用法: ./quick.sh mybot v2
# 逻辑全在 ab.sh 里，这里只是换了一组地图。

cd "$(dirname "$0")"
AB_MAPS="maps/default.map maps/big_empty.map maps/devil.map maps/trauma.map maps/default_small.map" \
    exec ./ab.sh "$@"
