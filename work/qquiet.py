import sys, os
sys.path.insert(0, '/Users/quasarpark/meow-loop'); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bc, ladq
from concurrent.futures import ProcessPoolExecutor
def one(a):
    f, ours, opp, mp, gid = a
    info, out, team_of = bc.walk(f)
    l0 = info['map'].splitlines()[0].split(); W, H = int(l0[1]), int(l0[2])
    q = 0 if team_of[0] == ours else 1
    heads = {}; first = None; alive100 = False; qlen = {}
    for e in out:
        if e[0] == 'move' and e[4]: heads[e[2]] = e[4]
        if e[0] == 'death': heads.pop(e[2], None)
        if e[0] == 'round':
            if e[1] == 100: alive100 = q in heads
            if e[1] in (300, 400, 450, 499): qlen[e[1]] = e[2].get(q, 0)
            if q in heads and e[1] <= 100 and first is None:
                qh = heads[q]
                for d, h in heads.items():
                    if team_of.get(d) != ours:
                        dist = min(abs(h[0] - qh[0]), W - abs(h[0] - qh[0])) + min(abs(h[1] - qh[1]), H - abs(h[1] - qh[1]))
                        if dist <= 7: first = e[1]; break
    r = ladq.run((f, ours, opp))
    return gid, mp, opp, alive100 and first is None, r['win'], r['how'], qlen, r['our_q'], r['their_q']
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
    n = 0
    for gid, mp, opp, quiet, win, how, qlen, oq, tq in res:
        if quiet:
            n += 1
            print('QUIET', gid, mp, opp[:10], 'W' if win else 'L', how, 'queen len', qlen, 'ourQ', oq, 'theirQ', tq)
    print(n, 'of', len(res), 'games look quiet (queen alive at r100, no enemy head within 7 before r100)')
