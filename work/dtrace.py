import sys, os
sys.path.insert(0, '/Users/quasarpark/meow-loop'); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replay, wipe
from collections import deque, Counter
R = ['wall', 'self', 'body', 'head', 'none']
def run(p, upto=60):
    ours = wipe.ours_of(p)
    info, _, team_of = replay.parse(p)
    bodies = {}
    for line in info['map'].splitlines():
        q = line.split()
        if q and q[0] == 'DRAGON':
            did = len(bodies); bodies[did] = deque((int(q[3+2*k]), int(q[4+2*k])) for k in range(int(q[2]))); team_of.setdefault(did, 'A' if int(q[1]) == 0 else 'B')
    side = lambda d: 'us' if team_of.get(d) == ours else 'them'
    root = replay.load(p).root(); rnd = 0; mover = None; msteps = 0; c = Counter(); rows = []
    for ev in root.pointer(3):
        k = replay.EVENT_NAMES[ev.u16(0)]; pl = ev.pointer(0)
        if k == 'roundStart':
            rnd = pl.i32(0)
            if rnd > upto: break
        elif k == 'dragonAction':
            mover = pl.i32(0); a = pl.pointer(0); msteps = 0; kind = a.u16(0) if a else -1
            if a and a.u16(0) == 0:
                try: msteps = len(a.pointer(0))
                except Exception: msteps = 0
        elif k == 'dragonUpdate':
            did = pl.i32(0); h = replay.point(pl.pointer(0)); tp = replay.point(pl.pointer(1)); b = bodies.setdefault(did, deque())
            if not b or b[0] != h: b.appendleft(h)
            while len(b) > 1 and b[-1] != tp: b.pop()
        elif k == 'dragonSplit':
            pa, ch = pl.i32(0), pl.i32(4)
            bodies[pa] = deque(replay.point(x) for x in pl.pointer(0)); bodies[ch] = deque(replay.point(x) for x in pl.pointer(1)); team_of[pa] = team_of[ch] = ('A','B')[pl.u16(8)]
            c[side(pa), 'split', len(bodies[pa]) + len(bodies[ch])] += 1
        elif k == 'dragonDeath':
            did = pl.i32(0); r = pl.u16(4); b = bodies.pop(did, deque())
            reason = R[r] if r < 5 else str(r)
            if r == 3: reason += '/' + ('self_move' if mover == did else 'by_' + side(mover))
            h = b[0] if b else None
            near = min((abs(h[0]-ob[0][0]) + abs(h[1]-ob[0][1]) for d, ob in bodies.items() if ob and side(d) != side(did)), default=99) if h else 99
            rows.append((rnd, side(did), did, len(b), reason, h, 'steps%d' % msteps if mover == did else '', 'enemy_head_dist%d' % near))
            c[side(did), 'death', reason] += 1
    return rows, c
if __name__ == '__main__':
    rows, c = run(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 60)
    for r in rows: print(*r)
    for k, v in sorted(c.items()): print(k, v)
