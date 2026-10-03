#!/bin/bash
export PATH=/Users/quasarpark/meow-loop/work/bc127/bin:$PATH NOSANDBOX=1 FAST=1 WORKERS=8
cd /Users/quasarpark/meow-loop/work
R=../loop/results
T=$(cat ../loop/dev/v61toggles.txt)
SEED0=3000 python3 ab3.py "$(cat heldset_sq.txt),$(cat freshset.txt)" v61 2 $R/H14_held.json "SL63@mybot2:$T,SPLIT_SOFT_LIMIT=63" "SL64@mybot2:$T,SPLIT_SOFT_LIMIT=64" > $R/H14_held.log 2>&1
touch $R/H14_done
