import sys, os
sys.path.insert(0, '/Users/UNSW/battlecode'); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bc
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
TOP = {'Cache_me_outside', 'Stockfish', '3.14159265', 'calc', 'Sponge(Albert_and_Bob)', 'Team_SKKU', 'Computers', 'horse', 'WeHaveQuizzes'}
D = '../tune_runs/official123/'
MAPF = {'Queen_Of_Spades': 'queen_of_spades', 'Default': 'default', 'Devil': 'devil', 'Schooltime': 'schooltime', 'Trauma': 'trauma', 'Trophy': 'trophy'}
def fast_tiles(f):
    s = set()
    for l in open(f):
        q = l.split()
        if q and q[0] == 'TILE' and 0 < int(q[4]) <= 60: s.add((int(q[1]), int(q[2])))
    return s
def one(a):
    f, ours, mp = a
    info, out, team_of = bc.walk(f)
    l0 = info['map'].splitlines()[0].split(); W, H = int(l0[1]), int(l0[2])
    fast = fast_tiles(D + MAPF[mp] + '.map')
    them = 'B' if ours == 'A' else 'A'
    heads = {}; seen = {ours: set(), them: set()}; res = {}; first_fast = {}; fastvisits = {ours: 0, them: 0}
    for e in out:
        if e[1] > 100: break
        if e[0] == 'move' and e[4]:
            heads[e[2]] = e[4]
            t = team_of.get(e[2])
            if e[4] in fast and t in fastvisits:
                fastvisits[t] += 1
                first_fast.setdefault(t, e[1])
        elif e[0] == 'death': heads.pop(e[2], None)
        elif e[0] == 'round':
            for d, h in heads.items():
                t = team_of.get(d)
                if t not in seen: continue
                for dx in range(-3, 4):
                    for dy in range(-3, 4): seen[t].add(((h[0] + dx) % W, (h[1] + dy) % H))
            if e[1] in (30, 50, 100): res[e[1]] = (len(seen[ours]) / (W * H), len(seen[them]) / (W * H))
    return mp, res, first_fast.get(ours), first_fast.get(them), fastvisits[ours], fastvisits[them]
if __name__ == '__main__':
    args = []
    for line in open(sys.argv[1]):
        p = line.split()
        if len(p) < 6 or p[2] not in TOP: continue
        for g in p[5].split(','):
            gid, mp, res, has = g.split(':')
            if mp in MAPF and os.path.exists(f'nr/{gid}.replay'): args.append((f'nr/{gid}.replay', p[4], mp))
    with ProcessPoolExecutor(6) as ex: rows = list(ex.map(one, args))
    by = defaultdict(list)
    for r in rows: by[r[0]].append(r)
    for mp, rs in sorted(by.items()):
        n = len(rs)
        cov = lambda k, i: sum(r[1].get(k, (0, 0))[i] for r in rs) / n
        med = lambda i: sorted(999 if r[i] is None else r[i] for r in rs)[n // 2]
        print(f"{mp:16s} n{n:2d} coverage r30 {cov(30,0):.2f}|{cov(30,1):.2f} r50 {cov(50,0):.2f}|{cov(50,1):.2f} r100 {cov(100,0):.2f}|{cov(100,1):.2f} | first fast-tile visit median {med(2)}|{med(3)} | fast-tile head visits r0-100 {sum(r[4] for r in rs)/n:.0f}|{sum(r[5] for r in rs)/n:.0f}")
