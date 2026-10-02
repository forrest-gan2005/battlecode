import sys, os, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bc
from collections import defaultdict, Counter
from concurrent.futures import ProcessPoolExecutor
TOP = {'Cache_me_outside', 'Stockfish', '3.14159265', 'calc', 'Sponge(Albert_and_Bob)', 'Team_SKKU', 'Computers', 'horse', 'WeHaveQuizzes'}
def inbox(p): return p is not None and 25 <= p[0] <= 34 and 32 <= p[1] <= 39
def one(a):
    f, ours = a
    them = 'B' if ours == 'A' else 'A'
    info, out, team_of = bc.walk(f)
    heads = {}; hr = Counter(); dth = Counter(); first = {}; lens = {}
    for e in out:
        if e[1] > 100: break
        if e[0] == 'move' and e[4]:
            heads[e[2]] = e[4]; lens[e[2]] = e[6]
        elif e[0] == 'death':
            h = heads.pop(e[2], None)
            t = team_of.get(e[2]); tt = 'us' if t == ours else 'them'
            if inbox(h): dth[(tt, e[3])] += 1
        elif e[0] == 'round':
            for d, h in heads.items():
                if inbox(h):
                    t = 'us' if team_of.get(d) == ours else 'them'
                    hr[t] += 1; first.setdefault(t, e[1])
    return hr, dth, first
if __name__ == '__main__':
    args = []
    if sys.argv[1] == 'local':
        for f in sorted(glob.glob(f'ab2/{sys.argv[2]}_schooltime_*.replay')):
            args.append((f, 'A' if f[-8] == '0' else 'B'))
    else:
        for line in open(sys.argv[1]):
            p = line.split()
            if len(p) < 6 or p[2] not in TOP: continue
            for g in p[5].split(','):
                gid, mp, res, has = g.split(':')
                if mp == 'Schooltime' and os.path.exists(f'nr/{gid}.replay'): args.append((f'nr/{gid}.replay', p[4]))
    with ProcessPoolExecutor(6) as ex: rows = list(ex.map(one, args))
    n = len(rows)
    hr = Counter(); dth = Counter()
    for r in rows: hr.update(r[0]); dth.update(r[1])
    print('games', n, 'cluster head-rounds r0-100 us', hr['us'] / n, 'them', hr['them'] / n)
    print('first entry us', sorted(r[2].get('us', 999) for r in rows))
    print('first entry them', sorted(r[2].get('them', 999) for r in rows))
    print('deaths in cluster per game', {k: round(v / n, 2) for k, v in sorted(dth.items())})
