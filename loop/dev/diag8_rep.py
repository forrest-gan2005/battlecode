import glob
from collections import Counter, defaultdict
NAME = {1: 'queen', 2: 'round/len<4/leader', 3: 'stop_round', 4: 'soft_limit', 5: 'harvesting', 6: 'cannot_split', 7: 'no_exit/tail_room', 8: 'child_spans_portal', 9: 'tail_on_portal', 0: 'not_reached'}
tot = Counter(); why = defaultdict(Counter)
for f in glob.glob('/Users/quasarpark/meow-loop/loop/dev/diag8_logs/*.log'):
    cur = {}
    for line in open(f):
        r, cells, i, L, c, lead = map(int, line.split())
        if c < 98:
            cur[i, r] = c; continue
        if L < 4: continue
        k = ('big' if cells > 1200 else 'mid' if cells > 800 else 'small', 'r50-150' if 50 <= r < 150 else 'r150-300' if r >= 150 else 'r0-50', 'L4' if L == 4 else 'L5-7' if L <= 7 else 'L8+', 'lead' if lead else '')
        tot[k] += 1
        why[k]['split' if c == 99 else NAME[cur.get((i, r), 0)]] += 1
for k in sorted(tot):
    n = tot[k]
    print(k, n, ' '.join(f'{w}:{v/n:.2f}' for w, v in why[k].most_common()))
