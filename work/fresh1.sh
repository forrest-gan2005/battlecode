cd /Users/quasarpark/meow-loop/work
export PATH=$PWD/bc123/bin:$PATH
big=$(for f in ../tune_runs/genfresh/*.map; do echo "$(head -1 $f | awk '{print $2*$3}') $f"; done | sort -rn | head -8 | awk '{print $2}')
echo "$big" | xargs -P 4 -I{} sh -c 'n=$(basename {} .map); unswbc run {} ../v55 ../v55 --sandbox --seed 3 --no-replay 2>&1 | grep "points per turn" | sed "s/^/$n /"' > fresh_cpu.txt
NOSANDBOX=1 DIST=1 WORKERS=3 KEEP=1 SEED0=2000 python3 ab3.py "$(cat freshset.txt)" v53 2 fresh1.json "V55@v55:" > fresh1.txt 2>&1
echo FRESH1DONE >> fresh1.txt
