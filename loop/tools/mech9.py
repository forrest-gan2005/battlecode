import sys, glob
sys.path.insert(0, '/Users/quasarpark/meow-loop')
import replay
from collections import deque, Counter
from concurrent.futures import ProcessPoolExecutor
def one(path):
    ours = 'A' if path.endswith('_0.replay') else 'B'
    info, _, team_of = replay.parse(path)
    lines = info['map'].splitlines(); W, H = map(int, lines[0].split()[1:3])
    if W * H <= 1200: return None
    bodies = {}
    for line in lines:
        q = line.split()
        if q and q[0] == 'DRAGON':
            did = len(bodies); bodies[did] = deque((int(q[3+2*k]), int(q[4+2*k])) for k in range(int(q[2]))); team_of.setdefault(did, 'A' if int(q[1]) == 0 else 'B')
    side = lambda d: 'us' if team_of.get(d) == ours else 'them'
    c = Counter(); rnd = 0; mover = -1
    for ev in replay.load(path).root().pointer(3):
        k = replay.EVENT_NAMES[ev.u16(0)]; pl = ev.pointer(0)
        if k == 'roundStart': rnd = pl.i32(0)
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
            if rnd < 300:
                s = side(did)
                if r == 3:
                    c[s, 'ram' if mover == did else 'rammed'] += 1; c[s, 'hlen'] += len(b)
                elif r in (0, 1, 2, 4): c[s, 'self'] += 1
    return c
if __name__ == '__main__':
    with ProcessPoolExecutor(3) as ex:
        for pat in sys.argv[1:]:
            fs = sorted(glob.glob(pat)); rs = [r for r in ex.map(one, fs) if r is not None]; n = max(1, len(rs)); T = Counter()
            for r in rs: T.update(r)
            print('%s games(>1200 cells) %d  r<300 head_ram %.1f:%.1f  rammed %.1f:%.1f  head-on len lost %.1f:%.1f  self %.1f:%.1f' % (
                pat, len(rs), T['us','ram']/n, T['them','ram']/n, T['us','rammed']/n, T['them','rammed']/n, T['us','hlen']/n, T['them','hlen']/n, T['us','self']/n, T['them','self']/n))
