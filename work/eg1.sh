cd /Users/UNSW/battlecode/work
until grep -q "SY1DONE" sy1.txt 2>/dev/null; do sleep 20; done
B=$(cat v55toggles.txt)
export PATH=$PWD/bc123/bin:$PATH NOSANDBOX=1 FAST=1 DIST=1 WORKERS=4
SEED0=1000 python3 ab3.py "$(cat official.txt)" v55 8 eg1o.json "E350@snap36:$B,ENDGAME_ROUND=350" "E450@snap36:$B,ENDGAME_ROUND=450" > eg1.txt 2>&1
python3 paired.py lf1o.json V55 eg1o.json >> eg1.txt
SEED0=700 python3 ab3.py "$(cat sqfull.txt)" v53 2 eg1d.json "E350@snap36:$B,ENDGAME_ROUND=350" "E450@snap36:$B,ENDGAME_ROUND=450" >> eg1.txt 2>&1
python3 paired.py qc6d.json QMC eg1d.json >> eg1.txt
echo EG1DONE >> eg1.txt
