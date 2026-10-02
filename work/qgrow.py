import sys, os
sys.path.insert(0, '/Users/quasarpark/meow-loop'); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bc
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
def one(arg):
    gid, ours = arg
    info, out, team_of = bc.walk(f'nr/{gid}.replay')
    q = 0 if team_of[0] == ours else 1
    l0 = info['map'].splitlines()[0].split(); cells = int(l0[1]) * int(l0[2])
    ql = {}; splits = 0; eats = 0
    for e in out:
        if e[0] == 'round' and e[1] in (50, 100, 200, 300, 400, 499): ql[e[1]] = e[2].get(q, 0)
        if e[0] == 'split' and e[2] == q: splits += 1
        if e[0] == 'move' and e[2] == q and e[6] > e[5]: eats += e[6] - e[5]
    return gid, cells, ql, splits, eats
if __name__ == '__main__':
    args = []
    for line in open(sys.argv[1]):
        p = line.split()
        if len(p) < 6: continue
        for g in p[5].split(','):
            gid = g.split(':')[0]
            if os.path.exists(f'nr/{gid}.replay'): args.append((gid, p[4]))
    with ProcessPoolExecutor(6) as ex: res = list(ex.map(one, args))
    for big in (False, True):
        rs = [r for r in res if (r[1] > 600) == big]
        print('maps >600' if big else 'maps <=600', len(rs), 'games; queen splits mean %.1f, eats mean %.1f' % (sum(r[3] for r in rs) / len(rs), sum(r[4] for r in rs) / len(rs)))
        for rr in (50, 100, 200, 300, 400, 499):
            alive = [r[2].get(rr, 0) for r in rs if r[2].get(rr, 0) > 0]
            if alive: print('   r%d alive %d/%d, len dist %s' % (rr, len(alive), len(rs), dict(sorted(Counter(min(l, 10) for l in alive).items()))))
