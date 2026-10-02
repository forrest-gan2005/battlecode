cd /Users/UNSW/battlecode/work
B="$(cat v59toggles.txt)"
export PATH=$PWD/bc123/bin:$PATH NOSANDBOX=1 FAST=1 DIST=1 WORKERS=4
V1="FG2@snap49:$B,FAR_GAIN=2"
V2="FG3@snap49:$B,FAR_GAIN=3"
V3="FG6@snap49:$B,FAR_GAIN=6"
SEED0=3000 python3 ab3.py "$(cat newset.txt)" v59 8 qe1n.json "V59@v59:" "$V1" "$V2" "$V3" > qe1.txt 2>&1
SEED0=3000 python3 ab3.py "$(cat official.txt)" v59 8 qe1o.json "V59@v59:" "$V1" "$V2" "$V3" >> qe1.txt 2>&1
SEED0=3000 python3 ab3.py "$(cat sqfull.txt)" v53 2 qe1d.json "$V1" "$V2" "$V3" >> qe1.txt 2>&1
python3 paired.py qd1d.json SF300 qe1d.json >> qe1.txt
SEED0=3000 python3 ab3.py "$(cat heldset_sq.txt)" v53 2 qe1h.json "$V1" "$V2" "$V3" >> qe1.txt 2>&1
python3 paired.py qd1h.json SF300 qe1h.json >> qe1.txt
SEED0=3000 python3 ab3.py "$(cat freshset.txt)" v53 2 qe1f.json "$V1" "$V2" "$V3" >> qe1.txt 2>&1
python3 paired.py qd1f.json SF300 qe1f.json >> qe1.txt
echo QE1DONE >> qe1.txt
