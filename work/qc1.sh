cd /Users/UNSW/battlecode/work
B="$(cat v55toggles.txt),QUEEN_SPLIT_ROUND=200,QUEEN_LEAD_BONUS=1000,QUEEN_LEAD_LATE=true,QUEEN_QUIET_ROUND=100,QUEEN_GAME_FEED_ROUND=300"
export PATH=$PWD/bc123/bin:$PATH NOSANDBOX=1 FAST=1 DIST=1 WORKERS=4
SEED0=1000 python3 ab3.py "$(cat official.txt)" v57 8 qc1o.json "V57@v57:" "QF3@snap47:$B" > qcf.txt 2>&1
SEED0=7000 python3 ab3.py "trauma,stronghold,portals,schooltime,big_empty" v57 16 qc1t.json "V57@v57:" "QF3@snap47:$B" >> qcf.txt 2>&1
echo QCFDONE >> qcf.txt
