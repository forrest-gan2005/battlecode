# Loop ledger

One section per wave, facts only.

## Wave 1 — 2026-10-03 03:42-04:2x KST
- Phase A done. Parsed all 228 meow ladder games (`loop/tools/ladan.py`, reports `ladrep.out`, `ladrep2.out`); facts in `loop/ANALYSIS.md`. Results 120/228; S 61/101, M 38/68, L 21/59; vs >=1950 8/42. r100 total-length lead: ahead 79-33, behind 35-73. Pressure self-deaths (enemy head <=3) us 29.8 vs them 20.4 per game in r100-300.
- Hypothesis queue H1-H6 written to `loop/STATE.md` (TR, CB, EC first; queen/feeding parked for QWQ/Zhe).
- Phase B started 03:43 (`loop/phaseB.sh`, pid 30425): B61, P1 (TIE_SEED=1), P2 (TIE_SEED=2) vs v61; held x2 then main x8, SEED0=3000.
- B61 build: main.cpp/helper.hpp/bot.toml byte-identical to v61 at start. At ~03:53 `tune_runs/ab2/B61` was rebuilt from mybot2 with the new TR_PRESS_ROOM code (toggle off, branch unreachable: `TR_PRESS_ROOM > 0` short-circuits). Games after that point used this build. Play should be identical; ident.py vs v61 still has to be run on this build (wave 2, after the batch).
- Code: `TR_PRESS_ROOM` (int, 0 = off) and `TR_PRESS_MAX_LEN` (8) in mybot2. When > 0, a dragon of length <= MAX_LEN whose destination has an enemy head within TR_PRESS_ROOM cells surveys room without cells the enemy reaches no later than we do. Compiles off and with =3. `work/ident.py` now accepts a path (tag = basename). `loop/tools/press.py` = pressure-death metric for local KEEP replays.

### Pre-registration: H1 (TR_PRESS_ROOM), to run in wave 2+
- Variant PR3 = B61 + TR_PRESS_ROOM=3.
- Runs, in order: (0) `REF=v61 python3 ident.py tune_runs/ab2/B61` must say identical. (1) held: heldset_sq+freshset x2, SEED0=3000, vs v61, tag PR3, paired vs B61 in `B_held.json`. (2) main: official+newset x8, SEED0=3000, paired vs B61 in `B_main.json`. (3) only if (1)+(2) pass: held SEED0=5000 x2 with B61 and PR3. (4) mechanism: KEEP=1 (FAST unset) on 6 generated maps x2 seeds, B61 and PR3 vs v61; `press.py` on the replays. (5) CPU: sandbox on the 3 largest 64x64 maps, max turn < 60M.
- Let Nh = max |net| of P1, P2 on held, Nm = same on main.
- PASS (go to confirm): held net >= Nh + 4 and main net >= -Nm.
- CANDIDATE: PASS, and confirm held net > 0, and PR3 pressure deaths per 100 unit-rounds at least 15% below B61, and CPU OK.
- REJECTED: held net <= 0, or the mechanism shows no drop.
- Otherwise INCONCLUSIVE.

### Pre-registration: H2 (SMALL_UNIT_THREAT_REACH=2), same batch as H1
- Variant SR2 = B61 + SMALL_UNIT_THREAT_REACH=2 (existing constant, no new code).
- Runs: same held and main runs as H1 (one ab3 batch with PR3 and SR2), paired vs B61 in `B_held.json` / `B_main.json`. Confirm and mechanism only if it passes: held SEED0=5000; KEEP replays, our L4-9 head_rammed per game vs B61.
- Same PASS / CANDIDATE / REJECTED / INCONCLUSIVE rule as H1 (Nh, Nm from the placebos). Mechanism for CANDIDATE: our L4-9 head_rammed per game at least 15% below B61 and pressure deaths per unit not more than 10% above B61.

### Chained runner (started in wave 1)
- `loop/h12.sh` waits for `loop/results/B_done`, then: ident of B61 vs v61 -> `loop/results/ident_B61.txt`; held x2 SEED0=3000 PR3+SR2 vs v61 -> `loop/results/H12_held.json`; main x8 SEED0=3000 -> `loop/results/H12_main.json`; then `loop/results/H12_done`.
- The held/main runs start only if ident says identical; otherwise it writes `H12_ident_failed` and stops.

