#!/bin/bash
export PATH=/Users/quasarpark/meow-loop/work/bc127/bin:$PATH NOSANDBOX=1 FAST=1 WORKERS=8
cd /Users/quasarpark/meow-loop/work
R=../loop/results
T=$(cat ../loop/dev/v61toggles.txt)
until [ -f $R/H1b_done ]; do sleep 30; done
while [ -f $R/HOLD_H8 ]; do sleep 30; done
SEED0=5000 python3 ab3.py "$(cat heldset_sq.txt),$(cat freshset.txt)" v61 2 $R/H7b_held5.json "B61@mybot2:$T" "ES300@mybot2:$T,EC_SPLIT_ROUND_BIG=300" > $R/H7b_held5.log 2>&1
SEED0=3000 python3 ab3.py "$(cat heldset_sq.txt),$(cat freshset.txt)" v61 2 $R/H8_held.json "SL62@mybot2:$T,SPLIT_SOFT_LIMIT=62" > $R/H8_held.log 2>&1
touch $R/H8_done
