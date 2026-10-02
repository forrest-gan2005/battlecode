# Loop state

- Phase: B (Phase A done in wave 1: `loop/ANALYSIS.md`)
- Baseline B61 = mybot2 + `work/v60toggles.txt` + POCKET_CAP=48,QUEEN_HOME_CLOSED=true. Built at `tune_runs/ab2/B61`; main.cpp, helper.hpp and bot.toml are byte-identical to `v61/` (ident trivially identical).
- Placebos: P1 = B61 + TIE_SEED=1, P2 = B61 + TIE_SEED=2 (tie-break jitter only).
- Noise table: pending (Phase B batch running, see below).
- Running: `loop/phaseB.sh` (pid 30425, started 03:43 KST): B61/P1/P2 vs v61, held (heldset_sq+freshset x2, SEED0=3000) -> `loop/results/B_held.json`, then main (official+newset x8, SEED0=3000) -> `loop/results/B_main.json`; writes `loop/results/B_done` at the end.

## Noise table
| set | B61 W/N | P1 +/- (net) | P2 +/- (net) |
|---|---|---|---|
| held | pending | | |
| main | pending | | |

## Hypothesis queue (non-queen, non-feeding first)

### H1 TR — pressure room (priority 1, queued)
- Claim: when an enemy head is within a few cells, our survey counts cells the enemy can reach first as free room, so small dragons step into spaces that close and then die by wall/body. Make the survey treat cells the enemy reaches no later than we do as blocked when an enemy head is near the destination.
- Evidence: self-inflicted deaths with an enemy head within 3 cells: us 29.8 vs them 20.4 per game in r100-300 (6.3 vs 3.4 in r0-100) with fewer units, about 2x per unit; 29% of our self-inflicted deaths vs 17% of theirs. Mostly L2-5 wall (16.9 vs 8.5) and L3-5 body (2.7 vs 0.9).
- Toggle: `TR_PRESS_ROOM` (int, 0 = off): if an enemy head is within N of the destination, survey cells with rival_dist <= own step count are not counted as room.
- Expected signal: fewer pressure deaths per unit in local replays vs v61; held-out net above noise.
- Falsifier: pressure deaths per unit unchanged in KEEP replays, or held-out net within noise / negative while main gains.

### H2 CB — small heads threaten mid dragons (priority 2, queued; cheap, existing constant)
- Claim: enemy L<=3 dragons trade into our L4+ dragons; our L4+ should treat small enemy heads as reaching 2 cells.
- Evidence: our L4+ vs their L<=3 head-ons: 4.7 per game, we lose 30.4 length vs 14.8. Our L4-9 head_rammed 5.3 vs their 3.4 per game.
- Toggle: `SMALL_UNIT_THREAT_REACH=2` (no code). If it helps but raises pressure deaths, follow up with `CB_SMALL_REACH_MIN_LEN` (apply only for our length >= 4).
- Expected signal: our L4-9 head_rammed per game drops in KEEP replays.
- Falsifier: no drop, or held-out net within noise.

### H3 EC — midgame unit growth (REJECTED by analysis, wave 1)
- Claim was: we split too rarely in r50-r150. Falsified on ladder data: our splits per 100 L4+ dragon-rounds are 42.7 vs their 34.3, length mix equal, per-unit gain nearly equal (losses r50-100 0.081 vs 0.085). The unit gap is compounding of small per-unit edges and of the opponent's strength, not a split guard. No test run.
- Side fact: deaths eat most of the gain (losses r50-100: we lose 57.8 of 80.4 gained per game). Reducing avoidable deaths (H1, H4) is the economy lever.

### H4 CB — trade instead of trapped suicide (priority 4, queued)
- Claim: when a pressured small dragon (L<=3) has only trapped moves, a mutual head-on (enemy loses a unit too) beats a wall/self death.
- Evidence: same pressure-death numbers as H1; head-ons are almost always mutual (one-sided head-on deaths 518 ours vs 1802 theirs over 228 games).
- Toggle: `CB_TRAP_TRADE` (bool): if every candidate move has cramped >= PENALTY_TRAPPED and an enemy head cell is reachable, take the head-on move.
- Expected signal: our pressure self-deaths convert into head_ram deaths with enemy deaths in the same round.
- Falsifier: no conversion in replays, or net within noise.

### H5 CB — trade threshold on large maps (priority 5, queued; cheap, existing constant)
- Claim: on maps over 1200 cells we only trade small dragons when we have >= 8 units; opponents initiate most mid-game head-ons in our losses.
- Evidence: in losses r100-300 their head_ram 24.7 vs our 7.8 per game; L maps 21/59.
- Toggle: `TRADE_MIN_UNITS=4` (no code).
- Expected signal: our head_ram share rises on L maps without a units drop.
- Falsifier: units at r200 fall, or net within noise.

### H6 OP — opening (priority 6, low)
- Facts: no opening deficit found (r25 18:14, r50 29:21, units 11:8 overall; r50 28:30 in losses). Only queue an opening change if H3's step 0 shows a split guard that also binds before r50.

### Parked (other owners, record only)
- Queen (QWQ #2): our queen dies in 159/228, median r123, 95 head_rammed; S maps queen-decided games 1-13.
- Feeding (Zhe #3): r400 top dragon in losses 12:21; L maps longest finishes 11-20.
