Computed paired ES vs B61 outcomes from JSON using Python stdlib, keyed by (map, seed, side); no duplicate or unmatched keys in held, heldT, or old. Totals (games; B61 wins/ES wins; +/−; net): held (160; 80/74; 22/28; −6), heldT (160; 80/87; 29/22; +7), old (80; 40/40; 7/7; 0).
Family breakdown pools map sizes and sqheld/fresh_gen; cells = games; B61 wins/ES wins; ES-only/B61-only; net. Descriptive only, no extra decision criteria.

| Family | held | heldT |
|---|---|---|
| blobs | 36; 18/20; 6/4; +2 | 36; 18/20; 7/5; +2 |
| islands | 12; 6/4; 1/3; -2 | 12; 6/6; 1/1; +0 |
| maze | 18; 9/8; 3/4; -1 | 18; 9/8; 2/3; -1 |
| open | 24; 12/12; 1/1; +0 | 24; 12/14; 5/3; +2 |
| portalrooms | 18; 9/9; 4/4; +0 | 18; 9/10; 4/3; +1 |
| portals | 24; 12/10; 4/6; -2 | 24; 12/13; 5/4; +1 |
| rooms | 18; 9/8; 2/3; -1 | 18; 9/11; 4/2; +2 |
| stripes | 10; 5/3; 1/3; -2 | 10; 5/5; 1/1; +0 |

Old per-map breakdown: all 10 maps have 8 games, B61/ES wins 4/4, net 0; +/− are portals 1/1, schooltime 2/2, slithery_fight 3/3, trauma 1/1; autarky, default, devil, dilemma, queen_of_spades, trophy each 0/0.
Source subsets (games; B61/ES wins; +/−; net): held sqheld (80; 40/35; 12/17; −5), fresh_gen (80; 40/39; 10/11; −1); heldT sqheld (80; 40/43; 14/11; +3), fresh_gen (80; 40/44; 15/11; +4).
Coverage matches the held map lists and exact transposed keys: held/heldT seed 3000, both sides; old seeds 3000–3003, both sides. Toggle-off log: 40 OK entries and identical.
Mechanism numbers come from the complete saved 82-pair splitcheck summary, not a new replay calculation; checked 41 maps × both sides against the existing replay filenames. Four criteria pass; r200 units fail. Outcome bars unmet; old guardrail passes.
Oddity: mech_big.json/log have 78 pairs, missing both sides of sqheld_blobs_large_90009 and sqheld_blobs_large_90030; these appear in the 82-pair summary and replay inventory. JSON mechanism wins B61/ES = 39/32 (+11/−18, net −7); do not conflate denominators. Cause unverified.
