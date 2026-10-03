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

## Split propensity and per-unit growth (wave 1 addendum; `loop/tools/splitgap.py`, `splitgap.out`)
- r50-r150, non-queen dragons: length mix is the same for both sides (L2 59%, L4+ 7% vs 9%). Splits per 100 dragon-rounds at L4+: us 42.7, them 34.3 (wins 44.7:38.2, losses 40.7:32.2). We do not split less than the opponents.
- Length gain per unit-round (gain = change in total + length lost in deaths), losses (N=104): r25-50 0.094:0.101, r50-100 0.081:0.085, r100-150 0.066:0.072. Wins (N=97): 0.100:0.094, 0.086:0.085, 0.072:0.075.
- Length lost in deaths per game in losses: r50-100 us 57.8 of 80.4 gained, them 61.1 of 95.2; r100-150 us 73.6 of 87.8, them 89.5 of 119.4. Our gain and loss numbers are nearly the same in wins and losses; the opponent's numbers move.

## Wave 2 addendum: small-dragon deaths next to an enemy head (H4 sizing)
- Source: `loop/tools/ladan.pkl`, all 228 games. "Small" = length <= 5 at death; self = wall/self/body/none; adjacent = enemy head at Manhattan distance 1 from our head.
- Before r300, per game: our small self deaths 108.7, of which with an enemy head adjacent 7.13; theirs 108.0 and 3.81.
- Before r300, per game: small head_ram deaths (the dying dragon moved into a head) ours 9.8, theirs 22.8.
- From r300: our small self 60.3 (adjacent 2.38), theirs 88.5 (adjacent 1.73); small head_ram ours 2.9, theirs 8.3.
- Reading: H4 can act on at most about 7 events per game before r300 (the gap to the opponents is about 3.3). Opponents convert small dragons into head-ons about 2.3x as often as we do; this matches the older finding in `work/plan.md` (top teams initiate 14-25 head-ons per game). The TRADE_MIN_UNITS=1 test (te1) listed there has no recorded result.

## Wave 5 addendum: split timing and the unit cap (`loop/tools/splitlen.py`, `splitlen_rep.py`; diagnosis `loop/dev/diag8*`)
- Non-queen length mix r50-300 is nearly identical for both sides on all sizes (L2 ~0.6, L3 ~0.3, L4+ ~0.07); exception: maps > 1200 cells r150-300 losses, L4+ share 0.15 vs 0.31.
- Share of splits made from parents of length >= 6, r50-150: maps 801-1200 cells us 0.19-0.29 vs them 0.07-0.12; maps > 1200 cells us 0.31-0.40 vs them 0.12-0.20; maps <= 800 equal.
- Median units us:them on maps > 1600 cells (losses N=46): r100 46.5:42, r150 56:61, r200 47:62, r300 42:62. Wins (N=24): r150 60:53, r300 51:63. Engine cap is 64; opponents stay at 62-63 from r150.
- Local diagnosis (24 games vs v61, 800+ cell maps): in r50-150, 82-95% of refused splits by L4+ non-leader dragons are refused by SPLIT_SOFT_LIMIT = 60; exit/room, portal and harvest checks refuse <= 5%. After r150 on maps > 1200 cells the stop-round rule refuses 92-95%.

## Wave 8 addendum: where the food goes on maps <= 1200 cells (`loop/tools/eatnear.py`, `eatnear.pkl`)
- Length eaten per game r25-150, binned by the eater's distance to the nearest enemy head (e) and to the nearest other own head (a), at the eat. Maps <= 800 cells: losses N=40, wins N=61. 801-1200: losses N=22, wins N=35.
- <= 800 losses, r50-100 us:them: e<=3 alone (a4+) 14.9:9.9; e9+ with an ally within 3 1.1:11.2; e4-8 with an ally within 3 4.5:12.4. r100-150: e<=3 alone 21.2:13.7; e9+ ally near 3.0:23.1.
- <= 800 wins mirror this (e9+ ally near r50-100 18.9:1.1, r100-150 25.4:0.7), but our e<=3 alone eating stays higher than theirs in wins too (19.4:12.4).
- 801-1200 losses r50-100: e9+ ally near 6.8:17.3; wins 8.3:6.7.
- Reading: on small maps the side that wins eats in a safe back zone in clusters, far from enemy heads; this flips with the result, so it is mostly a symptom of territory. Our extra eating next to enemy heads while alone shows in both wins and losses (a style difference: the small-dragon contest rule targets pearls where the enemy is up to 1 step closer).

## Wave 10 addendum: static tight terrain next to enemy heads (`loop/tools/terr13.py`, `terr13_rep.py`, `terr13.pkl`)
- r50-300, non-queen dragons. Each head cell is classed by its static 3-step ball (cells reachable in <= 3 steps through non-kelp edges, bodies ignored): tight <= 12, mid 13-18, open 19+. "E" = an enemy head within Manhattan 3. Rates are self-inflicted deaths (wall/self/body/none) per 1000 head-rounds.
- Maps <= 800 cells, losses (N=40): share of head-rounds in tight+E us 0.130 vs them 0.051; death rate there 192 vs 127. Wins (N=61): 0.089 vs 0.126; 204 vs 130.
- Maps <= 800, tight+E deaths per game by length: losses L2 28.5:16.6, L3 24.8:13.2; wins L2 31.2:15.3, L3 29.6:14.3. L4+ < 3 per game for both.
- Maps > 800: tight+E deaths per game L2-3 losses 9.9:7.8, wins 5.8:7.5 (no gap). Tight cells without an enemy near, maps > 1200 losses: rate 121 vs 92.
- Reading: on small maps our L2-3 dragons die about 2x as often as the opponents' in corridor and dead-end cells while an enemy head is close, in both wins and losses (a style difference, not a result symptom). Open-terrain rates are equal or lower for us.
