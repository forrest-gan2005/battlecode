#!/bin/bash
export PATH=/Users/quasarpark/meow-loop/work/bc127/bin:$PATH NOSANDBOX=1 WORKERS=8 KEEP=1
unset FAST
cd /Users/quasarpark/meow-loop/work
R=../loop/results
T=$(cat ../loop/dev/v61toggles.txt)
until [ -f $R/H4_done ] || [ -f $R/H4_ident_failed ] || [ -f $R/H12_ident_failed ]; do sleep 30; done
rm -f ab2/MB61_* ab2/MPR3_* ab2/MSR2_* ab2/MTT5_* ab2/MTT5D_*
SEED0=7000 python3 ab3.py "$(cat ../loop/dev/mechset.txt)" v61 4 $R/mech.json "MB61@mybot2:$T" "MPR3@mybot2:$T,TR_PRESS_ROOM=3" "MSR2@mybot2:$T,SMALL_UNIT_THREAT_REACH=2" "MTT5@mybot2:$T,CB_TRAP_TRADE=5" "MTT5D@mybot2:$T,CB_TRAP_TRADE=5,CB_TRAP_DEAD=true" > $R/mech.log 2>&1
python3 ../loop/tools/press.py 'ab2/MB61_*.replay' 'ab2/MPR3_*.replay' 'ab2/MSR2_*.replay' 'ab2/MTT5_*.replay' 'ab2/MTT5D_*.replay' > $R/mech_press.txt 2>&1
touch $R/mech_done
