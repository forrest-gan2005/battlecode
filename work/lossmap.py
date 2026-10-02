import sys, os, statistics as S
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lossan
from concurrent.futures import ProcessPoolExecutor
if __name__ == '__main__':
    args = []
    for line in open(sys.argv[1]):
        p = line.split()
        if len(p) < 6: continue
        for g in p[5].split(','):
            gid, mp, res, has = g.split(':')
            f = os.path.join('nr', gid + '.replay')
            if os.path.exists(f): args.append((f, p[4], p[2], gid, mp))
    with ProcessPoolExecutor(6) as ex: res = list(ex.map(lossan.run, args))
    import pickle; pickle.dump(res, open('lossan.pkl', 'wb'))
    for mp in sorted({r['map'] for r in res}):
        for w in (True, False):
            rs = [r for r in res if r['map'] == mp and r['win'] == w]
            if not rs: continue
            cells = []
            for k in (50, 100, 200, 300, 400):
                v = [r['snaps'][k] for r in rs if k in r['snaps']]
                if not v: cells.append(f"r{k}: -"); continue
                cells.append(f"r{k}: {S.mean(a[1] for a, b in v):5.0f}/{S.mean(a[2] for a, b in v):3.0f}u v {S.mean(b[1] for a, b in v):5.0f}/{S.mean(b[2] for a, b in v):3.0f}u")
            print(f"{mp[:12]:12s} {'W' if w else 'L'} n{len(rs):2d} | " + ' | '.join(cells))
