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

## Per-map tables

Mean ± sd over seeds. `**` = flagged (Benjamini-Hochberg q < 0.05 over all tests), `*` = p < 0.01 only.

### autarky (54x18, SYMMETRY xy, 16 seeds)

| metric | original | transpose | rot90 | mirror_x |
|---|---|---|---|---|
| ends (winner) | elim 8 longest 6 queen 2 (A 5, B 11) | elim 9 longest 5 queen 2 (A 6, B 10) | elim 5 longest 5 queen 6 (A 12, B 4) | elim 10 longest 5 queen 1 (A 4, B 12) |
| game length | 403 ± 111 | 408 ± 111 | 451 ± 83.7 | 346 ± 133 |
| ended by elimination | 0.50 ± 0.50 | 0.56 ± 0.50 | 0.31 ± 0.46 | 0.62 ± 0.48 |
| team A won | 0.31 ± 0.46 | 0.38 ± 0.48 | 0.75 ± 0.43 | 0.25 ± 0.43 |
| total len A r100 | 40.1 ± 15.7 | 44.1 ± 11.8 | **55.7 ± 11.3** (d +1.1) | 27.1 ± 12.8 |
| total len B r100 | 40.6 ± 16.6 | 52.4 ± 12.7 | 46.5 ± 11.4 | 50.8 ± 14.0 |
| total len A r300 | 58.4 ± 54.4 | 54.1 ± 51.5 | 84.9 ± 47.7 | 29.7 ± 40.2 |
| total len B r300 | 71.9 ± 53.6 | 75.9 ± 54.3 | 48.5 ± 44.4 | 94.9 ± 48.5 |
| units A r100 | 16.4 ± 6.25 | 18.2 ± 5.09 | **22.6 ± 4.44** (d +1.1) | 10.8 ± 5.13 |
| units B r100 | 16.6 ± 6.40 | 21.2 ± 5.50 | 18.6 ± 4.94 | 20.4 ± 5.60 |
| queen A died | 0.81 ± 0.39 | 0.81 ± 0.39 | 0.56 ± 0.50 | 1.00 ± 0.00 |
| queen B died | 0.81 ± 0.39 | 0.62 ± 0.48 | 0.81 ± 0.39 | 0.62 ± 0.48 |
| queen A death round (end if alive) | 277 ± 154 | 241 ± 122 | 320 ± 154 | 134 ± 132 |
| queen B death round (end if alive) | 202 ± 166 | 302 ± 110 | 271 ± 132 | 220 ± 140 |
| queen A length at end | 9.44 ± 27.1 | 6.81 ± 24.6 | 24.8 ± 42.0 | 0.00 ± 0.00 |
| queen B length at end | 2.06 ± 5.46 | 10.9 ± 24.9 | 6.56 ± 24.4 | 9.69 ± 24.2 |
| self deaths A <r200 | 48.7 ± 19.5 | 50.2 ± 24.1 | **71.5 ± 18.5** (d +1.2) | 35.4 ± 14.6 |
| self deaths B <r200 | 62.9 ± 24.4 | 68.9 ± 22.1 | 52.2 ± 18.2 | 72.1 ± 22.2 |
| head-centre dist r30 (norm) | 0.52 ± 0.06 | **0.86 ± 0.06** (d +5.8) | **0.84 ± 0.07** (d +4.8) | 0.50 ± 0.06 |
| head-centre dist r60 (norm) | 0.46 ± 0.06 | **0.88 ± 0.06** (d +7.4) | **0.91 ± 0.06** (d +7.6) | 0.43 ± 0.05 |
| E share of E/W steps r<60 (orig frame) | 0.51 ± 0.03 | 0.51 ± 0.04 | 0.51 ± 0.04 | 0.48 ± 0.03 * (d -1.0) |
| N share of N/S steps r<60 (orig frame) | 0.49 ± 0.02 | 0.50 ± 0.01 | 0.50 ± 0.02 | 0.50 ± 0.02 |
| portal jumps | 373 ± 94.4 | 418 ± 107 | 452 ± 73.8 | 313 ± 137 |

### default (32x32, SYMMETRY xy, 16 seeds)

| metric | original | transpose | rot90 | mirror_x |
|---|---|---|---|---|
| ends (winner) | elim 6 longest 6 queen 4 (A 9, B 7) | elim 10 longest 3 queen 3 (A 10, B 6) | elim 12 longest 3 queen 1 (A 9, B 7) | elim 11 longest 4 queen 1 (A 7, B 9) |
| game length | 437 ± 95.7 | 367 ± 113 | 366 ± 115 | 347 ± 109 |
| ended by elimination | 0.38 ± 0.48 | 0.62 ± 0.48 | 0.75 ± 0.43 | 0.69 ± 0.46 |
| team A won | 0.56 ± 0.50 | 0.62 ± 0.48 | 0.56 ± 0.50 | 0.44 ± 0.50 |
| total len A r100 | 39.8 ± 13.8 | 41.8 ± 9.90 | 39.2 ± 11.7 | 35.6 ± 13.0 |
| total len B r100 | 38.7 ± 9.92 | 34.8 ± 12.2 | 40.6 ± 12.9 | 40.9 ± 10.0 |
| total len A r300 | 74.2 ± 49.9 | 75.4 ± 52.9 | 67.8 ± 48.9 | 49.7 ± 53.4 |
| total len B r300 | 50.9 ± 44.6 | 48.6 ± 52.5 | 52.2 ± 49.4 | 78.3 ± 52.2 |
| units A r100 | 17.1 ± 6.16 | 17.1 ± 3.82 | 16.0 ± 4.69 | 15.1 ± 5.70 |
| units B r100 | 16.0 ± 4.20 | 14.5 ± 5.33 | 16.8 ± 5.53 | 17.1 ± 4.12 |
| queen A died | 0.62 ± 0.48 | 0.62 ± 0.48 | 0.69 ± 0.46 | 0.75 ± 0.43 |
| queen B died | 0.88 ± 0.33 | 0.75 ± 0.43 | 0.75 ± 0.43 | 0.56 ± 0.50 |
| queen A death round (end if alive) | 280 ± 128 | 293 ± 127 | 226 ± 84.7 | 224 ± 103 |
| queen B death round (end if alive) | 322 ± 135 | 218 ± 77.9 | 279 ± 121 | 247 ± 84.2 |
| queen A length at end | 6.06 ± 11.8 | 17.8 ± 35.6 | 4.94 ± 16.3 | 1.31 ± 2.66 |
| queen B length at end | 7.00 ± 21.2 | 1.38 ± 2.78 | 10.6 ± 26.1 | 2.81 ± 6.65 |
| self deaths A <r200 | 9.81 ± 5.54 | 10.9 ± 6.30 | 10.4 ± 5.25 | 7.62 ± 4.27 |
| self deaths B <r200 | 9.88 ± 5.57 | 10.2 ± 7.72 | 10.3 ± 6.92 | 11.6 ± 7.64 |
| head-centre dist r30 (norm) | 1.14 ± 0.08 | 1.11 ± 0.09 | **1.00 ± 0.13** (d -1.3) | 1.11 ± 0.08 |
| head-centre dist r60 (norm) | 0.98 ± 0.07 | 1.02 ± 0.08 | 0.99 ± 0.10 | 1.00 ± 0.07 |
| E share of E/W steps r<60 (orig frame) | 0.53 ± 0.08 | 0.49 ± 0.05 | 0.51 ± 0.08 | 0.51 ± 0.09 |
| N share of N/S steps r<60 (orig frame) | 0.52 ± 0.05 | 0.50 ± 0.05 | 0.49 ± 0.05 | 0.48 ± 0.06 |
| portal jumps | 397 ± 77.8 | 331 ± 92.0 | 360 ± 106 | 328 ± 88.3 |

