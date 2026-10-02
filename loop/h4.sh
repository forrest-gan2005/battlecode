#!/bin/bash
export PATH=/Users/quasarpark/meow-loop/work/bc127/bin:$PATH NOSANDBOX=1 FAST=1 WORKERS=8
cd /Users/quasarpark/meow-loop/work
R=../loop/results
T=$(cat ../loop/dev/v61toggles.txt)
until [ -f $R/H12_done ] || [ -f $R/H12_ident_failed ]; do sleep 30; done
python3 -c "import ab2; ab2.build('B61c', [tuple(kv.split('=')) for kv in '$T'.split(',')], 'mybot2')"
REF=v61 python3 ident.py tune_runs/ab2/B61c > $R/ident_B61c.txt 2>&1
if ! tail -1 $R/ident_B61c.txt | grep -qx identical; then touch $R/H4_ident_failed; exit 1; fi
SEED0=3000 python3 ab3.py "$(cat heldset_sq.txt),$(cat freshset.txt)" v61 2 $R/H4_held.json "TT5@mybot2:$T,CB_TRAP_TRADE=5" "TT5D@mybot2:$T,CB_TRAP_TRADE=5,CB_TRAP_DEAD=true" > $R/H4_held.log 2>&1
SEED0=3000 python3 ab3.py "$(cat official.txt),$(cat newset.txt)" v61 8 $R/H4_main.json "TT5@mybot2:$T,CB_TRAP_TRADE=5" "TT5D@mybot2:$T,CB_TRAP_TRADE=5,CB_TRAP_DEAD=true" > $R/H4_main.log 2>&1
touch $R/H4_done
