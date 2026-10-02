import sys, os, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bc, reach
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from portfirst import TOP
MAPF = {'Queen_Of_Spades': 'queen_of_spades', 'Default': 'default', 'Schooltime': 'schooltime', 'Trauma': 'trauma', 'Autarky': 'autarky', 'Portals': 'portals', 'Stronghold': 'stronghold', 'Slithery_Fight': 'slithery_fight', 'Trophy': 'trophy'}
def pcells(m):
    W, H, E, T, D, P = reach.load(f'../tune_runs/official123/{m}.map'); S = 2 * (W + 1); cells = set()
    for pid, es in P.items():
        for e in es:
            y = e // S; r = e % S
            if r <= W: cells.add((r % W, y)); cells.add((r % W, (y - 1) % H))
            else: x = r - (W + 1); cells.add((x % W, y)); cells.add(((x - 1) % W, y))
    return W, H, cells
def one(a):
    f, ours, mp = a
    W, H, cells = pcells(MAPF[mp])
    info, out, team_of = bc.walk(f)
    heads = {}; qsee = nsee = cross = None
    for e in out:
        if e[1] > 150: break
        if e[0] == 'move' and e[4]:
            if team_of.get(e[2]) == ours and e[3]:
                dx = min(abs(e[3][0] - e[4][0]), W - abs(e[3][0] - e[4][0])); dy = min(abs(e[3][1] - e[4][1]), H - abs(e[3][1] - e[4][1]))
                if dx + dy > 6 and e[2] > 1 and cross is None: cross = e[1]
            heads[e[2]] = e[4]
        elif e[0] == 'death': heads.pop(e[2], None)
        elif e[0] == 'round':
            for d, h in heads.items():
                if team_of.get(d) != ours: continue
                vis = any((min(abs(c[0] - h[0]), W - abs(c[0] - h[0])) <= 3 and min(abs(c[1] - h[1]), H - abs(c[1] - h[1])) <= 3) for c in cells)
                if vis:
                    if d <= 1 and qsee is None: qsee = e[1]
                    if d > 1 and nsee is None: nsee = e[1]
    return mp, qsee or 999, nsee or 999, cross or 999
if __name__ == '__main__':
    args = []
    if sys.argv[1] == 'local':
        for f in sorted(glob.glob(f'ab2/{sys.argv[2]}_*.replay')):
            p = os.path.basename(f)[:-7].split('_'); m = '_'.join(p[1:-2])
            mp = {v: k for k, v in MAPF.items()}.get(m)
            if mp: args.append((f, 'A' if p[-1] == '0' else 'B', mp))
    else:
        for line in open(sys.argv[1]):
            p = line.split()
            if len(p) < 6: continue
            for g in p[5].split(','):
                gid, mp, res, has = g.split(':')
                if mp in MAPF and os.path.exists(f'nr/{gid}.replay'): args.append((f'nr/{gid}.replay', p[4], mp))
    with ProcessPoolExecutor(6) as ex: rows = list(ex.map(one, args))
    by = defaultdict(list)
    for r in rows: by[r[0]].append(r)
    for mp, rs in sorted(by.items()):
        n = len(rs); med = lambda i: sorted(r[i] for r in rs)[n // 2]
        qfirst = sum(1 for r in rs if r[1] < r[2])
        print(f"{mp:16s} n{n:3d} our queen first sees portal (median) r{med(1)}  non-queen first sees r{med(2)}  non-queen first crossing r{med(3)}  queen saw first in {qfirst}/{n}")
