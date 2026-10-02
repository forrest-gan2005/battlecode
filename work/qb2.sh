cd /Users/UNSW/battlecode/work
until grep -q QB1DONE qb1.txt 2>/dev/null; do sleep 20; done
B="$(cat v55toggles.txt),QUEEN_SPLIT_ROUND=200,QUEEN_LEAD_BONUS=1000,QUEEN_LEAD_LATE=true,QUEEN_QUIET_ROUND=100,QUEEN_GAME_FEED_ROUND=300"
export PATH=$PWD/bc123/bin:$PATH NOSANDBOX=1 FAST=1 DIST=1 WORKERS=4
V1="H4@snap47:$B,QUEEN_HUNT=true,QUEEN_HUNT_MAX_LEN=4"
V2="H4K@snap47:$B,QUEEN_HUNT=true,QUEEN_HUNT_MAX_LEN=4,QUEEN_KEEP=4"
V3="H4KG@snap47:$B,QUEEN_HUNT=true,QUEEN_HUNT_MAX_LEN=4,QUEEN_KEEP=4,QUEEN_GIVE_WAY=3"
SEED0=3000 python3 ab3.py "$(cat sqfull.txt)" v53 2 qb2d.json "$V1" "$V2" "$V3" > qb2.txt 2>&1
python3 paired.py qk3d.json QSR200 qb2d.json >> qb2.txt
SEED0=3000 python3 ab3.py "$(cat heldset_sq.txt)" v53 2 qb2h.json "$V1" "$V2" "$V3" >> qb2.txt 2>&1
python3 paired.py qk3h.json QSR200 qb2h.json >> qb2.txt
SEED0=3000 python3 ab3.py "$(cat freshset.txt)" v53 2 qb2f.json "$V1" "$V2" "$V3" >> qb2.txt 2>&1
python3 paired.py qk3f.json QSR200 qb2f.json >> qb2.txt
echo QB2DONE >> qb2.txt
