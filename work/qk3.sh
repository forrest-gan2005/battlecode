cd /Users/UNSW/battlecode/work
B=$(cat v55toggles.txt)
export PATH=$PWD/bc123/bin:$PATH NOSANDBOX=1 FAST=1 DIST=1 WORKERS=4
SEED0=3000 python3 ab3.py "$(cat heldset_sq.txt)" v53 2 qk3h.json "V55@v55:" "QSR100@snap41:$B,QUEEN_SPLIT_ROUND=100" "QSR200@snap41:$B,QUEEN_SPLIT_ROUND=200" > qk3.txt 2>&1
SEED0=3000 python3 ab3.py "$(cat freshset.txt)" v53 2 qk3f.json "V55@v55:" "QSR100@snap41:$B,QUEEN_SPLIT_ROUND=100" "QSR200@snap41:$B,QUEEN_SPLIT_ROUND=200" >> qk3.txt 2>&1
SEED0=3000 python3 ab3.py "$(cat sqfull.txt)" v53 2 qk3d.json "QSR200@snap41:$B,QUEEN_SPLIT_ROUND=200" >> qk3.txt 2>&1
python3 paired.py qk2d.json V55 qk3d.json >> qk3.txt
echo QK3DONE >> qk3.txt
