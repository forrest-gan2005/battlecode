import sys, os, pickle
sys.path.insert(0, '/Users/quasarpark/meow-loop'); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bc
from concurrent.futures import ProcessPoolExecutor
from collections import Counter
D = '../tune_runs/official123/'
MAPF = {'Queen_Of_Spades': 'queen_of_spades', 'Autarky': 'autarky', 'Default': 'default', 'Devil': 'devil', 'Portals': 'portals',
        'Prisoners_Dilemma': 'dilemma', 'Schooltime': 'schooltime', 'Slithery_Fight': 'slithery_fight', 'Trauma': 'trauma', 'Trophy': 'trophy'}
def classes(f):
    s = {}
    for l in open(f):
        q = l.split()
        if q and q[0] == 'TILE':
            a, b = int(q[3]), int(q[4])
            s[(int(q[1]), int(q[2]))] = 'never' if b <= 0 else ('fount' if b <= 1 else ('fast' if b <= 60 else 'slow'))
    return s
def one(arg):
    gid, ours, mp = arg
    cls = classes(D + MAPF[mp] + '.map')
    info, out, team_of = bc.walk(os.path.join('nr', gid + '.replay'))
    c = Counter()
    for e in out:
        if e[0] == 'move' and e[6] > e[5] > 0 and e[1] < 100:
            t = 'us' if team_of.get(e[2]) == ours else 'them'
            c[t, cls.get(e[4], 'never')] += e[6] - e[5]
    return gid, c
if __name__ == '__main__':
    res = pickle.load(open('lossan.pkl', 'rb'))
    side = {}
    for line in open('nr_v55all.txt'):
        p = line.split()
        for g in p[5].split(','): side[g.split(':')[0]] = p[4]
    with ProcessPoolExecutor(6) as ex: out = dict(ex.map(one, [(r['gid'], side[r['gid']], r['map']) for r in res]))
    for mp in sorted({r['map'] for r in res}):
        for w in (True, False):
            rs = [r for r in res if r['map'] == mp and r['win'] == w]
            if not rs: continue
            f = lambda t, k: sum(out[r['gid']][t, k] for r in rs) / len(rs)
            print(f"{mp[:12]:12s} {'W' if w else 'L'} n{len(rs):2d} r0-100吃 " + '  '.join(f"{k} {f('us',k):5.1f}:{f('them',k):5.1f}" for k in ('fount', 'fast', 'slow', 'never')))
