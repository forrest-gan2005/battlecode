cd /Users/UNSW/battlecode/work
until grep -q "EG1DONE" eg1.txt 2>/dev/null; do sleep 20; done
B=$(cat v55toggles.txt)
export PATH=$PWD/bc123/bin:$PATH NOSANDBOX=1 FAST=1 DIST=1 WORKERS=4
SEED0=1000 python3 ab3.py "$(cat official.txt)" v55 8 cap1o.json "CAP@snap37:$B,SURVEY_CAP=2500" > cap1.txt 2>&1
python3 paired.py lf1o.json V55 cap1o.json >> cap1.txt
SEED0=700 python3 ab3.py "$(cat sqfull.txt)" v53 2 cap1d.json "CAP@snap37:$B,SURVEY_CAP=2500" >> cap1.txt 2>&1
python3 paired.py qc6d.json QMC cap1d.json >> cap1.txt
SEED0=900 python3 ab3.py "$(cat heldset_sq.txt)" v53 2 cap1h.json "CAP@snap37:$B,SURVEY_CAP=2500" >> cap1.txt 2>&1
python3 paired.py qc6h.json QMC cap1h.json >> cap1.txt
SEED0=1100 python3 ab3.py "huge_open_96,huge_wide_128" v55 4 cap1g.json "V55@v55:" "CAP@snap37:$B,SURVEY_CAP=2500" >> cap1.txt 2>&1
echo CAP1DONE >> cap1.txt
