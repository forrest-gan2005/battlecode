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

# 没有 TIE_SEED 的老版本换不了种子，几个种子会跑出一模一样的对局
for f in _ab_l/main.cpp _ab_r/main.cpp; do
    if ! grep -q 'constexpr int TIE_SEED = ' "$f"; then
        echo "!! $f 里没有 TIE_SEED，无法换种子" >&2
        rm -rf _ab_l _ab_r
        exit 1
    fi
done

for s in $(seq 0 $((seeds-1))); do
    # -i.bak 在 macOS 和 GNU sed 上都能用；sed -i '' 只有 BSD sed 认
    sed -i.bak "s/constexpr int TIE_SEED = .*/constexpr int TIE_SEED = $s;/" _ab_l/main.cpp _ab_r/main.cpp
    rm -f _ab_l/main.cpp.bak _ab_r/main.cpp.bak
    echo "=== seed $s ==="
    ./ab.sh _ab_l _ab_r | tail -1
done

rm -rf _ab_l _ab_r
