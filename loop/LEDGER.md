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
