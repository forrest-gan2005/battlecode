#!/bin/bash
export PATH=/Users/quasarpark/meow-loop/work/bc127/bin:$PATH NOSANDBOX=1 FAST=1 WORKERS=8
cd /Users/quasarpark/meow-loop/work
R=../loop/results
T=$(cat ../loop/dev/v61toggles.txt)
SEED0=3000 python3 ab3.py "$(cat heldset_sq.txt),$(cat freshset.txt)" v61 2 $R/H16_held.json "QGK4@mybot2:$T,QUEEN_GUARD_CELLS=1200,QG_KEEP=4" "QGK6@mybot2:$T,QUEEN_GUARD_CELLS=1200,QG_KEEP=6" > $R/H16_held.log 2>&1
touch $R/H16_done
