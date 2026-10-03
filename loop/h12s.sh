#!/bin/bash
export PATH=/Users/quasarpark/meow-loop/work/bc127/bin:$PATH NOSANDBOX=1 FAST=1 WORKERS=8
cd /Users/quasarpark/meow-loop/work
R=../loop/results
T=$(cat ../loop/dev/v61toggles.txt)
until [ -f $R/H11_done ]; do sleep 30; done
SEED0=3000 python3 ab3.py "$(cat heldset_sq.txt),$(cat freshset.txt)" v61 2 $R/H12s_held.json "ST2@mybot2:$T,SMALL_THREAT_MULT=2.0" "ST2O@mybot2:$T,SMALL_THREAT_MULT=2.0,SMALL_THREAT_OUTNUMBERED=true" > $R/H12s_held.log 2>&1
touch $R/H12s_done
