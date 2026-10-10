[test] QG_SAFEZONE vs v61

Setup: Zhe's card #10 criteria; `zm1/` Z10c (v3) vs B61, 144 matched (map, seed, side) games on 36 maps, seeds 100–101, both sides. Exact coverage: `codex-report-queen.md`.
Outcome: `nh1.json`, B61/Z10, 320 pairs on 160 map variants, seed 3000, both sides. Z10's build is unidentified: `nh1.log` has no launch arguments; this is not verified v3 outcome evidence.

| Mechanism, matched games | B61 | Z10c |
|---|---:|---:|
| Games with zone found / approach / entry command | — | 143 / 90 / 63 of 144 |
| Entry commands with a resulting head update | — | 60 of 63; 3 same-round head deaths |
| Queen alive at end | 29/144 | 28/144; paired +9 / −10 |
| Queen deaths before r300 | 101/144 | 105/144; 10 avoided / 14 new |
| Death-round change, candidate minus base, both queens died | 106 pairs | median 0; 32 later / 26 earlier / 48 equal |
| Checker first-stay inside / portal-adjacent head-rounds | — | 4,646 / 372 (includes exit-trigger round) |

Card falsifier hit: 30/63 entry games log an enemy head inside (`ZBAD`); `dilemma_100_0` enters r18, logs invasion and dies head-to-head r101. `autarky_101_0` starts approach r36 and dies head-to-head r43 without entry. These are failures of this implementation, not a verdict on Zhe's idea.
`ZENTER` is a move command, not proof of surviving entry; the three same-round deaths above must not count as successful refuge.

Outcome by generator family (originals + `_T` variants); + = baseline loss → candidate win, − = reverse:
| Family | Pairs | Wins B61/Z10 | + | − | Net |
|---|---:|---:|---:|---:|---:|
| blobs | 72 | 36/37 | 3 | 2 | +1 |
| islands | 24 | 12/11 | 0 | 1 | −1 |
| maze | 36 | 18/17 | 0 | 1 | −1 |
| open | 48 | 24/22 | 1 | 3 | −2 |
| portalrooms | 36 | 18/18 | 1 | 1 | 0 |
| portals | 48 | 24/27 | 4 | 1 | +3 |
| rooms | 36 | 18/17 | 0 | 1 | −1 |
| stripes | 20 | 10/11 | 1 | 0 | +1 |
| All | 320 | 160/160 | 10 | 10 | 0 |

Noise: supplied SD 0.63/game gives a rough 1-SD scale of 11.3 net wins (3.5 percentage points); one seed and related transforms limit independence.
Reading: not supported for v3's expected survival signal; the unidentified-build outcome is inside noise (net 0), not evidence of equivalence.
Suggested next step: Zhe and QWQ review the saved entry/invasion failures before deciding whether to revise entry safety and containment.
