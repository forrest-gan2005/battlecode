import pickle
from collections import Counter
G = pickle.load(open('/Users/quasarpark/meow-loop/loop/tools/terr13.pkl', 'rb'))
CAT = ['tight(b3<=12)', 'mid(13-18)', 'open(19+)']
for lab, f in (('all', lambda g: True), ('<=800', lambda g: g['cells'] <= 800), ('801-1200', lambda g: 800 < g['cells'] <= 1200), ('>1200', lambda g: g['cells'] > 1200)):
    for res in ('L', 'W'):
        gs = [g for g in G if f(g) and g['win'] == (res == 'W')]
        if not gs: continue
        occ = Counter(); dth = Counter()
        for g in gs:
            occ.update(g['occ']); dth.update(g['dth'])
        print(f'== {lab} {res} N={len(gs)}')
        for s in ('us', 'them'):
            to = sum(occ[s, c, e] for c in range(3) for e in (0, 1))
            row = []
            for c in range(3):
                for e in (0, 1):
                    o = occ[s, c, e]; d = sum(v for k, v in dth.items() if k[:3] == (s, c, e))
                    row.append(f'{CAT[c][:5]}{"E" if e else "-"} occ {o/to:.3f} d/1kr {1000*d/max(o,1):.1f} n{d}')
            print(s, ' | '.join(row))
