#!/bin/bash
export PATH=/Users/quasarpark/meow-loop/work/bc127/bin:$PATH NOSANDBOX=1 FAST=1 WORKERS=8
cd /Users/quasarpark/meow-loop/work
R=../loop/results
T=$(cat ../loop/dev/v61toggles.txt)
until [ -f $R/H5_done ]; do sleep 30; done
while [ -f $R/HOLD_H7 ]; do sleep 30; done
SEED0=3000 python3 ab3.py "$(cat heldset_sq.txt),$(cat freshset.txt)" v61 2 $R/H7_held.json "ES225@mybot2:$T,EC_SPLIT_ROUND_BIG=225" "ES300@mybot2:$T,EC_SPLIT_ROUND_BIG=300" > $R/H7_held.log 2>&1
SEED0=3000 python3 ab3.py "$(cat official.txt),$(cat newset.txt)" v61 8 $R/H7_main.json "ES225@mybot2:$T,EC_SPLIT_ROUND_BIG=225" "ES300@mybot2:$T,EC_SPLIT_ROUND_BIG=300" > $R/H7_main.log 2>&1
touch $R/H7_done
rm -f $R/HOLD_H1B
