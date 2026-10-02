cd /Users/UNSW/battlecode/work
B="$(cat v55toggles.txt),QUEEN_SPLIT_ROUND=200,QUEEN_LEAD_BONUS=1000,QUEEN_LEAD_LATE=true,QUEEN_QUIET_ROUND=100"
export PATH=$PWD/bc123/bin:$PATH NOSANDBOX=1 FAST=1 DIST=1 WORKERS=4
V1="PA@snap45:$B,QUEEN_PORTAL_ALL=true"
V2="QF3@snap45:$B,QUEEN_GAME_FEED_ROUND=300"
V3="QS@snap45:$B,QUEEN_GAME_FEED_ROUND=300,QUEEN_SAFE_ROUND=250,QUEEN_SAFE_SPAN=100"
SEED0=3000 python3 ab3.py "$(cat official.txt)" v57 8 qa1o.json "V57@v57:" "$V1" "$V2" "$V3" > qa1.txt 2>&1
SEED0=3000 python3 ab3.py "$(cat sqfull.txt)" v53 2 qa1d.json "$V1" "$V2" "$V3" >> qa1.txt 2>&1
python3 paired.py qk3d.json QSR200 qa1d.json >> qa1.txt
SEED0=3000 python3 ab3.py "$(cat heldset_sq.txt)" v53 2 qa1h.json "$V1" "$V2" "$V3" >> qa1.txt 2>&1
python3 paired.py qk3h.json QSR200 qa1h.json >> qa1.txt
SEED0=3000 python3 ab3.py "$(cat freshset.txt)" v53 2 qa1f.json "$V1" "$V2" "$V3" >> qa1.txt 2>&1
python3 paired.py qk3f.json QSR200 qa1f.json >> qa1.txt
echo QA1DONE >> qa1.txt
