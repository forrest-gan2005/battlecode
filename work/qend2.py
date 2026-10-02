import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qend
from concurrent.futures import ProcessPoolExecutor
if __name__ == '__main__':
    maps = set(sys.argv[2].split(',')) if len(sys.argv) > 2 else None
    args = []
    for line in open(sys.argv[1]):
        p = line.split()
        if len(p) < 6: continue
        for g in p[5].split(','):
            gid, mp, res, has = g.split(':')
            if (maps is None or mp in maps) and os.path.exists(f'nr/{gid}.replay'): args.append((f'nr/{gid}.replay', p[4], p[2], mp, gid))
    with ProcessPoolExecutor(6) as ex: res = list(ex.map(qend.one, args))
    for gid, mp, opp, r, hist in res:
        print(gid, mp[:10], opp[:8], 'W' if r['win'] else 'L', r['how'], 'ourQdead', r['our_q'], 'theirQdead', r['their_q'], ' '.join(f"{k}:{v}" for k, v in sorted(hist.items())))
