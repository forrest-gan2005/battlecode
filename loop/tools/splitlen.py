import sys, os, pickle
sys.path.insert(0, '/Users/quasarpark/meow-loop')
import replay
from collections import deque, Counter
from concurrent.futures import ProcessPoolExecutor
NR = '/Users/quasarpark/meow-loop/work/nr'
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
    rnd = 0; sp = []; hist = Counter()
    for ev in replay.load(p).root().pointer(3):
        k = replay.EVENT_NAMES[ev.u16(0)]; pl = ev.pointer(0)
        if k == 'roundStart':
            rnd = pl.i32(0)
            if 50 <= rnd < 300:
                for d, b in bodies.items():
                    if b and d not in (0, 1): hist[side(d), rnd // 50, min(len(b), 9)] += 1
        elif k == 'dragonUpdate':
            did = pl.i32(0); h = replay.point(pl.pointer(0)); tp = replay.point(pl.pointer(1)); b = bodies.setdefault(did, deque())
            if not b or b[0] != h: b.appendleft(h)
            while len(b) > 1 and b[-1] != tp: b.pop()
        elif k == 'dragonSplit':
            pa, ch = pl.i32(0), pl.i32(4); before = len(bodies.get(pa, ()))
            bodies[pa] = deque(replay.point(x) for x in pl.pointer(0)); bodies[ch] = deque(replay.point(x) for x in pl.pointer(1)); team_of[pa] = team_of[ch] = ('A', 'B')[pl.u16(8)]
            sp.append((rnd, side(pa), before, len(bodies[pa]), len(bodies[ch]), pa in (0, 1)))
        elif k == 'dragonDeath':
            bodies.pop(pl.i32(0), None)
    return dict(gid=gid, W=W, H=H, win=res == 'W', sp=sp, hist=hist)
if __name__ == '__main__':
    args = []
    for line in open('/Users/quasarpark/meow-loop/work/nr_meow.txt'):
        q = line.split()
        if len(q) < 6: continue
        for g in q[5].split(','):
            gid, mp, res, has = g.split(':')
            if os.path.exists(os.path.join(NR, gid + '.replay')): args.append((gid, mp, q[4], res))
    with ProcessPoolExecutor(4) as ex: out = list(ex.map(one, args))
    pickle.dump(out, open('/Users/quasarpark/meow-loop/loop/tools/splitlen.pkl', 'wb'))
    print(len(out))
