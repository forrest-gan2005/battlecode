import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bc
from collections import Counter
MAPS = set(sys.argv[2].split(','))
tot = Counter(); lens = Counter(); crowd = Counter(); n = 0
for line in open(sys.argv[1]):
    p = line.split()
    for g in p[5].split(','):
        gid, mp, res, has = g.split(':')
        if mp not in MAPS: continue
        n += 1
        info, out, team_of = bc.walk(f'nr/{gid}.replay')
        l0 = info['map'].splitlines()[0].split(); W, H = int(l0[1]), int(l0[2])
        def d(a, b): return min(abs(a[0]-b[0]), W-abs(a[0]-b[0])) + min(abs(a[1]-b[1]), H-abs(a[1]-b[1]))
        heads = {}; age = {}
        for e in out:
            if e[0] == 'move' and e[4]: heads[e[2]] = e[4]
            elif e[0] == 'split': age[e[3]] = e[1]
            elif e[0] == 'death':
                h = heads.pop(e[2], None)
                if e[1] > 200 or team_of.get(e[2]) != p[4] or e[3] not in (0, 1, 2): continue
                r = bc.REASON[e[3]]; L = len(e[4]); tot[r] += 1; lens[min(L, 6)] += 1
                if h:
                    allies = sum(1 for k, x in heads.items() if team_of.get(k) == p[4] and d(x, h) <= 3)
                    foes = sum(1 for k, x in heads.items() if team_of.get(k) != p[4] and d(x, h) <= 3)
                    crowd[('allies<=3:' + str(min(allies, 3)), 'foes<=3:' + str(min(foes, 2)))] += 1
                a = e[1] - age.get(e[2], 0)
                crowd['age<=3' if a <= 3 else 'age<=10' if a <= 10 else 'age>10'] += 1
print('games', n, 'reasons', dict(tot), 'len', dict(sorted(lens.items())))
for k, v in sorted(crowd.items(), key=lambda x: -x[1]): print(k, v)
