cd /Users/quasarpark/meow-loop/work
B="$(cat v60toggles.txt)"
export PATH=$PWD/bc123/bin:$PATH NOSANDBOX=1 FAST=1 DIST=1 WORKERS=4
SEED0=3000 python3 ab3.py "$(cat newset.txt),$(cat official.txt)" v60 8 qg1o.json "V60@v60:" "PK48@snap51:$B,POCKET_CAP=48" "PK48D3@snap51:$B,POCKET_CAP=48,POCKET_DIV=3" "PK32@snap51:$B,POCKET_CAP=32" > qg1.txt 2>&1
echo QG1DONE >> qg1.txt
