cd /Users/quasarpark/meow-loop/work
export PATH=$PWD/bc123/bin:$PATH NOSANDBOX=1 FAST=1 DIST=1 WORKERS=4
B="SPRINT_FREE_DIV=4,STRIDE=true,CELL_BUDGET=12000,QUEEN_MODE=true,QUEEN_LEAD_BONUS=0,QUEEN_THREAT_MULT=1.0,QUEEN_GUARD_RADIUS=0,QUEEN_DEAD_PENALTY=0.0,QUEEN_PESSIMIST=false,QUEEN_SPLIT_CLEAR=0,QUEEN_DEFEND_RADIUS=0,QUEEN_HUNT=false,QUEEN_NO_PORTAL=true,QUEEN_MIN_CELLS=600,QUEEN_SPLIT_ROUND=200,QUEEN_LEAD_BONUS=1000,QUEEN_LEAD_LATE=true,QUEEN_QUIET_ROUND=100,QUEEN_GAME_FEED_ROUND=300,QUEEN_SAFE_ROUND=300,QUEEN_SAFE_SPAN=0,FAR_GAIN=2,POCKET_CAP=48,QUEEN_HOME_CLOSED=true"
V1="PKHC@snap55:$B"
SEED0=3000 python3 ab3.py "$(cat newset.txt),$(cat official.txt)" v60 8 qk2o.json "$V1" > qk2.txt 2>&1
python3 paired.py qg1o.json PK48 qk2o.json >> qk2.txt
SEED0=3000 python3 ab3.py "$(cat sqfull.txt)" v53 2 qk2d.json "$V1" >> qk2.txt 2>&1
python3 paired.py qg2d.json PK48 qk2d.json >> qk2.txt
SEED0=3000 python3 ab3.py "$(cat heldset_sq.txt)" v53 2 qk2h.json "$V1" >> qk2.txt 2>&1
python3 paired.py qg2h.json PK48 qk2h.json >> qk2.txt
SEED0=3000 python3 ab3.py "$(cat freshset.txt)" v53 2 qk2f.json "$V1" >> qk2.txt 2>&1
python3 paired.py qg2f.json PK48 qk2f.json >> qk2.txt
echo QK2DONE >> qk2.txt
