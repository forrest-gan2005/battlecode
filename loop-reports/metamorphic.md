# Metamorphic test: does v61 play a transformed map the same way?

Oct 3, branch `tx/map-transforms`. Engine unswbc 1.2.7, run natively (`NOSANDBOX=1`). v61 plays against itself on the old 10 ladder maps and on transposed, rot90 and mirror_x copies of them: the same games with a different layout. 16 seeds per variant, one side (v61 vs itself is deterministic per map and seed, so swapping sides repeats the game; checked 40/40).

## Answer
No. Of 660 comparisons (10 maps x 3 transforms x 22 metrics), 83 differ at Benjamini-Hochberg q < 0.05 (94 at p < 0.01, about 7 expected by chance).

- **dilemma:** the winner depends on orientation. Original: team A wins 16/16. transpose and mirror_x: team B wins 16/16. rot90: B wins 11/16. Caveat: on dilemma the result barely depends on the seed (spread is about 0), so this is one deterministic game per orientation rather than 16 independent ones; the flip itself is real.
- **slithery_fight:** team A's queen dies at round 7 in all 16 original games; on the transposed, rotated and mirrored copies it lives to round 318, 269 and 138. Traced to one exact score tie at round 0, broken by v61's direction-indexed tie-break.
- **queen_of_spades (transpose):** A and B swap which team grows (A's total length at round 100: 20.9 -> 40.4; B's: 29.8 -> 14.5).
- **Centre pull** (`width >= 2*height`, mybot2/main.cpp ~410) switches as expected: autarky stood upright loses it (head-centre distance at round 60: 0.46 -> 0.88/0.91); devil, portals and dilemma drop from 60 rounds of pull to 30 with an outnumber check. mirror_x changes no size rule and shows none of this.
- **Stable maps:** default, trophy, schooltime and portals have at most one flagged outcome metric per transform.

## What this means
- Some of v61's results hang on arbitrary choices: the order in which directions are tried when scores tie, and size rules written as `width` vs `height`. On unseen maps these break one way or the other by chance.
- Making tie-breaks orientation-neutral changes play on old maps too, so it is a "real fix" under the two-level rule (no big regression on old maps), not a refactor.

## Flag counts per variant (q < 0.05)

outcome = the requested metrics (ends, length, lengths, units, queen deaths, self deaths); mechanism = centre distance, compass shares, portal jumps.

| map | transpose | rot90 | mirror_x |
|---|---|---|---|
| autarky | 0 outcome, 2 mechanism | 3 outcome, 2 mechanism | 0 outcome, 0 mechanism |
| default | 0 outcome, 0 mechanism | 0 outcome, 1 mechanism | 0 outcome, 0 mechanism |
| devil | 0 outcome, 2 mechanism | 1 outcome, 2 mechanism | 0 outcome, 0 mechanism |
| dilemma | 11 outcome, 4 mechanism | 10 outcome, 4 mechanism | 10 outcome, 5 mechanism |
| portals | 1 outcome, 1 mechanism | 0 outcome, 1 mechanism | 0 outcome, 0 mechanism |
| queen_of_spades | 6 outcome, 0 mechanism | 0 outcome, 1 mechanism | 0 outcome, 1 mechanism |
| schooltime | 0 outcome, 3 mechanism | 0 outcome, 2 mechanism | 0 outcome, 2 mechanism |
| slithery_fight | 1 outcome, 0 mechanism | 1 outcome, 1 mechanism | 1 outcome, 0 mechanism |
| trauma | 1 outcome, 1 mechanism | 1 outcome, 0 mechanism | 0 outcome, 0 mechanism |
| trophy | 0 outcome, 0 mechanism | 0 outcome, 1 mechanism | 0 outcome, 0 mechanism |

## v61 size rules per variant

From the v61 constructor (main.cpp:403-412). outnumber margin: centre pull only while enemy heads - ally heads <= margin.

