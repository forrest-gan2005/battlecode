cd /Users/UNSW/battlecode/work
export PATH=$PWD/bc123/bin:$PATH NOSANDBOX=1 FAST=1 DIST=1 WORKERS=4
B="SPRINT_FREE_DIV=4,STRIDE=true,CELL_BUDGET=12000,QUEEN_MODE=true,QUEEN_LEAD_BONUS=0,QUEEN_THREAT_MULT=1.0,QUEEN_GUARD_RADIUS=0,QUEEN_DEAD_PENALTY=0.0,QUEEN_PESSIMIST=false,QUEEN_SPLIT_CLEAR=0,QUEEN_DEFEND_RADIUS=0,QUEEN_HUNT=false,QUEEN_NO_PORTAL=true,QUEEN_MIN_CELLS=600,QUEEN_SPLIT_ROUND=200,QUEEN_LEAD_BONUS=1000,QUEEN_LEAD_LATE=true,QUEEN_QUIET_ROUND=100,QUEEN_GAME_FEED_ROUND=300,QUEEN_SAFE_ROUND=300,QUEEN_SAFE_SPAN=0,FAR_GAIN=2,POCKET_CAP=48"
V2="CPP@snap54:$B,CENTER_PATH=true"
V3="CPPN@snap54:$B,CENTER_PATH=true,NO_TAIL_ROOM=6"
SEED0=3000 python3 ab3.py "$(cat newset.txt),$(cat official.txt)" v60 8 qi1o.json "$V2" "$V3" > qi1.txt 2>&1
python3 paired.py qg1o.json PK48 qi1o.json >> qi1.txt
SEED0=3000 python3 ab3.py "$(cat sqfull.txt)" v53 2 qi1d.json "$V2" "$V3" >> qi1.txt 2>&1
python3 paired.py qg2d.json PK48 qi1d.json >> qi1.txt
SEED0=3000 python3 ab3.py "$(cat heldset_sq.txt)" v53 2 qi1h.json "$V2" "$V3" >> qi1.txt 2>&1
python3 paired.py qg2h.json PK48 qi1h.json >> qi1.txt
SEED0=3000 python3 ab3.py "$(cat freshset.txt)" v53 2 qi1f.json "$V2" "$V3" >> qi1.txt 2>&1
python3 paired.py qg2f.json PK48 qi1f.json >> qi1.txt
echo QI1DONE >> qi1.txt
