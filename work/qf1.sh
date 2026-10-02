cd /Users/quasarpark/meow-loop/work
B="$(cat v60toggles.txt)"
export PATH=$PWD/bc123/bin:$PATH NOSANDBOX=1 FAST=1 DIST=1 WORKERS=4
SEED0=3000 python3 ab3.py "$(cat newset.txt),$(cat official.txt)" v60 8 qf1o.json "V60@v60:" "AB4@snap50:$B,ALLY_BLOCK_MAX_LEN=4" "AB8@snap50:$B,ALLY_BLOCK_MAX_LEN=8" > qf1.txt 2>&1
echo QF1DONE >> qf1.txt
