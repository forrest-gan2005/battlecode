import sys, os, pickle
sys.path.insert(0, '/Users/quasarpark/meow-loop')
import replay
from collections import deque, Counter
from concurrent.futures import ProcessPoolExecutor
NR = '/Users/quasarpark/meow-loop/work/nr'
RAD = 6
def one(arg):
    gid, mp, ours, res = arg
    p = os.path.join(NR, gid + '.replay')
    info, _, team_of = replay.parse(p)
    side = lambda d: 'us' if team_of.get(d) == ours else 'them'
    lines = info['map'].splitlines()
    W, H = map(int, lines[0].split()[1:3])
    bodies = {}
    for line in lines:
        q = line.split()
        if q and q[0] == 'DRAGON':
            did = len(bodies); bodies[did] = deque((int(q[3+2*k]), int(q[4+2*k])) for k in range(int(q[2]))); team_of.setdefault(did, 'A' if int(q[1]) == 0 else 'B')
    rnd = 0; mover = None; out = []; start = {}
    for ev in replay.load(p).root().pointer(3):
        k = replay.EVENT_NAMES[ev.u16(0)]; pl = ev.pointer(0)
        if k == 'roundStart':
            rnd = pl.i32(0); start = {d: b[0] for d, b in bodies.items() if b}
        elif k == 'dragonAction': mover = pl.i32(0)
        elif k == 'dragonUpdate':
            did = pl.i32(0); h = replay.point(pl.pointer(0)); tp = replay.point(pl.pointer(1)); b = bodies.setdefault(did, deque())
            if not b or b[0] != h: b.appendleft(h)
            while len(b) > 1 and b[-1] != tp: b.pop()
        elif k == 'dragonSplit':
            pa, ch = pl.i32(0), pl.i32(4)
            bodies[pa] = deque(replay.point(x) for x in pl.pointer(0)); bodies[ch] = deque(replay.point(x) for x in pl.pointer(1)); team_of[pa] = team_of[ch] = ('A', 'B')[pl.u16(8)]
        elif k == 'dragonDeath':
            did = pl.i32(0); r = pl.u16(4); b = bodies.pop(did, deque())
            if r == 3 and mover == did and rnd < 300 and did in start:
                h = start[did]; s = side(did)
                own = sum(1 for d, x in start.items() if d != did and side(d) == s and abs(x[0]-h[0]) + abs(x[1]-h[1]) <= RAD)
                opp = sum(1 for d, x in start.items() if side(d) != s and abs(x[0]-h[0]) + abs(x[1]-h[1]) <= RAD)
                out.append((s, rnd, len(b), own + 1 - opp, W * H))
    return dict(gid=gid, win=res == 'W', cells=W*H, ev=out)
if __name__ == '__main__':
    args = []
    for line in open('/Users/quasarpark/meow-loop/work/nr_meow.txt'):
        q = line.split()
        if len(q) < 6: continue
        for g in q[5].split(','):
            gid, mp, res, has = g.split(':')
            if os.path.exists(os.path.join(NR, gid + '.replay')): args.append((gid, mp, q[4], res))
    with ProcessPoolExecutor(2) as ex: out = list(ex.map(one, args))
    pickle.dump(out, open('/Users/quasarpark/meow-loop/loop/tools/edge10.pkl', 'wb'))
    sz = lambda c: 'S' if c <= 800 else 'M' if c <= 1200 else 'L'
    for s in 'SML':
        gs = [g for g in out if sz(g['cells']) == s]; n = len(gs)
        for who in ('us', 'them'):
            c = Counter()
            for g in gs:
                for e in g['ev']:
                    if e[0] == who: c[max(-2, min(2, e[3]))] += 1
            print(s, n, who, 'initiated head-ons r<300 by local edge (own+1-opp, r<=%d):' % RAD, {k: round(c[k] / n, 2) for k in sorted(c)})
