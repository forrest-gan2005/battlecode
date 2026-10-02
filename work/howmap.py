import sys, os
sys.path.insert(0, '/Users/UNSW/battlecode'); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ladq
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
def one(a):
    f, ours, opp, mp = a
    r = ladq.run((f, ours, opp))
    return mp, ('W_' if r['win'] else 'L_') + r['how']
if __name__ == '__main__':
    args = []
    for line in open(sys.argv[1]):
        p = line.split()
        if len(p) < 6: continue
        for g in p[5].split(','):
            gid, mp, res, has = g.split(':')
            f = f'nr/{gid}.replay'
            if os.path.exists(f): args.append((f, p[4], p[2], mp))
    with ProcessPoolExecutor(6) as ex: res = list(ex.map(one, args))
    c = defaultdict(Counter)
    for mp, k in res: c[mp][k] += 1
    for mp in sorted(c): print(f"{mp:18s} n={sum(c[mp].values()):3d}", dict(sorted(c[mp].items())))
