import sys, os
sys.path.insert(0, '/Users/quasarpark/meow-loop'); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replay, ourside
from collections import deque, Counter
R = ['wall', 'self', 'body', 'head', 'none']
D = [(0, -1), (1, 0), (0, 1), (-1, 0)]
def run(p):
    ours = ourside.ours_of(p)
    info, _, team_of = replay.parse(p)
    lines = info['map'].splitlines(); W, H = map(int, lines[0].split()[1:3])
    edges = {}
    for q in (x.split() for x in lines):
        if q and q[0] == 'EDGE': edges[int(q[1])] = int(q[2])
    def ek(x, y, d):
        if d == 0: return edges.get(y*2*(W+1)+x, 0)
        if d == 2: return edges.get(((y+1) % H)*2*(W+1)+x, 0)
        if d == 3: return edges.get(y*2*(W+1)+(W+1)+x, 0)
        return edges.get(y*2*(W+1)+(W+1)+(x+1) % W, 0)
    bodies = {}
    for line in lines:
        q = line.split()
        if q and q[0] == 'DRAGON':
            did = len(bodies); bodies[did] = deque((int(q[3+2*k]), int(q[4+2*k])) for k in range(int(q[2]))); team_of.setdefault(did, 'A' if int(q[1]) == 0 else 'B')
    qid = 0 if team_of.get(0) == ours else 1
    rnd = 0; pre = None; steps = []; hist = deque(maxlen=4)
    for ev in replay.load(p).root().pointer(3):
        k = replay.EVENT_NAMES[ev.u16(0)]; pl = ev.pointer(0)
        if k == 'roundStart': rnd = pl.i32(0)
        elif k == 'dragonAction':
            mover = pl.i32(0); a = pl.pointer(0)
            if mover == qid:
                b = bodies.get(qid, deque())
                occ = {}
                for d, bb in bodies.items():
                    for i, c in enumerate(bb): occ[c] = (d, i, len(bb))
                hx, hy = b[0]
                opts = []
                for di, (dx, dy) in enumerate(D):
                    if ek(hx, hy, di) == 1: opts.append('kelp'); continue
                    if ek(hx, hy, di) == 2: opts.append('portal'); continue
                    c = ((hx+dx) % W, (hy+dy) % H)
                    if c in occ:
                        d, i, L = occ[c]
                        opts.append('own_tail' if d == qid and i == L-1 else ('own' if d == qid else ('ally' if team_of.get(d) == ours else 'enemy')))
                    else: opts.append('free')
                kind = a.u16(0) if a else -1
                try: steps = list(a.pointer(0)) if kind == 0 else []
                except Exception: steps = []
                pre = dict(round=rnd, len=len(b), opts=opts, kind=kind, steps=len(steps) if steps else 0)
                hist.append(pre)
        elif k == 'dragonUpdate':
            did = pl.i32(0); h = replay.point(pl.pointer(0)); tp = replay.point(pl.pointer(1)); b = bodies.setdefault(did, deque())
            if not b or b[0] != h: b.appendleft(h)
            while len(b) > 1 and b[-1] != tp: b.pop()
        elif k == 'dragonSplit':
            pa, ch = pl.i32(0), pl.i32(4); bodies[pa] = deque(replay.point(x) for x in pl.pointer(0)); bodies[ch] = deque(replay.point(x) for x in pl.pointer(1)); team_of[pa] = team_of[ch] = ('A','B')[pl.u16(8)]
        elif k == 'dragonDeath':
            did = pl.i32(0); r = pl.u16(4); bodies.pop(did, None)
            if did == qid:
                return os.path.basename(p), R[r] if r < 5 else r, list(hist)
    return os.path.basename(p), 'alive', []
if __name__ == '__main__':
    for f in sys.argv[1:]:
        name, why, hist = run(f)
        if why in ('wall', 'self', 'body', 'none'):
            print(name, why)
            for h in hist: print('    r%d len%d kind%d steps%d opts %s' % (h['round'], h['len'], h['kind'], h['steps'], h['opts']))
