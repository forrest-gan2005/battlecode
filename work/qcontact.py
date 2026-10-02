import sys, os
sys.path.insert(0, '/Users/quasarpark/meow-loop'); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bc
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
def one(a):
    f, ours, mp, gid = a
    info, out, team_of = bc.walk(f)
    l0 = info['map'].splitlines()[0].split(); W, H = int(l0[1]), int(l0[2])
    q = 0 if team_of[0] == ours else 1
    heads = {}; first = None; first_any = None; nearest = 99
    last = {}
    for e in out:
        if e[0] == 'move' and e[4]: heads[e[2]] = e[4]
        if e[0] == 'death': heads.pop(e[2], None)
        if e[0] == 'round':
            last = e[2]
            if q in heads and e[1] <= 200:
                qh = heads[q]
                for d, h in heads.items():
                    if team_of.get(d) != ours:
                        dist = min(abs(h[0] - qh[0]), W - abs(h[0] - qh[0])) + min(abs(h[1] - qh[1]), H - abs(h[1] - qh[1]))
                        if dist <= 5 and first is None: first = e[1]
            if first_any is None and e[1] <= 200:
                for d, h in heads.items():
                    if team_of.get(d) != ours:
                        for d2, h2 in heads.items():
                            if team_of.get(d2) == ours and abs(h[0]-h2[0]) + abs(h[1]-h2[1]) <= 5:
                                first_any = e[1]; break
                    if first_any is not None: break
    both = last.get(q, 0) > 0 and last.get(1 - q, 0) > 0
    return mp, W * H, first, first_any, both, last.get(q, 0) > 0
if __name__ == '__main__':
    args = []
    for line in open(sys.argv[1]):
        p = line.split()
        if len(p) < 6: continue
        for g in p[5].split(','):
            gid, mp, res, has = g.split(':')
            f = f'nr/{gid}.replay'
            if os.path.exists(f): args.append((f, p[4], mp, gid))
    with ProcessPoolExecutor(6) as ex: res = list(ex.map(one, args))
    by = defaultdict(list)
    for r in res: by[r[0]].append(r)
    for mp, rs in sorted(by.items(), key=lambda x: x[1][0][1]):
        fq = sorted(r[2] if r[2] is not None else 999 for r in rs)
        fa = sorted(r[3] if r[3] is not None else 999 for r in rs)
        both = sum(r[4] for r in rs)
        print(f"{mp:18s} cells {rs[0][1]:4d} n={len(rs):3d} both queens alive at end {both:2d} | queen first contact median {fq[len(fq)//2]} (<=50: {sum(x<=50 for x in fq)}, >100: {sum(x>100 for x in fq)}) | any contact median {fa[len(fa)//2]}")
