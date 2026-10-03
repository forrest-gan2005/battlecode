# Loop state

- Phase: C (wave 9, 09:11). Phase A done (`loop/ANALYSIS.md`), Phase B done (noise table below).
- Baseline B61 = mybot2 + `loop/dev/v61toggles.txt` (= `work/v60toggles.txt` + POCKET_CAP=48,QUEEN_HOME_CLOSED=true). `ident_B61.txt` identical. B61c (mybot2 with CB_TRAP code) ident in `ident_B61c.txt`. TR_PRESS_DEPTH (wave 3) and EC_SPLIT_ROUND_BIG (wave 4): toggle-off object file byte-identical (md5 aee4013d...).
- Placebos: P1 = B61 + TIE_SEED=1, P2 = B61 + TIE_SEED=2 (tie-break jitter only).
- Running chain (check `ps` before starting anything; never more than 8 workers):
  1. `loop/h8c.sh` (pid 40325): H8c B61 + SL62 held x2 SEED0=7000 (started 08:56, est. ~09:22) -> `H8c_held7.json`, then `H8c_done`.
  2. `loop/h11.sh` (pid 11021): waits for `H8c_done`: H11 CS0 + CS2 held x2 SEED0=3000 (est. ~09:48) -> `H11_held.json`, then `H11_done`.
  3. `loop/h12s.sh` (pid 30704): waits for `H11_done`: H12 ST2 + ST2O held x2 SEED0=3000 (est. ~10:15) -> `H12s_held.json`, then `H12s_done`.
- Next wave: H8c: `judge.py loop/results/H8c_held7.json loop/results/H8c_held7.json` (judge takes the B61 tag from the base file) and add to H8 (+23 -16) and H8b (+23 -18). H11: `judge.py B_held.json H11_held.json`. H12: `judge.py B_held.json H12s_held.json`.
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

### H1b TR — local press ring: REJECTED (wave 6)
- PD2 held 38/160 net -42, PD4 33/160 net -47 (all sizes negative). TR_PRESS family closed.
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

### H7b EC — ES300 confirm, SEED0=5000: REJECTED (wave 6)
- ES300 SEED0=5000 held 76/160, +14 -18, net -4 (B61 80/160). Combined with H7: +29 -29, net 0. H7 family closed.
- Rule in LEDGER wave 5. PASS = new-seed held net >= 9.

### H8 EC — SPLIT_SOFT_LIMIT 60 -> 62: INCONCLUSIVE (wave 7); H8b confirm running
- SL62 held 87/160, +23 -16, net +7 (large +4, medium +3; > 1200 cells +18 -14, <= 800 +3 -0). H8b = SEED0=5000 held, rule in LEDGER wave 7.
- Diagnosis: on 800+ cell maps in r50-150, 82-95% of refused L4+ split turns are refused by the soft limit (we sit at 60; engine cap 64; opponents 62-63 on the ladder). Rule in LEDGER wave 5. Risk: escape splits lose their 2-unit reserve at the cap.

### H9 CB — even trades on maps over 1200 cells: REJECTED (wave 7)
- TE held 76/160, +17 -21, net -4; zero flips on maps <= 1200 cells.
- Ladder, maps > 1200 cells, r < 300: head_ram us 12.4 vs them 53.3 (losses), 12.5 vs 44.4 (wins); head-on length lost even (190:221). Our big-map rule needs target parts >= max(5, L+2) below the cap. Toggle: existing `TRADE_EVEN=true` (TE). Rule in LEDGER wave 6.
- Local caveat: mirror games vs v61 already show 63 head_rams per side per game on big maps (at-cap rule), so the local signal may be small.

### H10 CB — trade while locally even or outnumbered: REJECTED (wave 9)
- LE0 held 80/160 net 0 (68 flips); LEM1 63/160 net -17. TRADE_LOCAL_EDGE family closed.
- Ladder (edge10.py, r < 300, initiator head-on deaths per game by own heads within 6 + 1 - enemy heads within 6): maps > 1200 cells us edge <= 0 4.0, >= 1 8.2; them 14.4, 34.3. 801-1200: us 2.9, 7.7; them 5.8, 9.7. <= 800: us 2.3, 4.9; them 3.4, 4.5.
- Toggle: existing `TRADE_LOCAL_EDGE` 1 -> 0 (LE0) and -1 (LEM1). Rule in LEDGER wave 7. Falsifier: held net <= 0; head_ram not up 20% in KEEP replays.

### H11 EC — small-dragon pearl contest slack (queued, chained in h11.sh)
- CONTEST_SLACK 1 -> 0 (CS0) and 2 (CS2). Rule in LEDGER wave 8. Mechanism tool `mech11.py` (MB61 near-enemy eaten 84.2/game, pressure 0.246 per 100 unit-rounds).

### H12 CB — small dragons weigh enemy-head threat 2x (queued, chained in h12s.sh)
- SMALL_THREAT_MULT=2.0 (ST2), + SMALL_THREAT_OUTNUMBERED=true (ST2O). Rule in LEDGER wave 9. Evidence: pressure deaths ~2x the opponents' per unit; threat penalty for L<=2 (~225) < pearl + EAT_BONUS.

### H6 OP — opening (priority 6, low)
- No opening deficit found (r50 29:21 overall). Only if something new shows up.

### Parked (other owners, record only)
- Queen (QWQ #2): our queen dies in 159/228, median r123, 95 head_rammed; S maps queen-decided games 1-13.
- Feeding (Zhe #3): r400 top dragon in losses 12:21; L maps longest finishes 11-20.
