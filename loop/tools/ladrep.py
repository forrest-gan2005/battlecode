import pickle, statistics as S
from collections import Counter, defaultdict
G = pickle.load(open('/Users/quasarpark/meow-loop/loop/tools/ladan.pkl', 'rb'))
def wl(rs): return '%d/%d' % (sum(r['win'] for r in rs), len(rs))
print('N', len(G), 'W', wl(G))
def size(r):
    c = r['W'] * r['H']
    return 'S<=800' if c <= 800 else 'M<=2000' if c <= 2000 else 'L>2000'
for k in ('S<=800', 'M<=2000', 'L>2000'):
    rs = [r for r in G if size(r) == k]; print('size', k, wl(rs), 'maps', len(set(r['map'] for r in rs)))
for lo, hi in ((0, 1700), (1700, 1850), (1850, 1950), (1950, 9999)):
    rs = [r for r in G if lo <= r['elo'] < hi]; print('elo', lo, hi, wl(rs), 'opps', len(set(r['opp'] for r in rs)))
def how(r):
    if r['elim']: return 'elim'
    qa, qb = r['qlen']['us'], r['qlen']['them']
    if qa or qb: return 'queen'
    return 'longest'
c = Counter((how(r), 'W' if r['win'] else 'L') for r in G); print('ending', dict(sorted(c.items())))
qa = Counter(('alive' if r['qd']['us'] is None else 'dead', 'alive' if r['qd']['them'] is None else 'dead', 'W' if r['win'] else 'L') for r in G)
print('queen (us,them,res)', dict(sorted(qa.items())))
qr = [r['qd']['us'][0] for r in G if r['qd']['us']]; tr = [r['qd']['them'][0] for r in G if r['qd']['them']]
print('queen death round median us', S.median(qr), 'them', S.median(tr), '| our q death reasons', Counter(r['qd']['us'][4] for r in G if r['qd']['us']), '| their', Counter(r['qd']['them'][4] for r in G if r['qd']['them']))
print('queen death round buckets us', Counter(min(4, d // 100) for d in qr), 'them', Counter(min(4, d // 100) for d in tr))
ph = lambda t: 'p0<100' if t < 100 else 'p1<300' if t < 300 else 'p2>=300'
for res in (True, False):
    rs = [r for r in G if r['win'] == res]; n = len(rs)
    print('\n== %s games %d: deaths per game by phase/reason (us | them), and length lost' % ('WIN' if res else 'LOSS', n))
    cnt = Counter(); lost = Counter()
    for r in rs:
        for d in r['deaths']:
            cnt[ph(d[0]), d[1], d[4]] += 1; lost[ph(d[0]), d[1], d[4]] += d[3]
    for p in ('p0<100', 'p1<300', 'p2>=300'):
        reasons = sorted(set(k[2] for k in cnt if k[0] == p))
        print(p, '  '.join('%s %.1f/%.1f (len %.0f/%.0f)' % (x, cnt[p, 'us', x] / n, cnt[p, 'them', x] / n, lost[p, 'us', x] / n, lost[p, 'them', x] / n) for x in reasons))
print('\n== self-inflicted (wall/self/body/none) deaths per game by length bucket, all games')
sb = Counter()
for r in G:
    for d in r['deaths']:
        if d[4] in ('wall', 'self', 'body', 'none'):
            sb[d[1], 'L2' if d[3] <= 2 else 'L3-5' if d[3] <= 5 else 'L6-15' if d[3] <= 15 else 'L16+'] += 1
print({k: round(v / len(G), 2) for k, v in sorted(sb.items())})
print('self-inflicted deaths near enemy head (<=3) share us', end=' ')
a = [d for r in G for d in r['deaths'] if d[1] == 'us' and d[4] in ('wall', 'self', 'body', 'none')]
print('%.2f' % (sum(d[5] <= 3 for d in a) / len(a)), 'them', end=' ')
b = [d for r in G for d in r['deaths'] if d[1] == 'them' and d[4] in ('wall', 'self', 'body', 'none')]
print('%.2f' % (sum(d[5] <= 3 for d in b) / len(b)))
print('\n== economy (median total length, units, top) us vs them')
for res in (None, True, False):
    rs = [r for r in G if res is None or r['win'] == res]
    line = []
    for s in (25, 50, 100, 150, 200, 300, 400, 'end'):
        v = [r['snaps'][s] for r in rs if s in r['snaps']]
        if not v: continue
        line.append('r%s %d:%d u%d:%d top%d:%d' % (s, S.median(x['us'][0] for x in v), S.median(x['them'][0] for x in v), S.median(x['us'][1] for x in v), S.median(x['them'][1] for x in v), S.median(x['us'][2] for x in v), S.median(x['them'][2] for x in v)))
    print({None: 'ALL', True: 'WIN', False: 'LOSS'}[res], len(rs)); print('  ' + '\n  '.join(line))
print('\n== total-length lead at r100/r200/r300 vs result')
for s in (100, 200, 300):
    c = Counter()
    for r in G:
        if s not in r['snaps']: continue
        x = r['snaps'][s]; lead = 'ahead' if x['us'][0] > x['them'][0] else 'behind'
        c[lead, 'W' if r['win'] else 'L'] += 1
    print(s, dict(sorted(c.items())))
print('\n== eats (length gained) per game by phase us:them; splits per game')
for res in (True, False):
    rs = [r for r in G if r['win'] == res]; n = len(rs)
    print('WIN' if res else 'LOSS', ' '.join('ph%d eat %.0f:%.0f split %.1f:%.1f' % (p, sum(r['eat']['us', p] for r in rs) / n, sum(r['eat']['them', p] for r in rs) / n, sum(r['splits']['us', p] for r in rs) / n, sum(r['splits']['them', p] for r in rs) / n) for p in (0, 1, 2)))
print('\n== by size: ending + self deaths/game + r100 total')
for k in ('S<=800', 'M<=2000', 'L>2000'):
    rs = [r for r in G if size(r) == k]; n = len(rs)
    sd = sum(1 for r in rs for d in r['deaths'] if d[1] == 'us' and d[4] in ('wall', 'self', 'body', 'none') and d[0] < 300) / n
    st = sum(1 for r in rs for d in r['deaths'] if d[1] == 'them' and d[4] in ('wall', 'self', 'body', 'none') and d[0] < 300) / n
    v = [r['snaps'][100] for r in rs if 100 in r['snaps']]
    print(k, wl(rs), dict(Counter((how(r), r['win']) for r in rs)), 'selfdeaths<r300 %.1f:%.1f' % (sd, st), 'r100 total %d:%d' % (S.median(x['us'][0] for x in v), S.median(x['them'][0] for x in v)))
print('\n== head-on deaths per game (ram=we moved into, rammed=they moved into us) by length bucket, us:them')
hb = Counter()
for r in G:
    for d in r['deaths']:
        if d[4].startswith('head'):
            hb[d[1], d[4], 'L<=3' if d[3] <= 3 else 'L4-9' if d[3] <= 9 else 'L10+'] += 1
print({k: round(v / len(G), 2) for k, v in sorted(hb.items())})
print('\n== big dragon (len>=10) deaths per game us:them by reason')
bb = Counter((d[1], d[4]) for r in G for d in r['deaths'] if d[3] >= 10)
print({k: round(v / len(G), 2) for k, v in sorted(bb.items())})
