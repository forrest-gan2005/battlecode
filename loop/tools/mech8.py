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
    def units():
        for t in ('us', 'them'): c[t, 'ur'] += sum(1 for d, b in bodies.items() if b and side(d) == t)
    for ev in replay.load(path).root().pointer(3):
        k = replay.EVENT_NAMES[ev.u16(0)]; pl = ev.pointer(0)
        if k == 'roundStart':
            rnd = pl.i32(0)
            if 100 <= rnd < 200: units()
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
            if 100 <= rnd < 200 and r in (0, 1, 2, 4): c[side(did), 'self'] += 1
    return c
if __name__ == '__main__':
    with ProcessPoolExecutor(3) as ex:
        for pat in sys.argv[1:]:
            fs = sorted(glob.glob(pat)); rs = [r for r in ex.map(one, fs) if r is not None]; n = max(1, len(rs)); T = Counter()
            for r in rs: T.update(r)
            print('%s games(>1200 cells) %d  r100-200 mean units %.1f:%.1f  self deaths per 100 unit-rounds %.2f:%.2f' % (
                pat, len(rs), T['us','ur']/n/100, T['them','ur']/n/100, 100*T['us','self']/max(1,T['us','ur']), 100*T['them','self']/max(1,T['them','ur'])))
