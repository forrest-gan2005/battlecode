#!/bin/bash
export PATH=/Users/quasarpark/meow-loop/work/bc127/bin:$PATH NOSANDBOX=1 FAST=1 WORKERS=8
cd /Users/quasarpark/meow-loop/work
R=../loop/results
T=$(cat ../loop/dev/v61toggles.txt)
until [ -f $R/H9_done ]; do sleep 30; done
SEED0=5000 python3 ab3.py "$(cat heldset_sq.txt),$(cat freshset.txt)" v61 2 $R/H8b_held5.json "SL62@mybot2:$T,SPLIT_SOFT_LIMIT=62" > $R/H8b_held5.log 2>&1
touch $R/H8b_done
rm -f $R/HOLD_H10
