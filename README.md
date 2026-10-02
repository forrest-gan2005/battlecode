# C-- Battlecode bot

## Layout
- `v61/`: the version currently live on the ladder (server label v61). `v60/` is the previous submission.
- `mybot2/`: the development bot. Every new behaviour is a `constexpr` toggle at the top of `main.cpp` and is off by default. `v61` = dev bot + the toggles in `work/v60toggles.txt` + `POCKET_CAP=48,QUEEN_HOME_CLOSED=true`.
- `work/`: testing and replay-analysis scripts, plus the experiment log `plan.md`.
- `maps/`, `tune_maps/`, `tune_runs/*`: official maps, the new maps rebuilt from replays (`tune_runs/newmaps`), and the generated dev / held-out / fresh sets.
- `swarm/`: a sparring bot.

## Local A/B tests
```
cd work
python3 -m venv bc127 && bc127/bin/pip install unswbc==1.2.7
export PATH=$PWD/bc127/bin:$PATH NOSANDBOX=1 FAST=1 WORKERS=4
SEED0=3000 python3 ab3.py "$(cat newset.txt),$(cat official.txt)" v61 8 out.json "TAG@mybot2:TOGGLE_A=value,TOGGLE_B=value"
python3 paired.py baseline.json BASELINE_TAG out.json
```
`ab3.py` builds one variant per toggle set (into `tune_runs/ab2/TAG`), plays it against the opponent directory and prints the wins. `paired.py` compares two result files game by game (same map, same seed).

## Conventions
- No comments in the bot code and no per-map hardcoding.
- Before submitting, run a 64×64 map with `unswbc run --sandbox` and keep the worst turn under about 60M points.
- Tag every ladder submission in git (v61, v62, ...).
- Commit messages in English.
