import sys, os, glob
sys.path.insert(0, '/Users/UNSW/battlecode'); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bc
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from cover import fast_tiles, D
def one(f):
    p = os.path.basename(f)[:-7].split('_')
    side = p[-1]; mp = '_'.join(p[1:-2])
    ours = 'A' if side == '0' else 'B'
    them = 'B' if ours == 'A' else 'A'
    info, out, team_of = bc.walk(f)
    fast = fast_tiles(D + mp + '.map')
    fv = {ours: 0, them: 0}; eat = {ours: 0, them: 0}
    for e in out:
        if e[1] > 100: break
        if e[0] == 'move' and e[4]:
            t = team_of.get(e[2])
            if t not in fv: continue
            if e[4] in fast: fv[t] += 1
            if e[6] is not None and e[5] is not None and e[6] > e[5]: eat[t] += e[6] - e[5]
    return mp, fv[ours], fv[them], eat[ours], eat[them]
if __name__ == '__main__':
    fs = sorted(glob.glob(f'ab2/{sys.argv[1]}_*.replay'))
    with ProcessPoolExecutor(6) as ex: rows = list(ex.map(one, fs))
    by = defaultdict(list)
    for r in rows: by[r[0]].append(r)
    for mp, rs in sorted(by.items()):
        n = len(rs)
        print(f"{mp:16s} n{n} fast-tile visits r0-100 {sum(r[1] for r in rs)/n:.0f}|{sum(r[2] for r in rs)/n:.0f}  len gain r0-100 {sum(r[3] for r in rs)/n:.0f}|{sum(r[4] for r in rs)/n:.0f}")
