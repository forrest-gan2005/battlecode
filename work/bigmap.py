import sys, os
sys.path.insert(0, '/Users/UNSW/battlecode')
import replay
from collections import deque, Counter
CK = [25, 50, 100, 150, 200, 300]
def run(f):
    info, _, team_of = replay.parse(f)
    lines = info['map'].splitlines(); W, H = map(int, lines[0].split()[1:3])
    name = [l[9:] for l in lines if l.startswith('MAP_NAME')][0]
    bodies = {}
    for l in lines:
        q = l.split()
        if q and q[0] == 'DRAGON':
            did = len(bodies); bodies[did] = deque((int(q[3+2*k]), int(q[4+2*k])) for k in range(int(q[2]))); team_of.setdefault(did, 'A' if int(q[1]) == 0 else 'B')
    seen = {'A': set(), 'B': set()}; eat = Counter(); deaths = Counter(); splits = Counter(); rnd = 0; rows = []
    def vis(t):
        for d, b in bodies.items():
            if b and team_of.get(d) == t:
                hx, hy = b[0]
                for dx in range(-3, 4):
                    for dy in range(-3, 4): seen[t].add(((hx+dx) % W, (hy+dy) % H))
    for ev in replay.load(f).root().pointer(3):
        k = replay.EVENT_NAMES[ev.u16(0)]; pl = ev.pointer(0)
        if k == 'roundStart':
            rnd = pl.i32(0)
            if rnd <= 300:
                vis('A'); vis('B')
            if rnd in CK:
                r = [rnd]
                for t in 'AB':
                    mb = [len(b) for d, b in bodies.items() if b and team_of.get(d) == t]
                    r.append('%s u%2d tot%4d top%3d eat%4d seen%4.0f%% die%3d spl%3d' % (t, len(mb), sum(mb), max(mb or [0]), eat[t], 100*len(seen[t])/(W*H), deaths[t], splits[t]))
                rows.append(r)
        elif k == 'dragonUpdate':
            did = pl.i32(0); h = replay.point(pl.pointer(0)); tp = replay.point(pl.pointer(1)); b = bodies.setdefault(did, deque()); before = len(b)
            if not b or b[0] != h: b.appendleft(h)
            while len(b) > 1 and b[-1] != tp: b.pop()
            if len(b) > before: eat[team_of.get(did)] += len(b) - before
        elif k == 'dragonSplit':
            pa, ch = pl.i32(0), pl.i32(4); t = ('A','B')[pl.u16(8)]
            bodies[pa] = deque(replay.point(x) for x in pl.pointer(0)); bodies[ch] = deque(replay.point(x) for x in pl.pointer(1)); team_of[pa] = team_of[ch] = t; splits[t] += 1
        elif k == 'dragonDeath':
            did = pl.i32(0); deaths[team_of.get(did)] += 1; bodies.pop(did, None)
    print(name, W, 'x', H, 'winner', info['winner'])
    for r in rows: print('  r%-3d %s | %s' % tuple(r))
for f in sys.argv[1:]: run(f)
