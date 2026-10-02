cd /Users/UNSW/battlecode/work
until grep -q QG2DONE qg2.txt 2>/dev/null; do sleep 20; done
B="$(cat v60toggles.txt),POCKET_CAP=48"
export PATH=$PWD/bc123/bin:$PATH NOSANDBOX=1 FAST=1 DIST=1 WORKERS=4
V2="C2@snap53:$B,CENTER_PULL=0"
V3="C3@snap53:$B,CENTER_PULL=0,NO_TAIL_ROOM=6"
SEED0=3000 python3 ab3.py "$(cat newset.txt),$(cat official.txt)" v60 8 qh1o.json "$V2" "$V3" > qh1.txt 2>&1
python3 paired.py qg1o.json PK48 qh1o.json >> qh1.txt
SEED0=3000 python3 ab3.py "$(cat sqfull.txt)" v53 2 qh1d.json "$V2" "$V3" >> qh1.txt 2>&1
python3 paired.py qg2d.json PK48 qh1d.json >> qh1.txt
SEED0=3000 python3 ab3.py "$(cat heldset_sq.txt)" v53 2 qh1h.json "$V2" "$V3" >> qh1.txt 2>&1
python3 paired.py qg2h.json PK48 qh1h.json >> qh1.txt
SEED0=3000 python3 ab3.py "$(cat freshset.txt)" v53 2 qh1f.json "$V2" "$V3" >> qh1.txt 2>&1
python3 paired.py qg2f.json PK48 qh1f.json >> qh1.txt
echo QH1DONE >> qh1.txt
