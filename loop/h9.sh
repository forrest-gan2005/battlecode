#!/bin/bash
export PATH=/Users/quasarpark/meow-loop/work/bc127/bin:$PATH NOSANDBOX=1 FAST=1 WORKERS=8
cd /Users/quasarpark/meow-loop/work
R=../loop/results
T=$(cat ../loop/dev/v61toggles.txt)
until [ -f $R/H8_done ]; do sleep 30; done
while [ -f $R/HOLD_H9 ]; do sleep 30; done
SEED0=3000 python3 ab3.py "$(cat heldset_sq.txt),$(cat freshset.txt)" v61 2 $R/H9_held.json "TE@mybot2:$T,TRADE_EVEN=true" > $R/H9_held.log 2>&1
touch $R/H9_done
