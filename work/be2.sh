cd /Users/UNSW/battlecode/work
B=$(cat v55toggles.txt)
export PATH=$PWD/bc123/bin:$PATH NOSANDBOX=1 FAST=1 DIST=1 WORKERS=4
SEED0=1000 python3 ab3.py "$(cat official.txt)" hunt55 8 be2x.json "V55@v55:" "BEL12@snap40:$B,BIG_ESCAPE_STEPS=12,BIG_ESCAPE_LATE=true" "BE12@snap40:$B,BIG_ESCAPE_STEPS=12" > be2.txt 2>&1
SEED0=1000 python3 ab3.py "$(cat official.txt)" v55 8 be2o.json "BEL12@snap40:$B,BIG_ESCAPE_STEPS=12,BIG_ESCAPE_LATE=true" >> be2.txt 2>&1
python3 paired.py lf1o.json V55 be2o.json >> be2.txt
SEED0=700 python3 ab3.py "$(cat sqfull.txt)" v53 2 be2d.json "BEL12@snap40:$B,BIG_ESCAPE_STEPS=12,BIG_ESCAPE_LATE=true" >> be2.txt 2>&1
python3 paired.py qc6d.json QMC be2d.json >> be2.txt
SEED0=900 python3 ab3.py "$(cat heldset_sq.txt)" v53 2 be2h.json "BEL12@snap40:$B,BIG_ESCAPE_STEPS=12,BIG_ESCAPE_LATE=true" >> be2.txt 2>&1
python3 paired.py qc6h.json QMC be2h.json >> be2.txt
echo BE2DONE >> be2.txt
