cd /Users/UNSW/battlecode/work
B="$(cat v55toggles.txt),QUEEN_SPLIT_ROUND=200,QUEEN_LEAD_BONUS=1000,QUEEN_LEAD_LATE=true,QUEEN_QUIET_ROUND=100,QUEEN_GAME_FEED_ROUND=300"
export PATH=$PWD/bc123/bin:$PATH NOSANDBOX=1 FAST=1 DIST=1 WORKERS=4
V0="QF3@snap47:$B"
V1="H4@snap47:$B,QUEEN_HUNT=true,QUEEN_HUNT_MAX_LEN=4"
V2="H4K@snap47:$B,QUEEN_HUNT=true,QUEEN_HUNT_MAX_LEN=4,QUEEN_KEEP=4"
V3="H4KG@snap47:$B,QUEEN_HUNT=true,QUEEN_HUNT_MAX_LEN=4,QUEEN_KEEP=4,QUEEN_GIVE_WAY=3"
SEED0=3000 python3 ab3.py "$(cat official.txt)" tune_runs/ab2/QHSPAR 8 qb1s.json "V57@v57:" "$V0" "$V1" "$V2" "$V3" > qb1.txt 2>&1
echo "== vs v57" >> qb1.txt
SEED0=3000 python3 ab3.py "$(cat official.txt)" v57 8 qb1o.json "V57@v57:" "$V0" "$V1" "$V2" "$V3" >> qb1.txt 2>&1
echo QB1DONE >> qb1.txt
