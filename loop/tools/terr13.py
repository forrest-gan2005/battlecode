import sys, os, pickle
sys.path.insert(0, '/Users/quasarpark/meow-loop')
import replay
from collections import deque, Counter
from concurrent.futures import ProcessPoolExecutor
R = ['wall', 'self', 'body', 'head', 'none']
NR = '/Users/quasarpark/meow-loop/work/nr'
def one(arg):
    gid, ours, res = arg
    p = os.path.join(NR, gid + '.replay')
    info, _, team_of = replay.parse(p)
    side = lambda d: 'us' if team_of.get(d) == ours else 'them'
    lines = info['map'].splitlines()
    W, H = map(int, lines[0].split()[1:3])
    kind = {}
    for line in lines:
        q = line.split()
        if q and q[0] == 'EDGE': kind[int(q[1])] = int(q[2])
    n = lambda x, y: y * 2 * (W + 1) + x
    w = lambda x, y: y * 2 * (W + 1) + (W + 1) + x
    def nb(x, y):
        out = []
        for e, (dx, dy) in ((n(x, y), (0, -1)), (n(x, y + 1), (0, 1)), (w(x, y), (-1, 0)), (w(x + 1, y), (1, 0))):
            if kind.get(e, 0) == 1: continue
            a, b = x + dx, y + dy
            if 0 <= a < W and 0 <= b < H: out.append((a, b))
        return out
    deg = {(x, y): len(nb(x, y)) for x in range(W) for y in range(H)}
    def ball(c, r=3):
        seen = {c}; fr = [c]
        for _ in range(r):
            nf = []
            for u in fr:
                for v in nb(*u):
                    if v not in seen: seen.add(v); nf.append(v)
            fr = nf
        return len(seen)
    bc = {}
    def cat(c):
        if c not in bc:
            b = ball(c); bc[c] = 0 if b <= 12 else 1 if b <= 18 else 2
        return bc[c]
    bodies = {}
    for line in lines:
        q = line.split()
        if q and q[0] == 'DRAGON':
            did = len(bodies); bodies[did] = deque((int(q[3+2*k]), int(q[4+2*k])) for k in range(int(q[2]))); team_of.setdefault(did, 'A' if int(q[1]) == 0 else 'B')
    occ = Counter(); dth = Counter(); rnd = 0; mover = None
    for ev in replay.load(p).root().pointer(3):
        k = replay.EVENT_NAMES[ev.u16(0)]; pl = ev.pointer(0)
        if k == 'roundStart':
            rnd = pl.i32(0)
            if 50 <= rnd < 300:
                for d, b in bodies.items():
                    if b and d > 1:
                        h = b[0]
                        enear = min((abs(h[0]-ob[0][0]) + abs(h[1]-ob[0][1]) for e, ob in bodies.items() if ob and side(e) != side(d)), default=99)
                        occ[side(d), cat(h), enear <= 3] += 1
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
            if 50 <= rnd < 300 and did > 1 and b and r in (0, 1, 2, 4):
                h = b[0]
                enear = min((abs(h[0]-ob[0][0]) + abs(h[1]-ob[0][1]) for e, ob in bodies.items() if ob and side(e) != side(did)), default=99)
                dth[side(did), cat(h), enear <= 3, min(len(b), 6)] += 1
    return dict(gid=gid, cells=W * H, win=res == 'W', occ=occ, dth=dth)
if __name__ == '__main__':
    args = []
    for line in open('/Users/quasarpark/meow-loop/work/nr_meow.txt'):
        q = line.split()
        if len(q) < 6: continue
        for g in q[5].split(','):
            gid, mp, res, has = g.split(':')
            if os.path.exists(os.path.join(NR, gid + '.replay')): args.append((gid, q[4], res))
    with ProcessPoolExecutor(3) as ex: out = list(ex.map(one, args))
    pickle.dump(out, open('/Users/quasarpark/meow-loop/loop/tools/terr13.pkl', 'wb'))
    print(len(out))
