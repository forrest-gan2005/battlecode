#!/bin/zsh
# A/B 对照：在 5 张代表性地图上各打先后手两局，共 10 局
# 用法: ./ab.sh mybot v2
# 想换地图: AB_MAPS="maps/arena.map maps/big_empty.map" ./ab.sh mybot v2

set -e
left=$1
right=$2

# 覆盖尺寸 16x16 到 48x24、开阔图和海草迷宫各一张；64x64 的 big_empty 留给算力检查
if [[ -n $AB_MAPS ]]; then
    maps=(${=AB_MAPS})
else
    maps=(maps/default.map maps/default_small.map maps/devil.map maps/trauma.map maps/trophy.map)
fi

lw=0
rw=0
draw=0

# $1 = 结果行, $2 = left 这局所在的队伍字母
tally() {
    case "$1" in
        *draw*)             draw=$((draw+1));;
        *"team $2 wins"*)   lw=$((lw+1));;
        *)                  rw=$((rw+1));;
    esac
}

for m in $maps; do
    name=$(basename "$m" .map)
    a=$(unswbc run "$m" "$left" "$right" --sandbox 2>&1 | rg 'wins|draw' | head -1)
    b=$(unswbc run "$m" "$right" "$left" --sandbox 2>&1 | rg 'wins|draw' | head -1)

    tally "$a" A
    tally "$b" B

    printf "%-16s %s | %s\n" "$name" "$a" "$b"
done

echo "----"
echo "$left: $lw 胜   $right: $rw 胜   平: $draw   （共 $((${#maps} * 2)) 局）"
