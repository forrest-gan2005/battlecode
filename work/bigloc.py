import sys, os, glob
sys.path.insert(0, '/Users/UNSW/battlecode')
import bc
from concurrent.futures import ProcessPoolExecutor
from collections import Counter
R = ['wall', 'self', 'body', 'head', 'none']
def one(p):
    ours = 'A' if p[-8] == '0' else 'B'
    info, out, team_of = bc.walk(p)
    c = Counter(); maxlen = Counter()
    for e in out:
        if e[0] == 'death' and len(e[4]) >= 15 and e[1] >= 300:
            c['us' if team_of.get(e[2]) == ours else 'them', R[e[3]] if e[3] < 5 else e[3]] += 1
    return p, c, info['winner'] == ours
if __name__ == '__main__':
    for tag in sys.argv[1:]:
        ps = [p for p in sorted(glob.glob(f'ab2/{tag}_*.replay')) if any(m in p for m in ('slithery', 'schooltime', 'portals'))]
        with ProcessPoolExecutor(6) as ex: res = list(ex.map(one, ps))
        tot = Counter(); wins = 0
        for p, c, w in res: tot.update(c); wins += w
        print(tag, len(ps), 'games, wins', wins, '| >=15-long deaths after r300:', dict(sorted(tot.items())))
