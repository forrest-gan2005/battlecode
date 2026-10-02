import sys, os
sys.path.insert(0, '/Users/UNSW/battlecode'); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dtrace, ladq
from concurrent.futures import ProcessPoolExecutor
from collections import Counter
def one(arg):
    p, ours, opp, gid, mp = arg
    rows, _ = dtrace.run(p, 500)
    q = ladq.run((p, ours, opp))
    return gid, mp, opp, q['win'], q['how'], [r for r in rows if r[3] >= int(os.environ.get('MINLEN', 15)) and r[0] >= 200]
if __name__ == '__main__':
    args = []
    for line in open(sys.argv[1]):
        p = line.split()
        if len(p) < 6: continue
        for g in p[5].split(','):
            gid, mp, res, has = g.split(':')
            f = os.path.join('nr', gid + '.replay')
            if os.path.exists(f): args.append((f, p[4], p[2], gid, mp))
    with ProcessPoolExecutor(6) as ex: res = list(ex.map(one, args))
    c = Counter()
    for gid, mp, opp, win, how, rows in res:
        for r in rows:
            c[r[1], r[4].split('/')[0] if not r[4].startswith('head') else r[4], 'W' if win else 'L'] += 1
            print(gid, mp[:10], opp[:12], 'W' if win else 'L', how, r[:5])
    for k, v in sorted(c.items()): print(k, v)
