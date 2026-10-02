cd /Users/UNSW/battlecode/work
export PATH=$PWD/bc123/bin:$PATH
for job in "around_unsw 6" "around_unsw 7" "australia 6" "big_empty 6"; do echo $job; done | xargs -P 2 -L 1 sh -c 'm=$0; s=$1; f=../tune_runs/newmaps/$m.map; [ -f $f ] || f=../tune_runs/official123/big_empty.map; unswbc run $f ../cpu_pkhc ../v60 --sandbox --seed $s --no-replay 2>&1 | grep "points per turn" | sed "s/^/$m s$s /" > cpu/pkhc_${m}_$s.txt'
echo CPUDONE > cpu/pkhc_done.txt
