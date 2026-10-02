# Loop state

- Phase: C (wave 3). Phase A done (`loop/ANALYSIS.md`), Phase B done (noise table below).
- Baseline B61 = mybot2 + `loop/dev/v61toggles.txt` (= `work/v60toggles.txt` + POCKET_CAP=48,QUEEN_HOME_CLOSED=true). `ident_B61.txt` identical. B61c (mybot2 with CB_TRAP code) ident in `ident_B61c.txt`. TR_PRESS_DEPTH added in wave 3: toggle-off object file byte-identical to the previous build.
- Placebos: P1 = B61 + TIE_SEED=1, P2 = B61 + TIE_SEED=2 (tie-break jitter only).
- Running chain (each script waits for the previous marker file; check `ps` before starting anything; never more than 8 workers):
  1. `loop/h4.sh` (pid 26722): B61c ident -> H4 TT5 + TT5D held x2 (`H4_held.json`), main x8 (`H4_main.json`) -> `H4_done`. Started 05:18, est. ~06:05.
  2. `loop/mech.sh` (pid 28961): after `H4_done`: KEEP replays, 10 devset maps x4, MB61/MPR3/MSR2/MTT5/MTT5D vs v61 -> `mech.json`, `mech_press.txt`, `mech_done`. Est. ~06:35.
  3. `loop/h5.sh` (pid 38751): after `mech_done`, waits while `loop/results/HOLD_H5` exists: H5 TM4 + TM1 held x2, main x8 -> `H5_done`. Est. ~07:20.
  4. `loop/h1b.sh` (pid 11892): after `H5_done`, waits while `HOLD_H1B` exists: H1b PD2 + PD4 held x2, main x8 -> `H1b_done`. Est. ~08:05.
- To run a confirm (SEED0=5000) before a queued step: `touch loop/results/HOLD_H5` (or HOLD_H1B) before its wait ends, run the confirm, then remove the file.
- Stopping an ab3 batch: kill `ab3.py` AND its `multiprocessing.spawn` workers (they keep launching games), then the leftover `unswbc run` processes.
- Next wave: judge H4 under the wave 2 rule (`python3 loop/tools/judge.py loop/results/B_held.json loop/results/H4_held.json`). If both TT5 and TT5D held net <= 0, H4 is REJECTED and the main step may be killed. Read `mech_press.txt` when present: MPR3 wiped/pressure counts (why H1 collapsed), MTT5 small_ram/small_self (H4 mechanism).

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

### H1b TR — local press ring (priority 2, chained after H5)
- Same claim as H1; block only cells within DEPTH steps of the destination that the enemy reaches no later than we do. Toggle `TR_PRESS_DEPTH` with `TR_PRESS_ROOM=3`. Variants PD2, PD4. Pre-registered in wave 3.
- Falsifier: held net <= 0, or pressure deaths per unit not lower in KEEP replays.

### H2 CB — SMALL_UNIT_THREAT_REACH=2: REJECTED (wave 3)
- SR2 held 69/160, net -11 (small -3, medium -9, large +1).

### H3 EC — midgame unit growth: REJECTED by analysis (wave 1)
- Our split rate is higher than the opponents' (42.7 vs 34.3 per 100 L4+ dragon-rounds); per-unit gain is equal.

### H4 CB — trade instead of trapped suicide (priority 1, running)
- `CB_TRAP_TRADE` (max length), `CB_TRAP_DEAD`. Variants TT5, TT5D. Rule in LEDGER wave 2.
- Sizing: before r300 our small self deaths with an enemy head adjacent 7.1 per game (theirs 3.8); small head_rams 9.8 vs 22.8.

### H5 CB — trade threshold on maps over 1200 cells (priority 3, chained)
- TRADE_MIN_UNITS=4 (TM4) and =1 (TM1). Rule in LEDGER wave 3. Maps <= 1200 cells must be unchanged.

### H6 OP — opening (priority 6, low)
- No opening deficit found (r50 29:21 overall). Only if something new shows up.

### Parked (other owners, record only)
- Queen (QWQ #2): our queen dies in 159/228, median r123, 95 head_rammed; S maps queen-decided games 1-13.
- Feeding (Zhe #3): r400 top dragon in losses 12:21; L maps longest finishes 11-20.
