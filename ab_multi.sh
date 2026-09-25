#!/bin/zsh
# 多种子 A/B：每个种子下跑一遍 ab.sh 的 10 局。
# 对局是确定性的，换 TIE_SEED 相当于换一批独立样本。
# 只在需要分辨小差异时用，默认还是 ./ab.sh 的 10 局。
# 用法: ./ab_multi.sh mybot v2 [种子个数，默认 2]

set -e
left=$1
right=$2
seeds=${3:-2}

rm -rf _ab_l _ab_r
cp -r "$left" _ab_l
cp -r "$right" _ab_r

for s in $(seq 0 $((seeds-1))); do
    sed -i '' "s/constexpr int TIE_SEED = .*/constexpr int TIE_SEED = $s;/" _ab_l/main.cpp _ab_r/main.cpp
    echo "=== seed $s ==="
    ./ab.sh _ab_l _ab_r | tail -1
done

rm -rf _ab_l _ab_r
