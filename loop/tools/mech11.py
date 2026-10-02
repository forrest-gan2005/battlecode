import sys, glob
sys.path.insert(0, '/Users/quasarpark/meow-loop')
import replay
from collections import deque, Counter
from concurrent.futures import ProcessPoolExecutor
def one(path):
    ours = 'A' if path.endswith('_0.replay') else 'B'
    info, _, team_of = replay.parse(path)
    lines = info['map'].splitlines()
    bodies = {}
    for line in lines:
        q = line.split()
        if q and q[0] == 'DRAGON':
            did = len(bodies); bodies[did] = deque((int(q[3+2*k]), int(q[4+2*k])) for k in range(int(q[2]))); team_of.setdefault(did, 'A' if int(q[1]) == 0 else 'B')
    side = lambda d: 'us' if team_of.get(d) == ours else 'them'
    def near(h, s):
        return min((abs(h[0]-ob[0][0]) + abs(h[1]-ob[0][1]) for d, ob in bodies.items() if ob and side(d) != s), default=99)
    c = Counter(); rnd = 0
    for ev in replay.load(path).root().pointer(3):
        k = replay.EVENT_NAMES[ev.u16(0)]; pl = ev.pointer(0)
        if k == 'roundStart':
            rnd = pl.i32(0)
            if 25 <= rnd < 150:
                for t in ('us', 'them'): c[t, 'ur'] += sum(1 for d, b in bodies.items() if b and side(d) == t)
        elif k == 'dragonUpdate':
            did = pl.i32(0); h = replay.point(pl.pointer(0)); tp = replay.point(pl.pointer(1)); b = bodies.setdefault(did, deque())
            before = len(b)
            if not b or b[0] != h: b.appendleft(h)
            while len(b) > 1 and b[-1] != tp: b.pop()
            if len(b) > before and before > 0 and 25 <= rnd < 150:
                s = side(did); c[s, 'eat'] += len(b) - before
                if near(h, s) <= 3: c[s, 'eat_e3'] += len(b) - before
        elif k == 'dragonSplit':
            pa, ch = pl.i32(0), pl.i32(4)
            bodies[pa] = deque(replay.point(x) for x in pl.pointer(0)); bodies[ch] = deque(replay.point(x) for x in pl.pointer(1)); team_of[pa] = team_of[ch] = ('A', 'B')[pl.u16(8)]
        elif k == 'dragonDeath':
            did = pl.i32(0); r = pl.u16(4); b = bodies.pop(did, deque())
            if 25 <= rnd < 150 and r in (0, 1, 2, 4) and b and near(b[0], side(did)) <= 3: c[side(did), 'press'] += 1
    return c
if __name__ == '__main__':
    with ProcessPoolExecutor(3) as ex:
        for pat in sys.argv[1:]:
            fs = sorted(glob.glob(pat)); rs = list(ex.map(one, fs)); n = max(1, len(rs)); T = Counter()
            for r in rs: T.update(r)
            print('%s games %d  r25-150 eaten per game %.1f:%.1f  with enemy head <=3 %.1f:%.1f  pressure deaths per 100 unit-rounds %.3f:%.3f' % (
                pat, len(rs), T['us','eat']/n, T['them','eat']/n, T['us','eat_e3']/n, T['them','eat_e3']/n,
                100*T['us','press']/max(1,T['us','ur']), 100*T['them','press']/max(1,T['them','ur'])))