### devil (32x16, SYMMETRY y, 16 seeds)

| metric | original | transpose | rot90 | mirror_x |
|---|---|---|---|---|
| ends (winner) | elim 16 (A 9, B 7) | elim 12 longest 3 total 1 (A 10, B 6) | elim 13 longest 3 (A 13, B 3) | elim 16 (A 8, B 8) |
| game length | 172 ± 92.7 | 286 ± 138 | 274 ± 121 | 158 ± 67.8 |
| ended by elimination | 1.00 ± 0.00 | 0.75 ± 0.43 | 0.81 ± 0.39 | 1.00 ± 0.00 |
| team A won | 0.56 ± 0.50 | 0.62 ± 0.48 | 0.81 ± 0.39 | 0.50 ± 0.50 |
| total len A r100 | 42.4 ± 31.3 | 58.4 ± 28.1 | 72.2 ± 26.6 * (d +1.0) | 43.6 ± 33.8 |
| total len B r100 | 32.7 ± 27.1 | 35.8 ± 28.3 | 30.4 ± 26.1 | 38.9 ± 32.8 |
| total len A r300 | 62.6 ± 59.7 | 80.8 ± 55.9 | 107 ± 46.6 | 50.2 ± 52.9 |
| total len B r300 | 41.7 ± 52.2 | 50.2 ± 56.1 | 29.7 ± 48.3 | 56.9 ± 62.6 |
| units A r100 | 17.0 ± 12.8 | 23.7 ± 11.3 | **29.8 ± 10.6** (d +1.1) | 18.0 ± 13.7 |
| units B r100 | 13.1 ± 10.9 | 14.8 ± 11.4 | 12.1 ± 10.2 | 15.5 ± 12.7 |
| queen A died | 0.88 ± 0.33 | 0.94 ± 0.24 | 0.94 ± 0.24 | 0.88 ± 0.33 |
| queen B died | 1.00 ± 0.00 | 1.00 ± 0.00 | 1.00 ± 0.00 | 1.00 ± 0.00 |
| queen A death round (end if alive) | 64.2 ± 48.7 | 59.7 ± 50.3 | 71.6 ± 82.9 | 56.7 ± 38.8 |
| queen B death round (end if alive) | 37.0 ± 30.7 | 40.9 ± 46.4 | 62.6 ± 75.9 | 35.2 ± 19.8 |
| queen A length at end | 0.31 ± 0.85 | 0.19 ± 0.73 | 0.12 ± 0.48 | 0.31 ± 0.85 |
| queen B length at end | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 |
| self deaths A <r200 | 60.1 ± 62.7 | 87.2 ± 60.9 | 121 ± 58.8 | 43.1 ± 48.3 |
| self deaths B <r200 | 32.7 ± 44.8 | 56.2 ± 61.4 | 39.8 ± 54.6 | 47.8 ± 56.0 |
| head-centre dist r30 (norm) | 0.46 ± 0.05 | **0.57 ± 0.04** (d +2.3) | **0.56 ± 0.04** (d +2.2) | 0.46 ± 0.06 |
| head-centre dist r60 (norm) | 0.51 ± 0.04 | **0.66 ± 0.04** (d +3.6) | **0.69 ± 0.05** (d +3.6) | 0.50 ± 0.06 |
| E share of E/W steps r<60 (orig frame) | 0.50 ± 0.03 | 0.50 ± 0.02 | 0.50 ± 0.02 | 0.49 ± 0.03 |
| N share of N/S steps r<60 (orig frame) | 0.50 ± 0.04 | 0.47 ± 0.03 | 0.49 ± 0.04 | 0.48 ± 0.04 |
| portal jumps | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 |

### dilemma (32x16, SYMMETRY xy, 16 seeds)

| metric | original | transpose | rot90 | mirror_x |
|---|---|---|---|---|
| ends (winner) | elim 16 (A 16, B 0) | elim 15 longest 1 (A 0, B 16) | elim 11 longest 5 (A 5, B 11) | elim 16 (A 0, B 16) |
| game length | 261 ± 67.2 | 243 ± 90.5 | 364 ± 116 * (d +1.1) | 212 ± 57.5 |
| ended by elimination | 1.00 ± 0.00 | 0.94 ± 0.24 | 0.69 ± 0.46 | 1.00 ± 0.00 |
| team A won | 1.00 ± 0.00 | **0.00 ± 0.00** (d -inf) | **0.31 ± 0.46** (d -2.1) | **0.00 ± 0.00** (d -inf) |
| total len A r100 | 16.9 ± 0.33 | **3.00 ± 0.00** (d -59.3) | **6.00 ± 0.00** (d -46.5) | **4.12 ± 1.45** (d -12.1) |
| total len B r100 | 7.25 ± 0.66 | **17.0 ± 0.00** (d +20.8) | **8.00 ± 0.00** (d +1.6) | **17.2 ± 0.97** (d +12.1) |
| total len A r300 | 29.6 ± 6.17 | **1.06 ± 2.68** (d -6.0) | **6.12 ± 7.62** (d -3.4) | **0.31 ± 1.21** (d -6.6) |
| total len B r300 | 0.44 ± 1.27 | **25.3 ± 6.83** (d +5.1) | **18.9 ± 9.03** (d +2.9) | **23.8 ± 9.08** (d +3.6) |
| units A r100 | 7.88 ± 0.33 | **1.00 ± 0.00** (d -29.4) | **3.00 ± 0.00** (d -20.8) | **1.38 ± 0.48** (d -15.7) |
| units B r100 | 3.00 ± 0.00 | **6.00 ± 0.00** (d +inf) | **4.00 ± 0.00** (d +inf) | **6.25 ± 0.97** (d +4.7) |
| queen A died | 1.00 ± 0.00 | 1.00 ± 0.00 | 1.00 ± 0.00 | 1.00 ± 0.00 |
| queen B died | 1.00 ± 0.00 | 1.00 ± 0.00 | 1.00 ± 0.00 | 0.69 ± 0.46 |
| queen A death round (end if alive) | 85.0 ± 0.00 | **83.0 ± 0.00** (d -inf) | **40.0 ± 0.00** (d -inf) | 117 ± 47.2 |
| queen B death round (end if alive) | 113 ± 15.4 | **39.0 ± 0.00** (d -6.8) | **34.0 ± 0.00** (d -7.2) | **166 ± 72.7** (d +1.0) |
| queen A length at end | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 |
| queen B length at end | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.69 ± 1.04 |
| self deaths A <r200 | 26.5 ± 1.90 | **5.75 ± 1.09** (d -13.4) | **9.44 ± 1.37** (d -10.3) | **5.50 ± 1.62** (d -11.9) |
| self deaths B <r200 | 14.9 ± 2.64 | **29.7 ± 2.31** (d +6.0) | 14.9 ± 2.22 | **26.1 ± 6.26** (d +2.3) |
| head-centre dist r30 (norm) | 0.45 ± 0.00 | **0.42 ± 0.00** (d -inf) | **0.47 ± 0.00** (d +inf) | **0.54 ± 0.00** (d +inf) |
| head-centre dist r60 (norm) | 0.50 ± 0.00 | **0.76 ± 0.00** (d +inf) | **0.39 ± 0.00** (d -inf) | **0.64 ± 0.00** (d +inf) |
| E share of E/W steps r<60 (orig frame) | 0.52 ± 0.00 | **0.46 ± 0.00** (d -inf) | **0.51 ± 0.00** (d -inf) | **0.52 ± 0.00** (d +inf) |
| N share of N/S steps r<60 (orig frame) | 0.48 ± 0.00 | **0.48 ± 0.00** (d +inf) | **0.52 ± 0.00** (d +inf) | **0.49 ± 0.00** (d +inf) |
| portal jumps | 61.1 ± 19.1 | 64.7 ± 23.0 | 60.7 ± 19.9 | **33.9 ± 16.3** (d -1.5) |

