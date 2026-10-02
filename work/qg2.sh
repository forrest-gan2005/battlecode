cd /Users/quasarpark/meow-loop/work
B="$(cat v60toggles.txt)"
export PATH=$PWD/bc123/bin:$PATH NOSANDBOX=1 FAST=1 DIST=1 WORKERS=4
V="PK48@snap52:$B,POCKET_CAP=48"
SEED0=3000 python3 ab3.py "$(cat sqfull.txt)" v53 2 qg2d.json "$V" > qg2.txt 2>&1
python3 paired.py qe1d.json FG2 qg2d.json >> qg2.txt
SEED0=3000 python3 ab3.py "$(cat heldset_sq.txt)" v53 2 qg2h.json "$V" >> qg2.txt 2>&1
python3 paired.py qe1h.json FG2 qg2h.json >> qg2.txt
SEED0=3000 python3 ab3.py "$(cat freshset.txt)" v53 2 qg2f.json "$V" >> qg2.txt 2>&1
python3 paired.py qe1f.json FG2 qg2f.json >> qg2.txt
echo QG2DONE >> qg2.txt
