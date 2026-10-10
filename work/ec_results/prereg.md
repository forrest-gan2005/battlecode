# #14 pre-registration (written 2026-10-03 16:45 KST, before any candidate result)

Mechanism criteria, 41 big maps x2 (bigmaps.txt, SEED0=3000, KEEP), paired with B61 in the same ab3 call, `splitcheck.py B61 <TAG>`:
1. Fires: growth splits by parents longer than 4 in r150-300 (`lspl`) go from ~0 (B61) to >= 10 per game.
2. Splits r150-300 (`spl`, `gspl`) rise.
3. Units at r200 and r300 rise (nearer the 64 cap).
4. Total length at r300 (`tot300`) rises.
5. Self-deaths (wall + self, r150-300) rise by less than the added growth splits.
Wrong if: splits rise but tot300 does not, or self-deaths rise by as much as the added splits.

Outcome reading (vs B61, paired): bar = net >= 9 per 160-game set (held = heldset_sq + freshset x2; heldT = transposed copies x2); old 10 x8 must not lose noticeably (net >= -9 is within noise on 80 games).
