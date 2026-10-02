import sys, os
sys.path.insert(0, '/Users/UNSW/battlecode'); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replay, ourside
from collections import deque
def run(p):
    ours = ourside.ours_of(p)
    info, _, team_of = replay.parse(p)
    lines = info['map'].splitlines(); W, H = map(int, lines[0].split()[1:3])
    bodies = {}
    for line in lines:
        q = line.split()
        if q and q[0] == 'DRAGON':
            did = len(bodies); bodies[did] = deque((int(q[3+2*k]), int(q[4+2*k])) for k in range(int(q[2]))); team_of.setdefault(did, 'A' if int(q[1]) == 0 else 'B')
    qid = 0 if team_of.get(0) == ours else 1
    rnd = 0; mover = None; snap = None; ms = 0; last = None
    def dist(a, b):
        dx = abs(a[0]-b[0]); dy = abs(a[1]-b[1]); return min(dx, W-dx) + min(dy, H-dy)
    for ev in replay.load(p).root().pointer(3):
        k = replay.EVENT_NAMES[ev.u16(0)]; pl = ev.pointer(0)
        if k == 'roundStart': rnd = pl.i32(0)
        elif k == 'dragonAction':
            mover = pl.i32(0); a = pl.pointer(0); ms = 0
            if a and a.u16(0) == 0:
                try: ms = len(a.pointer(0))
                except Exception: ms = 0
            if mover == qid: last = dict(round=rnd, before=bodies[qid][0], len=len(bodies[qid]), steps=ms)
        elif k == 'dragonUpdate':
            did = pl.i32(0); h = replay.point(pl.pointer(0)); tp = replay.point(pl.pointer(1)); b = bodies.setdefault(did, deque())
            if not b or b[0] != h: b.appendleft(h)
            while len(b) > 1 and b[-1] != tp: b.pop()
            if did == qid and mover == qid and last: last['after'] = h; last['enemies'] = sorted((dist(h, bb[0]), len(bb), (len(bb)+3)//4 + len(bb) - 2) for d, bb in bodies.items() if bb and team_of.get(d) != ours and dist(h, bb[0]) <= 8)
        elif k == 'dragonSplit':
            pa, ch = pl.i32(0), pl.i32(4); bodies[pa] = deque(replay.point(x) for x in pl.pointer(0)); bodies[ch] = deque(replay.point(x) for x in pl.pointer(1)); team_of[pa] = team_of[ch] = ('A','B')[pl.u16(8)]
        elif k == 'dragonDeath':
            did = pl.i32(0); r = pl.u16(4); b = bodies.pop(did, None)
            if did == qid:
                if r == 3 and mover != qid:
                    return '%s r%d rammed by len%d (moved %d steps) | queen last move r%d len%d steps%d, enemies after its move (dist,len,reach): %s' % (os.path.basename(p)[:34], rnd, len(bodies.get(mover, ())) , ms, last['round'], last['len'], last['steps'], last.get('enemies'))
                return None
    return None
if __name__ == '__main__':
    for f in sys.argv[1:]:
        r = run(f)
        if r: print(r)
