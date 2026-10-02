cd /Users/quasarpark/meow-loop/work
B=$(cat v55toggles.txt)
export PATH=$PWD/bc123/bin:$PATH NOSANDBOX=1 FAST=1 DIST=1 WORKERS=4
SEED0=1000 python3 ab3.py "$(cat official.txt)" v55 8 be1o.json "BE8@snap39:$B,BIG_ESCAPE_STEPS=8" "BE12@snap39:$B,BIG_ESCAPE_STEPS=12" > be1.txt 2>&1
python3 paired.py lf1o.json V55 be1o.json >> be1.txt
SEED0=700 python3 ab3.py "$(cat sqfull.txt)" v53 2 be1d.json "BE8@snap39:$B,BIG_ESCAPE_STEPS=8" "BE12@snap39:$B,BIG_ESCAPE_STEPS=12" >> be1.txt 2>&1
python3 paired.py qc6d.json QMC be1d.json >> be1.txt
SEED0=900 python3 ab3.py "$(cat heldset_sq.txt)" v53 2 be1h.json "BE8@snap39:$B,BIG_ESCAPE_STEPS=8" "BE12@snap39:$B,BIG_ESCAPE_STEPS=12" >> be1.txt 2>&1
python3 paired.py qc6h.json QMC be1h.json >> be1.txt
echo BE1DONE >> be1.txt