### Wave 1 close (04:12 KST)
- Extra analysis: split propensity is not lower than the opponents' (L4+ splits per 100 dragon-rounds 42.7 vs 34.3); per-unit gain is equal (losses r50-100 0.081 vs 0.085). H3 REJECTED by analysis, no runs spent.
- No game results yet. Phase B at held map 44/79 at 04:10 (no partial output; ab3 writes at the end).
- Open runs: phaseB.sh pid 30425; h12.sh pid 47893 (waits for B_done). Verdicts on H1/H2 pending.

## Wave 2 — 2026-10-03 04:23-04:28 KST
- Phase B held finished 04:24 (`loop/results/B_held.json`, 80 maps x2 = 160 games per tag, SEED0=3000, vs v61):
  - B61 80/160. P1 (TIE_SEED=1) 85/160, +34 -29 vs B61 (net +5). P2 (TIE_SEED=2) 77/160, +35 -38 (net -3). P1 vs P2 differ in 58/160.
  - So about 40% of held games flip under a no-effect change; null SD of net is about sqrt(flips) ~ 8. Nh = 5.
  - Wave 1 pre-registration therefore gives the H1/H2 held bar: net >= 9 (unchanged rule; recorded here as a fact that this is ~1 SD, so the SEED0=5000 confirm carries the weight).
- Phase B main started 04:24 (B61 build from mybot2 at 04:24:17, contains TR_PRESS code off, no CB_TRAP code). Expected ~05:40.
- Code: `CB_TRAP_TRADE` (int, 0 = off) and `CB_TRAP_DEAD` (bool) added to mybot2 (installed 04:24:48, after the B_main build). When CB_TRAP_TRADE > 0, a non-queen non-leader dragon of length <= CB_TRAP_TRADE whose every scored move is closed (no tail reach and room < length+2; with CB_TRAP_DEAD also dead-end moves count as closed) and that has an enemy head on an adjacent non-portal cell takes the head-on move (engine: stepping into a head kills both). Compiles with (0,false), (5,false), (5,true). Text diff of the toggle-off build (B61c) vs v61/main.cpp is only the constexpr lines and the guarded TR_PRESS / CB_TRAP blocks; helper.hpp identical.
- Note: H12's PR3/SR2 builds (made when H12 starts, after B_done) will contain the CB_TRAP code off. `h4.sh` runs ident on B61c (current mybot2 + v61 toggles); if that fails, H12 results are also suspect.
- `loop/tools/press.py` now also prints per game: our L4-9 head_rammed, our L<=5 head_ram (mover), our L<=5 self deaths.

### Pre-registration: H4 (CB_TRAP_TRADE)
- Variants: TT5 = B61 + CB_TRAP_TRADE=5. TT5D = B61 + CB_TRAP_TRADE=5, CB_TRAP_DEAD=true.
- Runs (chained in `loop/h4.sh`, starts after H12_done): (0) build B61c from mybot2 with v61 toggles, `REF=v61 ident.py tune_runs/ab2/B61c` must say identical, else `H4_ident_failed` and stop. (1) held x2 SEED0=3000 -> `H4_held.json`. (2) main x8 SEED0=3000 -> `H4_main.json`. Paired vs B61 in `B_held.json` / `B_main.json`.
- Mechanism (chained in `loop/mech.sh`, after H4_done): KEEP=1, 10 devset_sq maps (one per generator/size type, `loop/dev/mechset.txt`) x4 (2 seeds x 2 sides), SEED0=7000, tags MB61, MPR3, MSR2, MTT5, MTT5D vs v61 -> `mech.json`, `mech_press.txt`. This also serves the H1/H2 mechanism step.
- PASS / CANDIDATE / REJECTED / INCONCLUSIVE: same rule as H1 (held net >= Nh+4 = 9, main net >= -Nm; confirm SEED0=5000 held net > 0; CPU check). Mechanism for CANDIDATE: our L<=5 head_ram per game rises and our L<=5 self deaths per game fall vs MB61 (both directions required); if L<=5 head_ram does not rise at all, the toggle never fires -> REJECTED as no-op.
- Two variants are tested, so a pass by only one of them needs the confirm run before any claim.

### Wave 2 close (04:28 KST)
- Open runs: phaseB.sh pid 30425 (B_main, est. 05:40); h12.sh pid 47893 (est. 07:00); h4.sh pid 26722 (est. 08:30); mech.sh pid 28961 (est. 09:15). No verdicts this wave (no H results yet). H5 not chained: CPU after the chain is kept for SEED0=5000 confirm runs of any PASS.

