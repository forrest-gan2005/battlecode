import sys, os
sys.path.insert(0, '/Users/quasarpark/meow-loop')
import replay
from collections import deque, Counter
from concurrent.futures import ProcessPoolExecutor
LO, HI = int(sys.argv[1]), int(sys.argv[2])
NR = '/Users/quasarpark/meow-loop/work/nr'
def one(arg):
    gid, ours, res = arg
    p = os.path.join(NR, gid + '.replay')
    info, _, team_of = replay.parse(p)
    W, H = map(int, info['map'].splitlines()[0].split()[1:3])
    bodies = {}
    for line in info['map'].splitlines():
        q = line.split()
        if q and q[0] == 'DRAGON':
            did = len(bodies); bodies[did] = deque((int(q[3+2*k]), int(q[4+2*k])) for k in range(int(q[2]))); team_of.setdefault(did, 'A' if int(q[1]) == 0 else 'B')
    side = lambda d: 'us' if team_of.get(d) == ours else 'them'
    c = Counter(); rnd = 0
    for ev in replay.load(p).root().pointer(3):
        k = replay.EVENT_NAMES[ev.u16(0)]; pl = ev.pointer(0)
        if k == 'roundStart':
            rnd = pl.i32(0)
            if rnd > HI: break
            if rnd >= LO:
                for d, b in bodies.items():
                    if d in (0, 1) or not b: continue
                    L = len(b); s = side(d)
                    c[s, 'dr'] += 1
                    c[s, 'L4+'] += L >= 4
                    c[s, 'L6+'] += L >= 6
                    c[s, 'L2'] += L == 2
        elif k == 'dragonUpdate':
            did = pl.i32(0); h = replay.point(pl.pointer(0)); tp = replay.point(pl.pointer(1)); b = bodies.setdefault(did, deque())
            if not b or b[0] != h: b.appendleft(h)
            while len(b) > 1 and b[-1] != tp: b.pop()
        elif k == 'dragonSplit':
            pa, ch = pl.i32(0), pl.i32(4)
            bodies[pa] = deque(replay.point(x) for x in pl.pointer(0)); bodies[ch] = deque(replay.point(x) for x in pl.pointer(1)); team_of[pa] = team_of[ch] = ('A', 'B')[pl.u16(8)]
            if LO <= rnd <= HI: c[side(pa), 'splits'] += 1; c[side(pa), 'split_parent_len'] += len(bodies[pa]) + len(bodies[ch])
        elif k == 'dragonDeath':
            bodies.pop(pl.i32(0), None)
    return (res, 'big' if W * H > 1600 else 'small'), c
if __name__ == '__main__':
    args = []
    for line in open('/Users/quasarpark/meow-loop/work/nr_meow.txt'):
        q = line.split()
        for g in q[5].split(','):
            gid, mp, res, has = g.split(':'); args.append((gid, q[4], res))
    with ProcessPoolExecutor(3) as ex: out = list(ex.map(one, args))
    for sel in ('W', 'L', None):
      for sz in ('big', 'small'):
        c = Counter(); n = 0
        for (res, z), x in out:
            if (sel is None or res == sel) and z == sz: c.update(x); n += 1
        print(sel or 'ALL', sz, n, 'splits/game %.1f:%.1f' % (c['us','splits']/n, c['them','splits']/n), ' | '.join('%s: share L4+ %.2f L6+ %.2f L2 %.2f, splits per 100 L4+ dragon-rounds %.1f, mean split parent len %.1f' % (s, c[s, 'L4+'] / c[s, 'dr'], c[s, 'L6+'] / c[s, 'dr'], c[s, 'L2'] / c[s, 'dr'], 100 * c[s, 'splits'] / max(1, c[s, 'L4+']), c[s, 'split_parent_len'] / max(1, c[s, 'splits'])) for s in ('us', 'them')))
