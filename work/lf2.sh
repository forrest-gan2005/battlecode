cd /Users/UNSW/battlecode/work
B="$(cat v55toggles.txt),QUEEN_SPLIT_ROUND=200"
export PATH=$PWD/bc123/bin:$PATH NOSANDBOX=1 FAST=1 DIST=1 WORKERS=4
V1="F400@snap41:$B,QUEEN_LEAD_BONUS=1000,QUEEN_LEAD_LATE=true"
V2="F300@snap41:$B,QUEEN_LEAD_BONUS=1000,QUEEN_LEAD_ROUND=300"
SEED0=3000 python3 ab3.py "$(cat official.txt)" v56 8 lf2o.json "V56@v56:" "$V1" "$V2" > lf2.txt 2>&1
SEED0=3000 python3 ab3.py "$(cat sqfull.txt)" v53 2 lf2d.json "$V1" "$V2" >> lf2.txt 2>&1
python3 paired.py qk3d.json QSR200 lf2d.json >> lf2.txt
SEED0=3000 python3 ab3.py "$(cat heldset_sq.txt)" v53 2 lf2h.json "$V1" "$V2" >> lf2.txt 2>&1
python3 paired.py qk3h.json QSR200 lf2h.json >> lf2.txt
SEED0=3000 python3 ab3.py "$(cat freshset.txt)" v53 2 lf2f.json "$V1" "$V2" >> lf2.txt 2>&1
python3 paired.py qk3f.json QSR200 lf2f.json >> lf2.txt
echo LF2DONE >> lf2.txt