## Wave 3 — 2026-10-03 05:03 KST
- Phase B main finished 04:48 (`B_main.json`, `B_main.log`). B61 88/176 vs v61 (identical builds, 50%). P1 78/176 (+34 -44, net -10), P2 74/176 (+26 -40, net -14). P1 vs P2 on main: +35 -39 (74 flips).
- Fact: on held both placebos are near 0 (+5, -3); on main both are below B61 (-10, -14). v61 was tuned on the official maps, so a no-effect perturbation already loses ~12 on main. Main net is biased against any change; this is why held carries the verdict.
- From the wave 1 rule: Nh = 5, Nm = 14. PASS bar: held net >= 9 and main net >= -14.
- `ident_B61.txt`: identical (h12.sh step 0). H12 held started 04:52.

### Pre-registration: H5 (TRADE_MIN_UNITS on maps over 1200 cells)
- Variants (existing constant, no code): TM4 = B61 + TRADE_MIN_UNITS=4; TM1 = B61 + TRADE_MIN_UNITS=1.
- Runs (`loop/h5.sh`, after `mech_done` and while no `loop/results/HOLD_H5` exists): held heldset_sq+freshset x2 SEED0=3000 vs v61 -> `H5_held.json`; main official+newset x8 SEED0=3000 -> `H5_main.json`; paired vs B61 in `B_held.json` / `B_main.json`.
- Only maps over 1200 cells can change (small maps already use AGGRESSIVE_TRADE_MIN_UNITS=1). Games on smaller maps should be identical; any flip there is a bug signal.
- Same rule as H1: PASS = held net >= 9 and main net >= -14; CANDIDATE = PASS + SEED0=5000 held net > 0 + mechanism + CPU. Mechanism (KEEP replays, large generated maps): our head_ram per game rises vs B61 and our unit count at r200 does not fall by more than 10%. REJECTED: held net <= 0, or no rise in head_ram. Otherwise INCONCLUSIVE.

### H1 / H2 held results (`H12_held.json`, finished 05:17)
- Paired vs B61 (`python3 loop/tools/judge.py loop/results/B_held.json loop/results/H12_held.json`):
  - PR3 23/160, +11 -68, net -57. By size: small 1/40 wins (+0 -20), medium 2 (+1 -24), large 20 (+10 -24). sqheld -31, fresh -26. Wiped (eliminated) 71/160 vs B61 28/160. dlen -19.3.
  - SR2 69/160, +25 -36, net -11. Small -3, medium -9, large +1. sqheld -8, fresh -3. Wiped 33 vs 28.
- **H1 (TR_PRESS_ROOM=3): REJECTED** (held net -57 <= 0).
- **H2 (SMALL_UNIT_THREAT_REACH=2): REJECTED** (held net -11 <= 0).
- H12 main batch was stopped at 05:18 (both verdicts already fixed by held; main cannot change a REJECTED). Killing `ab3.py` alone leaves its multiprocessing workers alive; they kept starting games until killed (pids 95671-95679). No H12_main.json. h12.sh touched H12_done; h4.sh started at 05:18.
- Code reading for H1: the press block uses `rival_dist`, a BFS from every visible enemy head over the whole map, and it cuts the survey BFS, so it removes every cell the enemy reaches first anywhere (a Voronoi split), not only the closing ring. It also hides pearls, feed and trade targets behind that boundary. A blunt implementation, not a clean test of the claim. MPR3 replays from `mech.sh` will show what happened.

### Pre-registration: H1b (TR_PRESS_DEPTH, local press ring only)
- Code: `TR_PRESS_DEPTH` (int, 0 = unlimited, the H1 behaviour). With > 0 the press block applies only to survey cells at steps < DEPTH from the destination. Toggle-off object file byte-identical to the previous mybot2 (clang++ -O2 md5 aee4013d... before and after), so ident vs v61 carries over from B61c.
- Variants: PD2 = B61 + TR_PRESS_ROOM=3, TR_PRESS_DEPTH=2; PD4 = B61 + TR_PRESS_ROOM=3, TR_PRESS_DEPTH=4.
- Runs (`loop/h1b.sh`, after `H5_done`, while no `HOLD_H1B`): held x2 SEED0=3000 -> `H1b_held.json`; main x8 SEED0=3000 -> `H1b_main.json`; paired vs B61.
- PASS = held net >= 9 and main net >= -14. CANDIDATE = PASS + SEED0=5000 held net > 0 + mechanism (pressure deaths per 100 unit-rounds >= 15% below B61 and wiped count not above B61 by more than 10%) + CPU. REJECTED = held net <= 0 or no drop in pressure deaths. Otherwise INCONCLUSIVE.
- Kill early: if the held net of both variants is <= 0, the main batch may be skipped.
