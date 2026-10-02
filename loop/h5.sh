#!/bin/bash
export PATH=/Users/quasarpark/meow-loop/work/bc127/bin:$PATH NOSANDBOX=1 FAST=1 WORKERS=8
cd /Users/quasarpark/meow-loop/work
R=../loop/results
T=$(cat ../loop/dev/v61toggles.txt)
until [ -f $R/mech_done ]; do sleep 30; done
while [ -f $R/HOLD_H5 ]; do sleep 30; done
SEED0=3000 python3 ab3.py "$(cat heldset_sq.txt),$(cat freshset.txt)" v61 2 $R/H5_held.json "TM4@mybot2:$T,TRADE_MIN_UNITS=4" "TM1@mybot2:$T,TRADE_MIN_UNITS=1" > $R/H5_held.log 2>&1
SEED0=3000 python3 ab3.py "$(cat official.txt),$(cat newset.txt)" v61 8 $R/H5_main.json "TM4@mybot2:$T,TRADE_MIN_UNITS=4" "TM1@mybot2:$T,TRADE_MIN_UNITS=1" > $R/H5_main.log 2>&1
touch $R/H5_done