### portals (32x16, SYMMETRY xy, 16 seeds)

| metric | original | transpose | rot90 | mirror_x |
|---|---|---|---|---|
| ends (winner) | longest 16 (A 9, B 7) | longest 16 (A 6, B 10) | longest 16 (A 9, B 7) | longest 16 (A 4, B 12) |
| game length | 500 ± 0.00 | 500 ± 0.00 | 500 ± 0.00 | 500 ± 0.00 |
| ended by elimination | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 |
| team A won | 0.56 ± 0.50 | 0.38 ± 0.48 | 0.56 ± 0.50 | 0.25 ± 0.43 |
| total len A r100 | 41.7 ± 8.00 | 48.8 ± 8.85 | 43.5 ± 13.0 | 39.8 ± 8.26 |
| total len B r100 | 44.1 ± 10.6 | 45.9 ± 5.58 | 47.1 ± 9.67 | 44.6 ± 7.50 |
| total len A r300 | 61.3 ± 8.18 | 61.5 ± 3.10 | 62.0 ± 10.6 | 59.6 ± 9.49 |
| total len B r300 | 63.2 ± 9.19 | 59.1 ± 6.37 | 62.9 ± 5.28 | 62.9 ± 6.53 |
| units A r100 | 15.9 ± 2.87 | 18.6 ± 2.98 | 15.8 ± 4.60 | 15.2 ± 3.09 |
| units B r100 | 16.9 ± 3.94 | 17.8 ± 2.19 | 18.0 ± 3.67 | 16.7 ± 2.84 |
| queen A died | 1.00 ± 0.00 | 1.00 ± 0.00 | 1.00 ± 0.00 | 1.00 ± 0.00 |
| queen B died | 1.00 ± 0.00 | 1.00 ± 0.00 | 1.00 ± 0.00 | 1.00 ± 0.00 |
| queen A death round (end if alive) | 84.4 ± 83.9 | 38.6 ± 34.8 | 84.5 ± 58.6 | 81.6 ± 74.1 |
| queen B death round (end if alive) | 99.0 ± 84.7 | 61.4 ± 44.5 | 84.1 ± 59.8 | 75.6 ± 95.0 |
| queen A length at end | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 |
| queen B length at end | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 |
| self deaths A <r200 | 179 ± 26.0 | **206 ± 16.4** (d +1.2) | 194 ± 23.4 | 173 ± 22.5 |
| self deaths B <r200 | 190 ± 29.1 | 202 ± 18.3 | 207 ± 21.5 | 197 ± 20.4 |
| head-centre dist r30 (norm) | 0.82 ± 0.06 | 0.83 ± 0.07 | 0.85 ± 0.06 | 0.86 ± 0.07 |
| head-centre dist r60 (norm) | 0.73 ± 0.05 | **0.83 ± 0.04** (d +2.0) | **0.85 ± 0.06** (d +1.9) | 0.76 ± 0.06 |
| E share of E/W steps r<60 (orig frame) | 0.50 ± 0.02 | 0.49 ± 0.02 | 0.49 ± 0.02 | 0.49 ± 0.02 |
| N share of N/S steps r<60 (orig frame) | 0.50 ± 0.01 | 0.50 ± 0.01 | 0.51 ± 0.02 | 0.49 ± 0.02 |
| portal jumps | 1293 ± 128 | 1355 ± 68.0 | 1361 ± 69.0 | 1302 ± 87.0 |

### queen_of_spades (25x35, SYMMETRY xy, 16 seeds)

| metric | original | transpose | rot90 | mirror_x |
|---|---|---|---|---|
| ends (winner) | elim 10 longest 5 queen 1 (A 4, B 12) | elim 11 longest 3 queen 2 (A 11, B 5) | elim 8 longest 4 queen 4 (A 7, B 9) | elim 11 longest 2 queen 3 (A 5, B 11) |
| game length | 363 ± 132 | 302 ± 143 | 395 ± 118 | 318 ± 132 |
| ended by elimination | 0.62 ± 0.48 | 0.69 ± 0.46 | 0.50 ± 0.50 | 0.69 ± 0.46 |
| team A won | 0.25 ± 0.43 | 0.69 ± 0.46 | 0.44 ± 0.50 | 0.31 ± 0.46 |
| total len A r100 | 20.9 ± 10.5 | **40.4 ± 11.3** (d +1.8) | 29.5 ± 8.37 | 21.2 ± 9.32 |
| total len B r100 | 29.8 ± 8.67 | **14.5 ± 7.37** (d -1.9) | 28.6 ± 8.02 | 33.9 ± 10.0 |
| total len A r300 | 27.1 ± 33.4 | 62.7 ± 31.7 * (d +1.1) | 38.2 ± 35.7 | 28.1 ± 35.9 |
| total len B r300 | 54.7 ± 35.0 | 20.2 ± 29.0 * (d -1.1) | 42.2 ± 34.7 | 55.6 ± 35.2 |
| units A r100 | 8.12 ± 3.85 | **16.1 ± 4.81** (d +1.8) | 11.9 ± 3.41 | 8.88 ± 3.81 |
| units B r100 | 11.9 ± 3.24 | **6.06 ± 3.07** (d -1.8) | 11.8 ± 3.30 | 13.3 ± 3.65 |
| queen A died | 0.88 ± 0.33 | 0.44 ± 0.50 | 0.69 ± 0.46 | 0.75 ± 0.43 |
| queen B died | 0.56 ± 0.50 | 0.94 ± 0.24 | 0.62 ± 0.48 | 0.44 ± 0.50 |
| queen A death round (end if alive) | 211 ± 123 | 238 ± 116 | 235 ± 120 | 260 ± 141 |
| queen B death round (end if alive) | 290 ± 111 | 180 ± 104 * (d -1.0) | 275 ± 151 | 238 ± 100 |
| queen A length at end | 0.38 ± 0.99 | 1.69 ± 1.86 | 3.31 ± 7.93 | 7.69 ± 19.1 |
| queen B length at end | 4.94 ± 14.1 | 0.75 ± 2.90 | 10.0 ± 22.2 | 2.00 ± 2.69 |
| self deaths A <r200 | 16.0 ± 13.4 | **31.5 ± 12.0** (d +1.2) | 22.8 ± 5.84 | 12.6 ± 10.2 |
| self deaths B <r200 | 26.8 ± 10.8 | **6.94 ± 8.51** (d -2.0) | 26.3 ± 7.02 | 27.4 ± 10.4 |
| head-centre dist r30 (norm) | 1.02 ± 0.15 | 1.00 ± 0.14 | **1.42 ± 0.06** (d +3.5) | 1.07 ± 0.11 |
| head-centre dist r60 (norm) | 1.13 ± 0.15 | 1.03 ± 0.11 | 1.26 ± 0.10 * (d +1.0) | 1.10 ± 0.07 |
| E share of E/W steps r<60 (orig frame) | 0.44 ± 0.09 | 0.46 ± 0.05 | 0.48 ± 0.05 | **0.52 ± 0.04** (d +1.2) |
| N share of N/S steps r<60 (orig frame) | 0.49 ± 0.08 | 0.50 ± 0.06 | 0.49 ± 0.07 | 0.52 ± 0.06 |
| portal jumps | 111 ± 36.6 | 104 ± 41.3 | 138 ± 31.8 | 110 ± 43.2 |

