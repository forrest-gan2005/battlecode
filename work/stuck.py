import sys, os, glob
sys.path.insert(0, '/Users/UNSW/battlecode')
import bc
from concurrent.futures import ProcessPoolExecutor
from collections import defaultdict
WIN = 100
def one(p):
    ours = 'A' if p[-8] == '0' else 'B'
    info, out, team_of = bc.walk(p)
    heads = defaultdict(dict); lens = defaultdict(dict)
    for e in out:
        if e[0] == 'move':
            heads[e[2]][e[1]] = e[4]; lens[e[2]][e[1]] = e[6]
    res = []
    for d, hp in heads.items():
        rs = sorted(hp)
        if len(rs) < WIN: continue
        worst = None
        for i in range(0, len(rs) - WIN + 1, 10):
            window = rs[i:i + WIN]
            if window[-1] - window[0] > WIN + 5: continue
            cells = {hp[r] for r in window}
            grow = lens[d][window[-1]] - lens[d][window[0]]
            if len(cells) <= 6 and grow <= 0:
                worst = (window[0], window[-1], len(cells), lens[d][window[-1]]); break
        if worst: res.append(('us' if team_of.get(d) == ours else 'them', d, worst))
    return p, info['winner'] == ours, res
if __name__ == '__main__':
    ps = sorted(glob.glob(sys.argv[1]))
    with ProcessPoolExecutor(6) as ex: out = list(ex.map(one, ps))
    n_us = n_them = 0
    for p, w, res in out:
        for side, d, wd in res:
            if side == 'us': n_us += 1
            else: n_them += 1
            if side == 'us': print(os.path.basename(p)[:-7], 'W' if w else 'L', side, 'id', d, 'stuck rounds %d-%d cells %d len %d' % wd)
    print(len(ps), 'games; stuck dragons us', n_us, 'them', n_them)
