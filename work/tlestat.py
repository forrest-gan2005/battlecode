import sys, os
sys.path.insert(0, '/Users/UNSW/battlecode')
import replay
from collections import Counter
for line in open(sys.argv[1]):
    p = line.split()
    for g in p[5].split(','):
        gid, mp, res, has = g.split(':')
        f = f'nr/{gid}.replay'
        if not os.path.exists(f): continue
        info, events, team_of = replay.parse(f)
        ours = p[4]
        tle = Counter(); acts = Counter(); pts = {'us': [], 'them': []}
        for e in events:
            if e['kind'] != 'action': continue
            t = 'us' if team_of.get(e['id']) == ours else 'them'
            acts[t] += 1
            if e['tle']: tle[t] += 1
            pts[t].append(e['points'])
        def mx(l): return max(l) / 1e6 if l else 0
        def p99(l): return sorted(l)[int(len(l) * 0.99)] / 1e6 if l else 0
        print(f"{gid} {mp[:12]:12s} {res} TLE us {tle['us']}/{acts['us']} them {tle['them']}/{acts['them']}  pts p99 {p99(pts['us']):.1f}M|{p99(pts['them']):.1f}M max {mx(pts['us']):.1f}M|{mx(pts['them']):.1f}M")
