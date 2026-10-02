cd /Users/UNSW/battlecode/work
until [ $(grep -c "^L460 " lf1.txt 2>/dev/null) -ge 2 ]; do sleep 20; done
sleep 5
B=$(cat v55toggles.txt)
export PATH=$PWD/bc123/bin:$PATH NOSANDBOX=1 FAST=1 DIST=1 WORKERS=4
SEED0=1000 python3 ab3.py "$(cat official.txt)" v55 8 sy1o.json "S55@snap36:$B,SYM_INFER=true" > sy1.txt 2>&1
python3 paired.py lf1o.json V55 sy1o.json >> sy1.txt
SEED0=700 python3 ab3.py "$(cat sqfull.txt)" v53 2 sy1d.json "S55@snap36:$B,SYM_INFER=true" >> sy1.txt 2>&1
python3 paired.py qc6d.json QMC sy1d.json >> sy1.txt
SEED0=900 python3 ab3.py "$(cat heldset_sq.txt)" v53 2 sy1h.json "S55@snap36:$B,SYM_INFER=true" >> sy1.txt 2>&1
python3 paired.py qc6h.json QMC sy1h.json >> sy1.txt
echo SY1DONE >> sy1.txt
