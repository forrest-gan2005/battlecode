import json, sys
from collections import defaultdict
base = {(r['map'], r['seed'], r['side']): r for r in json.load(open(sys.argv[1])) if r and r['tag'] == sys.argv[2]}
rows = [r for r in json.load(open(sys.argv[3])) if r]
by = defaultdict(list)
for r in rows:
    by[r['tag']].append(r)
for tag, rs in sorted(by.items()):
    plus = minus = 0; dl = []; diffs = []
    for r in rs:
        b = base.get((r['map'], r['seed'], r['side']))
        if not b:
            continue
        dl.append((r['us'] - r['them']) - (b['us'] - b['them']))
        if r['win'] != b['win']:
            plus += r['win'] > b['win']; minus += b['win'] > r['win']
            diffs.append('%s %s' % (r['map'][:8], '+' if r['win'] else '-'))
    bw = sum(b['win'] for b in base.values())
    print('%-7s %d/%d (base %d) +%d -%d dlen %+.1f | %s' % (tag, sum(r['win'] for r in rs), len(rs), bw, plus, minus, sum(dl) / max(1, len(dl)), ' '.join(diffs)))
