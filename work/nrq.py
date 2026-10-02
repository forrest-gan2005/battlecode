import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, '/Users/quasarpark/meow-loop')
import replay, queen
from collections import Counter, defaultdict
import ourside
side = {}; opp = {}; res = {}
for l in open(sys.argv[1]):
    p = l.split()
    for g in p[5].split(','):
        gid, m, w, _ = g.split(':'); side[gid] = p[4]; opp[gid] = p[2]; res[gid] = w
ourside.ours_of = lambda f: side[os.path.basename(f)[:-7]]
queen.ourside.ours_of = ourside.ours_of
agg = defaultdict(Counter)
for gid in side:
    r = queen.run(f'nr/{gid}.replay')
    if not r: continue
    o = opp[gid]; c = agg['Sabotage-d' if o == 'Sabotage-d' else 'others']
    c['n'] += 1; c['win'] += r['win']
    how = 'elim' if r['elim'] else 'queen' if r['qo'] != r['qt'] else 'longest'
    c['how_' + how + ('_W' if r['win'] else '_L')] += 1
    c['ourQalive'] += r['qo'] > 0; c['theirQalive'] += r['qt'] > 0
    if r['do'] is not None and r['do'] < 100: c['ourQdie<100'] += 1
    if r['dt'] is not None and r['dt'] < 100: c['theirQdie<100'] += 1
for k, c in agg.items(): print(k, dict(sorted(c.items())))
