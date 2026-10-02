# Phase A: meow ladder analysis (wave 1, 2026-10-03)

Source: `work/nr_meow.txt`, 36 battles, 228 games, all with replays. Tools: `loop/tools/ladan.py` (parse, writes `ladan.pkl`), `ladrep.py`, `ladrep2.py` (outputs `ladrep.out`, `ladrep2.out`). "Self-inflicted" = death reason wall, self, body or none. "Head-on" deaths split into `head_ram` (the dying dragon moved) and `head_rammed` (the other side moved). All numbers are per game unless N is given. Map sizes: S <= 800 cells, M <= 2000, L > 2000.

## Results
- Overall 120/228 (53%).
- By size: S 61/101, M 38/68, L 21/59.
- By opponent rating: <1700 24/30, 1700-1849 68/114, 1850-1949 20/42, >=1950 8/42.
- How games end (W/L): elimination 57/30, queen decides (a queen alive at the end) 20/41, longest dragon (both queens dead) 43/37.
- By size, ending: S queen-decided 1 W / 13 L; M 9 W / 15 L; L 10 W / 13 L, and L longest-dragon 11 W / 20 L.

## Economy (median total length us:them, units us:them)
| round | all | wins (120) | losses (108) |
|---|---|---|---|
| r25 | 18:14, u7:5 | 17:13 | 19:18 |
| r50 | 29:21, u11:8 | 30:18, u12:7 | 28:30, u11:12 |
| r100 | 50:40, u19:16 | 52:25, u21:10 | 41:59, u16:24 |
| r200 | 70:86, u26:33 | 76:63 | 67:114, u24:46 |
| r300 | 76:119, u28:46 | 101:84 | 60:165, u19:58 |
| r400 | 78:133 | 90:88 | 65:162 |

- Our early numbers are almost constant across wins and losses (r50 28-30, ph0 eats 122-124). The opponent's numbers decide the split. Losses diverge in r50-r150: opponents go from 12 to 24 units in r50-r100, we go from 11 to 16.
- In losses r100-r300: opponents eat 511 vs our 279 and split 164 vs our 103 times. Our units fall from r200 to r300 (24 -> 19) while theirs rise (46 -> 58).
- Total-length lead at r100 -> result: ahead 79 W / 33 L, behind 35 W / 73 L. By size: S ahead 41-8, behind 14-30; M ahead 27-10, behind 11-20; L ahead 11-15, behind 10-23 (L maps are not decided by r100).
- Losses vs >=1850 opponents: r100 56:65, r200 65:131, units r200 26:54. Losses vs <1850: r100 41:59, r200 67:103.
- Earlier tests already rejected the obvious split-more levers (LEADER_GROW_ROUND_BIG 300, HARVEST_SPLIT): see `work/plan.md`.

## Deaths
- Per 100 unit-rounds, self-inflicted deaths are about equal for both sides (all games r0-100 1.39:1.29, r100-300 1.36:1.57). Raw self-inflicted deaths per game by length: us L2 119, L3-5 50, L6-15 1.8; them L2 128, L3-5 68, L6-15 8.5. We rarely lose big dragons to our own moves.
- **Self-inflicted deaths with an enemy head within 3 cells** (pressure deaths): us 6.3:3.4 (r0-100), 29.8:20.4 (r100-300), 14.0:12.1 (r300+). Share of our self-inflicted deaths that are pressure deaths: 29% vs their 17%. Per unit this is about 2x the opponents' rate. In r100-300, ours are mostly wall (L2 9.2, L3-5 7.7 vs their 5.0, 3.5) and body (L3-5 2.7 vs 0.9).
- Head-on deaths are almost always mutual (same-round pairs 18352 deaths, one-sided 518 ours / 1802 theirs). Length lost in same-round head-ons: equal-length 44.1:44.5; our bigger dragon 51.9:27.9; their bigger 31.5:63.1. Our L4+ vs their L<=3: 4.7 events/game, we lose 30.4, they lose 14.8; the mirror is 4.4 events, 13.4 vs 31.9. Head-on trading is symmetric overall.
- In losses, opponents initiate the head-ons in r100-300 (our head_rammed 22.6 vs their 9.9; their head_ram 24.7 vs our 7.8). Head deaths per 100 unit-rounds in losses r300+: 0.40:0.19.
- 'none' (no valid action) deaths: us 0.0 in r0-100 (they 3.5-3.9); r300+ us 18-21, they 14-28 (late-game, mostly feeding-related).
- Big dragons (L>=10) deaths per game: us 1.5, them 3.8. Our big-dragon deaths are 0.95 head_rammed, the rest near zero.

## Queen (owner QWQ, issue #2; recorded only)
- Queen state at end (us, them, result): alive/alive 11 W 7 L; alive/dead 30 W; dead/alive 49 L; dead/dead 79 W 52 L.
- Our queen dies in 159/228 games, median round 123 (theirs 158/228, median 109). Our queen death reasons: head_rammed 95, wall 40, self 17, body 14, head_ram 12, none 2. Their queens: head_rammed 50, wall 39, head_ram 30, self 19, body 14, none 9.
- Queen survival to the end by size (us/them): S 13/20 of 101, M 19/27 of 68, L 16/20 of 59. Median queen max length: 4 for both except M (4 vs 6).
- 49 losses have our queen dead and theirs alive; on S maps queen-decided games go 1-13.

## Feeding / late game (owner Zhe, issue #3; recorded only)
- r400 top dragon: wins 17:10, losses 12:21. End top: wins 15:2, losses 14:27.
- Longest-dragon finishes on L maps 11 W / 20 L.
