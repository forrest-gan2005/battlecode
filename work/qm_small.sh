#!/bin/bash
# Small A/B for QUEEN_MARGIN (margin 2 and 3) vs main (fa61861) and a queen-hunting spar, all map sizes.
# usage: cd work && WORKERS=10 ./qm_small.sh
set -e
cd "$(dirname "$0")"
ROOT=$(cd .. && pwd)
REF=$ROOT/refmain_wt
[ -d "$REF" ] || git -C "$ROOT" worktree add "$REF" fa618613c2dba9292ec1311a7897b46635965dac
export SEED0=${SEED0:-3000} WORKERS=${WORKERS:-8} KEEP=1
python3 -c "import ab2; ab2.build('HQ', [('QUEEN_HUNT','true'), ('QUEEN_CHASE_DIST','8')], '$REF/mybot2')"
MAPS=default,trauma,queen_of_spades,schooltime,portals_v0,slithery_fight_v0,autarky_v0,devil_v0,prisoners_dilemma_v0,trophy,around_unsw,australia,islands,maze,stripes,tower_defense,weakhold
python3 ab3.py "$MAPS" refmain_wt/mybot2 4 qm_main.json "B@$REF/mybot2:" "QM2@mybot2:QUEEN_MARGIN=true" "QM3@mybot2:QUEEN_MARGIN=true,QM_MARGIN=3"
python3 ab3.py "$MAPS" tune_runs/ab2/HQ 4 qm_hunt.json "BH@$REF/mybot2:" "QM2H@mybot2:QUEEN_MARGIN=true" "QM3H@mybot2:QUEEN_MARGIN=true,QM_MARGIN=3"
python3 paired.py qm_main.json B qm_main.json
python3 paired.py qm_hunt.json BH qm_hunt.json
python3 qsmech.py B QM2 QM3 BH QM2H QM3H
