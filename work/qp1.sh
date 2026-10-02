cd /Users/UNSW/battlecode/work
B=$(cat v55toggles.txt)
export PATH=$PWD/bc123/bin:$PATH NOSANDBOX=1 FAST=1 DIST=1 WORKERS=4
SEED0=1000 python3 ab3.py "$(cat official.txt)" v55 8 qp1o.json "QP30@snap38:$B,QUEEN_PORTAL_ROUND=30" "QP15@snap38:$B,QUEEN_PORTAL_ROUND=15" > qp1.txt 2>&1
python3 paired.py lf1o.json V55 qp1o.json >> qp1.txt
SEED0=700 python3 ab3.py "$(cat sqfull.txt)" v53 2 qp1d.json "QP30@snap38:$B,QUEEN_PORTAL_ROUND=30" "QP15@snap38:$B,QUEEN_PORTAL_ROUND=15" >> qp1.txt 2>&1
python3 paired.py qc6d.json QMC qp1d.json >> qp1.txt
SEED0=900 python3 ab3.py "$(cat heldset_sq.txt)" v53 2 qp1h.json "QP30@snap38:$B,QUEEN_PORTAL_ROUND=30" "QP15@snap38:$B,QUEEN_PORTAL_ROUND=15" >> qp1.txt 2>&1
python3 paired.py qc6h.json QMC qp1h.json >> qp1.txt
echo QP1DONE >> qp1.txt