| map | variant | W x H | centre pull | centre rounds | outnumber margin | aggressive | queen cells | sonar |
|---|---|---|---|---|---|---|---|---|
| autarky | identity | 54x18 | True | 60 | none | True | True | True |
| autarky | transpose | 18x54 | False | - | - | True | True | True |
| autarky | rot90 | 18x54 | False | - | - | True | True | True |
| autarky | mirror_x | 54x18 | True | 60 | none | True | True | True |
| default | identity | 32x32 | False | - | - | True | True | True |
| default | transpose | 32x32 | False | - | - | True | True | True |
| default | rot90 | 32x32 | False | - | - | True | True | True |
| default | mirror_x | 32x32 | False | - | - | True | True | True |
| devil | identity | 32x16 | True | 60 | none | True | False | True |
| devil | transpose | 16x32 | True | 30 | 0 | True | False | True |
| devil | rot90 | 16x32 | True | 30 | 0 | True | False | True |
| devil | mirror_x | 32x16 | True | 60 | none | True | False | True |
| dilemma | identity | 32x16 | True | 60 | none | True | False | True |
| dilemma | transpose | 16x32 | True | 30 | 0 | True | False | True |
| dilemma | rot90 | 16x32 | True | 30 | 0 | True | False | True |
| dilemma | mirror_x | 32x16 | True | 60 | none | True | False | True |
| portals | identity | 32x16 | True | 60 | none | True | False | True |
| portals | transpose | 16x32 | True | 30 | 0 | True | False | True |
| portals | rot90 | 16x32 | True | 30 | 0 | True | False | True |
| portals | mirror_x | 32x16 | True | 60 | none | True | False | True |
| queen_of_spades | identity | 25x35 | False | - | - | True | True | True |
| queen_of_spades | transpose | 35x25 | False | - | - | True | True | True |
| queen_of_spades | rot90 | 35x25 | False | - | - | True | True | True |
| queen_of_spades | mirror_x | 25x35 | False | - | - | True | True | True |
| schooltime | identity | 60x40 | False | - | - | False | True | True |
| schooltime | transpose | 40x60 | False | - | - | False | True | True |
| schooltime | rot90 | 40x60 | False | - | - | False | True | True |
| schooltime | mirror_x | 60x40 | False | - | - | False | True | True |
| slithery_fight | identity | 63x27 | False | - | - | False | True | True |
| slithery_fight | transpose | 27x63 | False | - | - | False | True | True |
| slithery_fight | rot90 | 27x63 | False | - | - | False | True | True |
| slithery_fight | mirror_x | 63x27 | False | - | - | False | True | True |
| trauma | identity | 48x24 | False | - | - | True | True | True |
| trauma | transpose | 24x48 | False | - | - | True | True | True |
| trauma | rot90 | 24x48 | False | - | - | True | True | True |
| trauma | mirror_x | 48x24 | False | - | - | True | True | True |
| trophy | identity | 25x25 | True | 30 | 0 | True | True | True |
| trophy | transpose | 25x25 | True | 30 | 0 | True | True | True |
| trophy | rot90 | 25x25 | True | 30 | 0 | True | True | True |
| trophy | mirror_x | 25x25 | True | 30 | 0 | True | True | True |

## Method
- **Transforms (`work/maptx.py`):** the 8 symmetries of a rectangle, acting on centred coordinates u = 2x-(W-1), v = 2y-(H-1).
- **The board wraps (torus).** Edge index layout: row = 2(W+1); north edge of (x,y) = y*row + x; west edge of (x,y) = y*row + W+1 + x. Standard map files list exactly 2*W*H edges; the south edge of the last row is the north edge of row 0 and the east edge of the last column is the west edge of column 0.
- **Edges:** the edge between cells p and q goes to the edge between T(p) and T(q); under transpose and rotation, north edges become west edges and the reverse.
- **Portals:** ids are kept, so both edges of a pair move together; the engine rejects pairs joining a horizontal and a vertical edge, and transformed pairs never do.
- **Dragons:** bodies mapped cell by cell, head first; line order and team kept, so ids and turn order don't change.
- **SYMMETRY header:** recomputed (`y` = mirror in x, `x` = mirror in y, `xy` = rot180).
- **Generated maps** repeat the east/south border edges; these copies are accepted only if each matches the edge it wraps to, then dropped (8,422 lines across 80 maps, no mismatch).
- Commands: `maptx.py MAP t1,t2 OUTDIR [--suffix S]`, `--show MAP [t]` (ASCII render), `--selftest MAPS...`.
- Runner and statistics: `work/metamorphic.py`, `work/metamorphic_stats.py`.

## Validation from replays

- main: 640 games, 0 without a result or with engine defect notices; 350 went 500 rounds, the rest ended by elimination
  - head moves on original maps: {'step': 3057064, 'jump': 51783}
  - head moves on transformed maps, own coordinates: {'step': 9007438, 'jump': 153307}
  - the same moves mapped back onto the original map: {'step': 9007438, 'jump': 153307}
- side swap: 40 games, 0 without a result or with engine defect notices; 18 went 500 rounds, the rest ended by elimination
  - head moves on original maps: {'step': 178039, 'jump': 3014}
  - head moves on transformed maps, own coordinates: {'step': 543434, 'jump': 9429}
  - the same moves mapped back onto the original map: {'step': 543434, 'jump': 9429}
  - event-identical to the side-0 game with the same map and seed: 40/40
- rot180/rot270/mirror_y: 30 games, 0 without a result or with engine defect notices; 15 went 500 rounds, the rest ended by elimination
  - head moves on transformed maps, own coordinates: {'step': 552328, 'jump': 9768}
  - the same moves mapped back onto the original map: {'step': 552328, 'jump': 9768}

## Transposed test sets (for tall-map coverage)
- `tune_runs/tx_held/<name>_T.map` for all 40 + 40 maps in `heldset_sq` and `freshset`; lists `work/heldset_sq_T.txt`, `work/freshset_T.txt`; `tune_runs/tx_held` is last in `ab2.MAP_DIRS`.
- Only 5 of the 80 are actually tall (H >= 2W), because almost all generated maps are near-square. The transformed old-10 maps (`tune_runs/tx_old10`) are the stronger orientation test.

## Caveats
- The SYMMETRY meaning and the portal exit rule (you come out on the far side of the partner edge, same direction) are inferred from geometry and replays, not engine docs; every check agrees with them.
- antitranspose is implemented but was not played.
- Full 22-metric tables: `loop-reports/metamorphic-tables.md`.