### schooltime (60x40, SYMMETRY y, 16 seeds)

| metric | original | transpose | rot90 | mirror_x |
|---|---|---|---|---|
| ends (winner) | longest 16 (A 6, B 10) | longest 14 queen 2 (A 11, B 5) | longest 16 (A 7, B 9) | longest 16 (A 8, B 8) |
| game length | 500 ± 0.00 | 500 ± 0.00 | 500 ± 0.00 | 500 ± 0.00 |
| ended by elimination | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 |
| team A won | 0.38 ± 0.48 | 0.69 ± 0.46 | 0.44 ± 0.50 | 0.50 ± 0.50 |
| total len A r100 | 103 ± 27.4 | 90.0 ± 30.1 | 91.2 ± 23.1 | 89.3 ± 21.9 |
| total len B r100 | 82.4 ± 23.3 | 101 ± 33.4 | 77.5 ± 16.3 | 87.8 ± 20.9 |
| total len A r300 | 253 ± 63.6 | 260 ± 110 | 255 ± 62.3 | 265 ± 86.5 |
| total len B r300 | 222 ± 57.2 | 226 ± 96.0 | 209 ± 54.4 | 205 ± 63.7 |
| units A r100 | 40.6 ± 11.0 | 35.9 ± 11.9 | 36.4 ± 8.27 | 35.9 ± 8.19 |
| units B r100 | 32.6 ± 9.70 | 40.2 ± 12.8 | 31.1 ± 6.71 | 35.2 ± 8.41 |
| queen A died | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 |
| queen B died | 0.00 ± 0.00 | 0.12 ± 0.33 | 0.00 ± 0.00 | 0.00 ± 0.00 |
| queen A death round (end if alive) | 500 ± 0.00 | 500 ± 0.00 | 500 ± 0.00 | 500 ± 0.00 |
| queen B death round (end if alive) | 500 ± 0.00 | 474 ± 77.3 | 500 ± 0.00 | 500 ± 0.00 |
| queen A length at end | 3.00 ± 0.00 | 3.00 ± 0.00 | 3.00 ± 0.00 | 3.00 ± 0.00 |
| queen B length at end | 3.00 ± 0.00 | 2.62 ± 0.99 | 3.00 ± 0.00 | 3.00 ± 0.00 |
| self deaths A <r200 | 70.4 ± 17.0 | 61.4 ± 23.4 | 61.9 ± 16.5 | 60.9 ± 18.7 |
| self deaths B <r200 | 56.6 ± 16.6 | 62.8 ± 21.7 | 53.2 ± 18.2 | 55.9 ± 13.8 |
| head-centre dist r30 (norm) | 1.11 ± 0.07 | **1.24 ± 0.05** (d +2.1) | 1.12 ± 0.09 | **1.25 ± 0.08** (d +1.9) |
| head-centre dist r60 (norm) | 0.94 ± 0.10 | **1.04 ± 0.06** (d +1.3) | **1.05 ± 0.10** (d +1.1) | 1.02 ± 0.07 * (d +1.0) |
| E share of E/W steps r<60 (orig frame) | 0.53 ± 0.03 | **0.49 ± 0.02** (d -1.3) | **0.48 ± 0.04** (d -1.3) | **0.45 ± 0.03** (d -2.5) |
| N share of N/S steps r<60 (orig frame) | 0.38 ± 0.04 | 0.41 ± 0.02 * (d +1.1) | 0.40 ± 0.03 | 0.41 ± 0.03 |
| portal jumps | 619 ± 47.9 | 571 ± 94.8 | 613 ± 47.7 | 577 ± 64.6 |

### slithery_fight (63x27, SYMMETRY xy, 16 seeds)

| metric | original | transpose | rot90 | mirror_x |
|---|---|---|---|---|
| ends (winner) | longest 16 (A 7, B 9) | longest 14 queen 1 total 1 (A 9, B 7) | longest 16 (A 6, B 10) | longest 16 (A 10, B 6) |
| game length | 500 ± 0.00 | 500 ± 0.00 | 500 ± 0.00 | 500 ± 0.00 |
| ended by elimination | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 |
| team A won | 0.44 ± 0.50 | 0.56 ± 0.50 | 0.38 ± 0.48 | 0.62 ± 0.48 |
| total len A r100 | 172 ± 12.8 | 165 ± 7.93 | 172 ± 14.7 | 171 ± 14.1 |
| total len B r100 | 169 ± 15.9 | 164 ± 7.38 | 171 ± 12.6 | 162 ± 10.6 |
| total len A r300 | 228 ± 22.0 | 224 ± 20.5 | 225 ± 25.3 | 224 ± 23.3 |
| total len B r300 | 235 ± 23.6 | 222 ± 24.2 | 230 ± 33.2 | 232 ± 28.0 |
| units A r100 | 60.6 ± 1.46 | 60.9 ± 1.17 | 60.2 ± 1.30 | 60.0 ± 2.45 |
| units B r100 | 60.8 ± 1.39 | 60.8 ± 1.15 | 60.2 ± 1.94 | 59.6 ± 2.09 |
| queen A died | 1.00 ± 0.00 | 0.94 ± 0.24 | 1.00 ± 0.00 | 1.00 ± 0.00 |
| queen B died | 1.00 ± 0.00 | 1.00 ± 0.00 | 1.00 ± 0.00 | 1.00 ± 0.00 |
| queen A death round (end if alive) | 7.00 ± 0.00 | **318 ± 98.4** (d +4.5) | **269 ± 114** (d +3.2) | **138 ± 110** (d +1.7) |
| queen B death round (end if alive) | 247 ± 126 | 244 ± 84.6 | 238 ± 103 | 267 ± 67.6 |
| queen A length at end | 0.00 ± 0.00 | 5.50 ± 21.3 | 0.00 ± 0.00 | 0.00 ± 0.00 |
| queen B length at end | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 |
| self deaths A <r200 | 202 ± 20.4 | 204 ± 24.1 | 212 ± 25.5 | 215 ± 22.6 |
| self deaths B <r200 | 216 ± 31.0 | 221 ± 16.1 | 219 ± 23.6 | 213 ± 32.4 |
| head-centre dist r30 (norm) | 1.00 ± 0.03 | 0.98 ± 0.02 | **0.96 ± 0.02** (d -1.5) | 0.98 ± 0.02 |
| head-centre dist r60 (norm) | 0.94 ± 0.02 | 0.95 ± 0.02 | 0.95 ± 0.02 | 0.94 ± 0.03 |
| E share of E/W steps r<60 (orig frame) | 0.50 ± 0.01 | 0.49 ± 0.01 | 0.51 ± 0.02 | 0.50 ± 0.01 |
| N share of N/S steps r<60 (orig frame) | 0.50 ± 0.02 | 0.49 ± 0.01 | 0.50 ± 0.02 | 0.50 ± 0.01 |
| portal jumps | 163 ± 12.6 | 169 ± 12.3 | 157 ± 12.2 | 161 ± 17.1 |

