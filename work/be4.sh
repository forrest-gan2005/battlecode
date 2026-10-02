cd /Users/quasarpark/meow-loop/work
B=$(cat v55toggles.txt)
export PATH=$PWD/bc123/bin:$PATH NOSANDBOX=1 FAST=1 DIST=1 WORKERS=4
V1="TR12@snap41:$B,BIG_TRUE_REACH=12"
V2="TRL@snap41:$B,BIG_TRUE_REACH=12,BIG_ESCAPE_STEPS=12,BIG_ESCAPE_LATE=true"
SEED0=1000 python3 ab3.py "$(cat official.txt)" hunt55 8 be4x.json "$V1" "$V2" > be4.txt 2>&1
python3 paired.py be2x.json V55 be4x.json >> be4.txt
SEED0=1000 python3 ab3.py "$(cat official.txt)" v55 8 be4o.json "$V1" "$V2" >> be4.txt 2>&1
python3 paired.py lf1o.json V55 be4o.json >> be4.txt
SEED0=700 python3 ab3.py "$(cat sqfull.txt)" v53 2 be4d.json "$V1" "$V2" >> be4.txt 2>&1
python3 paired.py qc6d.json QMC be4d.json >> be4.txt
SEED0=900 python3 ab3.py "$(cat heldset_sq.txt)" v53 2 be4h.json "$V1" "$V2" >> be4.txt 2>&1
python3 paired.py qc6h.json QMC be4h.json >> be4.txt
echo BE4DONE >> be4.txt
