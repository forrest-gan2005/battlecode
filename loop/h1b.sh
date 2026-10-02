#!/bin/bash
export PATH=/Users/quasarpark/meow-loop/work/bc127/bin:$PATH NOSANDBOX=1 FAST=1 WORKERS=8
cd /Users/quasarpark/meow-loop/work
R=../loop/results
T=$(cat ../loop/dev/v61toggles.txt)
until [ -f $R/H5_done ]; do sleep 30; done
while [ -f $R/HOLD_H1B ]; do sleep 30; done
SEED0=3000 python3 ab3.py "$(cat heldset_sq.txt),$(cat freshset.txt)" v61 2 $R/H1b_held.json "PD2@mybot2:$T,TR_PRESS_ROOM=3,TR_PRESS_DEPTH=2" "PD4@mybot2:$T,TR_PRESS_ROOM=3,TR_PRESS_DEPTH=4" > $R/H1b_held.log 2>&1
SEED0=3000 python3 ab3.py "$(cat official.txt),$(cat newset.txt)" v61 8 $R/H1b_main.json "PD2@mybot2:$T,TR_PRESS_ROOM=3,TR_PRESS_DEPTH=2" "PD4@mybot2:$T,TR_PRESS_ROOM=3,TR_PRESS_DEPTH=4" > $R/H1b_main.log 2>&1
touch $R/H1b_done