### trauma (48x24, SYMMETRY xy, 16 seeds)

| metric | original | transpose | rot90 | mirror_x |
|---|---|---|---|---|
| ends (winner) | queen 15 total 1 (A 10, B 6) | queen 16 (A 10, B 6) | queen 16 (A 3, B 13) | queen 14 total 2 (A 6, B 10) |
| game length | 500 ± 0.00 | 500 ± 0.00 | 500 ± 0.00 | 500 ± 0.00 |
| ended by elimination | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 |
| team A won | 0.62 ± 0.48 | 0.62 ± 0.48 | 0.19 ± 0.39 | 0.38 ± 0.48 |
| total len A r100 | 22.4 ± 2.78 | **17.6 ± 4.51** (d -1.3) | 22.3 ± 8.35 | 22.6 ± 4.23 |
| total len B r100 | 16.9 ± 5.84 | 18.2 ± 5.60 | 22.4 ± 5.38 | 13.9 ± 3.30 |
| total len A r300 | 81.1 ± 17.3 | 73.8 ± 13.7 | 75.9 ± 14.8 | 74.1 ± 9.90 |
| total len B r300 | 71.4 ± 20.5 | 72.4 ± 13.5 | 68.4 ± 11.2 | 71.4 ± 16.9 |
| units A r100 | 9.00 ± 1.46 | 7.12 ± 1.87 * (d -1.1) | 8.44 ± 3.14 | 9.38 ± 1.96 |
| units B r100 | 6.50 ± 2.21 | 6.81 ± 2.10 | 8.88 ± 2.42 | 5.81 ± 1.55 |
| queen A died | 0.00 ± 0.00 | 0.12 ± 0.33 | 0.06 ± 0.24 | 0.12 ± 0.33 |
| queen B died | 0.06 ± 0.24 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0.00 ± 0.00 |
| queen A death round (end if alive) | 500 ± 0.00 | 493 ± 17.8 | 478 ± 86.4 | 489 ± 31.4 |
| queen B death round (end if alive) | 494 ± 21.3 | 500 ± 0.00 | 500 ± 0.00 | 500 ± 0.00 |
| queen A length at end | 39.9 ± 10.2 | 33.5 ± 17.7 | 29.3 ± 13.4 | 30.6 ± 16.1 |
| queen B length at end | 32.2 ± 15.4 | 29.8 ± 11.2 | 38.9 ± 7.32 | 40.0 ± 10.1 |
| self deaths A <r200 | 37.4 ± 9.45 | 30.9 ± 10.8 | 36.5 ± 11.6 | 39.4 ± 9.59 |
| self deaths B <r200 | 24.2 ± 12.7 | 27.1 ± 13.0 | **38.3 ± 10.1** (d +1.2) | 18.5 ± 10.8 |
| head-centre dist r30 (norm) | 1.15 ± 0.08 | **1.27 ± 0.07** (d +1.7) | 1.24 ± 0.11 | 1.08 ± 0.04 * (d -1.0) |
| head-centre dist r60 (norm) | 1.08 ± 0.08 | 1.12 ± 0.05 | 1.10 ± 0.07 | 1.16 ± 0.12 |
| E share of E/W steps r<60 (orig frame) | 0.51 ± 0.02 | 0.51 ± 0.02 | 0.49 ± 0.02 | 0.51 ± 0.02 |
| N share of N/S steps r<60 (orig frame) | 0.48 ± 0.03 | 0.50 ± 0.03 | 0.50 ± 0.04 | 0.48 ± 0.03 |
| portal jumps | 192 ± 17.5 | 176 ± 30.8 | 190 ± 22.4 | 175 ± 22.7 |

### trophy (25x25, SYMMETRY y, 16 seeds)

| metric | original | transpose | rot90 | mirror_x |
|---|---|---|---|---|
| ends (winner) | elim 16 (A 6, B 10) | elim 16 (A 10, B 6) | elim 16 (A 8, B 8) | elim 16 (A 11, B 5) |
| game length | 156 ± 66.7 | 141 ± 41.7 | 128 ± 30.6 | 123 ± 33.1 |
| ended by elimination | 1.00 ± 0.00 | 1.00 ± 0.00 | 1.00 ± 0.00 | 1.00 ± 0.00 |
| team A won | 0.38 ± 0.48 | 0.62 ± 0.48 | 0.50 ± 0.50 | 0.69 ± 0.46 |
| total len A r100 | 36.7 ± 35.5 | 57.9 ± 38.5 | 48.6 ± 41.6 | 63.5 ± 40.8 |
| total len B r100 | 61.1 ± 38.1 | 39.2 ± 35.4 | 49.3 ± 42.4 | 32.9 ± 37.6 |
| total len A r300 | 42.3 ± 57.2 | 73.2 ± 58.1 | 57.6 ± 58.2 | 74.1 ± 54.8 |
| total len B r300 | 76.2 ± 56.6 | 43.0 ± 56.8 | 57.2 ± 59.6 | 36.8 ± 55.1 |
| units A r100 | 15.2 ± 14.8 | 23.4 ± 15.4 | 19.9 ± 17.0 | 26.4 ± 17.0 |
| units B r100 | 25.2 ± 15.6 | 16.6 ± 14.9 | 20.9 ± 17.9 | 13.8 ± 15.7 |
| queen A died | 0.69 ± 0.46 | 0.44 ± 0.50 | 0.69 ± 0.46 | 0.44 ± 0.50 |
| queen B died | 0.56 ± 0.50 | 0.62 ± 0.48 | 0.56 ± 0.50 | 0.88 ± 0.33 |
| queen A death round (end if alive) | 103 ± 36.1 | 105 ± 47.0 | 86.1 ± 29.9 | 107 ± 39.5 |
| queen B death round (end if alive) | 104 ± 56.8 | 109 ± 57.1 | 106 ± 35.1 | 71.8 ± 37.9 |
| queen A length at end | 0.75 ± 1.15 | 1.44 ± 1.32 | 0.88 ± 1.32 | 1.38 ± 1.27 |
| queen B length at end | 1.12 ± 1.36 | 1.75 ± 3.42 | 1.12 ± 1.32 | 0.25 ± 0.66 |
| self deaths A <r200 | 3.44 ± 5.20 | 4.44 ± 4.27 | 3.75 ± 4.75 | 3.06 ± 3.21 |
| self deaths B <r200 | 6.38 ± 6.16 | 4.00 ± 6.18 | 3.62 ± 5.15 | 2.69 ± 4.69 |
| head-centre dist r30 (norm) | 0.53 ± 0.08 | 0.57 ± 0.08 | **0.66 ± 0.12** (d +1.3) | 0.55 ± 0.09 |
| head-centre dist r60 (norm) | 0.87 ± 0.06 | 0.81 ± 0.08 | 0.84 ± 0.09 | 0.86 ± 0.07 |
| E share of E/W steps r<60 (orig frame) | 0.50 ± 0.04 | 0.51 ± 0.06 | 0.51 ± 0.05 | 0.49 ± 0.03 |
| N share of N/S steps r<60 (orig frame) | 0.45 ± 0.04 | 0.48 ± 0.03 | 0.47 ± 0.05 | 0.46 ± 0.04 |
| portal jumps | 26.7 ± 13.7 | 21.8 ± 9.12 | 20.3 ± 8.42 | 19.6 ± 6.58 |

