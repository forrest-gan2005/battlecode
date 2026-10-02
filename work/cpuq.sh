cd /Users/UNSW/battlecode/work
export PATH=$PWD/bc123/bin:$PATH
for job in "around_unsw 6" "around_unsw 7" "australia 6" "australia 7" "islands 6" "big_empty 6"; do echo $job; done | xargs -P 3 -L 1 sh -c 'm=$0; s=$1; f=../tune_runs/newmaps/$m.map; [ -f $f ] || f=/Users/UNSW/battlecode/tune_runs/official123/big_empty.map; unswbc run $f ../cpu_cppn ../v60 --sandbox --seed $s --no-replay 2>&1 | grep "points per turn" | sed "s/^/$m s$s /" > cpu/cppn_${m}_$s.txt'
echo CPUDONE > cpu/cppn_done.txt
