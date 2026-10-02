import sys, os
sys.path.insert(0, '/Users/UNSW/battlecode'); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replay, wipe
from collections import deque
def show(p, rounds):
    ours = wipe.ours_of(p)
    info, _, team_of = replay.parse(p)
    lines = info['map'].splitlines()
    W, H = map(int, lines[0].split()[1:3])
    edges = {}
    for l in lines:
        q = l.split()
        if q and q[0] == 'EDGE' and len(q) >= 3: edges[int(q[1])] = int(q[2])
    bodies = {}
    for line in lines:
        q = line.split()
        if q and q[0] == 'DRAGON':
            did = len(bodies); bodies[did] = deque((int(q[3+2*k]), int(q[4+2*k])) for k in range(int(q[2]))); team_of.setdefault(did, 'A' if int(q[1]) == 0 else 'B')
    root = replay.load(p).root(); rnd = 0; pearls = set(); todo = sorted(rounds)
    ech = {0: ' ', 1: '#', 2: '%'}
    def render():
        g = [[' '] * (2 * W + 1) for _ in range(2 * H + 1)]
        for y in range(H + 1):
            for x in range(W + 1):
                g[2 * y][2 * x] = '+'
        for y in range(H):
            for x in range(W):
                n = edges.get(y * 2 * (W + 1) + x, 0); w = edges.get(y * 2 * (W + 1) + (W + 1) + x, 0)
                g[2 * y][2 * x + 1] = '-' if n == 1 else ('%' if n == 2 else ' ')
                g[2 * y + 1][2 * x] = '|' if w == 1 else ('%' if w == 2 else ' ')
                g[2 * y + 1][2 * x + 1] = '.'
        for c in pearls: g[2 * c[1] + 1][2 * c[0] + 1] = '*'
        for d, b in bodies.items():
            us = team_of.get(d) == ours
            for i, c in enumerate(b):
                ch = ('A' if i == 0 else 'a') if us else ('B' if i == 0 else 'b')
                if d <= 1 and i == 0: ch = 'Q' if us else 'K'
                g[2 * c[1] + 1][2 * c[0] + 1] = ch
        nu = sum(1 for d, b in bodies.items() if b and team_of.get(d) == ours); nt = sum(1 for d, b in bodies.items() if b and team_of.get(d) != ours)
        print(f'round {rnd} ours={ours} units {nu}:{nt}  (A/a us, B/b them, Q/K queens, * pearl)')
        for row in g: print(''.join(row))
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
            pearls.discard(h)
        elif k == 'dragonSplit':
            bodies[pl.i32(0)] = deque(replay.point(x) for x in pl.pointer(0)); bodies[pl.i32(4)] = deque(replay.point(x) for x in pl.pointer(1)); team_of[pl.i32(0)] = team_of[pl.i32(4)] = ('A','B')[pl.u16(8)]
        elif k == 'dragonDeath': bodies.pop(pl.i32(0), None)
if __name__ == '__main__':
    show(sys.argv[1], [int(x) for x in sys.argv[2:]])
