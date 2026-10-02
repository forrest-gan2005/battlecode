import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bc
from collections import defaultdict
f, ours = sys.argv[1], sys.argv[2]
info, out, team_of = bc.walk(f)
l0 = info['map'].splitlines()[0].split(); W, H = int(l0[1]), int(l0[2])
def d(a, b): return min(abs(a[0]-b[0]), W-abs(a[0]-b[0])) + min(abs(a[1]-b[1]), H-abs(a[1]-b[1]))
qo = 0 if team_of[0] == ours else 1; qt = 1 - qo
heads = {}; lens = {}; deaths = []
for e in out:
    if e[0] == 'move' and e[4]: heads[e[2]] = e[4]; lens[e[2]] = e[6]
    elif e[0] == 'death':
        h = heads.pop(e[2], None)
        deaths.append((e[1], 'us' if team_of.get(e[2]) == ours else 'them', e[2], e[3], lens.get(e[2]), h))
    elif e[0] == 'round' and e[1] % 25 == 0:
        row = [f"r{e[1]:3d}"]
        for name, q in (('ourQ', qo), ('theirQ', qt)):
            if q in heads:
                h = heads[q]; tq = team_of[q]
                allies = sorted(d(h, x) for k, x in heads.items() if k != q and team_of.get(k) == tq)
                foes = sorted(d(h, x) for k, x in heads.items() if team_of.get(k) != tq)
                row.append(f"{name} L{e[2].get(q,0):2d} at{h} allies<=4:{sum(1 for a in allies if a<=4)} nearest ally {allies[0] if allies else '-'} foe {foes[0] if foes else '-'}")
            else: row.append(f"{name} dead")
        print(' | '.join(row))
print('queen deaths', [x for x in deaths if x[2] in (0, 1)])
