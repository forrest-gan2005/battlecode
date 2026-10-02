cd /Users/quasarpark/meow-loop/work
B="$(cat v55toggles.txt),QUEEN_SPLIT_ROUND=200,QUEEN_LEAD_BONUS=1000,QUEEN_LEAD_LATE=true,QUEEN_QUIET_ROUND=100"
export PATH=$PWD/bc123/bin:$PATH NOSANDBOX=1 FAST=1 DIST=1 WORKERS=4
V1="RT05@snap43:$B,RATE_EXP=0.5"
V2="RT10@snap43:$B,RATE_EXP=1.0"
V3="HOTW@snap43:$B,HOT_TIMER=10,HOT_MAX_GAP=60,HOT_FALSE_TIMER=60"
SEED0=3000 python3 ab3.py "$(cat official.txt)" v57 8 rt1o.json "V57@v57:" "$V1" "$V2" "$V3" > rt1.txt 2>&1
SEED0=3000 python3 ab3.py "$(cat sqfull.txt)" v53 2 rt1d.json "$V1" "$V2" "$V3" >> rt1.txt 2>&1
python3 paired.py qk3d.json QSR200 rt1d.json >> rt1.txt
SEED0=3000 python3 ab3.py "$(cat heldset_sq.txt)" v53 2 rt1h.json "$V1" "$V2" "$V3" >> rt1.txt 2>&1
python3 paired.py qk3h.json QSR200 rt1h.json >> rt1.txt
SEED0=3000 python3 ab3.py "$(cat freshset.txt)" v53 2 rt1f.json "$V1" "$V2" "$V3" >> rt1.txt 2>&1
python3 paired.py qk3f.json QSR200 rt1f.json >> rt1.txt
echo RT1DONE >> rt1.txt
