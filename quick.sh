#!/bin/zsh
# 快速 A/B：5 张代表性地图各打先后手两局，共 10 局。
# default / schooltime / trauma 有传送门，devil 是海草迷宫，big_empty 是 64x64 上限。
# 用法: ./quick.sh mybot v2

set -e
left=$1
right=$2
lw=0
rw=0
draw=0

tally() {
    case "$1" in
        *draw*)             draw=$((draw+1));;
        *"team $2 wins"*)   lw=$((lw+1));;
        *)                  rw=$((rw+1));;
    esac
}

for name in default big_empty devil trauma default_small; do
    m=maps/$name.map
    a=$(unswbc run "$m" "$left" "$right" --sandbox 2>&1 | rg 'wins|draw' | head -1)
    b=$(unswbc run "$m" "$right" "$left" --sandbox 2>&1 | rg 'wins|draw' | head -1)

    tally "$a" A
    tally "$b" B

    printf "%-16s %s | %s\n" "$name" "$a" "$b"
done

echo "----"
echo "$left: $lw 胜   $right: $rw 胜   平: $draw   （共 10 局）"