## Compass check (steps before round 60, pooled over seeds)

Own frame = directions as the bot saw them; original frame = the same steps mapped back to the original map.

| map | variant | own E/(E+W) | own N/(N+S) | orig-frame E/(E+W) | orig-frame N/(N+S) | steps |
|---|---|---|---|---|---|---|
| autarky | identity | 0.508 | 0.486 | 0.508 | 0.486 | 18699 |
| autarky | transpose | 0.503 | 0.487 | 0.514 | 0.497 | 24397 |
| autarky | rot90 | 0.500 | 0.486 | 0.514 | 0.500 | 24737 |
| autarky | mirror_x | 0.525 | 0.498 | 0.475 | 0.498 | 18084 |
| default | identity | 0.536 | 0.515 | 0.535 | 0.515 | 16115 |
| default | transpose | 0.501 | 0.506 | 0.492 | 0.497 | 17262 |
| default | rot90 | 0.484 | 0.489 | 0.509 | 0.485 | 16349 |
| default | mirror_x | 0.495 | 0.483 | 0.505 | 0.483 | 16790 |
| devil | identity | 0.504 | 0.502 | 0.504 | 0.502 | 14351 |
| devil | transpose | 0.530 | 0.496 | 0.504 | 0.470 | 15775 |
| devil | rot90 | 0.488 | 0.496 | 0.504 | 0.487 | 16794 |
| devil | mirror_x | 0.513 | 0.477 | 0.486 | 0.477 | 14496 |
| dilemma | identity | 0.521 | 0.477 | 0.521 | 0.477 | 10480 |
| dilemma | transpose | 0.517 | 0.536 | 0.464 | 0.483 | 7712 |
| dilemma | rot90 | 0.523 | 0.486 | 0.514 | 0.523 | 7472 |
| dilemma | mirror_x | 0.479 | 0.493 | 0.521 | 0.493 | 7616 |
| portals | identity | 0.497 | 0.498 | 0.497 | 0.498 | 13715 |
| portals | transpose | 0.495 | 0.508 | 0.491 | 0.505 | 14834 |
| portals | rot90 | 0.505 | 0.512 | 0.489 | 0.505 | 14770 |
| portals | mirror_x | 0.509 | 0.489 | 0.491 | 0.489 | 13545 |
| queen_of_spades | identity | 0.447 | 0.494 | 0.440 | 0.486 | 6187 |
| queen_of_spades | transpose | 0.498 | 0.542 | 0.459 | 0.498 | 7541 |
| queen_of_spades | rot90 | 0.485 | 0.524 | 0.475 | 0.490 | 8454 |
| queen_of_spades | mirror_x | 0.486 | 0.512 | 0.517 | 0.516 | 7816 |
| schooltime | identity | 0.527 | 0.380 | 0.525 | 0.377 | 11881 |
| schooltime | transpose | 0.591 | 0.510 | 0.489 | 0.408 | 12527 |
| schooltime | rot90 | 0.400 | 0.519 | 0.480 | 0.397 | 11407 |
| schooltime | mirror_x | 0.547 | 0.407 | 0.452 | 0.407 | 13579 |
| slithery_fight | identity | 0.496 | 0.498 | 0.496 | 0.498 | 58479 |
| slithery_fight | transpose | 0.511 | 0.506 | 0.494 | 0.489 | 59546 |
| slithery_fight | rot90 | 0.500 | 0.494 | 0.506 | 0.500 | 60323 |
| slithery_fight | mirror_x | 0.504 | 0.501 | 0.496 | 0.501 | 56958 |
| trauma | identity | 0.506 | 0.477 | 0.505 | 0.477 | 7480 |
| trauma | transpose | 0.504 | 0.495 | 0.505 | 0.496 | 7561 |
| trauma | rot90 | 0.503 | 0.505 | 0.495 | 0.505 | 7963 |
| trauma | mirror_x | 0.487 | 0.479 | 0.514 | 0.478 | 7617 |
| trophy | identity | 0.504 | 0.455 | 0.504 | 0.455 | 12654 |
| trophy | transpose | 0.521 | 0.489 | 0.507 | 0.481 | 11895 |
| trophy | rot90 | 0.474 | 0.491 | 0.510 | 0.473 | 11928 |
| trophy | mirror_x | 0.506 | 0.461 | 0.494 | 0.462 | 12476 |

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

## Flagged differences

660 tests; 83 with q < 0.05; 94 with p < 0.01 (about 6.6 expected by chance).

