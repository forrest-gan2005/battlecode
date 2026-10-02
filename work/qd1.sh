cd /Users/UNSW/battlecode/work
B="$(cat v55toggles.txt),QUEEN_SPLIT_ROUND=200,QUEEN_LEAD_BONUS=1000,QUEEN_LEAD_LATE=true,QUEEN_QUIET_ROUND=100,QUEEN_GAME_FEED_ROUND=300"
export PATH=$PWD/bc123/bin:$PATH NOSANDBOX=1 FAST=1 DIST=1 WORKERS=4
V1="SF300@snap47:$B,QUEEN_SAFE_ROUND=300,QUEEN_SAFE_SPAN=0"
V2="SS250@snap47:$B,QUEEN_SAFE_ROUND=250,QUEEN_SAFE_SPAN=50"
SEED0=3000 python3 ab3.py "$(cat official.txt)" v58 8 qd1o.json "V58@v58:" "$V1" "$V2" > qd1.txt 2>&1
SEED0=7000 python3 ab3.py "trauma,stronghold,schooltime,big_empty,slithery_fight" v58 16 qd1t.json "V58@v58:" "$V1" "$V2" >> qd1.txt 2>&1
SEED0=3000 python3 ab3.py "$(cat sqfull.txt)" v53 2 qd1d.json "$V1" "$V2" >> qd1.txt 2>&1
python3 paired.py qk3d.json QSR200 qd1d.json >> qd1.txt
SEED0=3000 python3 ab3.py "$(cat heldset_sq.txt)" v53 2 qd1h.json "$V1" "$V2" >> qd1.txt 2>&1
python3 paired.py qk3h.json QSR200 qd1h.json >> qd1.txt
SEED0=3000 python3 ab3.py "$(cat freshset.txt)" v53 2 qd1f.json "$V1" "$V2" >> qd1.txt 2>&1
python3 paired.py qk3f.json QSR200 qd1f.json >> qd1.txt
echo QD1DONE >> qd1.txt
