# Loop state

- Phase: C (wave 5 closed 07:05). Phase A done (`loop/ANALYSIS.md`), Phase B done (noise table below).
- Baseline B61 = mybot2 + `loop/dev/v61toggles.txt` (= `work/v60toggles.txt` + POCKET_CAP=48,QUEEN_HOME_CLOSED=true). `ident_B61.txt` identical. B61c (mybot2 with CB_TRAP code) ident in `ident_B61c.txt`. TR_PRESS_DEPTH (wave 3) and EC_SPLIT_ROUND_BIG (wave 4): toggle-off object file byte-identical (md5 aee4013d...).
- Placebos: P1 = B61 + TIE_SEED=1, P2 = B61 + TIE_SEED=2 (tie-break jitter only).
- Running chain (check `ps` before starting anything; never more than 8 workers):
  1. `loop/h1b.sh` (pid 11892): H1b PD2 + PD4 held x2 started 06:59 (ab3 pid 87652, est. ~07:25), then main x8 (est. ~08:00) -> `H1b_done`.
  2. `loop/h8.sh` (pid 94571): waits for `H1b_done` and no `HOLD_H8`: H7b (B61 + ES300, held x2, SEED0=5000) -> `H7b_held5.json`, then H8 SL62 held x2 SEED0=3000 -> `H8_held.json`, then `H8_done`. Est. ~09:00.
- Next wave: judge H1b when `H1b_held.json` exists (`python3 loop/tools/judge.py loop/results/B_held.json loop/results/H1b_held.json`). If both PD variants have held net < 9, the main batch cannot make them PASS: kill h1b.sh first, then ab3 + spawn workers + unswbc runs, then `touch loop/results/H1b_done` (h8.sh starts by itself). H7b: pair B61 vs ES300 inside `H7b_held5.json` (judge.py needs a base file with tag B61: pass `H7b_held5.json` as both arguments). H8: `judge.py B_held.json H8_held.json`.
- Stopping an ab3 batch: kill the chain script first (it would move on), then `ab3.py`, its `multiprocessing.spawn` workers, then leftover `unswbc run` processes.
- Diagnostic split-reason build: `loop/dev/diag8/` + `diag8_run.py <maps>` (run from `work/`, 8 workers) + `diag8_rep.py`. Reusable for other binding checks (edit the dg() codes).

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

### H1b TR — local press ring (priority 1, running: held started 06:59)
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

### H5 CB — trade threshold on maps over 1200 cells: REJECTED (wave 4, no-op)
- TM4 and TM1 held 80/160, +0 -0: every game identical. TRADE_MIN_UNITS only binds below 8 units, which large maps never are. Binding trade conditions are TRADE_LOCAL_EDGE and the target size rule.
- TRADE_MIN_UNITS=4 (TM4) and =1 (TM1). Rule in LEDGER wave 3. Maps <= 1200 cells must be unchanged.

### H7 EC — keep non-leader splits on large maps after r150: ES225 REJECTED, ES300 INCONCLUSIVE (wave 5)
- ES225 held 80/160 net 0; ES300 84/160 net +4 (large +4). Only 1200+ cell maps flip. Main stopped.
- Ladder: maps over 1600 cells, units r200 47:62 and r300 42:62 in losses (opponents at the 64 cap). Locally both sides stay near the cap, which mutes this lever.

### H7b EC — ES300 confirm, SEED0=5000 (priority 2, chained in h8.sh)
- Rule in LEDGER wave 5. PASS = new-seed held net >= 9.

### H8 EC — SPLIT_SOFT_LIMIT 60 -> 62 (priority 3, chained in h8.sh)
- Diagnosis: on 800+ cell maps in r50-150, 82-95% of refused L4+ split turns are refused by the soft limit (we sit at 60; engine cap 64; opponents 62-63 on the ladder). Rule in LEDGER wave 5. Risk: escape splits lose their 2-unit reserve at the cap.

### H6 OP — opening (priority 6, low)
- No opening deficit found (r50 29:21 overall). Only if something new shows up.

### Parked (other owners, record only)
- Queen (QWQ #2): our queen dies in 159/228, median r123, 95 head_rammed; S maps queen-decided games 1-13.
- Feeding (Zhe #3): r400 top dragon in losses 12:21; L maps longest finishes 11-20.
