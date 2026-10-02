import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bc
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from portfirst import TOP, one
if __name__ == '__main__':
    args = []; opp = []
    for line in open(sys.argv[1]):
        p = line.split()
        if len(p) < 6 or p[2] not in TOP: continue
        for g in p[5].split(','):
            gid, mp, res, has = g.split(':')
            if mp in ('Queen_Of_Spades', 'Trauma') and os.path.exists(f'nr/{gid}.replay'): args.append((f'nr/{gid}.replay', p[4], mp)); opp.append(p[2])
    with ProcessPoolExecutor(6) as ex: rows = list(ex.map(one, args))
    by = defaultdict(list)
    for o, r in zip(opp, rows): by[(r[0], o)].append(r[2])
    for k, v in sorted(by.items()): print(k, sorted(v))
