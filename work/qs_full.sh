#!/bin/bash
# Full outcome A/B for QUEEN_STRIDE, same sets as the card loop:
# held (heldset_sq + freshset) x2, their transposed copies x2, old 10 maps x8.
# Base = main at fa61861 (checked out into a worktree), opponent = base.
# usage: cd work && WORKERS=10 ./qs_full.sh
set -e
cd "$(dirname "$0")"
ROOT=$(cd .. && pwd)
REF=$ROOT/refmain_wt
[ -d "$REF" ] || git -C "$ROOT" worktree add "$REF" fa618613c2dba9292ec1311a7897b46635965dac
export SEED0=${SEED0:-3000} WORKERS=${WORKERS:-8}
mkdir -p "$ROOT/loop_maps"
python3 - <<'EOF'
import sys, os
sys.path.insert(0, '.'); sys.path.insert(0, 'loop')
import ab2, jobs
held = []
for name in ('heldset_sq.txt', 'freshset.txt'):
    held += [x.strip() for x in open(name).read().split(',') if x.strip()]
for m in dict.fromkeys(held):
    out = os.path.join(ab2.ROOT, 'loop_maps', m + '_T.map')
    if not os.path.exists(out):
        open(out, 'w').write(jobs.transpose(open(ab2.mp(m)).read()))
EOF
grep -q "'loop_maps', " ab2.py || sed -i.bak "s/MAP_DIRS = \[/MAP_DIRS = ['loop_maps', /" ab2.py
HELD=$(python3 -c "print(','.join(dict.fromkeys(x.strip() for f in ('heldset_sq.txt','freshset.txt') for x in open(f).read().split(',') if x.strip())))")
HELDT=$(python3 -c "print(','.join(m+'_T' for m in '$HELD'.split(',')))")
OLD=default,trauma,queen_of_spades,schooltime,portals_v0,slithery_fight_v0,autarky_v0,devil_v0,prisoners_dilemma_v0,trophy
python3 ab3.py "$HELD" refmain_wt/mybot2 2 qs_held.json "B@$REF/mybot2:" "QS@mybot2:QUEEN_STRIDE=true"
python3 ab3.py "$HELDT" refmain_wt/mybot2 2 qs_trans.json "B@$REF/mybot2:" "QS@mybot2:QUEEN_STRIDE=true"
python3 ab3.py "$OLD" refmain_wt/mybot2 8 qs_old10.json "B@$REF/mybot2:" "QS@mybot2:QUEEN_STRIDE=true"
for f in qs_held qs_trans qs_old10; do echo "== $f"; python3 paired.py $f.json B $f.json; done
