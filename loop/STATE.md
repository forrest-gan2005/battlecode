# Loop state

- Phase: C (wave 4). Phase A done (`loop/ANALYSIS.md`), Phase B done (noise table below).
- Baseline B61 = mybot2 + `loop/dev/v61toggles.txt` (= `work/v60toggles.txt` + POCKET_CAP=48,QUEEN_HOME_CLOSED=true). `ident_B61.txt` identical. B61c (mybot2 with CB_TRAP code) ident in `ident_B61c.txt`. TR_PRESS_DEPTH (wave 3) and EC_SPLIT_ROUND_BIG (wave 4): toggle-off object file byte-identical (clang++ -std=c++20 -O2 -c mybot2/main.cpp, md5 aee4013d...).
- Placebos: P1 = B61 + TIE_SEED=1, P2 = B61 + TIE_SEED=2 (tie-break jitter only).
- mech.sh finished 06:02 (`mech.json`, `mech_press.txt`). Do not edit mybot2 while a batch builds from it.
- Running chain (each script waits for a marker file; check `ps` before starting anything; never more than 8 workers):
  1. `loop/h5.sh` (pid 38751): H5 TM4 + TM1 held x2 (started 06:02), then main x8 -> `H5_done`. Est. ~07:00.
  2. `loop/h7.sh` (pid 38919): after `H5_done`, waits while `HOLD_H7` exists: H7 ES225 + ES300 held x2, main x8 -> `H7_done`, then removes `HOLD_H1B`. Est. ~08:00.
  3. `loop/h1b.sh` (pid 11892): after `H5_done`, waits while `loop/results/HOLD_H1B` exists (set in wave 4 so H7 runs first; h7.sh removes it). Est. ~09:00.
- To run a confirm (SEED0=5000) before a queued step: `touch loop/results/HOLD_H7` (or HOLD_H1B) before its wait ends, run the confirm, then remove the file. Keep HOLD_H1B in place while H7 runs.
- Stopping an ab3 batch: kill `ab3.py` AND its `multiprocessing.spawn` workers (they keep launching games), then the leftover `unswbc run` processes.
- Next wave: judge H5 when `H5_held.json` exists (`python3 loop/tools/judge.py loop/results/B_held.json loop/results/H5_held.json`; maps <= 1200 cells should not flip). If H5 held net <= 0 for both, the H5 main batch may be stopped (kill as above, then `touch loop/results/H5_done` so the chain moves on). Same for H7. H7 mechanism if it passes: KEEP run on `loop/dev/mechset.txt` (as `loop/mech.sh`), then `python3 loop/tools/mech7.py 'work/ab2/MB61_*.replay' 'work/ab2/<TAG>_*.replay'` (maps > 1200 cells: splits r150-300, units/top/total at r300, us:them).

## Noise table (vs B61, same games)
| set | B61 W/N | P1 +/- (net) | P2 +/- (net) | P1 vs P2 flips |
|---|---|---|---|---|
| held (80 maps x2) | 80/160 | +34 -29 (+5) | +35 -38 (-3) | 58 |
| main (22 maps x8) | 88/176 | +34 -44 (-10) | +26 -40 (-14) | 74 |
- Nh = 5, Nm = 14. PASS bar: held net >= 9 and main net >= -14.
- About 40% of games flip under a no-effect change; null SD of net ~ 8-9. Main is biased: any perturbation of v61 loses ~12 there (v61 was tuned on these maps). Held decides.

## Hypothesis queue (non-queen, non-feeding first)

### H1 TR — pressure room: REJECTED (wave 3)
- PR3 held 23/160, net -57, wiped 71 vs 28. Implementation was a whole-map Voronoi cut of the survey (also hid pearls/targets). Refined as H1b.

### H1b TR — local press ring (priority 3, chained after H7)
- Same claim as H1; block only cells within DEPTH steps of the destination that the enemy reaches no later than we do. Toggle `TR_PRESS_DEPTH` with `TR_PRESS_ROOM=3`. Variants PD2, PD4. Pre-registered in wave 3.
- Falsifier: held net <= 0, or pressure deaths per unit not lower in KEEP replays.
- Wave 4 mechanism data on H1 (MPR3, 40 devset games): pressure deaths per 100 unit-rounds 0.386 vs MB61 0.221 (+75%), self 3.91 vs 2.50; wins 6/40 vs 20/40. The whole-map block raised pressure deaths per unit. Moved behind H7.

### H2 CB — SMALL_UNIT_THREAT_REACH=2: REJECTED (wave 3)
- SR2 held 69/160, net -11 (small -3, medium -9, large +1).

### H3 EC — midgame unit growth: REJECTED by analysis (wave 1)
- Our split rate is higher than the opponents' (42.7 vs 34.3 per 100 L4+ dragon-rounds); per-unit gain is equal.

### H4 CB — trade instead of trapped suicide: TT5 REJECTED, TT5D INCONCLUSIVE (closed, wave 4)
- TT5 held net -7; TT5D held net +1 (flips 47, fewer than placebo). Mechanism (MTT5D, 40 devset games): small head_ram 65.5 vs MB61 55.7 per game (+17.5%, it fires), small self deaths 456.7 vs 448.7 (no drop). Fires, but does not replace trapped self deaths. Not re-queued.
- Sizing: before r300 our small self deaths with an enemy head adjacent 7.1 per game (theirs 3.8); small head_rams 9.8 vs 22.8.

### H5 CB — trade threshold on maps over 1200 cells (priority 1, running)
- TRADE_MIN_UNITS=4 (TM4) and =1 (TM1). Rule in LEDGER wave 3. Maps <= 1200 cells must be unchanged.

### H7 EC — keep non-leader splits on large maps after r150 (priority 2, chained after H5)
- Ladder (maps over 1600 W*H, r150-300): our splits per game 83 vs 166 (wins 90:171, losses 80:163); share of L4+ dragon-rounds in losses 0.17:0.30. On maps over 1200 cells every dragon longer than 4 stops splitting after LEADER_GROW_ROUND_BIG=150.
- Toggle `EC_SPLIT_ROUND_BIG` (0 = off): the no-split rule uses max(grow_round, value) on maps over 1200 cells; leader and queen logic unchanged. Variants ES225, ES300. Rule in LEDGER wave 4.
- Falsifier: held net <= 0, or r150-300 splits not up >= 20% vs MB61 in KEEP replays.

### H6 OP — opening (priority 6, low)
- No opening deficit found (r50 29:21 overall). Only if something new shows up.

### Parked (other owners, record only)
- Queen (QWQ #2): our queen dies in 159/228, median r123, 95 head_rammed; S maps queen-decided games 1-13.
- Feeding (Zhe #3): r400 top dragon in losses 12:21; L maps longest finishes 11-20.
