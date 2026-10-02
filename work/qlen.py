import sys, os
sys.path.insert(0, '/Users/UNSW/battlecode'); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replay, ourside
from collections import deque, Counter
def run(p):
    ours = ourside.ours_of(p)
    info, _, team_of = replay.parse(p)
    bodies = {}
    for line in info['map'].splitlines():
        q = line.split()
        if q and q[0] == 'DRAGON':
            did = len(bodies); bodies[did] = deque((int(q[3+2*k]), int(q[4+2*k])) for k in range(int(q[2]))); team_of.setdefault(did, 'A' if int(q[1]) == 0 else 'B')
    qid = 0 if team_of.get(0) == ours else 1
    rnd = 0; mover = None; ms = 0; kind = -1; c = Counter(); before = None; log = []
    for ev in replay.load(p).root().pointer(3):
        k = replay.EVENT_NAMES[ev.u16(0)]; pl = ev.pointer(0)
        if k == 'roundStart': rnd = pl.i32(0)
        elif k == 'dragonAction':
            if mover == qid and before is not None and qid in bodies:
                after = len(bodies[qid])
                if after < before: c['shrink_' + ('split' if kind == 1 else 'move%d' % ms)] += before - after; log.append((rnd - (1 if False else 0), before, after, kind, ms))
            mover = pl.i32(0); a = pl.pointer(0); kind = a.u16(0) if a else -1; ms = 0
            if a and kind == 0:
                try: ms = len(a.pointer(0))
                except Exception: ms = 0
            before = len(bodies[qid]) if mover == qid and qid in bodies else None
        elif k == 'dragonUpdate':
            did = pl.i32(0); h = replay.point(pl.pointer(0)); tp = replay.point(pl.pointer(1)); b = bodies.setdefault(did, deque())
            if not b or b[0] != h: b.appendleft(h)
            while len(b) > 1 and b[-1] != tp: b.pop()
        elif k == 'dragonSplit':
            pa, ch = pl.i32(0), pl.i32(4); bodies[pa] = deque(replay.point(x) for x in pl.pointer(0)); bodies[ch] = deque(replay.point(x) for x in pl.pointer(1)); team_of[pa] = team_of[ch] = ('A','B')[pl.u16(8)]
        elif k == 'dragonDeath':
            did = pl.i32(0); bodies.pop(did, None)
            if did == qid: break
    return c, log
if __name__ == '__main__':
    T = Counter()
    for f in sys.argv[1:]:
        c, log = run(f); T.update(c)
        if '-v' in os.environ.get('V', ''): print(os.path.basename(f), log[:12])
    print(dict(T))
