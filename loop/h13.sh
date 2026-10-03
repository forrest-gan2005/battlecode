#!/bin/bash
export PATH=/Users/quasarpark/meow-loop/work/bc127/bin:$PATH NOSANDBOX=1 FAST=1 WORKERS=8
cd /Users/quasarpark/meow-loop/work
R=../loop/results
T=$(cat ../loop/dev/v61toggles.txt)
until [ -f $R/H12s_done ]; do sleep 30; done
SEED0=3000 python3 ab3.py "$(cat heldset_sq.txt),$(cat freshset.txt)" v61 2 $R/H13_held.json "TT4@mybot2:$T,TR_TIGHT_BALL=12,TR_TIGHT_PENALTY=400.0" "TT8@mybot2:$T,TR_TIGHT_BALL=12,TR_TIGHT_PENALTY=800.0" > $R/H13_held.log 2>&1
touch $R/H13_done
