import sys, os, pickle
sys.path.insert(0, '/Users/UNSW/battlecode'); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bc
from concurrent.futures import ProcessPoolExecutor
from collections import Counter
MAPF = {'Queen_Of_Spades': '../tune_runs/official123/queen_of_spades.map'}
def fast_tiles(f):
    s = set()
    for l in open(f):
        q = l.split()
        if q and q[0] == 'TILE' and int(q[3]) == 1 and 0 < int(q[4]) <= 50: s.add((int(q[1]), int(q[2])))
    return s
def one(arg):
    gid, ours, mp = arg
    fast = fast_tiles(MAPF[mp])
    info, out, team_of = bc.walk(os.path.join('nr', gid + '.replay'))
    c = Counter(); first = {}
    for e in out:
        if e[0] == 'move':
            t = 'us' if team_of.get(e[2]) == ours else 'them'
            h = e[4]
            if e[6] > e[5] > 0 and isinstance(h, tuple) and h in fast:
                for lim in (50, 100, 200):
                    if e[1] < lim: c[t, lim] += e[6] - e[5]
            if isinstance(h, tuple) and h in fast and t not in first: first[t] = e[1]
    return gid, c, first
if __name__ == '__main__':
    res = pickle.load(open('lossan.pkl', 'rb'))
    side = {}
    for line in open('nr_v55all.txt'):
        p = line.split()
        for g in p[5].split(','): side[g.split(':')[0]] = p[4]
    sel = [r for r in res if r['map'] == 'Queen_Of_Spades']
    with ProcessPoolExecutor(6) as ex: out = list(ex.map(one, [(r['gid'], side[r['gid']], r['map']) for r in sel]))
    meta = {r['gid']: r for r in sel}
    for gid, c, first in out:
        r = meta[gid]
        print(gid, r['opp'][:12], 'W' if r['win'] else 'L', 'side', side[gid], '首次进房 us', first.get('us'), 'them', first.get('them'), '| 房间吃 r50', c['us',50], c['them',50], 'r100', c['us',100], c['them',100], 'r200', c['us',200], c['them',200])
