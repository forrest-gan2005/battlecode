# A small sparring pool

Six opponents give changes a few different things to trip over. No ratings yet.
`pool.json` uses QWQ's exact addendum settings on main's `mybot2`:
hunter = queen hunt + chase distance 8; rammer = aggressive cells 100000 + local edge -10;
assassin = mod 2, minimum 2, target 12; nostride = STRIDE=false; plus v61 and live.
The assassin targets big enemy dragons; its own hunters are length 2–6.

From the repo root:
```sh
export PATH=~/meow-dev/work/bc127/bin:$PATH NOSANDBOX=1
python3 work/pool.py mybot2 'mybot2:QUEEN_HUNT=true' --set quick --n 2 --out work/check.md
python3 work/pool_styles.py --out work/pool-styles.md
```
Bot dirs are relative to the repo root (absolute paths work too).
Use `--maps a,b,c` or `--set held|new|quick`; `--n` counts seeds, each in both seats.
Quick uses tower_defense, trophy, australia, islands, default and schooltime.
`WORKERS` defaults to 6; `SEED0` defaults to 100. All game batches share the loop's blocking flock.
Reports include opponent, map-family and seat tables. Games means matched slots per build.
Scores mean final queen length, including 0 for a dead queen, even if its team wins a tiebreak.
Raw rows, death events and source/map hashes go to `<report>.rows.json`; replays/logs stay in tune_runs/pool.

Validation is pending the shared batch lock; no game result is claimed yet.
All six pool bots and passage compile. Four accounting/lock tests pass (`python3 -m unittest discover -s work -p test_pool.py`).

Limits: these bots share most of their code, and a small paired sample is noisy.
None plays like the top teams: about 60 units by round 200, feeding from round 300.
Native runs can catch runtime failures but don't establish the online sandbox CPU margin.
The online check stays the final word. The human maintainer decides what ships.
