[test] EC_STATE_SPLIT vs v61

Setup: B61 = v61; ES = EC_STATE_SPLIT on, both vs v61 (NOSANDBOX); toggle-off identity: 40 OK, identical.
Mechanism: 41 big maps × 2 sides, seed 3000; complete saved splitcheck summary, 82 paired games. Means below are B61 → ES; split/death window r150–300.
Outcomes: held = heldset_sq + freshset, 80 maps × 2 sides; heldT = transposed copies, seed 3000; old = 10 maps × 4 seeds (3000–3003) × 2 sides. Pair by (map, seed, side).

| Criterion | Expected | Observed | Pass/fail |
|---|---|---|---|
| Long-parent growth splits (`lspl`) | ~0 → ≥10/game | 0.09 → 14.44 (+14.35) | Pass |
| Splits (`spl`, `gspl`) | Both rise | 303.95 → 308.73 (+4.78); 83.26 → 94.78 (+11.52) | Pass |
| Units r200 and r300 | Both rise toward 64 | r200: 60.65 → 60.52 (−0.12); r300: 58.90 → 59.09 (+0.18) | Fail |
| Total length r300 | Rise | 516.68 → 522.29 (+5.61) | Pass |
| Self-deaths (wall + self) | Increase < added growth splits | 110.23 → 109.16 (−1.07), below Δgspl +11.52 | Pass |

The two explicit “wrong if” conditions do not fire; the full mechanism criteria still fail on r200 units. Deltas use underlying means, rounded separately.

| Set | Games per tag (paired keys) | ES only (+) | B61 only (−) | Net |
|---|---:|---:|---:|---:|
| held | 160 | 22 | 28 | -6 |
| heldT | 160 | 29 | 22 | +7 |
| old | 80 | 7 | 7 | +0 |

Wins ES/B61: held 74/80 of 160; heldT 87/80 of 160; old 40/40 of 80.
Noise reference: paired SD ≈0.63/game, giving ≈±8 net at 160 games (one SD).
Reading: not supported by the full preregistration; held −6 and heldT +7 are inside noise and each below the +9 bar; old 0 passes the ≥−9 guardrail.
Data note: mech_big.json/log contain only 78 pairs (39 maps); the complete mechanism summary and replay inventory cover 82 pairs (41 maps).
Next step: inspect the kept replays for why extra growth splits do not raise r200 units before revising the state signals.
