#!/bin/bash
# QUEEN_SPIN A/B on big maps only (> 1200 cells: 6 official + 35 held/fresh large), vs main (fa61861) and a queen hunter.
# usage: cd work && WORKERS=10 ./qsp_big.sh
set -e
cd "$(dirname "$0")"
ROOT=$(cd .. && pwd)
REF=$ROOT/refmain_wt
[ -d "$REF" ] || git -C "$ROOT" worktree add "$REF" fa618613c2dba9292ec1311a7897b46635965dac
export SEED0=${SEED0:-3000} WORKERS=${WORKERS:-8} KEEP=1
python3 -c "import ab2; ab2.build('HQ', [('QUEEN_HUNT','true'), ('QUEEN_CHASE_DIST','8')], '$REF/mybot2')"
BIG=big_empty,schooltime,slithery_fight,around_unsw,australia,islands,sqheld_blobs_large_90009,sqheld_blobs_large_90030,sqheld_open_large_90036,sqheld_portalrooms_large_90001,sqheld_portalrooms_large_90003,sqheld_portalrooms_large_90005,sqheld_portalrooms_large_90006,sqheld_portalrooms_large_90013,sqheld_portalrooms_large_90024,sqheld_portalrooms_large_90031,sqheld_portals_large_90008,sqheld_portals_large_90010,sqheld_portals_large_90016,sqheld_portals_large_90037,sqheld_portals_large_90043,sqheld_portals_large_90044,sqheld_rooms_large_90035,sqheld_stripes_large_90002,sqheld_stripes_large_90041,fresh_gen_blobs_large_70001,fresh_gen_blobs_large_70005,fresh_gen_blobs_large_70009,fresh_gen_rooms_large_70011,fresh_gen_blobs_large_70012,fresh_gen_rooms_large_70016,fresh_gen_maze_large_70024,fresh_gen_blobs_large_70042,fresh_gen_rooms_large_70045,fresh_gen_blobs_large_70053,fresh_gen_rooms_large_70054,fresh_gen_blobs_large_70055,fresh_gen_maze_large_70056,fresh_gen_rooms_large_70061,fresh_gen_blobs_large_70064,fresh_gen_open_medium_70065
python3 ab3.py "$BIG" refmain_wt/mybot2 2 qsp_main.json "B@$REF/mybot2:" "SP@mybot2:QUEEN_SPIN=true"
python3 ab3.py "$BIG" tune_runs/ab2/HQ 2 qsp_hunt.json "BH@$REF/mybot2:" "SPH@mybot2:QUEEN_SPIN=true"
python3 paired.py qsp_main.json B qsp_main.json
python3 paired.py qsp_hunt.json BH qsp_hunt.json
python3 qsmech.py B SP BH SPH
