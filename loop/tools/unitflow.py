import pickle
from collections import Counter
G = pickle.load(open('/Users/quasarpark/meow-loop/loop/tools/ladan.pkl', 'rb'))
def lb(L): return 'L2' if L <= 2 else 'L3-5' if L <= 5 else 'L6+'
for lo, hi in ((50, 100), (100, 150), (150, 300)):
    for name, sel in (('loss', lambda g: not g['win']), ('win', lambda g: g['win'])):
        gs = [g for g in G if sel(g)]; n = len(gs); c = Counter()
        for g in gs:
            for (r, s, did, L, reason, near, q) in g['deaths']:
                if lo <= r < hi:
                    c[s, 'all'] += 1
                    grp = 'self' if reason in ('wall', 'self', 'body', 'none') else reason
                    c[s, grp] += 1; c[s, grp, lb(L)] += 1
                    c[s, 'len'] += L
                    if grp == 'self' and near <= 3: c[s, 'press'] += 1
        u0 = sum(g['snaps'].get(lo, {}).get('us', (0, 0, 0))[1] for g in gs if lo in g['snaps']) / n
        t0 = sum(g['snaps'].get(lo, {}).get('them', (0, 0, 0))[1] for g in gs if lo in g['snaps']) / n
        hk = hi if hi in (100, 150, 200, 300) else None
        u1 = sum(g['snaps'].get(hk, {}).get('us', (0, 0, 0))[1] for g in gs) / n
        t1 = sum(g['snaps'].get(hk, {}).get('them', (0, 0, 0))[1] for g in gs) / n
        print(f'r{lo}-{hi} {name} N={n} units {u0:.1f}->{u1:.1f} : {t0:.1f}->{t1:.1f}')
        for k in ('all', 'self', 'press', 'head_ram', 'head_rammed', 'len'):
            print(f'   {k:12s} {c["us",k]/n:6.1f} : {c["them",k]/n:6.1f}')
        for grp in ('self', 'head_ram', 'head_rammed'):
            print('   ', grp, ' '.join(f'{b} {c["us",grp,b]/n:.1f}:{c["them",grp,b]/n:.1f}' for b in ('L2', 'L3-5', 'L6+')))