| map | variant | metric | original | transformed | diff | d | p | q |
|---|---|---|---|---|---|---|---|---|
| autarky | transpose | head-centre dist r30 (norm) | 0.52 ± 0.06 | 0.86 ± 0.06 | +0.34 | +5.8 | 0.0000 | 0.001 ** |
| autarky | transpose | head-centre dist r60 (norm) | 0.46 ± 0.06 | 0.88 ± 0.06 | +0.42 | +7.4 | 0.0000 | 0.001 ** |
| autarky | rot90 | head-centre dist r30 (norm) | 0.52 ± 0.06 | 0.84 ± 0.07 | +0.32 | +4.8 | 0.0000 | 0.001 ** |
| autarky | rot90 | head-centre dist r60 (norm) | 0.46 ± 0.06 | 0.91 ± 0.06 | +0.45 | +7.6 | 0.0000 | 0.001 ** |
| devil | transpose | head-centre dist r30 (norm) | 0.46 ± 0.05 | 0.57 ± 0.04 | +0.11 | +2.3 | 0.0000 | 0.001 ** |
| devil | transpose | head-centre dist r60 (norm) | 0.51 ± 0.04 | 0.66 ± 0.04 | +0.15 | +3.6 | 0.0000 | 0.001 ** |
| devil | rot90 | head-centre dist r30 (norm) | 0.46 ± 0.05 | 0.56 ± 0.04 | +0.10 | +2.2 | 0.0000 | 0.001 ** |
| devil | rot90 | head-centre dist r60 (norm) | 0.51 ± 0.04 | 0.69 ± 0.05 | +0.18 | +3.6 | 0.0000 | 0.001 ** |
| dilemma | transpose | team A won | 1.00 ± 0.00 | 0.00 ± 0.00 | -1.00 | -inf | 0.0000 | 0.001 ** |
| dilemma | transpose | total len A r100 | 16.9 ± 0.33 | 3.00 ± 0.00 | -13.88 | -59.3 | 0.0000 | 0.001 ** |
| dilemma | transpose | total len B r100 | 7.25 ± 0.66 | 17.0 ± 0.00 | +9.75 | +20.8 | 0.0000 | 0.001 ** |
| dilemma | transpose | total len A r300 | 29.6 ± 6.17 | 1.06 ± 2.68 | -28.56 | -6.0 | 0.0000 | 0.001 ** |
| dilemma | transpose | total len B r300 | 0.44 ± 1.27 | 25.3 ± 6.83 | +24.88 | +5.1 | 0.0000 | 0.001 ** |
| dilemma | transpose | units A r100 | 7.88 ± 0.33 | 1.00 ± 0.00 | -6.88 | -29.4 | 0.0000 | 0.001 ** |
| dilemma | transpose | units B r100 | 3.00 ± 0.00 | 6.00 ± 0.00 | +3.00 | +inf | 0.0000 | 0.001 ** |
| dilemma | transpose | queen A death round (end if alive) | 85.0 ± 0.00 | 83.0 ± 0.00 | -2.00 | -inf | 0.0000 | 0.001 ** |
| dilemma | transpose | queen B death round (end if alive) | 113 ± 15.4 | 39.0 ± 0.00 | -73.81 | -6.8 | 0.0000 | 0.001 ** |
| dilemma | transpose | self deaths A <r200 | 26.5 ± 1.90 | 5.75 ± 1.09 | -20.75 | -13.4 | 0.0000 | 0.001 ** |
| dilemma | transpose | self deaths B <r200 | 14.9 ± 2.64 | 29.7 ± 2.31 | +14.81 | +6.0 | 0.0000 | 0.001 ** |
| dilemma | transpose | head-centre dist r30 (norm) | 0.45 ± 0.00 | 0.42 ± 0.00 | -0.03 | -inf | 0.0000 | 0.001 ** |
| dilemma | transpose | head-centre dist r60 (norm) | 0.50 ± 0.00 | 0.76 ± 0.00 | +0.26 | +inf | 0.0000 | 0.001 ** |
| dilemma | transpose | E share of E/W steps r<60 (orig frame) | 0.52 ± 0.00 | 0.46 ± 0.00 | -0.06 | -inf | 0.0000 | 0.001 ** |
| dilemma | transpose | N share of N/S steps r<60 (orig frame) | 0.48 ± 0.00 | 0.48 ± 0.00 | +0.01 | +inf | 0.0000 | 0.001 ** |
| dilemma | rot90 | total len A r100 | 16.9 ± 0.33 | 6.00 ± 0.00 | -10.88 | -46.5 | 0.0000 | 0.001 ** |
| dilemma | rot90 | total len A r300 | 29.6 ± 6.17 | 6.12 ± 7.62 | -23.50 | -3.4 | 0.0000 | 0.001 ** |
| dilemma | rot90 | total len B r300 | 0.44 ± 1.27 | 18.9 ± 9.03 | +18.44 | +2.9 | 0.0000 | 0.001 ** |
| dilemma | rot90 | units A r100 | 7.88 ± 0.33 | 3.00 ± 0.00 | -4.88 | -20.8 | 0.0000 | 0.001 ** |
| dilemma | rot90 | units B r100 | 3.00 ± 0.00 | 4.00 ± 0.00 | +1.00 | +inf | 0.0000 | 0.001 ** |
| dilemma | rot90 | queen A death round (end if alive) | 85.0 ± 0.00 | 40.0 ± 0.00 | -45.00 | -inf | 0.0000 | 0.001 ** |
| dilemma | rot90 | queen B death round (end if alive) | 113 ± 15.4 | 34.0 ± 0.00 | -78.81 | -7.2 | 0.0000 | 0.001 ** |
| dilemma | rot90 | self deaths A <r200 | 26.5 ± 1.90 | 9.44 ± 1.37 | -17.06 | -10.3 | 0.0000 | 0.001 ** |
| dilemma | rot90 | head-centre dist r30 (norm) | 0.45 ± 0.00 | 0.47 ± 0.00 | +0.02 | +inf | 0.0000 | 0.001 ** |
| dilemma | rot90 | head-centre dist r60 (norm) | 0.50 ± 0.00 | 0.39 ± 0.00 | -0.11 | -inf | 0.0000 | 0.001 ** |
| dilemma | rot90 | E share of E/W steps r<60 (orig frame) | 0.52 ± 0.00 | 0.51 ± 0.00 | -0.01 | -inf | 0.0000 | 0.001 ** |
| dilemma | rot90 | N share of N/S steps r<60 (orig frame) | 0.48 ± 0.00 | 0.52 ± 0.00 | +0.05 | +inf | 0.0000 | 0.001 ** |
| dilemma | mirror_x | team A won | 1.00 ± 0.00 | 0.00 ± 0.00 | -1.00 | -inf | 0.0000 | 0.001 ** |
| dilemma | mirror_x | total len A r100 | 16.9 ± 0.33 | 4.12 ± 1.45 | -12.75 | -12.1 | 0.0000 | 0.001 ** |
| dilemma | mirror_x | total len B r100 | 7.25 ± 0.66 | 17.2 ± 0.97 | +10.00 | +12.1 | 0.0000 | 0.001 ** |
| dilemma | mirror_x | total len A r300 | 29.6 ± 6.17 | 0.31 ± 1.21 | -29.31 | -6.6 | 0.0000 | 0.001 ** |
| dilemma | mirror_x | total len B r300 | 0.44 ± 1.27 | 23.8 ± 9.08 | +23.31 | +3.6 | 0.0000 | 0.001 ** |
| dilemma | mirror_x | units A r100 | 7.88 ± 0.33 | 1.38 ± 0.48 | -6.50 | -15.7 | 0.0000 | 0.001 ** |
| dilemma | mirror_x | units B r100 | 3.00 ± 0.00 | 6.25 ± 0.97 | +3.25 | +4.7 | 0.0000 | 0.001 ** |
| dilemma | mirror_x | self deaths A <r200 | 26.5 ± 1.90 | 5.50 ± 1.62 | -21.00 | -11.9 | 0.0000 | 0.001 ** |
| dilemma | mirror_x | self deaths B <r200 | 14.9 ± 2.64 | 26.1 ± 6.26 | +11.19 | +2.3 | 0.0000 | 0.001 ** |
| dilemma | mirror_x | head-centre dist r30 (norm) | 0.45 ± 0.00 | 0.54 ± 0.00 | +0.08 | +inf | 0.0000 | 0.001 ** |
| dilemma | mirror_x | head-centre dist r60 (norm) | 0.50 ± 0.00 | 0.64 ± 0.00 | +0.14 | +inf | 0.0000 | 0.001 ** |
| dilemma | mirror_x | E share of E/W steps r<60 (orig frame) | 0.52 ± 0.00 | 0.52 ± 0.00 | +0.00 | +inf | 0.0000 | 0.001 ** |
| dilemma | mirror_x | N share of N/S steps r<60 (orig frame) | 0.48 ± 0.00 | 0.49 ± 0.00 | +0.02 | +inf | 0.0000 | 0.001 ** |
| queen_of_spades | transpose | total len B r100 | 29.8 ± 8.67 | 14.5 ± 7.37 | -15.31 | -1.9 | 0.0000 | 0.001 ** |
| queen_of_spades | transpose | units A r100 | 8.12 ± 3.85 | 16.1 ± 4.81 | +8.00 | +1.8 | 0.0000 | 0.001 ** |
| queen_of_spades | transpose | self deaths B <r200 | 26.8 ± 10.8 | 6.94 ± 8.51 | -19.81 | -2.0 | 0.0000 | 0.001 ** |
| queen_of_spades | rot90 | head-centre dist r30 (norm) | 1.02 ± 0.15 | 1.42 ± 0.06 | +0.40 | +3.5 | 0.0000 | 0.001 ** |
| schooltime | transpose | head-centre dist r30 (norm) | 1.11 ± 0.07 | 1.24 ± 0.05 | +0.14 | +2.1 | 0.0000 | 0.001 ** |
| schooltime | mirror_x | head-centre dist r30 (norm) | 1.11 ± 0.07 | 1.25 ± 0.08 | +0.15 | +1.9 | 0.0000 | 0.001 ** |
| schooltime | mirror_x | E share of E/W steps r<60 (orig frame) | 0.53 ± 0.03 | 0.45 ± 0.03 | -0.07 | -2.5 | 0.0000 | 0.001 ** |
| slithery_fight | transpose | queen A death round (end if alive) | 7.00 ± 0.00 | 318 ± 98.4 | +310.56 | +4.5 | 0.0000 | 0.001 ** |
| slithery_fight | rot90 | queen A death round (end if alive) | 7.00 ± 0.00 | 269 ± 114 | +261.69 | +3.2 | 0.0000 | 0.001 ** |
| slithery_fight | mirror_x | queen A death round (end if alive) | 7.00 ± 0.00 | 138 ± 110 | +130.88 | +1.7 | 0.0000 | 0.001 ** |
| portals | transpose | head-centre dist r60 (norm) | 0.73 ± 0.05 | 0.83 ± 0.04 | +0.09 | +2.0 | 0.0001 | 0.001 ** |
| portals | rot90 | head-centre dist r60 (norm) | 0.73 ± 0.05 | 0.85 ± 0.06 | +0.11 | +1.9 | 0.0001 | 0.001 ** |
| queen_of_spades | transpose | total len A r100 | 20.9 ± 10.5 | 40.4 ± 11.3 | +19.50 | +1.8 | 0.0001 | 0.001 ** |
| trauma | transpose | head-centre dist r30 (norm) | 1.15 ± 0.08 | 1.27 ± 0.07 | +0.13 | +1.7 | 0.0001 | 0.001 ** |
| dilemma | rot90 | team A won | 1.00 ± 0.00 | 0.31 ± 0.46 | -0.69 | -2.1 | 0.0002 | 0.002 ** |
| dilemma | mirror_x | portal jumps | 61.1 ± 19.1 | 33.9 ± 16.3 | -27.25 | -1.5 | 0.0002 | 0.002 ** |
| queen_of_spades | transpose | units B r100 | 11.9 ± 3.24 | 6.06 ± 3.07 | -5.81 | -1.8 | 0.0002 | 0.002 ** |
| slithery_fight | rot90 | head-centre dist r30 (norm) | 1.00 ± 0.03 | 0.96 ± 0.02 | -0.04 | -1.5 | 0.0003 | 0.003 ** |
| dilemma | rot90 | total len B r100 | 7.25 ± 0.66 | 8.00 ± 0.00 | +0.75 | +1.6 | 0.0005 | 0.005 ** |
| default | rot90 | head-centre dist r30 (norm) | 1.14 ± 0.08 | 1.00 ± 0.13 | -0.14 | -1.3 | 0.0008 | 0.008 ** |
| schooltime | transpose | head-centre dist r60 (norm) | 0.94 ± 0.10 | 1.04 ± 0.06 | +0.11 | +1.3 | 0.0011 | 0.011 ** |
| schooltime | transpose | E share of E/W steps r<60 (orig frame) | 0.53 ± 0.03 | 0.49 ± 0.02 | -0.04 | -1.3 | 0.0013 | 0.012 ** |
| schooltime | rot90 | E share of E/W steps r<60 (orig frame) | 0.53 ± 0.03 | 0.48 ± 0.04 | -0.05 | -1.3 | 0.0014 | 0.013 ** |
| trauma | transpose | total len A r100 | 22.4 ± 2.78 | 17.6 ± 4.51 | -4.75 | -1.3 | 0.0016 | 0.015 ** |
| trophy | rot90 | head-centre dist r30 (norm) | 0.53 ± 0.08 | 0.66 ± 0.12 | +0.13 | +1.3 | 0.0017 | 0.016 ** |
| trauma | rot90 | self deaths B <r200 | 24.2 ± 12.7 | 38.3 ± 10.1 | +14.12 | +1.2 | 0.0026 | 0.024 ** |
| queen_of_spades | transpose | self deaths A <r200 | 16.0 ± 13.4 | 31.5 ± 12.0 | +15.50 | +1.2 | 0.0027 | 0.024 ** |
| autarky | rot90 | self deaths A <r200 | 48.7 ± 19.5 | 71.5 ± 18.5 | +22.81 | +1.2 | 0.0028 | 0.025 ** |
| portals | transpose | self deaths A <r200 | 179 ± 26.0 | 206 ± 16.4 | +26.62 | +1.2 | 0.0029 | 0.025 ** |
| schooltime | rot90 | head-centre dist r60 (norm) | 0.94 ± 0.10 | 1.05 ± 0.10 | +0.11 | +1.1 | 0.0033 | 0.028 ** |
| queen_of_spades | mirror_x | E share of E/W steps r<60 (orig frame) | 0.44 ± 0.09 | 0.52 ± 0.04 | +0.08 | +1.2 | 0.0034 | 0.029 ** |
| autarky | rot90 | units A r100 | 16.4 ± 6.25 | 22.6 ± 4.44 | +6.12 | +1.1 | 0.0042 | 0.035 ** |
| dilemma | mirror_x | queen B death round (end if alive) | 113 ± 15.4 | 166 ± 72.7 | +53.25 | +1.0 | 0.0042 | 0.035 ** |
| autarky | rot90 | total len A r100 | 40.1 ± 15.7 | 55.7 ± 11.3 | +15.62 | +1.1 | 0.0048 | 0.039 ** |
| devil | rot90 | units A r100 | 17.0 ± 12.8 | 29.8 ± 10.6 | +12.75 | +1.1 | 0.0061 | 0.049 ** |
| trauma | transpose | units A r100 | 9.00 ± 1.46 | 7.12 ± 1.87 | -1.88 | -1.1 | 0.0065 | 0.051 |
| dilemma | rot90 | game length | 261 ± 67.2 | 364 ± 116 | +102.94 | +1.1 | 0.0066 | 0.052 |
| queen_of_spades | transpose | total len A r300 | 27.1 ± 33.4 | 62.7 ± 31.7 | +35.56 | +1.1 | 0.0069 | 0.053 |
| schooltime | mirror_x | head-centre dist r60 (norm) | 0.94 ± 0.10 | 1.02 ± 0.07 | +0.09 | +1.0 | 0.0072 | 0.055 |
| schooltime | transpose | N share of N/S steps r<60 (orig frame) | 0.38 ± 0.04 | 0.41 ± 0.02 | +0.03 | +1.1 | 0.0073 | 0.055 |
| queen_of_spades | transpose | total len B r300 | 54.7 ± 35.0 | 20.2 ± 29.0 | -34.50 | -1.1 | 0.0084 | 0.063 |
| autarky | mirror_x | E share of E/W steps r<60 (orig frame) | 0.51 ± 0.03 | 0.48 ± 0.03 | -0.03 | -1.0 | 0.0091 | 0.067 |
| queen_of_spades | rot90 | head-centre dist r60 (norm) | 1.13 ± 0.15 | 1.26 ± 0.10 | +0.13 | +1.0 | 0.0094 | 0.068 |
| queen_of_spades | transpose | queen B death round (end if alive) | 290 ± 111 | 180 ± 104 | -110.00 | -1.0 | 0.0096 | 0.069 |
| devil | rot90 | total len A r100 | 42.4 ± 31.3 | 72.2 ± 26.6 | +29.81 | +1.0 | 0.0098 | 0.070 |
| trauma | mirror_x | head-centre dist r30 (norm) | 1.15 ± 0.08 | 1.08 ± 0.04 | -0.07 | -1.0 | 0.0099 | 0.070 |
