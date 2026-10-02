import pickle
from collections import Counter
G = pickle.load(open('ladan.pkl', 'rb'))
SI = ('wall', 'self', 'body', 'none')
print('== deaths per 100 unit-rounds (approx units from snapshots), us:them')
for res in (True, False, None):
    rs = [r for r in G if res is None or r['win'] == res]
    for lo, hi, a, b in ((0, 100, 50, 100), (100, 300, 150, 200), (300, 500, 400, 400)):
        ur = {t: sum((r['snaps'].get(a, r['snaps']['end'])[t][1] + r['snaps'].get(b, r['snaps']['end'])[t][1]) / 2 * (hi - lo) for r in rs) for t in ('us', 'them')}
        c = Counter((d[1], 'self' if d[4] in SI else 'head') for r in rs for d in r['deaths'] if lo <= d[0] < hi)
        print({True: 'WIN', False: 'LOSS', None: 'ALL'}[res], lo, hi, 'selfinf %.2f:%.2f head %.2f:%.2f' % tuple(100 * c[t, k] / ur[t] for k in ('self', 'head') for t in ('us', 'them')))
print('== self-inflicted deaths near enemy head (dist<=3) per game by phase, us:them')
for lo, hi in ((0, 100), (100, 300), (300, 500)):
    c = Counter(d[1] for r in G for d in r['deaths'] if lo <= d[0] < hi and d[4] in SI and d[5] <= 3)
    print(lo, hi, '%.1f:%.1f' % (c['us'] / len(G), c['them'] / len(G)))
print('== head-on pairs: same-round head deaths of both sides')
pairs = Counter()
for r in G:
    hd = Counter((d[0], d[1]) for d in r['deaths'] if d[4].startswith('head'))
    for (rd, s), n in hd.items():
        pairs['both' if (rd, 'us' if s == 'them' else 'them') in hd else 'one_' + s] += n
print(dict(pairs))
print('== r100 ahead by map size -> W/L')
size = lambda r: 'S' if r['W'] * r['H'] <= 800 else 'M' if r['W'] * r['H'] <= 2000 else 'L'
c = Counter((size(r), r['snaps'][100]['us'][0] > r['snaps'][100]['them'][0], r['win']) for r in G if 100 in r['snaps'])
for k in sorted(c): print(k, c[k])
print('== losses by elo band: r100 / r200 total us:them median')
import statistics as S
for lo, hi in ((0, 1850), (1850, 9999)):
    rs = [r for r in G if lo <= r['elo'] < hi and not r['win'] and 200 in r['snaps']]
    print(lo, hi, len(rs), 'r100 %d:%d r200 %d:%d units r200 %d:%d' % (S.median(r['snaps'][100]['us'][0] for r in rs), S.median(r['snaps'][100]['them'][0] for r in rs), S.median(r['snaps'][200]['us'][0] for r in rs), S.median(r['snaps'][200]['them'][0] for r in rs), S.median(r['snaps'][200]['us'][1] for r in rs), S.median(r['snaps'][200]['them'][1] for r in rs)))
print('== our queen max length / survival by size')
for s in 'SML':
    rs = [r for r in G if size(r) == s]
    print(s, len(rs), 'our q alive at end', sum(r['qd']['us'] is None for r in rs), 'their', sum(r['qd']['them'] is None for r in rs), 'median qmax us %d them %d' % (S.median(r['qmax']['us'] for r in rs), S.median(r['qmax']['them'] for r in rs)))
