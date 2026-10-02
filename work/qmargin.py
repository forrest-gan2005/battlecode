import sys, os, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bc
from collections import Counter
def reach(L): return max(1, (L + 3) // 4 + max(0, L - 2))
def one(f, ours):
    info, out, team_of = bc.walk(f)
    l0 = info['map'].splitlines()[0].split(); W, H = int(l0[1]), int(l0[2])
    def d(a, b): return min(abs(a[0]-b[0]), W-abs(a[0]-b[0])) + min(abs(a[1]-b[1]), H-abs(a[1]-b[1]))
    heads = {}; lens = {}; res = {'us': Counter(), 'them': Counter()}; qlen = {'us': [], 'them': []}
    qo = 0 if team_of[0] == ours else 1
    for e in out:
        if e[0] == 'move' and e[4]: heads[e[2]] = e[4]; lens[e[2]] = e[6]
        elif e[0] == 'death': heads.pop(e[2], None)
        elif e[0] == 'round' and e[1] >= 5:
            for side, q in (('us', qo), ('them', 1 - qo)):
                if q not in heads: continue
                tq = team_of[q]
                m = min((d(heads[q], h) - reach(lens.get(k, 2)) for k, h in heads.items() if team_of.get(k) != tq), default=99)
                res[side]['danger' if m <= 0 else 'edge' if m == 1 else 'safe'] += 1
                qlen[side].append(e[2].get(q, 0))
    return res, qlen
if __name__ == '__main__':
    tot = {'us': Counter(), 'them': Counter()}
    for line in open(sys.argv[1]):
        p = line.split()
        for g in p[5].split(','):
            gid = g.split(':')[0]; f = f'nr/{gid}.replay'
            if not os.path.exists(f): continue
            r, ql = one(f, p[4])
            for s in tot: tot[s].update(r[s])
            print(gid, g.split(':')[1][:10], {s: dict(r[s]) for s in r}, 'qlen avg us %.1f them %.1f' % (sum(ql['us'])/max(1,len(ql['us'])), sum(ql['them'])/max(1,len(ql['them']))))
    for s in tot:
        n = sum(tot[s].values()); print(s, {k: f'{v/n:.2f}' for k, v in tot[s].items()}, 'queen-rounds', n)
