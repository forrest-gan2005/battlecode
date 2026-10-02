import json, sys, re
from collections import defaultdict
base_file, new_file = sys.argv[1], sys.argv[2]
base = {(r['map'], r['seed'], r['side']): r for r in json.load(open(base_file)) if r and r['tag'] == 'B61'}
def size(m):
    g = re.search(r'_(small|medium|large)_', m)
    return g.group(1) if g else 'official'
def src(m):
    s = m.split('_')[0]
    return s if s in ('sqheld', 'fresh', 'sq') else 'official'
rows = [r for r in json.load(open(new_file)) if r]
by = defaultdict(list)
for r in rows: by[r['tag']].append(r)
for tag, rs in sorted(by.items()):
    t = defaultdict(lambda: [0, 0, 0])
    for r in rs:
        b = base.get((r['map'], r['seed'], r['side']))
        if not b: continue
        for k in {'all', size(r['map']), src(r['map'])}:
            t[k][0] += r['win']; t[k][1] += r['win'] > b['win']; t[k][2] += b['win'] > r['win']
    print(tag, '  '.join('%s %d(+%d-%d=%+d)' % (k, v[0], v[1], v[2], v[1] - v[2]) for k, v in sorted(t.items())))
