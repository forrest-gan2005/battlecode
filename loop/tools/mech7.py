import sys, os, glob
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
    c = Counter(); rnd = 0; snapped = False
    for ev in replay.load(path).root().pointer(3):
        k = replay.EVENT_NAMES[ev.u16(0)]; pl = ev.pointer(0)
        if k == 'roundStart':
            rnd = pl.i32(0)
            if rnd >= 300 and not snapped:
                snapped = True
                for t in ('us', 'them'):
                    ls = [len(b) for d, b in bodies.items() if side(d) == t and b]
                    c[t, 'u300'] = len(ls); c[t, 'top300'] = max(ls, default=0); c[t, 'tot300'] = sum(ls)
        elif k == 'dragonUpdate':
            did = pl.i32(0); h = replay.point(pl.pointer(0)); tp = replay.point(pl.pointer(1)); b = bodies.setdefault(did, deque())
            if not b or b[0] != h: b.appendleft(h)
            while len(b) > 1 and b[-1] != tp: b.pop()
        elif k == 'dragonSplit':
            pa, ch = pl.i32(0), pl.i32(4)
            bodies[pa] = deque(replay.point(x) for x in pl.pointer(0)); bodies[ch] = deque(replay.point(x) for x in pl.pointer(1)); team_of[pa] = team_of[ch] = ('A', 'B')[pl.u16(8)]
            if 150 <= rnd < 300: c[side(pa), 'sp'] += 1
        elif k == 'dragonDeath':
            bodies.pop(pl.i32(0), None)
    return c
if __name__ == '__main__':
    with ProcessPoolExecutor(3) as ex:
        for pat in sys.argv[1:]:
            fs = sorted(glob.glob(pat)); rs = [r for r in ex.map(one, fs) if r is not None]; n = max(1, len(rs)); T = Counter()
            for r in rs: T.update(r)
            print('%s games(>1200 cells) %d  splits r150-300 %.1f:%.1f  units r300 %.1f:%.1f  top r300 %.1f:%.1f  total r300 %.1f:%.1f' % (
                pat, len(rs), T['us','sp']/n, T['them','sp']/n, T['us','u300']/n, T['them','u300']/n, T['us','top300']/n, T['them','top300']/n, T['us','tot300']/n, T['them','tot300']/n))
