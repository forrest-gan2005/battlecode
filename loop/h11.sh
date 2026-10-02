#!/bin/bash
export PATH=/Users/quasarpark/meow-loop/work/bc127/bin:$PATH NOSANDBOX=1 FAST=1 WORKERS=8
cd /Users/quasarpark/meow-loop/work
R=../loop/results
T=$(cat ../loop/dev/v61toggles.txt)
until [ -f $R/H8c_done ]; do sleep 30; done
SEED0=3000 python3 ab3.py "$(cat heldset_sq.txt),$(cat freshset.txt)" v61 2 $R/H11_held.json "CS0@mybot2:$T,CONTEST_SLACK=0" "CS2@mybot2:$T,CONTEST_SLACK=2" > $R/H11_held.log 2>&1
touch $R/H11_done
