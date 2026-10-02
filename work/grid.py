import sys, os
sys.path.insert(0, '/Users/UNSW/battlecode'); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replay, wipe
from collections import deque
def show(p, rounds):
    ours = wipe.ours_of(p)
    info, _, team_of = replay.parse(p)
    W, H = map(int, info['map'].splitlines()[0].split()[1:3])
    bodies = {}
    for line in info['map'].splitlines():
        q = line.split()
        if q and q[0] == 'DRAGON':
            did = len(bodies); bodies[did] = deque((int(q[3+2*k]), int(q[4+2*k])) for k in range(int(q[2]))); team_of.setdefault(did, 'A' if int(q[1]) == 0 else 'B')
    root = replay.load(p).root(); rnd = 0; pearls = set(); eaten = set(); todo = sorted(rounds)
    def render():
        g = [['.'] * W for _ in range(H)]
        for c in eaten: g[c[1]][c[0]] = 'o'
        for c in pearls: g[c[1]][c[0]] = '*'
        for d, b in bodies.items():
            us = team_of.get(d) == ours
            for i, c in enumerate(b): g[c[1]][c[0]] = ('A' if i == 0 else 'a') if us else ('B' if i == 0 else 'b')
        print(f'round {rnd}  (A/a = us, B/b = them, * = pearl, o = pearl eaten earlier)')
        for y in range(H): print(f'{y:2d} ' + ''.join(g[y]))
    for ev in root.pointer(3):
        k = replay.EVENT_NAMES[ev.u16(0)]; pl = ev.pointer(0)
        if k == 'roundStart':
            rnd = pl.i32(0)
            while todo and rnd >= todo[0]: render(); todo.pop(0)
            if not todo: return
        elif k == 'tileChange' and pl.u32(0) == 1: pearls.add(replay.point(pl.pointer(0)))
        elif k == 'dragonUpdate':
            did = pl.i32(0); h = replay.point(pl.pointer(0)); tp = replay.point(pl.pointer(1)); b = bodies.setdefault(did, deque())
            if not b or b[0] != h: b.appendleft(h)
            while len(b) > 1 and b[-1] != tp: b.pop()
            if h in pearls: pearls.discard(h); eaten.add(h)
        elif k == 'dragonSplit':
            bodies[pl.i32(0)] = deque(replay.point(x) for x in pl.pointer(0)); bodies[pl.i32(4)] = deque(replay.point(x) for x in pl.pointer(1)); team_of[pl.i32(0)] = team_of[pl.i32(4)] = ('A','B')[pl.u16(8)]
        elif k == 'dragonDeath': bodies.pop(pl.i32(0), None)
if __name__ == '__main__':
    show(sys.argv[1], [int(x) for x in sys.argv[2:]])
