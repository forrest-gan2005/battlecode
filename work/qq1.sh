cd /Users/quasarpark/meow-loop/work
B="$(cat v55toggles.txt),QUEEN_SPLIT_ROUND=200,QUEEN_LEAD_BONUS=1000,QUEEN_LEAD_LATE=true"
export PATH=$PWD/bc123/bin:$PATH NOSANDBOX=1 FAST=1 DIST=1 WORKERS=4
V1="QQ60@snap42:$B,QUEEN_QUIET_ROUND=60"
V2="QQ100@snap42:$B,QUEEN_QUIET_ROUND=100"
SEED0=3000 python3 ab3.py "$(cat official.txt)" v56 8 qq1o.json "$V1" "$V2" > qq1.txt 2>&1
python3 paired.py lf2o.json V56 qq1o.json >> qq1.txt
SEED0=3000 python3 ab3.py "$(cat sqfull.txt)" v53 2 qq1d.json "$V1" "$V2" >> qq1.txt 2>&1
python3 paired.py qk3d.json QSR200 qq1d.json >> qq1.txt
SEED0=3000 python3 ab3.py "$(cat heldset_sq.txt)" v53 2 qq1h.json "$V1" "$V2" >> qq1.txt 2>&1
python3 paired.py qk3h.json QSR200 qq1h.json >> qq1.txt
SEED0=3000 python3 ab3.py "$(cat freshset.txt)" v53 2 qq1f.json "$V1" "$V2" >> qq1.txt 2>&1
python3 paired.py qk3f.json QSR200 qq1f.json >> qq1.txt
echo QQ1DONE >> qq1.txt
