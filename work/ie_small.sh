#!/bin/bash
# Small A/B for IDLE_EXIT (20 and 40) vs main (fa61861): old 10 + 7 new maps x4 games, plus tower_defense x16.
# usage: cd work && WORKERS=10 ./ie_small.sh
set -e
cd "$(dirname "$0")"
ROOT=$(cd .. && pwd)
REF=$ROOT/refmain_wt
[ -d "$REF" ] || git -C "$ROOT" worktree add "$REF" fa618613c2dba9292ec1311a7897b46635965dac
export SEED0=${SEED0:-3000} WORKERS=${WORKERS:-8} KEEP=1
MAPS=default,trauma,queen_of_spades,schooltime,portals_v0,slithery_fight_v0,autarky_v0,devil_v0,prisoners_dilemma_v0,trophy,around_unsw,australia,islands,maze,stripes,tower_defense,weakhold
python3 ab3.py "$MAPS" refmain_wt/mybot2 4 ie_main.json "B@$REF/mybot2:" "IE20@mybot2:IDLE_EXIT=20" "IE40@mybot2:IDLE_EXIT=40"
SEED0=4000 python3 ab3.py tower_defense refmain_wt/mybot2 16 ie_td.json "B@$REF/mybot2:" "IE20@mybot2:IDLE_EXIT=20" "IE40@mybot2:IDLE_EXIT=40"
python3 paired.py ie_main.json B ie_main.json
python3 paired.py ie_td.json B ie_td.json
