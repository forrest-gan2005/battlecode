import sys, os
sys.path.insert(0, '/Users/UNSW/battlecode'); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bc, ladq
from concurrent.futures import ProcessPoolExecutor
def one(a):
    f, ours, opp, mp, gid = a
    r = ladq.run((f, ours, opp))
    info, out, team_of = bc.walk(f)
    q = 0 if team_of[0] == ours else 1
    hist = {}
    for e in out:
        if e[0] == 'round' and e[1] in (100, 200, 300, 400, 450, 499):
            mine = sorted((l for d, l in e[2].items() if team_of.get(d) == ours and l > 0), reverse=True)
            hist[e[1]] = (e[2].get(q, 0), e[2].get(1 - q, 0), mine[0] if mine else 0, sum(mine))
    return gid, mp, opp, r, hist
if __name__ == '__main__':
    args = []
    for line in open(sys.argv[1]):
        p = line.split()
        if len(p) < 6: continue
        for g in p[5].split(','):
            gid, mp, res, has = g.split(':')
            f = f'nr/{gid}.replay'
            if os.path.exists(f): args.append((f, p[4], p[2], mp, gid))
    with ProcessPoolExecutor(6) as ex: res = list(ex.map(one, args))
    for gid, mp, opp, r, hist in res:
        if r['win'] or (r['our_q'] and r['their_q']): continue
        print(gid, mp[:12], opp[:10], r['how'], 'ourQ', r['our_q'], 'theirQ', r['their_q'], '| r:(ourQ,theirQ,our top,our total) ' + ' '.join(f"{k}:{v}" for k, v in sorted(hist.items())))
