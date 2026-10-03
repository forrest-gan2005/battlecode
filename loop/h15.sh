#!/bin/bash
export PATH=/Users/quasarpark/meow-loop/work/bc127/bin:$PATH NOSANDBOX=1 FAST=1 WORKERS=8
cd /Users/quasarpark/meow-loop/work
R=../loop/results
T=$(cat ../loop/dev/v61toggles.txt)
SEED0=3000 python3 ab3.py "$(cat heldset_sq.txt),$(cat freshset.txt)" v61 2 $R/H15_held.json "QG8@mybot2:$T,QUEEN_GUARD_CELLS=800" "QG12@mybot2:$T,QUEEN_GUARD_CELLS=1200" > $R/H15_held.log 2>&1
touch $R/H15_done
