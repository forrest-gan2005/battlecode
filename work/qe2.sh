cd /Users/quasarpark/meow-loop/work
B="$(cat v59toggles.txt)"
export PATH=$PWD/bc123/bin:$PATH NOSANDBOX=1 FAST=1 DIST=1 WORKERS=4
SEED0=1000 python3 ab3.py "$(cat newset.txt),$(cat official.txt)" v59 8 qe2o.json "V59@v59:" "FG2@snap49:$B,FAR_GAIN=2" "FG15@snap49:$B,FAR_GAIN=1.5" > qe2.txt 2>&1
SEED0=5000 python3 ab3.py "$(cat heldset_sq.txt)" v53 2 qe2h.json "V59@v59:" "FG2@snap49:$B,FAR_GAIN=2" >> qe2.txt 2>&1
SEED0=5000 python3 ab3.py "$(cat freshset.txt)" v53 2 qe2f.json "V59@v59:" "FG2@snap49:$B,FAR_GAIN=2" >> qe2.txt 2>&1
echo QE2DONE >> qe2.txt
