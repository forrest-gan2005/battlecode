#!/bin/bash
export PATH=/Users/quasarpark/meow-loop/work/bc127/bin:$PATH NOSANDBOX=1 FAST=1 WORKERS=8
cd /Users/quasarpark/meow-loop/work
R=../loop/results
T=$(cat ../loop/dev/v61toggles.txt)
until [ -f $R/H10_done ]; do sleep 30; done
SEED0=7000 python3 ab3.py "$(cat heldset_sq.txt),$(cat freshset.txt)" v61 2 $R/H8c_held7.json "B61@mybot2:$T" "SL62@mybot2:$T,SPLIT_SOFT_LIMIT=62" > $R/H8c_held7.log 2>&1
touch $R/H8c_done
