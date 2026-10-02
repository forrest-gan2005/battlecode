import sys, os, pickle
sys.path.insert(0, '/Users/UNSW/battlecode'); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bc
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
def one(arg):
    gid, ours = arg
    info, out, team_of = bc.walk(os.path.join('nr', gid + '.replay'))
    eat = Counter(); splits = Counter()
    for e in out:
        if e[0] == 'move' and e[6] > e[5] > 0:
            t = 'us' if team_of.get(e[2]) == ours else 'them'
            for lim in (30, 50, 100):
                if e[1] < lim: eat[t, lim] += e[6] - e[5]
    return gid, eat
if __name__ == '__main__':
    res = pickle.load(open('lossan.pkl', 'rb'))
    side = {}
    for line in open('nr_v55all.txt'):
        p = line.split()
        for g in p[5].split(','): side[g.split(':')[0]] = p[4]
    with ProcessPoolExecutor(6) as ex: eats = dict(ex.map(one, [(r['gid'], side[r['gid']]) for r in res]))
    pickle.dump(eats, open('eats.pkl', 'wb'))
    for w in (True, False):
        for mp in sorted({r['map'] for r in res}):
            rs = [r for r in res if r['map'] == mp and r['win'] == w]
            if not rs: continue
            f = lambda t, l: sum(eats[r['gid']][t, l] for r in rs) / len(rs)
            print(f"{'W' if w else 'L'} {mp[:12]:12s} n{len(rs):2d} 吃 r30 {f('us',30):5.1f}:{f('them',30):5.1f}  r50 {f('us',50):5.1f}:{f('them',50):5.1f}  r100 {f('us',100):5.1f}:{f('them',100):5.1f}")
