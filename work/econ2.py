import sys, os
sys.path.insert(0, '/Users/quasarpark/meow-loop'); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bc
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
TOP = {'Cache_me_outside', 'Stockfish', '3.14159265', 'calc', 'Sponge(Albert_and_Bob)', 'Team_SKKU', 'Computers', 'horse', 'WeHaveQuizzes'}
CK = (10, 20, 30, 50, 75, 100)
def one(a):
    f, ours, opp, mp, res = a
    info, out, team_of = bc.walk(f)
    them = 'B' if ours == 'A' else 'A'
    st = {t: dict(units={}, eat=Counter(), split_first=None, splits=0, deaths=0, steps=0, idle=0, moves=0, sprint=0) for t in (ours, them)}
    lastlen = {}
    for e in out:
        if e[1] > 100: break
        if e[0] == 'round':
            if e[1] in CK:
                for t in (ours, them): st[t]['units'][e[1]] = sum(1 for d, l in e[2].items() if team_of.get(d) == t and l > 0)
        elif e[0] == 'move':
            t = team_of.get(e[2])
            if t not in st: continue
            st[t]['steps'] += 1
            if e[6] > e[5] > 0:
                for c in CK:
                    if e[1] < c: st[t]['eat'][c] += e[6] - e[5]
        elif e[0] == 'split':
            t = team_of.get(e[2])
            if t in st:
                st[t]['splits'] += 1
                if st[t]['split_first'] is None: st[t]['split_first'] = e[1]
        elif e[0] == 'death':
            t = team_of.get(e[2])
            if t in st: st[t]['deaths'] += 1
    return mp, opp, res, st[ours], st[them]
if __name__ == '__main__':
    args = []
    for line in open(sys.argv[1]):
        p = line.split()
        if len(p) < 6 or p[2] not in TOP: continue
        for g in p[5].split(','):
            gid, mp, res, has = g.split(':')
            f = f'nr/{gid}.replay'
            if os.path.exists(f): args.append((f, p[4], p[2], mp, res))
    with ProcessPoolExecutor(6) as ex: rows = list(ex.map(one, args))
    by = defaultdict(list)
    for r in rows: by[r[0]].append(r)
    print('vs top teams, first 100 rounds; us | them (means)')
    for mp, rs in sorted(by.items()):
        n = len(rs)
        m = lambda side, key, c=None: sum((r[side][key].get(c, 0) if c is not None else r[side][key]) or 0 for r in rs) / n
        fs = lambda side: sorted(999 if r[side]['split_first'] is None else r[side]['split_first'] for r in rs)[n // 2]
        print(f"{mp[:12]:12s} n{n:2d} W{sum(r[2]=='W' for r in rs):2d} | units r20 {m(3,'units',20):4.1f}|{m(4,'units',20):4.1f} r50 {m(3,'units',50):4.1f}|{m(4,'units',50):4.1f} r100 {m(3,'units',100):4.1f}|{m(4,'units',100):4.1f} | eat r30 {m(3,'eat',30):5.1f}|{m(4,'eat',30):5.1f} r50 {m(3,'eat',50):5.1f}|{m(4,'eat',50):5.1f} r100 {m(3,'eat',100):5.1f}|{m(4,'eat',100):5.1f} | splits {m(3,'splits'):4.1f}|{m(4,'splits'):4.1f} 1st {fs(3)}|{fs(4)} | deaths {m(3,'deaths'):4.1f}|{m(4,'deaths'):4.1f}")
