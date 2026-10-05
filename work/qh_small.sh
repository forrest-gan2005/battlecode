#!/bin/bash
# Small A/B for QUEEN_HOME_LOOP (radius 4 and 6) against main (fa61861) and a queen-hunting spar.
# 17 maps x 2 games vs main, 10 big maps x 2 games vs the hunter; base runs included for pairing.
# usage: cd work && WORKERS=10 ./qh_small.sh
set -e
cd "$(dirname "$0")"
ROOT=$(cd .. && pwd)
REF=$ROOT/refmain_wt
[ -d "$REF" ] || git -C "$ROOT" worktree add "$REF" fa618613c2dba9292ec1311a7897b46635965dac
export SEED0=${SEED0:-3000} WORKERS=${WORKERS:-8} KEEP=1
python3 -c "import ab2; ab2.build('HQ', [('QUEEN_HUNT','true'), ('QUEEN_CHASE_DIST','8')], '$REF/mybot2')"
MAPS=default,trauma,queen_of_spades,schooltime,portals_v0,slithery_fight_v0,autarky_v0,devil_v0,prisoners_dilemma_v0,trophy,around_unsw,australia,islands,maze,stripes,tower_defense,weakhold
BIG=default,trauma,queen_of_spades,schooltime,slithery_fight_v0,autarky_v0,around_unsw,australia,islands,maze
python3 ab3.py "$MAPS" refmain_wt/mybot2 2 qh_main.json "B@$REF/mybot2:" "QH@mybot2:QUEEN_HOME_LOOP=true" "QH6@mybot2:QUEEN_HOME_LOOP=true,QH_RADIUS=6"
python3 ab3.py "$BIG" tune_runs/ab2/HQ 2 qh_hunt.json "BH@$REF/mybot2:" "QHH@mybot2:QUEEN_HOME_LOOP=true" "QH6H@mybot2:QUEEN_HOME_LOOP=true,QH_RADIUS=6"
python3 paired.py qh_main.json B qh_main.json
python3 paired.py qh_hunt.json BH qh_hunt.json
python3 qsmech.py B QH QH6 BH QHH QH6H
