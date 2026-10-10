[test] QG_CORNER vs v61

Setup: Zhe's card #11 criteria; `zm1/` Z11 vs B61, 96 matched (map, seed, side) games on 24 maps, seeds 100–101, both sides. Exact coverage: `codex-report-queen.md`.
Outcome: `nh1.json`, B61/Z11, 320 pairs on 160 map variants, seed 3000, both sides; includes small, medium and large maps plus `_T` variants.

| Mechanism, matched games | B61 | Z11 |
|---|---:|---:|
| Games with anchor / portal at anchor / known portal exit | — | 78 / 6 / 5 of 96 |
| Corner-near logged rounds / escape commands | — | 4,130 / 4 commands in 4 games |
| Queen alive at end | 11/96 | 8/96; paired +0 / −3 |
| Queen deaths before r150 | 65/96 | 62/96; 7 avoided / 4 new |
| Death-round change, candidate minus base, both queens died | 85 pairs | median 0; 32 later / 28 earlier / 25 equal |
| All queen head-collision deaths (location unclassified) | 32/96 | 32/96 |

Card falsifier status: not established. The checker's proximity flags find 27 deaths within 2 rounds of `CNEAR`, which does not prove boxing-in; 1 death within 15 rounds of escape is `portals_100_0`, self-collision r53 after crossing r52, not an enemy collision. Open-space rams are not separately identified, so that expected signal remains unresolved.
Only 6/78 anchored games had a portal at an anchor; the emergency-escape part of the claim received little exposure.

Outcome by generator family (originals + `_T` variants); + = baseline loss → candidate win, − = reverse:
| Family | Pairs | Wins B61/Z11 | + | − | Net |
|---|---:|---:|---:|---:|---:|
| blobs | 72 | 36/41 | 15 | 10 | +5 |
| islands | 24 | 12/9 | 1 | 4 | −3 |
| maze | 36 | 18/11 | 4 | 11 | −7 |
| open | 48 | 24/24 | 0 | 0 | 0 |
| portalrooms | 36 | 18/17 | 1 | 2 | −1 |
| portals | 48 | 24/24 | 0 | 0 | 0 |
| rooms | 36 | 18/12 | 4 | 10 | −6 |
| stripes | 20 | 10/10 | 0 | 0 | 0 |
| All | 320 | 160/148 | 25 | 37 | −12 |

Noise: supplied SD 0.63/game gives a rough 1-SD scale of 11.3 net wins (3.5 percentage points); −12 is about −1.06 SD, with dependence possible across transforms/sides.
Reading: inside noise for outcome (−3.75 percentage points); a small early-death improvement, worse end survival, and unresolved open-space/falsifier evidence do not establish the claim.
Suggested next step: Zhe and QWQ inspect the saved corner-death and four escape sequences to determine whether boxing-in or unsafe destinations warrant a change.
